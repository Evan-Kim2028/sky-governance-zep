#!/usr/bin/env python3
"""
Interactive ZEP graph RAG query CLI for MakerDAO/Sky governance history.

Usage:
  python scripts/query.py

Enter a number to run a predefined query, or type your own free-form question.
ZEP's temporal knowledge graph returns extracted facts with scores and timestamps.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from zep_cloud.client import Zep

from governance.ingest import ZEP_USER_ID

load_dotenv(Path(__file__).parent.parent / ".env")

PREDEFINED = [
    # Person-level temporal graph — the core ZEP showcase
    "Who are the most influential aligned delegates and what positions do they hold?",
    "How have delegate voting patterns on Atlas edits changed over 2025 and 2026?",
    "What did Bonapublica say about WBTC risk and what did they vote on executive spells?",
    "Which delegates abstained or voted against proposals and what were their reasons?",
    # Protocol evolution over time
    "What was the community debate around the MKR to SKY token migration?",
    "How did governance treat the USDS launch and what concerns were raised?",
    "What risk discussions surrounded WBTC as collateral in 2024 and 2025?",
    "What is the Atlas and how has the community contributed to structuring it?",
    # Ecosystem actors and contributors
    "What does BA Labs do and what risk recommendations have they made recently?",
    "What technical work has Sidestream submitted for executor agent onboarding?",
    "Who are the key contributors to the Sky Endgame transition?",
    # AI and tooling (meta — about the DAO's own AI experiments)
    "What is the GAIT initiative and who drove it?",
    "What is Brendan_Navigator and how does it participate in governance?",
]


def search(client: Zep, query: str, limit: int = 8, scope: str = "edges") -> list:
    results = client.graph.search(
        user_id=ZEP_USER_ID,
        query=query,
        limit=limit,
        scope=scope,
    )
    return getattr(results, scope, None) or (results if isinstance(results, list) else [])


def format_edge(i: int, edge) -> str:
    fact = getattr(edge, "fact", str(edge))
    rating = getattr(edge, "fact_rating", None)
    valid_at = getattr(edge, "valid_at", None)
    ts = f"[{str(valid_at)[:10]}] " if valid_at else ""
    score = f"  (score={rating:.3f})" if isinstance(rating, float) else ""
    return f"  [{i}] {ts}{fact}{score}"


def format_node(i: int, node) -> str:
    name = getattr(node, "name", "?")
    summary = getattr(node, "summary", "") or ""
    return f"  [{i}] {name}\n       {summary[:200]}"


def main() -> None:
    api_key = os.environ.get("ZEP_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ZEP_API_KEY not set — copy .env.example to .env and add your key from https://app.getzep.com"
        )

    client = Zep(api_key=api_key)

    print("\nMakerDAO/Sky Governance — ZEP Temporal Graph RAG")
    print("=" * 55)
    print("Predefined queries (enter number) or type your own.")
    print("Prefix with 'n:' for node search (e.g. 'n:hexonaut').")
    print()
    for i, q in enumerate(PREDEFINED, 1):
        print(f"  {i:2}. {q}")
    print("   q. quit\n")

    while True:
        try:
            raw = input("Query> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if raw.lower() in ("q", "quit", "exit", ""):
            break

        scope = "edges"
        if raw.lower().startswith("n:"):
            scope = "nodes"
            raw = raw[2:].strip()

        if raw.isdigit() and 1 <= int(raw) <= len(PREDEFINED):
            query = PREDEFINED[int(raw) - 1]
            print(f"\nRunning: '{query}'")
        else:
            query = raw

        print(f"Searching ZEP graph (scope={scope})...\n")
        results = search(client, query, scope=scope)
        if not results:
            print("  No results yet — graph may still be processing (allow ~90s after ingest).")
            print("  Try rephrasing or use 'n:' prefix for entity/node search.")
        else:
            fmt = format_node if scope == "nodes" else format_edge
            for i, item in enumerate(results, 1):
                print(fmt(i, item))
        print()


if __name__ == "__main__":
    main()
