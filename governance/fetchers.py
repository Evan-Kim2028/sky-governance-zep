# governance/fetchers.py
import time
from datetime import datetime, timezone

import requests

VOTE_BASE  = "https://vote.makerdao.com"
HEADERS    = {"Accept": "application/json", "User-Agent": "ZEP-Governance-Explorer/1.0"}
GOV_KEYWORDS = {
    # Sky Endgame era (current): forum.skyeco.com categories post-2024 rebrand
    "sky", "spark", "grove", "keel", "obex", "pattern", "alignment", "proposal",
    # MakerDAO legacy era: kept for any historical forum data that may surface
    "governance", "mips", "risk", "signal", "collateral", "executive",
}

PAGE_SIZE  = 30   # Discourse default topics-per-page
BATCH_SIZE = 20   # Max post IDs per /posts.json batch request

MAKER_FORUM_BASE = "https://forum.makerdao.com"   # historical alias — now mirrors skyeco
SKY_FORUM_BASE   = "https://forum.skyeco.com"     # current canonical forum
FORUM_BASE       = SKY_FORUM_BASE                 # default for single-forum calls

# Post-rebrand, forum.makerdao.com redirects to the same content as forum.skyeco.com.
# Fetching both would duplicate episodes. Use only the canonical Sky forum.
BOTH_FORUMS = [SKY_FORUM_BASE]


def _get(url: str, params: dict | None = None) -> dict | list:
    resp = requests.get(url, headers=HEADERS, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_governance_categories(forum_base: str = FORUM_BASE) -> list[dict]:
    """Return Discourse categories whose name or slug matches governance keywords."""
    data = _get(f"{forum_base}/categories.json")
    cats = data.get("category_list", {}).get("categories", [])
    return [
        cat for cat in cats
        if any(
            kw in (cat.get("name") or "").lower() or kw in (cat.get("slug") or "").lower()
            for kw in GOV_KEYWORDS
        )
    ]


def fetch_all_topics_since(
    cat_id: int,
    cat_slug: str,
    since: datetime,
    max_pages: int = 5,
    forum_base: str = FORUM_BASE,
) -> list[dict]:
    """Paginate through a Discourse category, returning topics created on or after `since`.

    Discourse sorts by recent activity (bumped_at), so active old topics still surface.
    Stops early when a page is empty. Sleeps 0.5s between pages to respect rate limits.
    """
    topics = []
    for page in range(max_pages):
        data = _get(f"{forum_base}/c/{cat_slug}/{cat_id}.json", params={"page": page})
        page_topics = data.get("topic_list", {}).get("topics", [])
        if not page_topics:
            break
        for topic in page_topics:
            raw_date = topic.get("created_at", "")
            try:
                topic_dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                if topic_dt >= since:
                    topics.append(topic)
            except (ValueError, AttributeError):
                topics.append(topic)  # include if date unparseable
        if page < max_pages - 1:
            time.sleep(0.5)
    return topics


def fetch_all_topic_post_records(topic_id: int, forum_base: str = FORUM_BASE) -> list[dict]:
    """Return all post dicts for a topic, fetching every page.

    Uses post_stream.stream (list of all post IDs) from the first request,
    then batch-fetches remaining IDs via /t/{id}/posts.json.
    Returns dicts with keys: id, username, created_at, cooked, post_number,
    like_count, reply_to_post_number.
    Returns empty list on any error.
    """
    try:
        data = _get(f"{forum_base}/t/{topic_id}.json")
        ps = data.get("post_stream", {})
        all_ids: list[int] = ps.get("stream", [])
        first_posts: list[dict] = ps.get("posts", [])

        records = [p for p in first_posts if p.get("cooked")]
        fetched_ids = {p["id"] for p in first_posts}
        remaining_ids = [pid for pid in all_ids if pid not in fetched_ids]

        for i in range(0, len(remaining_ids), BATCH_SIZE):
            batch = remaining_ids[i : i + BATCH_SIZE]
            params = [("post_ids[]", pid) for pid in batch]
            batch_data = _get(f"{forum_base}/t/{topic_id}/posts.json", params=params)
            batch_posts = batch_data.get("post_stream", {}).get("posts", [])
            records.extend(p for p in batch_posts if p.get("cooked"))
            if i + BATCH_SIZE < len(remaining_ids):
                time.sleep(0.3)

        return records
    except Exception:
        return []


def fetch_polls_paginated(max_polls: int = 150) -> list[dict]:
    """Paginate vote.makerdao.com polls to collect historical data.

    Fetches PAGE_SIZE polls per request across multiple pages until max_polls
    is reached or an empty page signals the end of results.
    """
    all_polls: list[dict] = []
    page = 0
    while len(all_polls) < max_polls:
        raw = _get(
            f"{VOTE_BASE}/api/polling/v2/all-polls",
            params={"pageSize": PAGE_SIZE, "page": page},
        )
        if isinstance(raw, list):
            batch = raw
        else:
            batch = raw.get("polls") or raw.get("data") or []
        if not batch:
            break
        all_polls.extend(batch)
        page += 1
        time.sleep(0.2)
    return all_polls[:max_polls]


def fetch_poll_tally(poll_id: int) -> dict | None:
    """Return vote tally for a specific poll, or None on error."""
    try:
        return _get(f"{VOTE_BASE}/api/polling/tally/{poll_id}")
    except Exception:
        return None


def fetch_executives(limit: int = 50) -> list[dict]:
    """Return up to `limit` executive proposals from vote.makerdao.com."""
    data = _get(f"{VOTE_BASE}/api/executive")
    if isinstance(data, list):
        return data[:limit]
    return []
