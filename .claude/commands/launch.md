---
description: Approved messages ko HeyReach campaign me daalo (pehle dry-run)
argument-hint: <heyreach_campaign_id> [--live]
---
1. Pehle hamesha dry-run: `./scripts/gtm.sh launch $1`. Preview + skipped reasons dikhao.
2. User ko count aur 2-3 sample lead dikhao aur poocho: "Live bhejun?"
3. **Sirf** jab user clearly "haan live" bole tab `./scripts/gtm.sh launch $1 --live` chalao.
4. Result: kitne pushed, kitne skipped. HeyReach dashboard me verify karne ko bolo.
