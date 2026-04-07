#!/usr/bin/env python3
"""
Governance ingestion pipeline — MakerDAO + Sky → ZEP Cloud.

Fetches from BOTH forums:
  - forum.makerdao.com  (historical: 2019-2024, pre-rebrand Maker governance)
  - forum.skyeco.com    (current: 2024+, post-rebrand Sky governance)

These are the same community/protocol lineage. The old forum holds all the
historically important decisions (Black Thursday, MIP-21, MIP-65, Endgame).
The new forum has the rebrand discussions and ongoing Sky protocol governance.

Usage:
  cp .env.example .env        # fill in ZEP_API_KEY
  python run_ingest.py

Free tier budget: ~350 credits per full run (1000/month limit).
"""

import logging
import os
import time
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from zep_cloud import Zep

from governance.episodes import executive_to_episode, poll_to_episode, topic_to_episode
from governance.fetchers import (
    BOTH_FORUMS,
    fetch_executives,
    fetch_governance_categories,
    fetch_all_topics_since,
    fetch_topic_posts,
    fetch_polls_paginated,
    fetch_poll_tally,
)
from governance.ingest import ZEP_USER_ID, ensure_user, estimate_credits, ingest_episodes

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

MAX_CATEGORIES   = 5      # per forum
MAX_PAGES        = 5      # 5 pages × 30 topics = up to 150 topics per category
MAX_POLLS        = 150    # ~5 pages of polls — covers 2+ years of governance history
MAX_EXECUTIVES   = 50     # all recent executive votes
LOOKBACK_DAYS    = 730    # 2 years — captures Endgame plan, MIP-65, core unit era

# Total budget: ~150 forum + 150 polls + 50 execs = ~350 credits out of 1000/month


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
        log.info(f"   [{cat['name']}] {len(topics)} topics within {LOOKBACK_DAYS}d window")
        for topic in topics:
            posts_html = fetch_topic_posts(topic["id"], forum_base=forum_base)
            episodes.append(topic_to_episode(topic, posts_html, cat["name"]))
            time.sleep(0.4)  # respect Discourse rate limit (~150 req/min max)

    log.info(f"   {label} episodes: {estimate_credits(episodes)} credits")
    return ingest_episodes(client, episodes)


def ingest_polls(client: Zep) -> int:
    log.info("── Polls: vote.makerdao.com ──")
    polls = fetch_polls_paginated(max_polls=MAX_POLLS)
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
    # Both forums: historical Maker (2019-2024) + current Sky (2024+)
    for forum_base in BOTH_FORUMS:
        total += ingest_forum(client, forum_base)
    total += ingest_polls(client)
    total += ingest_executives(client)

    log.info(f"── Done: {total} episodes ingested ({total}/1000 monthly credits used) ──")
    log.info("Graph processes asynchronously on free tier. Wait 60-90s then run query.py.")


if __name__ == "__main__":
    main()
