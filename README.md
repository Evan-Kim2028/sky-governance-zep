# sky-governance-zep

A temporal knowledge graph over MakerDAO/Sky governance history, built on [ZEP Cloud](https://app.getzep.com).

Ingests forum discussions (forum.skyeco.com), governance polls, delegate votes, executive proposals, and user profiles into ZEP's graph memory system. Enables queries like:

- *"Who are the most active governance delegates and what do they believe?"*
- *"What was the community sentiment around the SKY token migration?"*
- *"How have delegate voting patterns changed over time?"*

---

## Requirements

- Python 3.11+
- A ZEP Cloud account — [sign up at app.getzep.com](https://app.getzep.com)
  - Free tier: ~200 credits (enough for small exploratory ingests)
  - Flex plan ($25/mo): 20,000 credits/month — recommended for the full pipeline

---

## ZEP Features Demonstrated

This repo is a showcase for ZEP Cloud's graph RAG capabilities on a real governance domain.

| ZEP Feature | Where | Why It Matters |
|-------------|-------|----------------|
| **Standalone graph** (`graph_id`) | `governance/ingest.py`, `scripts/setup_graph.py` | Domain knowledge has no "user" — a named standalone graph is the correct abstraction for shared data |
| **Custom extraction instructions** | `governance/instructions.py`, `scripts/setup_graph.py` | Governance terms like "spell", "hat", "Atlas", "Endgame" need domain context to be classified correctly by ZEP's NLP |
| **Temporal fact edges** | All queries in `scripts/query.py` | ZEP automatically extracts time-stamped `(subject, predicate, object)` triples from plain text — no graph logic written by hand |
| **Retrieval tuning** (`limit=20`) | `scripts/query.py` | ZEP's 50-experiment benchmark: `limit=20` hits the accuracy/token sweet spot (~80% accuracy, ~1,400 tokens) vs ~70% at limit=5 |
| **Combined edge + node search** (`b:` prefix) | `scripts/query.py` | Edge search = temporal facts; node search = entity summaries. Combining gives the full picture for "who is X and what do they believe?" |
| **Search filters** (date, edge exclusion) | `scripts/query.py` | `YYYY:` prefix scopes results to a year; structural noise edges (`LOCATED_AT`, `OCCURRED_AT`) excluded by default |
| **Deduplication log** | `governance/ingest.py`, `scripts/run_ingest.py` | Local `.ingest_log.json` prevents double-ingestion when the pipeline runs monthly on overlapping 90-day windows |

---

## Installation

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd sky-governance-zep

# 2. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Create venv and install dependencies
uv venv
uv pip install -e ".[dev]"

# 4. Set up your API key
cp .env.example .env
# Edit .env and replace z_your_api_key_here with your key from:
# https://app.getzep.com → Settings → API Keys

# 5. Create the ZEP graph and apply extraction instructions (run once)
python scripts/setup_graph.py
```

---

## Usage

### Run the full ingestion pipeline

Fetches ~4,000 episodes from forum.skyeco.com and vote.makerdao.com and ingests them into ZEP.

```bash
python scripts/run_ingest.py
```

Covers (last 90 days):
- Per-post forum episodes across all governance categories + General Discussion
- Top-50 user profiles (monthly active posters)
- Delegate votes across 300 polls (~25 delegates × 300 polls)
- Poll summaries and executive vote results

Credit cost: ~4,000 / 20,000 Flex monthly credits.

### One-time historical backfill

Ingests governance-relevant General Discussion topics from all time (pre-90-day window).

```bash
# Dry run first — shows topic list and credit estimate without spending credits
python scripts/backfill_general_discussion.py --dry-run

# Full ingest
python scripts/backfill_general_discussion.py
```

Credit cost: ~1,133 credits (one-time).

### Query the graph

```bash
python scripts/query.py
```

Select a predefined query or type your own. Query prefixes:

| Prefix | Mode | Best for |
|--------|------|----------|
| *(none)* | Edge search | Temporal facts — "what did X say / what happened" |
| `n:` | Node search | Entity summaries — "who is X", "what is Y" |
| `b:` | Combined | Both edges and nodes — "who is X and what do they believe?" |
| `YYYY:` | Year filter | Scoped queries — `2025: delegate votes on Atlas` |

ZEP returns extracted temporal fact edges with scores and timestamps.

---

## Example queries

Once ingested, `query.py` can answer questions like:

```
Who are the most influential aligned delegates and what positions do they hold?
How did Bonapublica vote on WBTC-related executive spells?
What was the community debate around the SKY token migration from MKR?
What is the Atlas and how has the Endgame community structured it over time?
What did Brendan_Navigator say about governance proposals in March 2026?
```

Prefix with `n:` to search entity nodes, or `b:` for combined edge + node results:
```
n:hexonaut
n:BA Labs
b:Brendan_Navigator governance stance
```

---

## Running tests

```bash
uv run pytest tests/ -q
```

78 tests, no network calls (all external APIs are mocked).

---

## Project structure

```
sky-governance-zep/
├── pyproject.toml                 # project config, dependencies, version 0.1.0
├── README.md
├── CLAUDE.md                      # ZEP best practices and project conventions
├── .env.example                   # copy to .env and add ZEP_API_KEY
├── scripts/
│   ├── setup_graph.py             # run once: create standalone graph + custom instructions
│   ├── run_ingest.py              # main pipeline — fetch governance data → ZEP (monthly)
│   ├── backfill_general_discussion.py  # one-time historical backfill
│   └── query.py                   # interactive graph RAG query CLI
├── governance/                    # core library package
│   ├── __init__.py                # package version (0.1.0)
│   ├── fetchers.py                # Discourse + vote.makerdao.com API fetchers
│   ├── episodes.py                # converts raw API data → ZEP episode dicts
│   ├── ingest.py                  # ZEP graph.add wrapper; IngestLog dedup; ZEP_GRAPH_ID
│   └── instructions.py            # governance domain extraction instructions
└── tests/
    ├── conftest.py
    ├── test_fetchers.py           # mocked HTTP fetcher tests
    ├── test_episodes.py           # pure function episode conversion tests
    ├── test_ingest.py             # mocked ZEP client ingest tests
    └── test_setup.py              # setup_graph / custom instructions tests
```

---

## What data is in the graph

### What's covered

| Source | Time range | Episodes | Notes |
|--------|-----------|----------|-------|
| Forum — governance categories | Jan 2026 – Apr 2026 (90-day rolling) | ~950 | Sky Core, Spark Prime, Grove Prime, Keel Prime, Obex Prime, Pattern, Ecosystem Proposals |
| Forum — General Discussion (backfill) | 2022 – Apr 2026 | 1,133 | One-time all-time ingest of governance-relevant topics (≥5 posts, keyword-filtered) |
| Forum — General Discussion (rolling) | Jan 2026 – Apr 2026 (90-day) | ~200/run | Ongoing coverage of new governance-relevant topics |
| User profiles | Snapshot Apr 2026 | 50 | Top-50 monthly active posters; roles, groups, bio, activity stats |
| Delegate votes | May 2025 – Apr 2026 | ~7,500 | 300 most recent polls × ~25 active delegates; per-delegate option + MKR weight |
| Poll summaries | May 2025 – Apr 2026 | 300 | Winning option, total MKR participation, options list |
| Executive votes | 2025 – Apr 2026 | ~100 | Spell titles, pass/fail, MKR in support |

### What's missing

| Gap | Why | Workaround |
|-----|-----|-----------|
| **Governance category posts before Jan 2026** | 90-day lookback window; structured categories (Sky Core, Spark Prime, etc.) have no all-time backfill | Increase `LOOKBACK_DAYS` or run a targeted backfill similar to `backfill_general_discussion.py` |
| **Pre-Sky era MIPs and Signal Requests (2018–2024)** | Old `governance`, `mips`, `risk` categories from MakerDAO era aren't fully present in the Sky forum | These exist historically at forum.makerdao.com — a dedicated backfill would recover them |
| **Delegate votes before May 2025** | `MAX_POLLS=300` fetches only the 300 most recent polls | Increase `MAX_POLLS` to 500–1000 to extend coverage back to 2023–2024 |
| **Inactive/historical contributors** | User profiles only capture top-50 monthly active posters as of the last run | Historical contributors who are no longer active aren't represented as person nodes |
| **Off-forum governance discussions** | Discord, governance calls (Zoom/Meet), Twitter/X debate | Not API-accessible; would require manual or stream ingestion |
| **Real-time updates** | The graph is a point-in-time snapshot from the last `run_ingest.py` execution | Schedule `run_ingest.py` to run monthly to keep the 90-day window current |

---

## Credit budget (Flex plan — 20,000/month)

| Source | Episodes | Credits |
|--------|----------|---------|
| Forum posts (governance cats, 90d) | ~950 | ~950 |
| General Discussion (90d rolling) | ~200 | ~200 |
| User profiles (top 50) | 50 | 50 |
| Delegate votes (300 polls) | ~2,400 | ~2,400 |
| Poll summaries | 300 | 300 |
| Executive votes | ~100 | ~100 |
| **Total per monthly run** | **~4,000** | **~4,000** |
| One-time General Discussion backfill (already done) | 1,133 | 1,133 |

ZEP processes episodes asynchronously. Wait ~90 seconds after ingestion before querying.

> Note: the pipeline uses `.ingest_log.json` (gitignored) to track ingested episodes by `source_description`. Running the pipeline twice in the same month will skip already-ingested episodes — no double-ingestion.

---

## ZEP Cloud

- Dashboard & API keys: [app.getzep.com](https://app.getzep.com)
- Docs: [help.getzep.com](https://help.getzep.com)
- Pricing: Free (200 credits) → Flex ($25/mo, 20k credits) → higher tiers available
