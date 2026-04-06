# SKZ Database

A comprehensive Stray Kids discography database with a REST API. Covers studio albums, EPs, singles, digital releases, SKZ-RECORD, SKZ-PLAYER, unreleased songs, song credits, and chart data.

Data is scraped from Wikipedia, the Stray Kids Fandom Wiki, and Spotify.

---

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI |
| ORM | SQLAlchemy (async) |
| Database | PostgreSQL 16 |
| Migrations | Alembic |
| Package manager | Poetry |
| Infrastructure | Docker + Docker Compose |

---

## Project Structure

```
skz-database/
├── app/
│   ├── models/          # SQLAlchemy ORM models
│   ├── schemas/         # Pydantic response schemas
│   ├── routers/         # FastAPI route handlers
│   ├── repositories/    # SQLAlchemy query logic (one class per model group)
│   ├── constants.py     # Shared enum literals (ReleaseType, CreditRole, etc.)
│   ├── config.py        # Pydantic Settings (reads .env)
│   ├── database.py      # Async engine + session factory
│   └── main.py          # FastAPI app + router registration
├── scrapers/
│   ├── run_all.py       # Orchestrator: runs all phases in order
│   ├── config.py        # GroupConfig dataclass + per-group instances (SKZ_CONFIG, etc.)
│   ├── utils.py         # Shared text cleaning, title normalisation, DB lookup helpers
│   └── *.py             # Individual phase scrapers (Wikipedia, Fandom, Spotify, YouTube)
├── alembic/
│   └── versions/        # Migration history
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

---

## Data Model

### Artists
Stray Kids (group), sub-units, and members seeded via Alembic — see [`alembic/versions/b6a411184eed_seed_artists.py`](alembic/versions/b6a411184eed_seed_artists.py) for the full list. Artist hierarchy is stored in a self-referential `artist_members` join table.

### Releases
Every official release — studio albums, EPs, single albums, digital singles, repackages, mixtapes, and features. For the full list of valid `release_type` values see `ReleaseType` in [`app/constants.py`](app/constants.py). SKZ-RECORD and SKZ-PLAYER are stored as `digital_single` with a `release_subtype` of `"skz_record"` / `"skz_player"` respectively.

### Songs
Canonical songs with optional version linking. A song that is a Korean, English, Hip, or Festival version of another song has `parent_song_id` set to the canonical song's ID and a `version_label` (e.g. `"Korean"`, `"English"`).

### Tracks
A `Track` is the join between a `Song` and a `Release` — one song can appear on multiple releases (e.g. on both a single and the album it's included on).

### Credits
`song_credits` stores lyricist, composer, and arranger credits per song. Each credit links to either an `Artist` row (for Stray Kids members and units) or a `Collaborator` row (for external contributors like Versachoi, HotSauce, DJ Snake, etc.).

### Collaborators
External contributors not in the Stray Kids artist roster. Queryable via `/collaborators/{id}/releases`.

### Charts
`chart_entries` stores peak chart positions per release, scraped from Wikipedia. `release_sales` stores sales/certification data.

---

## Setup

### Prerequisites
- Docker Desktop
- Poetry (`brew install poetry`)
- Spotify Developer credentials (Client ID + Secret) — [create a free app](https://developer.spotify.com/dashboard)

### 1. Clone and install dependencies

```bash
git clone <repo>
cd skz-database
poetry install
```

### 2. Configure environment

Create a `.env` file:

```env
POSTGRES_USER=skz_user
POSTGRES_PASSWORD=skz_password
POSTGRES_DB=skz_db
DATABASE_URL=postgresql://skz_user:skz_password@db:5432/skz_db
LOCAL_DATABASE_URL=postgresql://skz_user:skz_password@localhost:5433/skz_db
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
```

> `LOCAL_DATABASE_URL` uses port `5433` because port `5432` is reserved for a native PostgreSQL installation on this machine.

### 3. Start the database and run migrations

```bash
docker compose up -d db
poetry run alembic upgrade head
```

### 4. Scrape data

```bash
poetry run python -m scrapers.run_all
```

This runs all phases in order. Phases 1–4 are idempotent — re-running skips already-present data. Phase 5 (Spotify) can be re-run after a rate limit clears and will pick up where it left off.

### 5. Start the API

```bash
docker compose up -d --build api
```

API available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## Scraper Pipeline

| Phase | `--phases` name | Source | What it populates |
|---|---|---|---|
| 1 | `wikipedia` | Wikipedia discography page | `releases`, `chart_entries` |
| 2 | `wikipedia-songs` | Wikipedia songs list | `songs`, `tracks`, `song_credits` |
| 2.5 | `reconcile` | *(reconciliation)* | Links `digital_single` releases to their songs; fixes stray quote characters in titles |
| 2.6 | `wikipedia-articles` | Wikipedia individual song articles | Version songs (English, Korean, Japanese vers.) + missing releases |
| 3 | `fandom` | Stray Kids Fandom Wiki | SKZ-RECORD + SKZ-PLAYER releases/songs, unreleased songs |
| 3.5 | `dedup-releases` | *(deduplication)* | Merges duplicate release rows created by overlapping Wikipedia + Fandom data |
| 4 | `dedup-songs` | *(deduplication)* | Merges case-insensitive duplicate songs created by overlapping Wikipedia + Fandom data |
| 5 | `spotify` | Spotify Web API | `spotify_id`, `isrc`, `duration_seconds` on songs; `spotify_id` on releases; creates missing songs from album tracklists; API responses cached to `data/spotify_cache/` |
| 6 | `youtube` | YouTube Data API | `youtube_url` (official MV links) on songs |

Phases run in dependency order regardless of the order `--phases` arguments are given.

The `--group` flag selects which group's config to use (default: `skz`). Adding a new group requires only a new entry in `scrapers/config.py` — no changes to `run_all.py` or any scraper.

```bash
poetry run python -m scrapers.run_all --group skz
```

---

## API Endpoints

> The interactive docs at `http://localhost:8000/docs` are always authoritative. The tables below are a high-level overview and may not reflect every endpoint.

