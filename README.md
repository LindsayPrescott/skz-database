# SKZ Database

A comprehensive Stray Kids discography database with a REST API. Covers studio albums, EPs, singles, digital releases, SKZ-RECORD, SKZ-PLAYER, unreleased songs, song credits, and chart data.

Data is scraped from Wikipedia, the Stray Kids Fandom Wiki, and Spotify.

---

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI |
| ORM | SQLAlchemy (sync) |
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
│   ├── config.py        # Pydantic Settings (reads .env)
│   ├── database.py      # Engine + session factory
│   └── main.py          # FastAPI app + router registration
├── scrapers/
│   ├── run_all.py       # Orchestrator: runs all phases in order
│   └── *.py             # Individual phase scrapers (Wikipedia, Fandom, Spotify)
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
Every official release — studio albums, EPs, single albums, digital singles, repackages, mixtapes, SKZ-RECORD episodes, SKZ-PLAYER episodes, and features. For the full list of valid `release_type` values see the `ReleaseType` literal in [`app/routers/releases.py`](app/routers/releases.py).

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

| Phase | Source | What it populates |
|---|---|---|
| 1 | Wikipedia discography page | `releases`, `chart_entries` |
| 2 | Wikipedia songs list | `songs`, `tracks`, `song_credits` |
| 2.5 | *(reconciliation)* | Links `digital_single` releases to their songs; fixes stray quote characters in titles |
| 3 | Stray Kids Fandom Wiki | SKZ-RECORD + SKZ-PLAYER releases/songs, unreleased songs |
| 4 | *(deduplication)* | Merges case-insensitive duplicate songs created by overlapping Wikipedia + Fandom data |
| 5 | Spotify Web API | `spotify_id`, `isrc`, `duration_seconds` on songs; creates missing songs from album tracklists |

---

## API Endpoints

> The interactive docs at `http://localhost:8000/docs` are always authoritative. The tables below are a high-level overview and may not reflect every endpoint.

All list endpoints return a paginated envelope:

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
| `GET` | `/artists` | List all artists |
| `GET` | `/artists/{id}` | Artist detail with members |
| `GET` | `/artists/{id}/releases` | All releases for an artist |

### Releases
| Method | Path | Description |
|---|---|---|
| `GET` | `/releases` | List releases — filter by `release_type[]`, `market[]` |
| `GET` | `/releases/{id}` | Release detail — optional `?tracks=summary\|full` |
| `GET` | `/releases/{id}/tracks` | Full tracklist for a release |

**`?tracks` values on `/releases/{id}`:**
- `summary` — adds `{track_number, disc_number, is_title_track, version_note, song: {id, title, duration_seconds}}`
- `full` — adds all track flags + complete nested song (all fields including credits)

### Songs
| Method | Path | Description |
|---|---|---|
| `GET` | `/songs` | List songs — filter by `status`, `?versions=true` to include version songs |
| `GET` | `/songs/search?q=` | Search by title (English, Korean, romanized) |
| `GET` | `/songs/{id}` | Song detail with credits and versions |
| `GET` | `/songs/{id}/versions` | All alternate versions of a song |

### Collaborators
| Method | Path | Description |
|---|---|---|
| `GET` | `/collaborators` | List all external collaborators |
| `GET` | `/collaborators/{id}` | Collaborator detail |
| `GET` | `/collaborators/{id}/releases` | All releases a collaborator is credited on |

### Tracks
| Method | Path | Description |
|---|---|---|
| `GET` | `/tracks/{id}` | Single track detail |

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

### Run only Spotify enrichment (after rate limit clears)

```bash
poetry run python -m scrapers.run_all
```

Phases 1–4 are idempotent and will skip existing data automatically.
