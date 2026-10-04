from app.heyreach import build_lead
from app.personalize import final_message, validate_draft
from app.textutil import grounded

CORPUS = "Our Tenable backlog hit 14,000 findings again. Exploitation windows are shrinking to days."

GOOD = {
    "hook": "Posted about a 14,000-finding Tenable backlog",
    "evidence_quote": "Tenable backlog hit 14,000 findings again",
    "connection_note": "Priya, your post on the Tenable backlog stuck with me. Running small private sessions on this at Black Hat. Worth connecting?",
    "message": "Saw your note on the backlog vs shrinking exploitation windows. We're hosting a few private suite sessions in Vegas on exactly this.",
}


def test_grounded():
    assert grounded("Tenable backlog hit 14,000 findings", CORPUS)
    assert not grounded("we migrated everything to Kubernetes last quarter", CORPUS)
    assert not grounded("", CORPUS)


def test_valid_draft_passes():
    assert validate_draft(GOOD, CORPUS) == []


def test_hallucinated_quote_fails():
    bad = {**GOOD, "evidence_quote": "you recently raised a Series C and hired a new CISO"}
    assert any("not found" in e for e in validate_draft(bad, CORPUS))


def test_link_and_banned_phrase_and_length_fail():
    assert any("links" in e for e in validate_draft({**GOOD, "message": GOOD["message"] + " https://x.io"}, CORPUS))
    assert any("banned" in e for e in validate_draft({**GOOD, "message": "I hope this finds you well. " + GOOD["message"]}, CORPUS))
    assert any("too long" in e for e in validate_draft({**GOOD, "connection_note": "x " * 150}, CORPUS))


def test_final_message_appends_cta():
    assert "lu.ma" in final_message("Hello")


def test_build_lead_shape():
    contact = {"first_name": "Priya", "last_name": "Nair", "linkedin_url": "https://www.linkedin.com/in/priya-nair-sec",
               "title": "VP Security", "companies": {"name": "Northwind Cloud"}}
    p = build_lead(contact, {"hook": "h", "connection_note": "c", "message": "m"}, sender_account_id=7)
    assert p["linkedInAccountId"] == 7
    assert p["lead"]["profileUrl"].endswith("priya-nair-sec")
    names = {f["name"] for f in p["lead"]["customUserFields"]}
    assert names == {"ai_hook", "connection_note", "ai_message"}
