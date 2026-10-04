"""HeyReach Public API client.
Base: https://api.heyreach.io/api/public | Auth: X-API-KEY | Limit: 300 req/min
Endpoint AddLeadsToCampaignV2: max 100 leads/request.

VERIFY: payload field names (accountLeadPairs / customUserFields) HeyReach Postman docs se
ek baar match kar lo: https://documenter.getpostman.com/view/23808049/2sA2xb5F75
Saara payload-shape ek hi function me hai (build_lead) taki change karna easy rahe."""
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

CHUNK = 100


class HeyReachError(RuntimeError):
    pass


class _Retryable(Exception):
    pass


def build_lead(contact: dict, msg: dict, sender_account_id: int | None = None) -> dict:
    """Custom variables HeyReach sequence me {ai_hook} / {ai_message} / {connection_note} se use hote hain."""
    lead = {
        "firstName": contact.get("first_name") or "",
        "lastName": contact.get("last_name") or "",
        "profileUrl": contact.get("linkedin_url"),
        "position": contact.get("title") or "",
        "companyName": (contact.get("companies") or {}).get("name") or "",
        "emailAddress": contact.get("email") or "",
        "customUserFields": [
            {"name": "ai_hook", "value": msg["hook"]},
            {"name": "connection_note", "value": msg["connection_note"]},
            {"name": "ai_message", "value": msg["message"]},
        ],
    }
    pair: dict = {"lead": lead}
    if sender_account_id:
        pair["linkedInAccountId"] = sender_account_id
    return pair


class HeyReachClient:
    def __init__(self, api_key: str, base_url: str = "https://api.heyreach.io/api/public", timeout: float = 30):
        self._c = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"X-API-KEY": api_key, "Content-Type": "application/json", "Accept": "application/json"},
            timeout=timeout,
        )

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        retry=retry_if_exception_type(_Retryable),
        reraise=True,
    )
    def _request(self, method: str, path: str, json_body: dict | None = None) -> dict:
        try:
            r = self._c.request(method, path, json=json_body)
        except httpx.TransportError as e:
            raise _Retryable(str(e)) from e
        if r.status_code == 429 or r.status_code >= 500:
            raise _Retryable(f"{r.status_code}: {r.text[:200]}")
        if r.status_code >= 400:
            raise HeyReachError(f"{r.status_code}: {r.text[:300]}")
        if not r.content:
            return {}
        try:
            return r.json()
        except ValueError:
            return {"raw": r.text[:300]}

    def check_api_key(self) -> bool:
        try:
            self._request("GET", "/auth/CheckApiKey")
            return True
        except Exception:
            return False

    def add_leads(self, campaign_id: int, pairs: list[dict]) -> list[dict]:
        """Chunks of 100. Har chunk ka response list me."""
        results = []
        for i in range(0, len(pairs), CHUNK):
            body = {"campaignId": campaign_id, "accountLeadPairs": pairs[i : i + CHUNK]}
            results.append(self._request("POST", "/campaign/AddLeadsToCampaignV2", body))
        return results