All endpoints are under `/v1`. All list endpoints return a paginated envelope:

```json
{
  "total": 169,
  "skip": 0,
  "limit": 50,
  "has_more": true,
  "items": [...]
}
```

### Artists
| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/artists` | List all artists — filter by `artist_type[]` |
| `GET` | `/v1/artists/{id}` | Artist detail with members — `?include_former=true` |
| `GET` | `/v1/artists/{id}/releases` | All releases for an artist — filter by `release_type[]`, `role[]` |
| `GET` | `/v1/artists/{id}/credits` | All songs this artist has a writing/production credit on |
| `GET` | `/v1/artists/{id}/collaborators` | Ranked list of most frequent co-credits |

### Releases
| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/releases` | List releases — filter by `release_type[]`, `market[]` |
| `GET` | `/v1/releases/{id}` | Release detail |
| `GET` | `/v1/releases/{id}/tracks` | Full tracklist with credits |
| `GET` | `/v1/releases/{id}/tracks/summary` | Tracklist with title and track number only |

### Songs
| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/songs` | List songs — filter by `status`, `?versions=true` to include version songs |
| `GET` | `/v1/songs/search?q=` | Search by title (English, Korean, romanized, Japanese) |
| `GET` | `/v1/songs/{id}` | Song detail with credits and versions |
| `GET` | `/v1/songs/{id}/versions` | All alternate versions of a song |

### Charts
| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/charts` | Peak chart positions per release |
| `GET` | `/v1/charts/sales` | Sales and certification data |

### Collaborators
| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/collaborators` | List all external collaborators — `?q=` name search |
| `GET` | `/v1/collaborators/{id}` | Collaborator detail with role breakdown |
| `GET` | `/v1/collaborators/{id}/releases` | All releases a collaborator is credited on |

### Health
| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Returns `{"status": "ok"}` or `503` if the DB is unreachable |

---

## Development

### Reset and rescrape from scratch

```bash
docker compose down -v
docker compose up -d db
poetry run alembic upgrade head
poetry run python -m scrapers.run_all
```

### Rebuild the API after code changes

```bash
docker compose up -d --build api
```

> Note: `docker compose up -d --build api` does **not** run migrations. Migrations must be applied separately from the host with `poetry run alembic upgrade head` (see below).

### Alembic migrations

```bash
# Apply all pending migrations (run this after pulling new changes or adding models)
poetry run alembic upgrade head

# Check current migration state
poetry run alembic current

# Generate a new migration after changing a model
poetry run alembic revision --autogenerate -m "describe_the_change"

# Roll back one migration
poetry run alembic downgrade -1
```

Migrations run against `LOCAL_DATABASE_URL` (`localhost:5433`) when run from the host. The API container itself never runs migrations automatically.

### Run individual phases

```bash
# Single phase
poetry run python -m scrapers.run_all --phases youtube

# Custom pipeline
poetry run python -m scrapers.run_all --phases fandom dedup-releases dedup-songs

# Spotify only (after rate limit clears)
poetry run python -m scrapers.run_all --phases spotify

# Spotify — bypass disk cache to force fresh API responses
poetry run python -m scrapers.run_all --phases spotify --no-cache

# Target a specific group (default: skz)
poetry run python -m scrapers.run_all --group skz --phases spotify
```

All phases are idempotent — already-present data is skipped automatically.
