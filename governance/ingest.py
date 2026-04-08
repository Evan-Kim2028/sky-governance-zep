# governance/ingest.py
import logging

from zep_cloud.client import Zep
from zep_cloud.core.api_error import ApiError

log = logging.getLogger(__name__)

ZEP_GRAPH_ID = "sky-governance"


def ensure_graph(client: Zep, graph_id: str = ZEP_GRAPH_ID) -> None:
    """Create standalone ZEP graph if not already present.

    Standalone graphs (graph_id) are ZEP's pattern for domain knowledge that
    isn't tied to a specific user. Governance data has no "user" — it belongs
    to a named graph that any query can access.
    """
    try:
        client.graph.get(graph_id=graph_id)
        log.info("Graph %s already exists", graph_id)
    except ApiError:
        client.graph.create(
            graph_id=graph_id,
            name="Sky/MakerDAO Governance",
            description=(
                "Temporal knowledge graph of MakerDAO/Sky governance history. "
                "Sources: forum.skyeco.com, vote.makerdao.com. "
                "Data: forum posts, delegate votes, poll summaries, executive votes, user profiles."
            ),
        )
        log.info("Created standalone graph %s", graph_id)


def ingest_episodes(client: Zep, episodes: list[dict | None], graph_id: str = ZEP_GRAPH_ID) -> int:
    """Send valid episodes to ZEP graph. Returns count of episodes ingested.

    Stops early and logs a warning if the free-tier monthly credit limit is reached.
    """
    count = 0
    for ep in episodes:
        if not ep or not ep.get("data"):
            continue
        created_at = ep.get("created_at") or None  # coerce empty string → None
        try:
            client.graph.add(
                graph_id=graph_id,
                data=ep["data"],
                type=ep.get("type", "text"),
                source_description=ep.get("source_description", "governance"),
                created_at=created_at,
            )
        except ApiError as e:
            if e.status_code == 403 and "usage limit" in str(e.body or "").lower():
                log.warning("Monthly credit limit reached — stopping ingest. Upgrade plan or wait for reset.")
                break
            if e.status_code == 400:
                log.warning(
                    "Skipping episode (400 bad request) source=%s: %s",
                    ep.get("source_description", "?"),
                    str(e.body or e)[:120],
                )
                continue
            raise
        count += 1
    return count


def estimate_credits(episodes: list[dict | None]) -> int:
    """Count valid episodes — each costs 1 ZEP credit."""
    return sum(1 for ep in episodes if ep and ep.get("data"))
