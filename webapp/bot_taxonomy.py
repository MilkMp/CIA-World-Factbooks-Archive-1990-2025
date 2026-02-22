"""Canonical bot taxonomy — single source of truth for UA classification.

Used by webapp middleware (main.py) and analytics dashboard (analytics_dashboard.py).
Categories based on Cloudflare, Matomo Device Detector, and Arcjet standards.

Actions:
  allow      — exempt from rate limits (search engines, social preview, monitors)
  rate_limit — apply tighter rate limits (AI crawlers, SEO tools)
  block      — instant ban + tarpit (scrapers, security scanners)
"""

BOT_TAXONOMY = {
    "search_engine": {
        "action": "allow",
        "patterns": [
            "googlebot", "bingbot", "slurp", "duckduckbot", "yandexbot",
            "baiduspider", "sogou", "seznam", "qwant",
        ],
    },
    "ai_crawler": {
        "action": "rate_limit",
        "patterns": [
            "gptbot", "claudebot", "claude-web", "anthropic-ai", "ccbot",
            "bytespider", "meta-externalagent", "meta-externalfetcher",
            "cohere-ai", "google-extended", "amazonbot", "diffbot",
            "omgili", "friendlycrawler", "imagesiftbot", "img2dataset",
            "timpibot", "petalbot",
        ],
    },
    "ai_search": {
        "action": "allow",
        "patterns": [
            "chatgpt-user", "perplexitybot", "youbot", "phind",
        ],
    },
    "seo_tool": {
        "action": "rate_limit",
        "patterns": [
            "semrush", "ahref", "mj12bot", "dotbot", "dataforseo",
            "serpstat", "seokicks", "blexbot", "linkdex", "megaindex",
            "rogerbot", "screaming frog",
        ],
    },
    "social_preview": {
        "action": "allow",
        "patterns": [
            "twitterbot", "facebookexternalhit", "linkedinbot", "slackbot",
            "discordbot", "telegrambot", "whatsapp", "pinterestbot",
            "redditbot", "mastodon",
        ],
    },
    "monitor": {
        "action": "allow",
        "patterns": [
            "uptimerobot", "pingdom", "site24x7", "statuscake",
            "freshping", "betteruptime", "nodeping",
        ],
    },
    "feed_fetcher": {
        "action": "allow",
        "patterns": [
            "feedly", "feedbin", "inoreader", "theoldreader",
            "newsblur", "feedspot", "tiny tiny rss",
        ],
    },
    "archiver": {
        "action": "allow",
        "patterns": [
            "ia_archiver", "archive.org_bot", "wayback", "internetarchivebot",
        ],
    },
    "security_scanner": {
        "action": "block",
        "patterns": [
            "nikto", "sqlmap", "nmap", "nessus", "openvas", "acunetix",
            "burpsuite", "qualys", "dirbuster", "gobuster", "wpscan",
            "nuclei", "zgrab",
        ],
    },
    "scraper": {
        "action": "block",
        "patterns": [
            "python-requests", "scrapy", "python-urllib", "go-http-client",
            "java/", "libwww-perl", "wget", "httpx",
            "php/", "okhttp", "axios/", "node-fetch", "colly",
        ],
    },
}

# Display names for dashboard charts
CATEGORY_LABELS = {
    "search_engine": "Search Engine",
    "ai_crawler": "AI Crawler",
    "ai_search": "AI Search",
    "seo_tool": "SEO Tool",
    "social_preview": "Social Preview",
    "monitor": "Monitor",
    "feed_fetcher": "Feed Fetcher",
    "archiver": "Archiver",
    "security_scanner": "Security Scanner",
    "scraper": "Scraper",
    "human": "Human",
}

# Colors for dashboard charts (DG2 palette)
CATEGORY_COLORS = {
    "search_engine": "#2D72D2",
    "ai_crawler": "#7C3AED",
    "ai_search": "#9D79EF",
    "seo_tool": "#D1980B",
    "social_preview": "#2D72D2",
    "monitor": "#238551",
    "feed_fetcher": "#238551",
    "archiver": "#5C7080",
    "security_scanner": "#CD4246",
    "scraper": "#CD4246",
    "human": "#238551",
}


def classify_ua(ua: str) -> tuple:
    """Return (category, action) for a user agent string.

    Returns ('human', 'allow') if no bot pattern matches.
    """
    low = ua.lower() if ua else ""
    for category, info in BOT_TAXONOMY.items():
        if any(p in low for p in info["patterns"]):
            return category, info["action"]
    return "human", "allow"


def get_all_patterns() -> list:
    """Flat list of all bot UA patterns (for SQL LIKE clauses)."""
    patterns = []
    for info in BOT_TAXONOMY.values():
        patterns.extend(info["patterns"])
    return patterns


def get_bot_sql_clause() -> str:
    """SQL WHERE clause that matches any bot UA pattern.

    Returns: 'lower(user_agent) LIKE '%pattern1%' OR ...'
    """
    parts = [f"lower(user_agent) LIKE '%{p}%'" for p in get_all_patterns()]
    return " OR ".join(parts)


def get_bot_sql_case() -> str:
    """SQL CASE expression that classifies a UA into a category name.

    Returns a CASE WHEN ... END expression suitable for SELECT.
    """
    lines = ["CASE"]
    for category, info in BOT_TAXONOMY.items():
        label = CATEGORY_LABELS.get(category, category)
        conditions = " OR ".join(
            f"lower(user_agent) LIKE '%{p}%'" for p in info["patterns"]
        )
        lines.append(f"  WHEN {conditions} THEN '{label}'")
    lines.append("  ELSE 'Other Bot'")
    lines.append("END")
    return "\n".join(lines)
