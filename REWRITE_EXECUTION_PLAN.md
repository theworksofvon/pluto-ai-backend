# Pluto AI Backend — Rewrite Execution Plan

Date: 2026-07-03
Inputs: `REWRITE_AUDIT.md`, `AGENT_REWRITE_PLAN.md`, Codex repo reconnaissance (2026-07-03).

## Locked Decisions

- **Repo strategy:** rewrite in this repo. New `app/` package built beside legacy code; legacy deleted at cutover.
- **V1 scope:** NBA **player prop predictions only**. Game-winner predictions deferred.
- **LLM providers:** OpenAI (primary), Anthropic, OpenRouter — all behind one provider port, plus a `FakeProvider` for tests. OpenRouter reuses the OpenAI-compatible adapter with a different base URL.
- **Compatibility:** nothing consumes the current API in production. No shims, no freeze phase. Old code keeps running only until cutover so behavior can be compared.
- **Process:** module-by-module slices. Each slice is one small reviewable diff with its own acceptance criteria and verification. No slice starts until the previous one is reviewed.
- **DB:** SQLite (`sqlite+aiosqlite`) by default for local; Postgres via Docker Compose as optional self-host mode. Alembic owns migrations.
- **Auth:** static admin token for admin routes; public routes unauthenticated locally (configurable off switch). No Supabase JWT, no Resend.

## Execution Model

- Fable (this session): plans, writes each slice contract, reviews every diff, decides accept/redo.
- Codex: implements one slice at a time under a narrow contract (goal / scope / constraints / acceptance / verification / report).
- User: reviews at slice boundaries. Each slice should land as its own commit (or PR) so review is per-module, never one blob.

## Target Architecture

```text
app/
  core/          config, logging, time/clock
  db/            SQLAlchemy models, session, repositories, alembic migrations
  domain/        pure types + prediction/evaluation logic (no I/O)
  adapters/
    nba/         schedule, player/team game log sources (nba_api v3 endpoints)
    props/       PrizePicks / odds line sources
    llm/         OpenAI-compatible, Anthropic, Fake providers
  data/
    ingest/      ingest jobs (raw snapshot -> normalized tables)
    features/    point-in-time feature snapshot builder
  ml/
    baselines/   rolling/season/prop-line baselines
    training/    trainers + time-series backtest harness
    registry/    model version manifests + artifact loading
  workflows/     GeneratePlayerPropPrediction, daily jobs, evaluation
  api/           FastAPI app, routes, dependencies (public + admin)
  worker/        scheduler process running daily jobs
  cli.py         `pluto` admin/ops commands
tests/
```

Ports (interfaces) exist only at real boundaries: NBA data, prop lines, LLM, DB repositories, model registry, clock, job runner.

## Slice Plan

Phases run in order; slices within a phase run in order. Every slice ends with: `ruff check`, `pytest`, and slice-specific verification. Legacy code is untouched until Phase F except for additive `pyproject.toml` changes.

### Phase A — Foundation (core pieces first)

**A1. Skeleton + tooling**
- New `app/` package with empty modules, `tests/` with a passing sanity test.
- Add dev/runtime deps (additive only — legacy keeps working): declare `sqlalchemy`, `alembic`, `aiosqlite`, `httpx`, `pytest`, `pytest-asyncio`, `ruff`, `typer`. Nothing removed yet.
- `Makefile` targets: `make lint`, `make test`, `make api`, `make worker`.
- Acceptance: `pytest` and `ruff check app tests` pass; legacy `main.py` still imports.

