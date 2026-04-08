#!/usr/bin/env python3
"""
One-time (idempotent) setup for the sky-governance ZEP standalone graph.

Run before first ingest:
  python scripts/setup_graph.py

What this does:
  1. Creates the standalone graph 'sky-governance' if it doesn't exist
  2. Applies governance domain extraction instructions (Flex+ plan required to activate)

Safe to run multiple times — graph creation is skipped if already present,
instructions are upserted by name.
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from zep_cloud.client import Zep
from zep_cloud import CustomInstruction

from governance.ingest import ZEP_GRAPH_ID, ensure_graph
from governance.instructions import GOVERNANCE_INSTRUCTIONS

load_dotenv(Path(__file__).parent.parent / ".env")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def setup_instructions(client: Zep, graph_id: str = ZEP_GRAPH_ID) -> None:
    """Apply governance domain extraction instructions to the graph.

    Custom instructions tell ZEP how to interpret domain-specific terminology
    (e.g. 'spell' = executive smart contract, not magic).

    Requires Flex+ plan. On lower plans, the call succeeds but instructions
    are not applied — no error is raised.
    """
    client.graph.add_custom_instructions(
        instructions=[
            CustomInstruction(
                name="sky_governance",
                text=GOVERNANCE_INSTRUCTIONS,
            )
        ],
        graph_ids=[graph_id],
    )
    log.info("Applied custom extraction instructions to graph %s", graph_id)


def main() -> None:
    api_key = os.environ.get("ZEP_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ZEP_API_KEY not set — copy .env.example to .env and add your key from https://app.getzep.com"
        )

    client = Zep(api_key=api_key)

    log.info("Setting up standalone graph '%s'...", ZEP_GRAPH_ID)
    ensure_graph(client)

    log.info("Applying custom extraction instructions...")
    setup_instructions(client)

    log.info("Setup complete. Run scripts/run_ingest.py to populate the graph.")


if __name__ == "__main__":
    main()
