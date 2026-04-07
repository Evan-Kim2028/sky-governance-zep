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
    try:
        data = _get(f"{VOTE_BASE}/api/executive")
        if isinstance(data, list):
            return data[:limit]
        return []
    except Exception:
        return []


def fetch_top_posters(
    forum_base: str = FORUM_BASE,
    limit: int = 50,
    period: str = "monthly",
) -> list[dict]:
    """Return top-posting community members from the Discourse directory.

    Each item has: {id, likes_received, post_count, topic_count,
                    user: {username, title, trust_level}}
    Returns empty list on error.
    """
    try:
        data = _get(
            f"{forum_base}/directory_items.json",
            params={"order": "post_count", "period": period, "page": 0},
        )
        items = data.get("directory_items", [])
        return items[:limit]
    except Exception:
        return []


def fetch_user_profile(username: str, forum_base: str = FORUM_BASE) -> dict | None:
    """Return the Discourse user profile dict for a username, or None on error.

    Keys of interest: username, title, trust_level, badge_count, bio_raw,
                      created_at, last_posted_at, groups (list of {name}).
    """
    try:
        data = _get(f"{forum_base}/u/{username}.json")
        return data.get("user")
    except Exception:
        return None


def fetch_delegates() -> dict[str, str]:
    """Return a mapping of voteDelegateAddress (lowercase) → delegate name.

    Used to resolve on-chain voter addresses in tally votesByAddress to
    human-readable delegate names.
    Returns empty dict on error.
    """
    try:
        data = _get(f"{VOTE_BASE}/api/delegates")
        delegates = data.get("delegates", []) if isinstance(data, dict) else []
        return {
            d["voteDelegateAddress"].lower(): d["name"]
            for d in delegates
            if d.get("voteDelegateAddress") and d.get("name")
        }
    except Exception:
        return {}


def fetch_poll_voters(
    poll_id: int,
    poll_title: str,
    address_to_name: dict[str, str] | None = None,
) -> list[dict]:
    """Return per-delegate vote records for a poll.

    Each record: {delegate_name, voter_address, option_name, mkr_support,
                  voted_at, poll_id, poll_title}
    Resolves voter addresses to delegate names using fetch_delegates().
    Addresses not in the delegate list are shown as truncated address.
    Returns empty list on tally fetch error.

    address_to_name: optional pre-fetched delegate map (address → name).
                     If None, fetches fresh via fetch_delegates().
                     Pass a pre-fetched map when processing many polls
                     to avoid 300 redundant API calls per run.
    """
    if address_to_name is None:
        address_to_name = fetch_delegates()
    try:
        tally = _get(f"{VOTE_BASE}/api/polling/tally/{poll_id}")
    except Exception:
        return []

    votes_by_address = tally.get("votesByAddress", [])
    results = tally.get("results", [])
    option_map = {str(r["optionId"]): r["optionName"] for r in results}

    records = []
    for v in votes_by_address:
        addr = (v.get("voter") or "").lower()
        option_id = str(v.get("optionIdRaw", ""))
        records.append({
            "delegate_name": address_to_name.get(addr, (addr[:10] + "...") if addr else "unknown"),
            "voter_address": addr,
            "option_name": option_map.get(option_id, f"option-{option_id}"),
            "mkr_support": v.get("mkrSupport", "?"),
            "voted_at": v.get("blockTimestamp", ""),
            "poll_id": poll_id,
            "poll_title": poll_title,
        })
    return records