**A2. Core config + logging + DB session**
- `app/core/config.py` (pydantic-settings): `DATABASE_URL` default `sqlite+aiosqlite:///./pluto.db`, `ENV`, LLM keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`), `ADMIN_TOKEN`, provider selection. New `.env.example` documenting every var the new app reads.
- `app/core/logging.py`, `app/core/clock.py` (injectable clock port).
- `app/db/session.py` async engine/session factory; Alembic initialized at `app/db/migrations` wired to `DATABASE_URL`.
- Acceptance: `alembic upgrade head` runs clean against SQLite (empty baseline migration).

**A3. Schema v1 (migration only)**
- SQLAlchemy models + one Alembic migration for: `teams`, `players`, `games`, `player_game_logs`, `prop_lines`, `raw_source_snapshots`, `injury_reports`, `feature_snapshots`, `model_versions`, `prompt_versions`, `prediction_runs`, `player_predictions`, `prediction_evaluations`, `job_runs`, `llm_call_logs`, `source_health_checks`.
- Every prediction row stores: context hash, feature version, model version, prompt version, provider/model, raw structured output, final output, confidence, data-quality flags.
- Acceptance: `alembic upgrade head` + `alembic downgrade base` both clean; schema review is the user checkpoint (this defines the system's spine).

**A4. Repositories + unit-of-work**
- Repository layer over the schema with an async unit-of-work; no service logic.
- Repository tests against in-memory/tmpfile SQLite covering CRUD + the queries later slices need (predictions search filters, latest prop line, feature snapshot by as-of).
- Acceptance: repo test suite green.

### Phase B — Data layer (reliability first)

**B1. NBA source adapters**
- Upgrade `nba_api` to latest (≥1.11.x); use `ScoreboardV3`/live endpoints only (no V2).
- `NbaScheduleSource`, `NbaPlayerGameLogSource`, `NbaTeamGameLogSource` behind ports, each returning typed results with `source`, `fetched_at`, `status`, `warnings`.
- Shared reliability wrapper: timeout, retry/backoff, rate limit, structured errors, raw snapshot persistence, health-check probe.
- Unit tests with recorded fixtures; opt-in live smoke tests (`pytest -m live_nba`).
- Acceptance: fixtures tests green; one live smoke run captured as evidence.

**B2. Ingest jobs + CLI**
- `pluto ingest schedule --date`, `pluto ingest player-logs --season`, writing raw snapshots + normalized rows, recording `job_runs` and freshness.
- One-time `pluto seed --from-csv` importer that loads `shared/data/pluto_training_dataset_v1.csv` (49.5k rows) into `player_game_logs` as immutable historical seed. CSVs stop being runtime state.
- Acceptance: fresh SQLite DB → seed + ingest commands produce queryable normalized tables; re-running is idempotent.

**B3. Prop line adapter + ingest**
- `PropLineSource` (PrizePicks first) with the same reliability wrapper; `pluto ingest props`.
- Stale-line handling: last known line servable with `stale=true`.
- Acceptance: fixture tests green; props for a real slate land in `prop_lines` with freshness metadata.

**B4. Feature snapshot builder**
- Port the proven feature logic from `scripts/create_dataset.py` (shifted last-5 rolling PTS/MIN/FGA/FG_PCT, home/away, opponent, rest days, back-to-back) into `app/data/features/`, keyed by `player + game + stat_type + as_of_time`, `feature_version` tagged.
- **Leakage tests are the acceptance gate:** for any as-of time, no same-game or future data appears in features.
- `pluto build-features --as-of YYYY-MM-DD`.

### Phase C — Modeling

**C1. Baselines + backtest harness**
- Baselines: last-5 avg, last-10 avg, season avg, weighted recent, prop-line-as-prediction.
- Time-based backtest (train past → predict future, by date segments) over seeded history; metrics: MAE/RMSE, over/under accuracy vs line, calibration buckets.
- `pluto backtest --stat points` prints a comparison table; results stored.
- Acceptance: backtest runs end-to-end on seed data; baseline numbers documented (they're the bar every later model must beat).

**C2. Trained models + registry**
- Points first: Ridge (interpretable) + HistGradientBoostingRegressor, quantile variants for ranges; time-series CV only.
- Registry at `models/registry/<name>/<version>/` with manifest (features, training window, metrics, created_at); loader validates version.
- Acceptance: trained model beats best baseline on held-out future dates, evidenced by the backtest report; registered version loadable by inference code. Rebounds/assists repeat this slice later.

### Phase D — LLM layer

**D1. Provider adapters**
- `LLMProvider` port: `complete_structured(prompt, schema, model) -> typed result`. Pydantic at the boundary, provider-native structured output (OpenAI/OpenRouter JSON schema mode, Anthropic tool-use).
- `OpenAICompatibleProvider` (OpenAI + OpenRouter via base URL), `AnthropicProvider`, `FakeProvider` (fixture-driven, used by all workflow tests).
- Every call logged to `llm_call_logs` (provider, model, prompt version, tokens, latency, validation outcome). Validation failure → typed failure, never persisted as a prediction.
- Acceptance: adapter unit tests with mocked HTTP green; one recorded real OpenAI structured call.

**D2. Prediction workflow**
- `GeneratePlayerPropPrediction`: load game/player/line → feature snapshot → base model prediction → assemble context (recent form, rest, injury/context if fresh) → LLM agrees-or-adjusts with structured output → guardrails clamp adjustment (max delta, confidence floor on stale data) → persist `prediction_run` storing **both** base and final predictions.
- Data-quality rules: critical staleness → no prediction or low-confidence flag, per audit.
- Acceptance: end-to-end workflow test on fixtures with `FakeProvider`; run persists all versions/metadata; guardrail unit tests green.

### Phase E — API & worker

**E1. Public API**
- `GET /healthz`, `GET /v1/slate/today`, `GET /v1/games/{game_id}`, `GET /v1/games/{game_id}/props`, `GET /v1/predictions` (filters: date, game, player, stat_type, min_confidence), `GET /v1/predictions/{id}`, `POST /v1/predictions/player-prop` (stored-or-generate; `force_refresh` creates a new run, keeps history).
- Typed response models everywhere; `data_freshness`, `model_version`, `prompt_version` in responses. Static routes before dynamic; no GET mutations.
- Acceptance: route tests via `httpx` + dependency overrides; OpenAPI schema reviewed as the frontend contract.

**E2. Admin API + worker process**
- `POST /v1/admin/jobs/{ingest,build-features,generate-predictions,evaluate}` → enqueue job, return `job_id`; `GET /v1/admin/jobs[/{id}]`, `GET /v1/admin/data/freshness`, `GET /v1/admin/data/sources/*/health`. Admin routes behind `ADMIN_TOKEN`.
- `app/worker/` separate process: daily flow (ingest schedule → logs → props → features → predictions) + hourly source health checks. FastAPI startup schedules nothing.
- Acceptance: worker runs the daily flow against SQLite locally; admin job POST → job visible → completes.

**E3. Evaluation loop + analytics**
- Post-game actuals backfill; `prediction_evaluations` scoring line hit, error, over/under correctness; `GET /v1/analytics/summary`, `GET /v1/analytics/model-performance` split **base-model-only vs LLM-adjusted** — the core question the system exists to answer.
- Acceptance: evaluation over seeded/backtested history produces the comparison; API tests green.

### Phase F — Cutover & deletion

**F1. Legacy removal**
- Delete: `agency/`, `agents/`, `agent/`, `ai/`, Supabase adapter + `supabase/`, Twitter/rogue/personality/crypto files + PDFs, `services/`, `routers/`, old `models/` response models no longer referenced, `utils/schema_json_parser.py`, `linear_models/*.pkl`, `scripts/` (superseded), empty NBA/NFL scaffolding, `clients/`, `connections.py`, old `main.py`/`config.py` (new entrypoints take over).
- Prune deps: `supabase`, `resend`, `llama-index*`, `llama-parse`, `datasets`, `requests-oauthlib`, `pipreqs`, `python-jose`, Twitter/grok config vars.
- Move seed CSV to `data/seeds/` (read-only fixture); delete mutable CSV paths.
- Acceptance: `pytest` + `ruff` green, API + worker boot clean, `grep` proves no references to removed modules; final full-repo Codex review + Fable review.

**F2. Packaging & docs**
- `docker-compose.yml`: api + worker + Postgres (optional profile), volume for model registry; README rewrite (local quickstart: `make api`, SQLite default); `.env.example` complete.
- Acceptance: `docker compose up` serves `/v1/slate/today` against Postgres; fresh-clone quickstart works on SQLite.

## Review Gates

Per slice: Codex reports changed files + verification output → Fable inspects the diff (scope, weakened tests, stale paths, duplicate concepts) → user reviews the commit. High-scrutiny checkpoints where user sign-off matters most: **A3 (schema)**, **B4 (leakage tests)**, **D2 (workflow + guardrails)**, **E1 (API contract)**, **F1 (deletion list)**.

## Explicitly Out of Scope for V1

Game-winner predictions, picks-of-the-day/parlay building, chat endpoint (`/prompt-pluto`), email/notifications, Twitter/social anything, NFL, Ollama/Vercel providers (port makes them easy later), frontend monorepo restructure.
