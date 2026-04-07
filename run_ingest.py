#!/usr/bin/env python3
"""
Governance ingestion pipeline — MakerDAO + Sky → ZEP Cloud.

Fetches from forum.skyeco.com (canonical post-rebrand forum) and vote.makerdao.com.
Ingests person-level episodes: one per post (author attributed), one per user profile,
one per delegate vote, plus poll and executive summaries.

Usage:
  cp .env.example .env        # fill in ZEP_API_KEY
  python run_ingest.py

Flex plan budget: ~3,700 episodes / 20,000 monthly credits.
"""

import logging
import os
import time
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from zep_cloud import Zep

from governance.episodes import (
    delegate_vote_to_episode,
    executive_to_episode,
    poll_to_episode,
    post_to_episode,
    user_profile_to_episode,
)
from governance.fetchers import (
    BOTH_FORUMS,
    SKY_FORUM_BASE,
    fetch_all_topic_post_records,
    fetch_all_topics_since,
    fetch_delegates,
    fetch_executives,
    fetch_governance_categories,
    fetch_poll_voters,
    fetch_polls_paginated,
    fetch_poll_tally,
    fetch_top_posters,
    fetch_user_profile,
)
from governance.ingest import ZEP_USER_ID, ensure_user, estimate_credits, ingest_episodes

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

MAX_CATEGORIES   = 10     # all governance-relevant categories
MAX_PAGES        = 10     # 10 pages × 30 topics = up to 300 topics per category
MAX_POLLS        = 300    # ~3 months of weekly polls
MAX_EXECUTIVES   = 100    # all recent executive votes
MAX_TOP_POSTERS  = 50     # top monthly posters — person-entity context for ZEP
LOOKBACK_DAYS    = 90     # 3 months — focused, recent, high-signal data

# Flex plan: 20,000 credits/month.
# Estimated budget: ~950 post episodes + 50 profiles + ~2,400 delegate votes
#                   + 300 polls + 5 executives = ~3,700 credits


def ingest_forum(client: Zep, forum_base: str) -> int:
    label = forum_base.replace("https://", "")
    log.info(f"── Forum: {label} ──")
    since = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    categories = fetch_governance_categories(forum_base=forum_base)
    log.info(f"   Found {len(categories)} governance categories: {[c['name'] for c in categories]}")

    episodes = []
    for cat in categories[:MAX_CATEGORIES]:
        topics = fetch_all_topics_since(
            cat["id"], cat["slug"], since=since,
            max_pages=MAX_PAGES, forum_base=forum_base,
        )
        log.info(f"   [{cat['name']}] {len(topics)} topics → fetching all posts per topic")
        for topic in topics:
            post_records = fetch_all_topic_post_records(topic["id"], forum_base=forum_base)
            for post in post_records:
                episodes.append(post_to_episode(
                    post,
                    topic_id=topic["id"],
                    topic_title=topic.get("title", "Untitled"),
                    category=cat["name"],
                ))
            time.sleep(0.4)

    log.info(f"   {label} post episodes: {estimate_credits(episodes)} credits")
    return ingest_episodes(client, episodes)


def ingest_user_profiles(client: Zep) -> int:
    log.info("── User profiles: forum.skyeco.com ──")
    top_items = fetch_top_posters(forum_base=SKY_FORUM_BASE, limit=MAX_TOP_POSTERS, period="monthly")
    log.info(f"   Fetched {len(top_items)} top posters")

    episodes = []
    for item in top_items:
        username = item.get("user", {}).get("username")
        if not username:
            continue
        profile = fetch_user_profile(username, forum_base=SKY_FORUM_BASE)
        if profile:
            stats = {
                "post_count": item.get("post_count", 0),
                "likes_received": item.get("likes_received", 0),
            }
            episodes.append(user_profile_to_episode(profile, stats))
        time.sleep(0.5)

    log.info(f"   User profile episodes: {estimate_credits(episodes)} credits")
    return ingest_episodes(client, episodes)


def ingest_delegate_votes(client: Zep, polls: list[dict]) -> int:
    log.info("── Delegate votes: vote.makerdao.com ──")
    address_to_name = fetch_delegates()
    log.info(f"   Loaded {len(address_to_name)} delegate address mappings")
    log.info(f"   Processing {len(polls)} polls for per-delegate vote records")

    episodes = []
    for poll in polls:
        poll_id = poll.get("pollId") or poll.get("id")
        poll_title = poll.get("title", "")
        if not poll_id:
            continue
        voters = fetch_poll_voters(poll_id=poll_id, poll_title=poll_title, address_to_name=address_to_name)
        for record in voters:
            episodes.append(delegate_vote_to_episode(record))
        time.sleep(0.2)

    log.info(f"   Delegate vote episodes: {estimate_credits(episodes)} credits")
    return ingest_episodes(client, episodes)


def ingest_polls(client: Zep, polls: list[dict]) -> int:
    log.info("── Polls: vote.makerdao.com ──")
    log.info(f"   Fetched {len(polls)} polls")

    episodes = []
    for poll in polls:
        poll_id = poll.get("pollId") or poll.get("id")
        tally = fetch_poll_tally(poll_id) if poll_id else None
        episodes.append(poll_to_episode(poll, tally))

    log.info(f"   Poll episodes: {estimate_credits(episodes)} credits")
    return ingest_episodes(client, episodes)


def ingest_executives(client: Zep) -> int:
    log.info("── Executive votes: vote.makerdao.com ──")
    executives = fetch_executives(limit=MAX_EXECUTIVES)
    log.info(f"   Fetched {len(executives)} executive proposals")
    episodes = [executive_to_episode(e) for e in executives]
    log.info(f"   Executive episodes: {estimate_credits(episodes)} credits")
    return ingest_episodes(client, episodes)


def main() -> None:
    api_key = os.environ.get("ZEP_API_KEY")
    if not api_key:
        raise RuntimeError("ZEP_API_KEY not set — copy .env.example to .env and fill it in")

    client = Zep(api_key=api_key)
    ensure_user(client)
    log.info(f"ZEP user ready: {ZEP_USER_ID}")

    total = 0
    for forum_base in BOTH_FORUMS:
        total += ingest_forum(client, forum_base)
    total += ingest_user_profiles(client)
    polls = fetch_polls_paginated(max_polls=MAX_POLLS)
    log.info(f"Fetched {len(polls)} polls (shared across delegate votes and poll summaries)")
    total += ingest_delegate_votes(client, polls)
    total += ingest_polls(client, polls)
    total += ingest_executives(client)

    log.info(f"── Done: {total} episodes ingested ({total}/20,000 Flex monthly credits) ──")
    log.info("Graph processes asynchronously. Wait 90s then run query.py.")


if __name__ == "__main__":
    main()
