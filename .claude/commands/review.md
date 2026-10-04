---
description: Draft messages review karo aur approve/reject karo
---
1. `./scripts/gtm.sh queue draft 20` chalao.
2. Score ke hisaab se sort karke har item dikhao: naam, title, company, score/tier, hook, connection_note, message.
3. Har draft pe 1 line me tumhari raay do (grounded hai? tone theek? risk?).
4. User jo IDs bole sirf unhi ko `./scripts/gtm.sh approve <id>` / `reject <id> "<reason>"` karo. Khud approve kabhi nahi.
Edit chahiye to user se naya text lo aur approve endpoint me `edited_message` ke saath bhejo (curl via scripts/gtm.sh ke pattern pe).
