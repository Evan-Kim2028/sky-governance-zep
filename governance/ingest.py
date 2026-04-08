# governance/ingest.py
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from zep_cloud.client import Zep
from zep_cloud.core.api_error import ApiError

log = logging.getLogger(__name__)

ZEP_GRAPH_ID = "sky-governance"


class IngestLog:
    """Local deduplication log — tracks ingested source_descriptions to prevent double-ingest.

    Stored as JSON at the given path (default: project root .ingest_log.json).
    The file is gitignored — it's local pipeline state, not source code.

    Usage:
        log = IngestLog()
        if not log.seen(ep["source_description"]):
            # ingest ep
            log.mark(ep["source_description"])
        log.save()
    """

    def __init__(self, path: Path = Path(".ingest_log.json")) -> None:
        self._path = path
        self._data: dict[str, str] = {}
        if path.exists():
            try:
                self._data = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def seen(self, key: str) -> bool:
        return key in self._data

    def mark(self, key: str) -> None:
        self._data[key] = datetime.now(timezone.utc).isoformat()

    def save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2))

    def __len__(self) -> int:
        return len(self._data)


def ensure_graph(client: Zep, graph_id: str = ZEP_GRAPH_ID) -> None:
    """Create standalone ZEP graph if not already present.

    Standalone graphs (graph_id) are ZEP's pattern for domain knowledge that
    isn't tied to a specific user. Governance data has no "user" — it belongs
    to a named graph that any query can access.
    """
    try:
        client.graph.get(graph_id=graph_id)
        log.info("Graph %s already exists", graph_id)
    except ApiError as e:
        if e.status_code != 404:
            raise
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


def ingest_episodes(
    client: Zep,
    episodes: list[dict | None],
    graph_id: str = ZEP_GRAPH_ID,
    ingest_log: "IngestLog | None" = None,
) -> int:
    """Send valid episodes to ZEP graph. Returns count of episodes ingested.

    If ingest_log is provided, episodes whose source_description is already in
    the log are skipped (deduplication). The caller is responsible for calling
    ingest_log.save() after all batches are complete.

    Stops early and logs a warning if the free-tier monthly credit limit is reached.
    """
    count = 0
    for ep in episodes:
        if not ep or not ep.get("data"):
            continue
        source = ep.get("source_description", "governance")
        if ingest_log is not None and ingest_log.seen(source):
            continue
        created_at = ep.get("created_at") or None  # coerce empty string → None
        try:
            client.graph.add(
                graph_id=graph_id,
                data=ep["data"],
                type=ep.get("type", "text"),
                source_description=source,
                created_at=created_at,
            )
        except ApiError as e:
            if e.status_code == 403 and "usage limit" in str(e.body or "").lower():
                log.warning("Monthly credit limit reached — stopping ingest. Upgrade plan or wait for reset.")
                break
            if e.status_code == 400:
                log.warning(
                    "Skipping episode (400 bad request) source=%s: %s",
                    source,
                    str(e.body or e)[:120],
                )
                continue
            raise
        if ingest_log is not None:
            ingest_log.mark(source)
        count += 1
    return count


def estimate_credits(episodes: list[dict | None]) -> int:
    """Count valid episodes — each costs 1 ZEP credit."""
    return sum(1 for ep in episodes if ep and ep.get("data"))
