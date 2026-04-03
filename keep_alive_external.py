"""
External keep-alive pinger for Render free tier.

Run this as a cron job on any free service (GitHub Actions, cron-job.org, etc.)
to ping your Render API and prevent spin-down.

Free cron services you can use:
- https://cron-job.org (free, every 5 min minimum)
- https://github.com/actions (free, schedule every 10 min)
- https://uptimerobot.com (free, every 5 min)
- https://betterstack.com (free, every 30 sec)

Setup on cron-job.org:
1. Create account at https://cron-job.org
2. Create new cron job
3. URL: https://api-toolkit-yb1l.onrender.com/health
4. Schedule: Every 10 minutes
5. Done — your API will never spin down

Setup on UptimeRobot:
1. Create account at https://uptimerobot.com
2. Add new monitor (HTTP(s))
3. URL: https://api-toolkit-yb1l.onrender.com/health
4. Interval: 5 minutes
5. Done

Setup on Better Stack:
1. Create account at https://betterstack.com
2. Create new heartbeat monitor
3. URL: https://api-toolkit-yb1l.onrender.com/health
4. Period: Every 1 minute
5. Done
"""

import httpx
import sys

API_URL = "https://api-toolkit-yb1l.onrender.com"

def ping():
    try:
        r = httpx.get(f"{API_URL}/health", timeout=10)
        if r.status_code == 200:
            print(f"OK — {r.json()}")
            return 0
        else:
            print(f"WARN — status {r.status_code}")
            return 1
    except Exception as e:
        print(f"FAIL — {e}")
        return 1

if __name__ == "__main__":
    sys.exit(ping())
