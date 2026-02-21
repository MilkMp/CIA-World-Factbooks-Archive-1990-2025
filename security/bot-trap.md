# Bot Trap: Self-Reinforcing Rate Limit Ban

## Origin

On February 21, 2026, an AWS EC2 instance (216.73.216.178, Columbus, Ohio) began
systematically scraping the CIA Factbook Archive at 2-second intervals -- crawling
every country-year page, field page, and CSV/XLSX export endpoint to clone the
full dataset.


## The Problem

Standard rate limiting (N requests per minute) only slows bots down -- they adapt
by spreading requests across endpoints or pacing just under the limit. A fixed-duration
ban (e.g. "blocked for 1 hour") doesn't work either: the bot just waits out the ban
and resumes scraping.

## The Solution: Multi-Layer Bot Defense

### Layer 1: Honeypot Endpoints

Fake paths listed as `Disallow` in `robots.txt`. Good bots obey the Disallow. Real
users never see these paths. Only bad scrapers follow them.

```
Honeypot paths: /admin, /database, /wp-admin, /wp-login, /.env, /backup
```

Any request to a honeypot = **instant ban + 15-second tarpit delay**. The bot
doesn't even get a useful error message -- just an empty 404 after waiting 15
seconds.

### Layer 2: User-Agent Blocking

Known scraper libraries are blocked on sight:

```
python-requests, scrapy, python-urllib, go-http-client,
java/, libwww-perl, wget, httpx
```

Matched UAs get an instant ban + tarpit. Empty User-Agents are allowed through
because Fly.io health checks don't send one.

### Layer 3: Request Fingerprinting

Bots have a telltale signature: machine-precise timing intervals. A human clicks
a page, reads for 10-60 seconds, clicks another. A bot requests pages at exactly
5.000-second intervals with near-zero variance.

The fingerprinter tracks the last 2 minutes of requests per IP. If it detects 8+
requests with < 1 second of timing variance and < 10 second average intervals,
it's a bot. Instant ban + tarpit.

```
Human:    intervals = [3.2s, 47.1s, 2.8s, 15.4s, 8.9s]  -> high variance
Bot:      intervals = [5.0s, 5.0s, 5.1s, 4.9s, 5.0s]    -> near-zero variance
```

### Layer 4: Targeted Rate Limits

Per-endpoint rate limits on scrape-prone paths. These thresholds are low enough
to catch bots but invisible to real users:

```python
RATE_RULES = [
    ("/export/",         5,  60.0),   # bulk CSV/XLSX downloads
    ("/archive/field/",  6,  60.0),   # individual field pages
    ("/archive/",        6,  60.0),   # country archive pages
    ("/countries",       6,  60.0),   # country listing pages
    ("/api/",            15, 60.0),   # API endpoints
]
```

Exceeding a limit returns 429 and records a "strike" against the IP.

### Layer 5: Escalating Ban (The Trap)

After 6 strikes (429 responses) within 5 minutes, the IP is banned for 1 hour.

The key insight: **every request a banned bot makes resets its own ban timer**. The
bot's persistence becomes the mechanism that keeps it locked out.

```
1. RATE LIMIT     Bot hits endpoint too many times per minute
                  -> Returns 429 Too Many Requests
                  -> Records a "strike" against the IP

2. ESCALATING BAN  After 6 strikes within 5 minutes
                  -> IP is banned for 1 hour
                  -> Returns 403 Forbidden (after 15s tarpit delay)

3. THE TRAP       Every request from a banned IP
                  -> Resets the 1-hour ban timer
                  -> Waits 15 seconds (tarpit)
                  -> Returns 403 Forbidden
                  -> Bot keeps trying, ban never expires
```

The bot is trapped in a loop: it keeps requesting pages, each request extends the
ban, so it never gets unbanned. The only way out is to stop completely for a full
hour -- which automated scrapers don't do.

### Layer 6: Tarpit

Every banned response (from any layer) is delayed by 15 seconds before returning.
This ties up the bot's connections and wastes its resources. Instead of getting a
fast rejection and moving on, the bot sits idle for 15 seconds per request.

At 5-second request intervals, the bot quickly saturates its own connection pool
waiting for tarpit responses.

