---
description: Real ClearCue payload dekh kar normalize.py ka FIELD_MAP tight karo
---
1. Supabase `raw_events` se latest 3 payload padho (MCP ya user se paste karwao). Secrets/PII mask karke dikhao.
2. `engine/app/normalize.py` ka `FIELD_MAP` real key names ke hisaab se update karo.
3. `samples/clearcue_webhook.json` ko real shape se replace karo (PII hata ke) aur `engine/tests/test_normalize.py` update karo.
4. `make test` chalao. Pass hone par diff summary do.
