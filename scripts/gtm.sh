#!/usr/bin/env bash
# GTM Engine ka CLI wrapper. Claude Code slash commands isi ko call karte hain.
# Usage: ./scripts/gtm.sh <health|ingest-sample|process|queue|approve|reject|launch|report> [args]
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi
ENGINE_URL="${ENGINE_URL:-http://localhost:8000}"
: "${ENGINE_API_KEY:?ENGINE_API_KEY .env me set karo}"
REVIEWER="${GTM_REVIEWER:-reviewer}"

call() {  # method path [json-body]
  if [ $# -ge 3 ]; then
    curl -sS -X "$1" "$ENGINE_URL$2" -H "X-API-Key: $ENGINE_API_KEY" -H 'Content-Type: application/json' -d "$3"
  else
    curl -sS -X "$1" "$ENGINE_URL$2" -H "X-API-Key: $ENGINE_API_KEY"
  fi
  echo
}

case "${1:-help}" in
  health)         curl -sS "$ENGINE_URL/healthz"; echo; call GET /health/deps ;;
  ingest-sample)  call POST /webhooks/clearcue "$(cat samples/clearcue_webhook.json)" ;;
  process)        call POST "/process/pending?limit=${2:-20}" ;;
  queue)          call GET "/queue?status=${2:-draft}&limit=${3:-20}" ;;
  approve)        call POST "/messages/${2:?message_id}/approve" "{\"reviewer\":\"$REVIEWER\"}" ;;
  reject)         call POST "/messages/${2:?message_id}/reject" "{\"reviewer\":\"$REVIEWER\",\"reason\":\"${3:-not a fit}\"}" ;;
  launch)         CID="${2:?campaign_id}"; LIVE=false; [ "${3:-}" = "--live" ] && LIVE=true
                  call POST /campaigns/launch "{\"campaign_id\":$CID,\"dry_run\":$([ "$LIVE" = true ] && echo false || echo true)}" ;;
  report)         call GET "/report/summary?days=${2:-7}" ;;
  *) sed -n '2,3p' "$0" ;;
esac
