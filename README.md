     1|
     2|## Vercel Status
     3|
     4|Using standard api/index.py layout.
     5|All data in /tmp → resets on cold starts.
     6|Visit / for health check.
     7|Next: proper config.py + Vercel Postgres.
     8|
## Current Vercel Status (Jan 2026)

- Using single `api/index.py` serverless function
- All data forced to `/tmp` (resets on cold starts)
- Old `src/` folder deleted
- Visit root URL → should return JSON with "alive on Vercel!"
- Next phase: re-add proper config + Vercel Postgres for persistence