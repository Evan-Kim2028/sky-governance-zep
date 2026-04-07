# governance/episodes.py
import re
from datetime import datetime, timezone


def strip_html(html: str | None) -> str:
    """Remove HTML tags, decode common entities, and collapse whitespace. Caps at 2000 chars."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    # Decode common HTML entities present in Discourse posts
    text = (text
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
            .replace("&nbsp;", " "))
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

    ORIGINAL APPROACH (kept as reference): bundles all posts into one episode,
    so ZEP extracts topic-level facts ("Topic X discussed governance") at the cost
    of losing per-author attribution.

    CURRENT APPROACH: use post_to_episode() instead — one episode per post so ZEP
    can extract person-level temporal edges like "@hexonaut supported X [valid 2026-01-15]".

    Credit cost: 1 credit regardless of post count (vs N credits for N post_to_episode calls).
    Use this if you need to minimise credit spend at the cost of person-graph fidelity.
    """
    title = topic.get("title", "Untitled")
    raw_tags = topic.get("tags") or []
    tag_names = [t["name"] if isinstance(t, dict) else str(t) for t in raw_tags]
    tags = ", ".join(tag_names) or "none"
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


def post_to_episode(
    post: dict,
    topic_id: int,
    topic_title: str,
    category: str,
) -> dict | None:
    """Convert a single Discourse post dict into a ZEP episode attributed to its author.

    Each post becomes one episode so ZEP can extract per-person belief edges:
    e.g. '@hexonaut supported lowering the USDS rate [valid 2026-01-15]'.

    Returns None for posts with < 80 chars of content (single-line reactions
    like "+1", "agreed", "thanks" that yield no extractable graph edges).

    post dict keys used: id, username, created_at, cooked, post_number,
                         like_count, reply_to_post_number
    """
    username = post.get("username", "unknown")
    post_id = post.get("id", 0)
    created_at = post.get("created_at", "")
    like_count = post.get("like_count", 0)
    reply_to = post.get("reply_to_post_number")
    content = strip_html(post.get("cooked") or "")[:1500]
    if len(content) < 80:
        return None

    reply_ctx = f" (replying to post #{reply_to})" if reply_to else ""
    likes_ctx = f" [{like_count} likes]" if like_count else ""

    text = (
        f"Forum post by @{username} in '{topic_title}' ({category}){reply_ctx}{likes_ctx}: "
        f"{content}"
    )

    return {
        "data": text[:2500],
        "type": "text",
        "created_at": created_at,
        "source_description": f"post-{topic_id}-{post_id}",
    }


def user_profile_to_episode(profile: dict, stats: dict) -> dict:
    """Convert a Discourse user profile + directory stats into a ZEP episode.

    This gives ZEP person-entity context: role, group membership,
    activity level, and bio — so it can answer who the key participants
    are and what their standing in the DAO is.

    profile: dict from fetch_user_profile (username, title, trust_level,
             badge_count, bio_raw, created_at, last_posted_at, groups)
    stats:   dict from fetch_top_posters item (post_count, likes_received)
    """
    username = profile.get("username", "unknown")
    title = profile.get("title") or "community member"
    trust_level = profile.get("trust_level", 0)
    badge_count = profile.get("badge_count", 0)
    bio = strip_html(profile.get("bio_raw") or "")[:500]
    created_at = profile.get("created_at") or None
    last_posted = profile.get("last_posted_at") or ""
    groups = [g.get("name", "") for g in (profile.get("groups") or [])
              if not g.get("name", "").startswith("trust_level")]

    post_count = stats.get("post_count", 0)
    likes_received = stats.get("likes_received", 0)

    active_since = f"Active since: {created_at}. " if created_at else ""
    last_post = f"Last post: {last_posted}. " if last_posted else ""
    text = (
        f"Sky/MakerDAO governance forum participant: @{username}. "
        f"Role: {title}. "
        f"Groups: {', '.join(groups) or 'none'}. "
        f"Trust level: {trust_level}. Badges: {badge_count}. "
        f"Activity: {post_count} posts, {likes_received} likes received. "
        f"{active_since}{last_post}"
    )
    if bio:
        text += f"Bio: {bio}"

    return {
        "data": text[:2500],
        "type": "text",
        "created_at": created_at,
        "source_description": f"user-{username}",
    }


def delegate_vote_to_episode(record: dict) -> dict:
    """Convert a per-delegate vote record into a ZEP episode.

    This lets ZEP build temporal edges like:
    'Bonapublica voted Yes on Atlas Edit Jan 2026 with 50,000 MKR [valid 2026-01-13]'

    record keys: delegate_name, voter_address, option_name, mkr_support,
                 voted_at, poll_id, poll_title
    """
    name = record.get("delegate_name", "unknown")
    option = record.get("option_name", "unknown")
    mkr = record.get("mkr_support", "?")
    voted_at = record.get("voted_at", "")
    poll_title = record.get("poll_title", "unknown poll")
    poll_id = record.get("poll_id", "?")
    voter_address = record.get("voter_address", "")

    text = (
        f"Delegate vote: {name} voted '{option}' on governance poll "
        f"'{poll_title}' (poll ID: {poll_id}) "
        f"with {mkr} MKR voting weight. "
        f"Voted at: {voted_at}."
    )

    return {
        "data": text,
        "type": "text",
        "created_at": _parse_date(voted_at),
        "source_description": f"delegate-vote-{poll_id}-{voter_address}",
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
