# governance/episodes.py
import re
from datetime import datetime, timezone


def strip_html(html: str | None) -> str:
    """Remove HTML tags and collapse whitespace. Caps at 2000 chars."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000]


def _parse_date(date_str: str | None) -> str | None:
    """Return an ISO 8601 datetime string or None.

    Handles both ISO format (already correct for ZEP) and the JavaScript
    Date.toString() format emitted by the vote.makerdao.com API, e.g.:
      'Thu May 15 2025 00:00:00 GMT+0000 (Coordinated Universal Time)'
    Returns None for empty/unparseable input so callers can omit created_at.
    """
    if not date_str:
        return None
    # Already ISO-ish (contains 'T' or starts with digit)
    if date_str[0].isdigit():
        return date_str
    # JS Date.toString() format — strip the timezone name in parentheses first
    cleaned = re.sub(r"\s*\(.*?\)\s*$", "", date_str).strip()
    try:
        dt = datetime.strptime(cleaned, "%a %b %d %Y %H:%M:%S GMT%z")
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def topic_to_episode(topic: dict, posts: list[str], category_name: str) -> dict:
    """Convert a Discourse topic + list of post HTML strings into one ZEP episode.

    All posts are bundled into a single episode (one ZEP credit regardless of post count).
    Each post is HTML-stripped and capped at 300 chars. Total episode capped at 4000 chars.
    """
    title = topic.get("title", "Untitled")
    tags = ", ".join(topic.get("tags") or []) or "none"
    created = topic.get("created_at", "")
    posts_count = topic.get("posts_count", 0)
    like_count = topic.get("like_count", 0)
    views = topic.get("views", 0)

    post_parts = []
    for i, html in enumerate(posts, 1):
        text = strip_html(html)
        if text:
            post_parts.append(f"Post {i}: {text[:300]}")

    discussion = " | ".join(post_parts)

    text = (
        f"Sky/MakerDAO governance forum topic: \"{title}\" "
        f"in category '{category_name}'. "
        f"Tags: {tags}. "
        f"Posted: {created}. "
        f"Engagement: {posts_count} replies, {like_count} likes, {views} views. "
    )
    if discussion:
        text += f"Discussion: {discussion}"

    return {
        "data": text[:4000],
        "type": "text",
        "created_at": created,
        "source_description": f"forum-topic-{topic.get('id')}",
    }


def poll_to_episode(poll: dict, tally: dict | None) -> dict | None:
    """Convert a vote.makerdao.com poll + optional tally into a ZEP episode dict."""
    title = poll.get("title", "")
    if not title:
        return None

    slug = poll.get("slug", "")
    options = poll.get("options") or []
    option_labels = [o.get("label", "") for o in options if isinstance(o, dict)]
    tags = ", ".join(poll.get("tags") or []) or "none"
    start_date = poll.get("startDate") or ""
    end_date = poll.get("endDate") or ""

    tally_text = ""
    if tally:
        results = tally.get("results") or []
        if results:
            top = results[0]
            tally_text = (
                f"Winning option: '{top.get('optionName', '?')}' "
                f"with {top.get('mkrSupport', '?')} MKR. "
                f"Total: {tally.get('totalMkrActiveParticipation', '?')} MKR."
            )

    text = (
        f"MakerDAO/Sky governance poll: \"{title}\" (slug: {slug}). "
        f"Tags: {tags}. Active: {start_date} to {end_date}. "
        f"Options: {', '.join(option_labels) or 'see poll'}. "
    )
    if tally_text:
        text += f"Result: {tally_text}"

    return {
        "data": text,
        "type": "text",
        "created_at": start_date,
        "source_description": f"poll-{poll.get('pollId') or slug or 'unknown'}",
    }


def executive_to_episode(exec_: dict) -> dict | None:
    """Convert a vote.makerdao.com executive proposal into a ZEP episode dict."""
    title = exec_.get("title", "")
    if not title:
        return None

    key = exec_.get("key", "")
    date = exec_.get("date") or ""
    passed = exec_.get("passed")
    mkr_support = exec_.get("mkrSupport", "?")
    about = strip_html(exec_.get("about") or "")[:500]

    text = (
        f"MakerDAO executive vote: \"{title}\" (key: {key}). "
        f"Date: {date}. Passed: {passed}. MKR in support: {mkr_support}. "
    )
    if about:
        text += f"Details: {about}"

    return {
        "data": text,
        "type": "text",
        "created_at": _parse_date(date),
        "source_description": f"executive-{key or 'unknown'}",
    }