## Why Real Users Are Safe

- **Honeypots**: Real users never type `/wp-admin` on a CIA Factbook site.
- **UA blocking**: Real users use browsers, not `python-requests`.
- **Fingerprinting**: Humans don't click pages at machine-precise intervals.
- **Rate limits**: Only apply to data-heavy endpoints. No one browses 6 archive
  pages in 60 seconds. Homepage, analysis, and other pages have no limits.
- **Good bot whitelist**: Googlebot, Bingbot, DuckDuckBot, and Slurp bypass
  all rate limiting entirely.

## The Scraper's Progression (Actual Logs)

```
Phase 1: Bot scrapes freely at 2-second intervals
  GET /archive/2004/AE  200 OK
  GET /archive/2004/WF  200 OK
  GET /export/CS/2005/xlsx  200 OK
  ...30 requests/minute

Phase 2: Rate limits deployed -- bot slows to 5-second intervals
  GET /archive/field/LB/Gross national saving  200 OK
  GET /archive/field/CI/National air transport  200 OK
  ...still getting through at ~12/min

Phase 3: Bot rotates across endpoints to avoid per-prefix limits
  GET /export/VE/2013/csv  200 OK
  GET /archive/2013/LI  200 OK
  GET /archive/field/FK/Net migration rate  200 OK
  ...spreading across /export/, /archive/, /archive/field/

Phase 4: Escalating ban triggers after 6 strikes
  BANNED ip=216.73.216.178 for 3600s after 6 strikes
  GET /archive/field/SS/Electricity  403 Forbidden
  GET /archive/field/BW/Economic overview  403 Forbidden
  GET /export/NE/2025/xlsx  403 Forbidden
  ...every request is 403, ban resets on each attempt

Phase 5: Bot is permanently trapped
  The bot continues hitting the server every 5 seconds.
  Each hit resets the 1-hour ban timer + 15s tarpit delay.
  Ban never expires. Bot is effectively locked out forever.
```

## Implementation

The full implementation lives in `webapp/main.py` in the `security_middleware`
function. All security checks run in this order:

1. Honeypot check (instant ban)
2. Ban check (self-reinforcing with tarpit)
3. Bad bot UA check (instant ban with tarpit)
4. Targeted rate limits (strikes toward ban)
5. Request fingerprinting (bot timing detection)

Key constants:

```python
# Honeypot paths (also Disallow'd in robots.txt)
HONEYPOT_PATHS = ("/admin", "/database", "/wp-admin", "/wp-login", "/.env", "/backup")

# Rate limit rules
RATE_RULES = [
    ("/export/",         5,  60.0),
    ("/archive/field/",  6,  60.0),
    ("/archive/",        6,  60.0),
    ("/countries",       6,  60.0),
    ("/api/",            15, 60.0),
]

# Escalating ban
BAN_STRIKE_LIMIT = 6
BAN_STRIKE_WINDOW = 300.0    # 5 minutes
BAN_DURATION = 3600.0        # 1 hour (resets on every attempt)
TARPIT_DELAY = 15.0          # seconds

# Fingerprinting
FINGERPRINT_WINDOW = 120.0               # analyze last 2 minutes
FINGERPRINT_MIN_REQUESTS = 8             # need 8+ requests to judge
FINGERPRINT_MAX_TIMING_VARIANCE = 1.0    # bots have <1s variance
```

## Constraints

- **Shared proxy IP**: Fly.io routes all traffic through an internal proxy
  (172.16.8.250), so rate limits only target endpoints real users don't hit
  repeatedly. No global catch-all -- that would block everyone.
- **In-memory state**: Ban data is stored in Python dicts, not persisted. A
  deploy or restart clears all bans. This is acceptable since deploys are
  infrequent and the bot will re-trigger the ban within minutes.
- **Good bot whitelist**: Googlebot, Bingbot, DuckDuckBot, and Slurp bypass
  all rate limiting to ensure search engine indexing works normally.
- **Tarpit caveat**: The 15-second delay holds an asyncio task open. This is
  fine for a single-machine deployment with occasional bots, but under a
  coordinated DDoS it could exhaust the event loop. For that scale, use
  Cloudflare.
