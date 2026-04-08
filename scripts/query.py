#!/usr/bin/env python3
"""
Interactive ZEP graph RAG query CLI for MakerDAO/Sky governance history.

Usage:
  python scripts/query.py

Query prefixes:
  (none)   Search temporal fact edges — "what did X say / what happened"
  n:       Search entity nodes — "who/what is X"
  b:       Search both edges and nodes — best for rich entity questions
  YYYY:    Scope to a year, e.g. "2025: delegate votes on Atlas"

ZEP returns extracted temporal fact edges with scores and timestamps.

Retrieval is tuned to limit=20, which ZEP's 50-experiment benchmark identifies
as the sweet spot (~80% accuracy, ~1,400 tokens) vs the default of 10.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from zep_cloud.client import Zep
from zep_cloud.types import SearchFilters
from zep_cloud.types.date_filter import DateFilter

from governance.ingest import ZEP_GRAPH_ID

load_dotenv(Path(__file__).parent.parent / ".env")

# Retrieval limit: ZEP benchmark shows limit=20 is the sweet spot.
# Accuracy: 5→20 = +10.4pp; 20→30 = +0.3pp (diminishing returns).
# Ref: https://blog.getzep.com/the-retrieval-tradeoff-what-50-experiments-taught-us
DEFAULT_LIMIT = 20

# Structural edge types that add noise to governance queries.
NOISE_EDGE_TYPES = ["LOCATED_AT", "OCCURRED_AT"]

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


def _parse_date_filter(raw: str) -> tuple[str, SearchFilters | None, int | None]:
    """Parse 'YYYY:query text' syntax into (query, SearchFilters | None, year | None).

    Examples:
      '2025:delegate votes on Atlas' -> ('delegate votes on Atlas', SearchFilters(...), 2025)
      'what did hexonaut say' -> ('what did hexonaut say', None, None)
    """
    if len(raw) >= 5 and raw[:4].isdigit() and raw[4] == ":":
        year = int(raw[:4])
        query = raw[5:].strip()
        year_filter = [[
            DateFilter(comparison_operator=">=", date=f"{year}-01-01T00:00:00Z"),
            DateFilter(comparison_operator="<=", date=f"{year}-12-31T23:59:59Z"),
        ]]
        filters = SearchFilters(valid_at=year_filter)
        return query, filters, year
    return raw, None, None


def search_edges(client: Zep, query: str, limit: int = DEFAULT_LIMIT,
                 search_filters: SearchFilters | None = None) -> list:
    """Search temporal fact edges. Returns facts ZEP extracted from ingested episodes."""
    if search_filters is not None:
        filters = SearchFilters(
            exclude_edge_types=NOISE_EDGE_TYPES,
            valid_at=getattr(search_filters, "valid_at", None),
        )
    else:
        filters = SearchFilters(exclude_edge_types=NOISE_EDGE_TYPES)

    results = client.graph.search(
        graph_id=ZEP_GRAPH_ID,
        query=query,
        limit=limit,
        scope="edges",
        search_filters=filters,
    )
    return getattr(results, "edges", None) or (results if isinstance(results, list) else [])


def search_nodes(client: Zep, query: str, limit: int = DEFAULT_LIMIT,
                 search_filters: SearchFilters | None = None) -> list:
    """Search entity nodes (summaries). Returns people, protocols, proposals."""
    results = client.graph.search(
        graph_id=ZEP_GRAPH_ID,
        query=query,
        limit=limit,
        scope="nodes",
        search_filters=search_filters,
    )
    return getattr(results, "nodes", None) or (results if isinstance(results, list) else [])


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
    print("Prefixes:  n: = node search   b: = both   YYYY: = year filter")
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

        # Parse scope prefix
        mode = "edges"
        if raw.lower().startswith("n:"):
            mode = "nodes"
            raw = raw[2:].strip()
        elif raw.lower().startswith("b:"):
            mode = "both"
            raw = raw[2:].strip()

        # Resolve predefined query number
        if raw.isdigit() and 1 <= int(raw) <= len(PREDEFINED):
            query = PREDEFINED[int(raw) - 1]
            print(f"\nRunning: '{query}'")
        else:
            query = raw

        # Parse year filter
        query, date_filter, parsed_year = _parse_date_filter(query)

        year_label = f", year={parsed_year}" if parsed_year else ""
        print(f"Searching ZEP graph (scope={mode}, limit={DEFAULT_LIMIT}{year_label})...\n")

        if mode == "nodes":
            results = search_nodes(client, query, search_filters=date_filter)
            _print_results(results, format_node)
        elif mode == "both":
            edges = search_edges(client, query, search_filters=date_filter)
            nodes = search_nodes(client, query, search_filters=date_filter)
            if edges or nodes:
                if nodes:
                    print("  — Entities —")
                    for i, item in enumerate(nodes, 1):
                        print(format_node(i, item))
                    print()
                if edges:
                    print("  — Facts —")
                    for i, item in enumerate(edges, 1):
                        print(format_edge(i, item))
            else:
                _no_results()
        else:
            results = search_edges(client, query, search_filters=date_filter)
            _print_results(results, format_edge)

        print()


def _print_results(results: list, fmt) -> None:
    if not results:
        _no_results()
    else:
        for i, item in enumerate(results, 1):
            print(fmt(i, item))


def _no_results() -> None:
    print("  No results — graph may still be processing (allow ~90s after ingest).")
    print("  Try: rephrasing, 'n:' for entity search, or 'b:' for combined search.")


if __name__ == "__main__":
    main()
