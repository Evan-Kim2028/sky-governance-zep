#!/usr/bin/env python3
"""
Interactive ZEP graph RAG query CLI for MakerDAO/Sky governance history.

Usage:
  python query.py

Enter a number to run a predefined query, or type your own free-form question.
ZEP's temporal knowledge graph returns extracted facts with scores and timestamps.
"""

import os

from dotenv import load_dotenv
from zep_cloud import Zep

from governance.ingest import ZEP_USER_ID

load_dotenv()

PREDEFINED = [
    "SKY token migration from MKR community sentiment and timeline",
    "core unit budget disputes and contested governance votes",
    "real world asset RWA vault approvals and collateral onboarding",
    "executive vote results MKR support and spell outcomes",
    "stability fee and risk parameter changes over time",
    "collateral offboarding decisions USDC USDT",
    "delegate voting history and aligned delegate participation",
    "surplus buffer and protocol revenue governance decisions",
]


def search(client: Zep, query: str, limit: int = 5) -> list:
    results = client.graph.search(
        user_id=ZEP_USER_ID,
        query=query,
        limit=limit,
        scope="edges",
    )
    return getattr(results, "edges", None) or (results if isinstance(results, list) else [])


def format_result(i: int, edge) -> str:
    fact = getattr(edge, "fact", str(edge))
    rating = getattr(edge, "fact_rating", "?")
    valid_at = getattr(edge, "valid_at", None)
    ts = f"[{valid_at}] " if valid_at else ""
    return f"  [{i}] {ts}{fact}  (score={rating})"


def main() -> None:
    api_key = os.environ.get("ZEP_API_KEY")
    if not api_key:
        raise RuntimeError("ZEP_API_KEY not set")

    client = Zep(api_key=api_key)

    print("\nMakerDAO/Sky Governance — ZEP Graph RAG")
    print("=" * 55)
    print("Predefined queries (enter number) or type your own:")
    for i, q in enumerate(PREDEFINED, 1):
        print(f"  {i}. {q}")
    print("  q. quit\n")

    while True:
        try:
            raw = input("Query> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if raw.lower() in ("q", "quit", "exit", ""):
            break

        if raw.isdigit() and 1 <= int(raw) <= len(PREDEFINED):
            query = PREDEFINED[int(raw) - 1]
            print(f"Running: '{query}'")
        else:
            query = raw

        print(f"\nSearching ZEP graph...")
        edges = search(client, query)
        if not edges:
            print("  No results — graph may still be processing, or try rephrasing.")
        else:
            for i, edge in enumerate(edges, 1):
                print(format_result(i, edge))
        print()


if __name__ == "__main__":
    main()
