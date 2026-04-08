# sky-governance-zep — Claude Code Instructions

## CI (mandatory)

Run tests before every commit: `uv run pytest tests/ -q` (78+ tests, all mocked, no network).
All tests must pass. Never skip hooks.

---

## ZEP Cloud Best Practices

### Graph identity — standalone graphs, not user graphs

Domain knowledge (governance data with no human "user") belongs in a **standalone graph**, not a user graph.

```python
# CORRECT — standalone graph for domain knowledge
ZEP_GRAPH_ID = "sky-governance"
client.graph.add(graph_id=ZEP_GRAPH_ID, data=..., ...)
client.graph.search(graph_id=ZEP_GRAPH_ID, query=..., ...)

# WRONG — user graph is for personal/conversational context
client.graph.add(user_id="some-user", data=..., ...)
```

Create the standalone graph once (idempotent): `python scripts/setup_graph.py`

### Episode design — one episode per atomic unit

Ingest one episode per **post** (not per topic/thread). Per-post episodes give ZEP person-attributed, timestamped statements it can extract into temporal fact edges.

- Minimum content: 80 chars (enforced in `episodes.py`)
- Always set `created_at` as ISO 8601 (e.g. `"2026-01-15T10:30:00Z"`) so ZEP places facts correctly in time
- 1 episode ≈ 1 ZEP credit

### Retrieval — limit and scope

ZEP's 50-experiment benchmark shows `limit=20` is the sweet spot (~80% accuracy, 1,378 tokens). Default is 10; max is 50.

```python
# Edge search: temporal facts — use for "what happened / what did X say"
client.graph.search(graph_id=..., query=..., scope="edges", limit=20)

# Node search: entity summaries — use for "who/what is X"
client.graph.search(graph_id=..., query=..., scope="nodes", limit=20)

# Combined: search both for rich entity + fact queries
```

### Search filters — cut noise, scope by time

```python
from zep_cloud.types import SearchFilters
from zep_cloud.types.date_filter import DateFilter

# Exclude structural noise edges
filters = SearchFilters(exclude_edge_types=["LOCATED_AT", "OCCURRED_AT"])

# Scope to a specific year (valid_at uses List[List[DateFilter]])
year = 2025
year_filter = [[
    DateFilter(comparison_operator=">=", date=f"{year}-01-01T00:00:00Z"),
    DateFilter(comparison_operator="<=", date=f"{year}-12-31T23:59:59Z"),
]]
filters = SearchFilters(valid_at=year_filter)

client.graph.search(graph_id=..., query=..., search_filters=filters)
```

### Custom extraction instructions — governance domain

Without instructions, ZEP's NLP misclassifies governance terms:

| Term | Default misread | Actual meaning |
|------|----------------|----------------|
| `spell` | magic | an executive smart contract |
| `hat` | clothing | the governance-approved executive vote |
| `Atlas` | mythology | Sky's foundational governance framework |
| `Endgame` | video game | MakerDAO protocol restructuring plan |
| `Core Unit` | unknown | DAO organizational/service unit |
| `MIP` | unknown | Maker Improvement Proposal |

Instructions live in `governance/instructions.py` and are applied at `scripts/setup_graph.py`.
**Requires Flex+ plan** to activate — code is always present, ZEP silently ignores on lower plans.

```python
from zep_cloud import CustomInstruction
client.graph.add_custom_instructions(
    instructions=[CustomInstruction(name="sky_governance", text=GOVERNANCE_INSTRUCTIONS)],
    graph_ids=[ZEP_GRAPH_ID],
)
```

### Deduplication — prevent double-ingest

Running the pipeline twice on the same 90-day window doubles episode count. Track ingested episodes in `.ingest_log.json` (gitignored):

```json
{"forum-post-12345": "2026-04-07T10:00:00Z", "vote-poll-300": "2026-04-07T10:05:00Z"}
```

### SDK import patterns

```python
from zep_cloud.client import Zep                    # main client
from zep_cloud.core.api_error import ApiError       # error handling
from zep_cloud.types import SearchFilters           # search filters
from zep_cloud import CustomInstruction             # extraction instructions
```

`ApiError` constructor: `ApiError(status_code=404, body="not found")` — no `headers` param (removed in v2.22.1).

### load_dotenv in scripts/

Scripts in `scripts/` must use an explicit path:

```python
load_dotenv(Path(__file__).parent.parent / ".env")
```

---

## Project structure

```
governance/           # library (importable)
  __init__.py         # version
  episodes.py         # raw API data → ZEP episode dicts
  fetchers.py         # Discourse + vote.makerdao.com API fetchers
  ingest.py           # ZEP graph.add wrapper; ZEP_GRAPH_ID constant
  instructions.py     # governance domain extraction instructions text

scripts/              # runnable entry points
  setup_graph.py      # create standalone graph + add custom instructions (run once)
  run_ingest.py       # full pipeline: fetch → ingest (monthly)
  backfill_general_discussion.py  # one-time historical backfill
  query.py            # interactive CLI for querying the graph

tests/                # pure unit tests, all mocked
```
