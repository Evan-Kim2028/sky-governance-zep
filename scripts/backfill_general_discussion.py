#!/usr/bin/env python3
"""
One-time backfill: ingest governance-relevant General Discussion topics → ZEP Cloud.

Fetches all General Discussion topics from forum.skyeco.com, filters to those with
≥5 posts and governance-relevant titles, and ingests per-post episodes.

Estimated cost: ~432 post episodes (~2% of Flex monthly credits).

Usage:
  python scripts/backfill_general_discussion.py [--dry-run]
"""

import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from zep_cloud.client import Zep

from governance.episodes import post_to_episode
from governance.fetchers import (
    SKY_FORUM_BASE,
    _get,
    fetch_all_topic_post_records,
    fetch_category_by_name,
    is_gov_relevant_title,
)
from governance.ingest import ZEP_GRAPH_ID, ensure_graph, estimate_credits, ingest_episodes

load_dotenv(Path(__file__).parent.parent / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

CATEGORY = "General Discussion"
MIN_POSTS = 5


def fetch_all_general_discussion_topics(
    cat_id: int,
    cat_slug: str,
    max_pages: int = 30,
    forum_base: str = SKY_FORUM_BASE,
) -> list[dict]:
    """Paginate through General Discussion, returning all topics (no date filter)."""
    topics = []
    for page in range(max_pages):
        data = _get(f"{forum_base}/c/{cat_slug}/{cat_id}.json", params={"page": page})
        page_topics = data.get("topic_list", {}).get("topics", [])
        if not page_topics:
            log.info(f"   Page {page}: empty — done paginating")
            break
        topics.extend(page_topics)
        log.info(f"   Page {page}: {len(page_topics)} topics (total so far: {len(topics)})")
        if page < max_pages - 1:
            time.sleep(0.5)
    return topics


def filter_governance_topics(topics: list[dict]) -> list[dict]:
    """Return topics with ≥MIN_POSTS posts and governance-relevant titles."""
    filtered = [
        t for t in topics
        if t.get("posts_count", 0) >= MIN_POSTS
        and is_gov_relevant_title(t.get("title", ""))
    ]
    return filtered


def main(dry_run: bool = False) -> None:
    api_key = os.environ.get("ZEP_API_KEY")
    if not api_key:
        raise RuntimeError("ZEP_API_KEY not set — copy .env.example to .env and fill it in")

    log.info("── General Discussion backfill ──")
    log.info(f"   Fetching category list from {SKY_FORUM_BASE}...")
    result = fetch_category_by_name("general")
    if result is None:
        log.error("Could not find General Discussion category — aborting")
        sys.exit(1)
    cat_id, cat_slug = result
    log.info(f"   Found General Discussion: id={cat_id}, slug={cat_slug}")

    log.info("   Paginating all General Discussion topics...")
    all_topics = fetch_all_general_discussion_topics(cat_id, cat_slug)
    log.info(f"   Total topics fetched: {len(all_topics)}")

    gov_topics = filter_governance_topics(all_topics)
    log.info(f"   Governance-relevant topics (≥{MIN_POSTS} posts): {len(gov_topics)}")
    for t in gov_topics:
        log.info(f"     [{t['posts_count']} posts] {t['title']}")

    log.info("   Fetching all posts per topic...")
    all_episodes = []
    for i, topic in enumerate(gov_topics, 1):
        topic_id = topic["id"]
        title = topic.get("title", "Untitled")
        log.info(f"   [{i}/{len(gov_topics)}] {title!r} (topic {topic_id})")
        post_records = fetch_all_topic_post_records(topic_id, forum_base=SKY_FORUM_BASE)
        for post in post_records:
            all_episodes.append(post_to_episode(
                post,
                topic_id=topic_id,
                topic_title=title,
                category=CATEGORY,
            ))
        time.sleep(0.4)

    credit_estimate = estimate_credits(all_episodes)
    log.info(f"   Episode count: {credit_estimate} (each costs 1 Flex credit)")

    if dry_run:
        log.info("   --dry-run: skipping ingest")
        return

    client = Zep(api_key=api_key)
    ensure_graph(client)
    ingested = ingest_episodes(client, all_episodes)
    log.info(f"── Done: {ingested} episodes ingested ──")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="One-time backfill: ingest governance-relevant General Discussion topics → ZEP Cloud."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and filter topics but skip ZEP ingest. Prints episode count and credit estimate.",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
