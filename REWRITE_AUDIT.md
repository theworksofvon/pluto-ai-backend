# Pluto AI Backend Rewrite Audit

Date: 2026-06-29

## Executive Summary

This repository should be treated as a full rewrite, not a modernization pass. The current service mixes HTTP serving, scheduled jobs, agent orchestration, model calls, data collection, prediction storage, notifications, and social posting into one FastAPI process. The old custom `agency/` framework and personality-based agents should be removed. The useful parts are the domain intent, some route shapes, some SQLAlchemy repository ideas, and portions of the feature engineering logic.

The new system should be a local/self-hostable prediction platform:

- FastAPI API for synchronous user requests.
- Local database via SQLite for simple local mode and Postgres for self-hosted production.
- Background worker/scheduler as a separate process.
- Provider adapters for OpenAI, Anthropic, Vercel AI Gateway, and local Ollama only where needed.
- Structured agentic workflow implemented as normal application services, not custom agent personas.
- Rebuilt data pipeline with versioned datasets, feature snapshots, model registry, and evaluation tables.
- Modern predictive models trained and evaluated independently from LLM analysis.

## Major Rewrite Targets

### 1. Remove the Custom Agent Library

Delete or replace:

- `agency/`
- `agents/helpers/personalities.py`
- `shared/personality.py`
- `shared/crypto_tweets.py`
- `shared/*.pdf` personality/conversation assets
- `agency/tools/default_tools/twitter/`
- `agency/tools/default_tools/web_search/`
- `agency/retrievers/`

Problems:

- `agency/agent.py` models agents as personalities with tendencies. That is no longer the right primitive.
- `agency/communication.py` ignores agent-specific OpenAI model names and always uses `gpt-4o-mini`.
- OpenAI calls are synchronous inside async code.
- History is in memory and unbounded by task semantics.
- Structured output is handled with prompt text and a custom parser instead of provider-native schemas.
- The reasoner chooses a single tool by asking an LLM to emit JSON, but it does not execute a real workflow graph.
- Tool ownership and agent ownership are blurred.
- There are placeholder crypto/token methods unrelated to NBA predictions.

Replacement:

- Create `app/llm/providers/` with explicit provider adapters:
  - `OpenAIProvider`
  - `AnthropicProvider`
  - `VercelProvider`
  - `OllamaProvider`
- Create `app/workflows/prediction_workflow.py`:
  - collect context
  - run statistical model
  - run optional research step
  - run analyst step with structured output
  - run verifier/critic step only when uncertainty or disagreement is high
  - persist prediction, evidence, model version, and prompt version
- Use Pydantic models as the boundary for all model outputs.

### 2. Replace Personality Prompts With Task Workflows

Current files:

- `agents/player_prediction_agent.py`
- `agents/game_prediction_agent.py`
- `agents/analyze_agent.py`
- `agents/twitter_agent.py`
- `agents/rogue_agent.py`

Problems:

- Prompts ask for chain-of-thought style reasoning.
- Prompts require web search inside the LLM instead of separating retrieval from analysis.
- Game prompt has malformed JSON schema text.
- Prediction logic, scheduling, persistence, provider selection, and prompt construction live in the same class.
- `AnalyzeAgent` is a static second-opinion agent instead of a conditional verification step.
- Twitter/rogue agents are product-noise for the prediction backend.

Replacement mindset:

- One orchestrator workflow can spawn specialized subtasks:
  - `DataCollector`: gather NBA logs, schedule, roster, injuries, odds/lines if configured.
  - `FeatureBuilder`: generate versioned feature snapshots.
  - `StatModel`: produce calibrated baseline predictions.
  - `Researcher`: fetch and summarize current news/injury context from configured local or provider-backed sources.
  - `Analyst`: combine statistical baseline and context into a structured prediction.
  - `Verifier`: challenge only high-impact or low-confidence predictions.
  - `Evaluator`: backfill actuals and score predictions after games.
- These should be plain services/functions with typed inputs and outputs. No agent personality objects.

### 3. Remove Supabase and External Hosted Infrastructure Assumptions

Current Supabase dependencies:

- `connections.py`
- `adapters/supabase/supabase.py`
- `services/player_prediction.py`
- `services/eval_service.py`
- `services/game_service.py`
- `services/player_service.py`
- `services/user_service.py`
- `adapters/auth/auth.py`
- `supabase/migrations/`

Problems:

- Startup always creates a Supabase client.
- Some services use SQLAlchemy repositories, others bypass them and call Supabase directly.
- Auth validates Supabase JWTs.
- Notifications depend on Resend.
- Migrations are Supabase SQL instead of the app's actual Alembic source of truth.

Replacement:

- Local/self-hosted DB:
  - SQLite for local development.
  - Postgres in Docker Compose for production-like self-hosting.
- Alembic owns migrations.
- SQLAlchemy repositories own persistence.
- Local auth options:
  - static admin token for local use,
  - self-hosted JWT signing key,
  - optional disabled auth mode for private local deployments.
- Remove Resend. If notifications are needed, use local webhook hooks or self-hosted SMTP as optional adapters.

### 4. Rebuild the Data Pipeline

Current files:

- `services/data_pipeline.py`
- `scripts/create_dataset.py`
- `scripts/create_team_dataset.py`
- `shared/data/pluto_training_dataset_v1.csv`
- `shared/data/team_predictions_enhanced.csv`
- `shared/data/vegas_odds.csv`

Problems:

- CSV files are treated as mutable application state.
- Data freshness is implicit.
- Feature definitions are embedded in scripts and services.
- NBA API calls are synchronous in async flows.
- Game odds and injury data are placeholders in important paths.
- There is no data versioning, feature store concept, or reproducible dataset manifest.
- Dataset paths and model paths are hardcoded.

Replacement:

- Store raw ingested data in local DB tables:
  - teams
  - players
  - games
  - player_game_logs
  - team_game_logs
  - injuries
  - odds_snapshots
  - prizepicks_lines
- Store derived data separately:
  - feature_snapshots
  - player_features
  - team_features
  - prediction_contexts
- Add an ingest CLI:
  - `pluto ingest nba --season 2025-26`
  - `pluto ingest odds --date today`
  - `pluto build-features --as-of YYYY-MM-DD`
- Include metadata:
  - source
  - fetched_at
  - source_version
  - season
  - feature_version

### 5. Replace Linear Regression Models

Current files:

- `linear_models/pluto_points_model.pkl`
- `linear_models/pluto_points_scaler.pkl`
- `linear_models/pluto_points_encoder.pkl`
- `scripts/linear_regression_model.py`
- model loading in `services/player_prediction.py`

Problems:

- Only points model exists in the repo.
- Rebounds and assists are TODOs.
- Training script saves to `ai_models/`, but runtime loads from `linear_models/`.
- `game_date_parsed` is one-hot encoded, which is not a sensible generalizable feature.
- Evaluation is a random train/test split, not time-series validation.
- No model registry, training metadata, calibration, or baseline comparison.
- Pickles are loaded directly without version checks.

Replacement:

- Establish baselines first:
  - rolling average baseline
  - opponent-adjusted rolling baseline
  - market-line baseline where lines exist
- Then train modern tabular models:
  - Ridge/ElasticNet as interpretable baseline
  - HistGradientBoostingRegressor or LightGBM/XGBoost if allowed
  - quantile models for prediction intervals
  - calibrated classifiers for over/under decisions
- Use time-series validation:
  - train on past dates
  - validate on future dates
  - evaluate by season segment
- Track:
  - MAE/RMSE
  - range hit rate
  - over/under accuracy
  - calibration by confidence bucket
  - performance by player/team/stat type
- Store models under `models/registry/<model_name>/<version>/` with a manifest.

### 6. Split API, Jobs, and Prediction Engine

Current problem:

- `main.py` starts agents and schedules jobs during FastAPI startup.
- Route dependencies create new agents/services per request.
- APScheduler instances are created inside adapters repeatedly.

Replacement processes:

- `api`: FastAPI only.
- `worker`: runs scheduled ingest, prediction, and evaluation jobs.
- `cli`: manual admin commands for local ops.

Suggested package layout:

```text
app/
  api/
    routes/
    dependencies.py
  core/
    config.py
    logging.py
    time.py
  db/
    models.py
    session.py
    repositories.py
    migrations/
  domain/
    predictions.py
    players.py
    games.py
    evaluation.py
  data/
    ingest/
    features/
    sources/
  ml/
    training/
    inference/
    registry/
    evaluation/
  llm/
    providers/
    prompts/
    schemas.py
  workflows/
    player_prediction.py
    game_prediction.py
    daily_jobs.py
  cli.py
```

### 7. Clean Dependencies

Likely remove:

- `supabase`
- `resend`
- `llama-index`
- `llama-index-embeddings-huggingface`
- `llama-index-llms-ollama`
- `llama-parse`
- `datasets`
- `requests-oauthlib`
- Twitter-specific code unless social posting is a separate product
- `pipreqs`

Keep or replace:

- Keep `fastapi`, `pydantic`, `pydantic-settings`, `uvicorn`.
- Keep `pandas`, `numpy`, `scikit-learn`, `joblib` initially.
- Keep SQLAlchemy/asyncpg, but make Postgres optional behind config.
- Add explicit testing/tooling:
  - `pytest`
  - `pytest-asyncio`
  - `ruff`
  - `mypy` or `pyright`
  - `httpx` for API tests

Optional:

- `openai`, `anthropic`, and/or Vercel provider SDKs.
- `duckdb` or SQLite for local analytics.
- `polars` if dataset size grows.

### 8. Rebuild Persistence and Schema

Current problems:

- SQLAlchemy table definitions and Supabase migration schema diverge.
- Evaluation code expects columns not present in the SQL migration, such as `actual`, model stats tables, and correctness flags.
- Prediction rows do not store enough reproducibility data.

New core tables:

- `players`
- `teams`
- `games`
- `player_game_logs`
- `team_game_logs`
- `odds_snapshots`
- `prop_lines`
- `injury_reports`
- `feature_snapshots`
- `model_versions`
- `prompt_versions`
- `prediction_runs`
- `player_predictions`
- `game_predictions`
- `prediction_evaluations`
- `job_runs`
- `llm_call_logs`

Every prediction should store:

- input context hash
- feature version
- model version
- prompt version
- provider/model used
- raw structured output
- final normalized output
- confidence/calibration metadata
- evidence citations or source references

### 9. Replace Custom JSON Parser

Current file:

- `utils/schema_json_parser.py`

Problems:

- JSON schema validation is homegrown.
- It tries to repair model output after prompting, which hides prompt/provider failures.

Replacement:

- Use Pydantic models for application types.
- Use provider-native structured output where available.
- Validate at the provider boundary.
- If validation fails, return a typed failure with raw output and do not persist as a successful prediction.

### 10. Testing and Quality Gates

Current state:

- No meaningful tests were found.
- `find . -maxdepth 3 -type f -name '*test*'` only found Supabase temp metadata.

Minimum rewrite test suite:

- Unit tests for feature builders.
- Unit tests for probability/over-under calculations.
- Unit tests for provider adapters with mocked responses.
- Repository tests against SQLite.
- API route tests with dependency overrides.
- End-to-end prediction workflow test using fixture data and a fake LLM provider.
- Backtest tests that prove no same-game or future data leaks into features.

## Recommended Rewrite Phases

### Phase 0: Freeze Current Behavior

- Capture current public endpoints and response models.
- Save small fixture datasets for local tests.
- Identify frontend contracts, if any.
- Decide whether Twitter/social posting is out of scope.

### Phase 1: New Skeleton Beside Old Code

- Add new `app/` package.
- Add config, logging, database session, repositories, Alembic migrations.
- Add SQLite local mode and Docker Compose Postgres mode.
- Add tests and CI commands.

### Phase 2: Data Foundation

- Build ingest tables and source adapters.
- Move CSV data into local DB-backed snapshots.
- Add feature generation with explicit as-of dates.
- Add stale-data detection.

### Phase 3: Modeling Foundation

- Add baseline predictors.
- Add model registry.
- Train/evaluate points, rebounds, assists, and game winner models.
- Add backtesting and calibration reports.

### Phase 4: Modern Agentic Workflow

- Implement typed LLM provider adapters.
- Implement player prediction workflow.
- Implement game prediction workflow.
- Add researcher/verifier steps as conditional subtasks.
- Store prompt/model/context metadata.

### Phase 5: API and Worker Cutover

- Rebuild routes against new services.
- Run scheduled jobs in a separate worker process.
- Remove old `agency/`, old agents, Supabase adapter, and unused social code.

### Phase 6: Evaluation Loop

- Backfill actual values after games.
- Evaluate prediction quality by model version and prompt version.
- Feed historical misses into features/evaluation, not into raw prompts as unstructured anecdotes.

## Code to Preserve Conceptually

- The idea of separate player and game prediction workflows.
- Some rolling feature logic from `scripts/create_dataset.py` and `scripts/create_team_dataset.py`.
- Some response model shapes in `models/prediction_models.py`.
- SQLAlchemy unit-of-work/repository direction, but not the current mixed Supabase implementation.
- Basic FastAPI router separation.

## Code to Avoid Carrying Forward

- Custom agent framework.
- Personality/tendency system.
- Twitter/rogue agents.
- Supabase client and Supabase auth assumptions.
- Mutable CSVs as application state.
- Current linear regression pickles.
- Custom schema parser.
- Startup-time agent scheduling inside FastAPI.
- Direct provider calls inside domain services.
- Prompt strings embedded in agent classes.

## First Concrete Implementation Step

Start by building the new skeleton and persistence layer in parallel with the old code:

1. Create `app/` package.
2. Add local config with `DATABASE_URL=sqlite+aiosqlite:///./pluto.db` by default.
3. Add SQLAlchemy models and Alembic migrations for the core prediction tables.
4. Add a fake LLM provider and a real OpenAI provider behind the same interface.
5. Rebuild one endpoint: player points prediction using fixture data, baseline model, and typed structured LLM output.

That creates the foundation for a controlled rewrite without trying to untangle the old system module by module.

## API Route Rewrite Plan

The product goal is narrower than the current API surface:

- Automatically ingest the latest NBA games and prop lines.
- Automatically generate stored predictions for available games/players.
- Let users query stored predictions.
- Let users request a fresh prediction for a specific player prop in a specific game when new information is available.

The rewrite should treat prediction generation, data refresh, evaluation, and notification as internal jobs/admin operations. The public API should focus on games, props, predictions, and prediction history.

### Current Route Inventory

Current routes under `/v1/api`:

```text
POST /predictions/all-predictions
POST /predictions/all-game-predictions
POST /predictions/player/{prediction_type}
POST /predictions/game/winner
GET  /predictions/game/winner
GET  /predictions/update-pluto-dataset
GET  /predictions/evaluate-predictions/{prediction_type}
GET  /predictions/evaluate-game-predictions
GET  /predictions/fill-actual-values
GET  /predictions/get-evaluation-metrics
GET  /predictions/get-key-metrics
POST /predictions/prompt-pluto
GET  /predictions/picks-of-the-day
GET  /players/player-predictions
POST /players/update-player-stats
GET  /players/get-player-image
GET  /games/{game_id}
GET  /games/today
GET  /games/{game_id}/prediction
GET  /teams/
GET  /teams/{team_name}
GET  /teams/game-winner/{home_team}/{away_team}/{game_date}
GET  /odds/today/{team}
GET  /odds/sports
GET  /odds/prizepicks/{player_name}
POST /user/send-users-prediction-email
POST /user/send-users-game-prediction-email
```

### Concepts to Carry Forward, Not Routes to Keep

Do not preserve the current route structure. Carry forward only these product concepts:

- `POST /predictions/player/{prediction_type}`
  - Concept: on-demand player prop prediction.
  - New endpoint should be centered around a specific game and prop line:
    - required `game_id`
    - required `player_id` or normalized `player_name`
    - required `stat_type`
    - optional `line`
    - optional `force_refresh`
    - optional `additional_context`
  - It should return either a newly generated prediction or the latest stored prediction, depending on request mode.

- `GET /players/player-predictions`
  - Concept: stored prediction query.
  - Replace with generalized prediction search.
  - Support filters:
    - `game_date`
    - `game_id`
    - `player_id`
    - `player_name`
    - `team`
    - `opponent`
    - `stat_type`
    - `status`
    - `min_confidence`

- `GET /games/today`
  - Concept: current slate.
  - Replace with a route that returns local stored schedule data first, with freshness metadata.

- `GET /games/{game_id}`
  - Concept: game details.
  - Replace with typed game detail response, including teams, start time, status, known props, prediction coverage, and data freshness.

- `GET /odds/prizepicks/{player_name}`
  - Concept: prop-line lookup.
  - Replace with local stored line snapshot queries, not live provider passthrough.

- `GET /predictions/get-evaluation-metrics`
- `GET /predictions/get-key-metrics`
  - Concept: prediction performance metrics.
  - Replace with `/analytics` or `/admin/analytics`.
  - Public users probably need summary accuracy; internal users need full model/prompt/version metrics.

### Move to Admin/Internal API

These should not be ordinary public product routes:

- `POST /predictions/all-predictions`
- `POST /predictions/all-game-predictions`
- `GET /predictions/update-pluto-dataset`
- `GET /predictions/evaluate-predictions/{prediction_type}`
- `GET /predictions/evaluate-game-predictions`
- `GET /predictions/fill-actual-values`
- `POST /players/update-player-stats`

Replacement:

```text
POST /admin/jobs/ingest
POST /admin/jobs/generate-predictions
POST /admin/jobs/evaluate
GET  /admin/jobs/{job_id}
GET  /admin/jobs
```

The normal path should be a background worker, not users hitting update/evaluate endpoints manually.

### Remove From Rewrite

Remove these from the core product API:

- `POST /predictions/prompt-pluto`
  - This exposes the LLM as a chat endpoint and does not match the product.
  - Replace with typed prediction/research workflows only.

- `GET /predictions/picks-of-the-day`
  - The current implementation asks the LLM to build a parlay from stored predictions.
  - If this remains, rebuild later as `GET /recommendations/daily-card` backed by scored predictions and constraints, not freeform prompting.

- `POST /user/send-users-prediction-email`
- `POST /user/send-users-game-prediction-email`
  - Remove Resend/Supabase user dependencies.
  - If notifications matter later, implement optional self-hosted SMTP/webhook jobs.

- `GET /odds/sports`
  - This is an Odds API passthrough, not a Pluto product route.

- `GET /odds/today/{team}`
  - Replace with local stored odds/line snapshot queries.

- `GET /teams/game-winner/{home_team}/{away_team}/{game_date}`
  - This is an adapter passthrough/helper route.
  - Game actuals should live under `/games/{game_id}` or `/analytics/evaluations`.

- Twitter/social routes and agents should not exist in the rewritten backend.

### Proposed Public API Contract

Use a smaller public API:

```text
GET  /healthz

GET  /v1/slate
GET  /v1/slate/today
GET  /v1/games/{game_id}

GET  /v1/players
GET  /v1/players/{player_id}
GET  /v1/players/search

GET  /v1/props
GET  /v1/props/latest
GET  /v1/games/{game_id}/props

GET  /v1/predictions
GET  /v1/predictions/{prediction_id}
POST /v1/predictions/player-prop

GET  /v1/analytics/summary
GET  /v1/analytics/model-performance
```

Notes:

- Prefer `/slate` over `/games/today` as the main user-facing entry point. The user wants today's board: games, players, props, generated predictions, and missing coverage.
- Keep `/games/{game_id}` for detailed drill-down.
- Game winner predictions are secondary to the stated player-prop product. Add them later only if they support the prop workflow.
- `/props` should represent available prop opportunities, not just raw provider odds.
- `/predictions/player-prop` should be the only public mutation that creates a user-requested prediction.

### Proposed Admin API

Use an admin namespace for operational actions:

```text
POST /v1/admin/jobs/ingest
POST /v1/admin/jobs/build-features
POST /v1/admin/jobs/generate-predictions
POST /v1/admin/jobs/evaluate
GET  /v1/admin/jobs
GET  /v1/admin/jobs/{job_id}

GET  /v1/admin/data/freshness
GET  /v1/admin/models
GET  /v1/admin/models/{model_version}
GET  /v1/admin/prompts
GET  /v1/admin/prompts/{prompt_version}
```

Admin endpoints should be backed by the same job system used by the worker. A manual API call should enqueue a job and return `job_id`; it should not run a long ingest/prediction loop inline in the request.

### Core User Flows

#### Automated Daily Flow

1. Worker ingests today's NBA schedule.
2. Worker ingests latest player/team/game data.
3. Worker ingests prop lines from configured sources.
4. Worker builds feature snapshots for each game/player/stat.
5. Worker generates predictions for configured target props.
6. API serves stored predictions from the local DB.
7. Evaluator fills actuals after games complete.

Primary UI endpoint:

```text
GET /v1/slate/today
```

This should return enough for the frontend's first screen:

```json
{
  "date": "2026-06-29",
  "data_freshness": {
    "schedule": "2026-06-29T09:00:00Z",
    "props": "2026-06-29T09:12:00Z",
    "predictions": "2026-06-29T09:30:00Z"
  },
  "games": [
    {
      "game_id": "0022500001",
      "home_team": "LAL",
      "away_team": "GSW",
      "start_time": "2026-06-29T23:30:00Z",
      "status": "scheduled",
      "prediction_coverage": {
        "available_props": 42,
        "predicted_props": 31,
        "missing_predictions": 11
      }
    }
  ]
}
```

#### Query Stored Predictions

```text
GET /v1/predictions?game_date=2026-06-29&stat_type=points
GET /v1/predictions?player_name=Stephen%20Curry&game_id=0022500001
GET /v1/games/{game_id}/props
```

#### Generate or Refresh One Prediction

```text
POST /v1/predictions/player-prop
```

Request shape:

```json
{
  "game_id": "0022500001",
  "player_name": "Stephen Curry",
  "team": "GSW",
  "opponent": "LAL",
  "stat_type": "points",
  "line": 27.5,
  "force_refresh": false,
  "additional_context": "Minutes restriction reportedly removed."
}
```

Behavior:

- If a current prediction exists and `force_refresh=false`, return the stored prediction.
- If no current prediction exists, generate one and store it.
- If `force_refresh=true`, create a new prediction run and keep the old prediction for history.
- Response must include:
  - prediction id
  - prediction run id
  - predicted value/range
  - over/under recommendation
  - confidence
  - model version
  - prompt version
  - data freshness
  - evidence/source summary

### Route-Level Bugs to Avoid

- Do not declare dynamic routes before static routes. Current `routers/games.py` declares `GET /games/{game_id}` before `GET /games/today`.
- Do not use GET routes for mutations. Current update/evaluate/fill routes mutate state with GET.
- Do not instantiate providers/adapters inside auth dependencies on every request.
- Do not expose raw provider passthroughs as product routes.
- Do not return untyped `dict` for core product responses.
- Do not mix prediction generation and stored prediction reads in ambiguous endpoint names.

## Frontend and Backend Packaging Recommendation

The old frontend repository was referenced as:

```text
https://github.com/theworksofvon/pluto-ai
```

As of this audit update, that repository returns GitHub `404` from both the GitHub connector and a direct HTTP request. That usually means the repo is private, renamed, deleted, or the current credentials do not have access. The architecture recommendation below is based on this backend's product and operational needs, not on inspected frontend code.

### Recommendation

Use a fullstack monorepo shape only if you want one developer workflow, but keep the frontend and backend as separate deployable applications.

Recommended layout:

```text
pluto-ai/
  apps/
    web/        # Next.js or Vite/React frontend
    api/        # FastAPI backend
    worker/     # scheduled ingest/prediction/evaluation worker
  packages/
    api-client/ # generated TypeScript client from OpenAPI
    shared/     # shared non-secret constants/types if useful
  infra/
    docker-compose.yml
    postgres/
  docs/
```

Why:

- The backend is Python ML/data infrastructure with background workers, model artifacts, scheduled jobs, and local/self-hosted database needs.
- The frontend should not be coupled to model training, ingestion, or worker runtime dependencies.
- A separate API boundary gives the mobile/app/dashboard options room to grow later.
- A monorepo still gives a single local `docker compose up` experience.
- The frontend can consume a generated client from the FastAPI OpenAPI schema, keeping contracts tight without sharing runtime code.

### Avoid

- Do not put Python model/worker code inside a Next.js app just to call it fullstack.
- Do not make frontend server actions directly perform prediction jobs.
- Do not let the frontend call provider APIs, odds APIs, or model APIs directly.
- Do not split into two repos if API/frontend contract churn is still high and one person or one small team owns both.

### Deployment Shape

Local/self-hosted deployment:

```text
web      -> serves UI
api      -> serves typed HTTP API
worker   -> runs scheduled ingest/predict/evaluate jobs
postgres -> local/self-hosted database
volume   -> model registry and artifacts
```

For simple local development:

```text
web    on localhost:3000
api    on localhost:8000
worker optional/manual
sqlite or postgres
```

### Frontend Contract Strategy

- Generate a TypeScript client from the FastAPI OpenAPI schema.
- Treat `/v1/slate/today`, `/v1/games/{game_id}/props`, and `/v1/predictions` as the main read paths.
- Use `POST /v1/predictions/player-prop` only for explicit user refresh/new-prediction actions.
- Include `data_freshness`, `prediction_run_id`, `model_version`, and `prompt_version` in responses so the UI can explain why a prediction exists and when it was produced.

## Data Source Reliability Plan

The current backend depends heavily on `nba_api`, plus odds/prop providers. This is a risk area and should be treated as a first-class part of the rewrite, not a utility detail.

### Current NBA API Findings

The repo currently uses `nba_api` through:

- `adapters/nba_stats/nba_api.py`
- `scripts/create_dataset.py`
- `scripts/create_team_dataset.py`
- `services/game_prediction.py`

The installed lockfile references:

```text
nba_api 1.8.0
```

The package is still active. The GitHub releases page lists `v1.11.4` as latest, released `2026-02-20`. That matters because the release notes say:

- `ScoreboardV2` is deprecated because it returns empty line scores for 2025-26 games.
- `ScoreboardV3` should be used instead.
- `PlayByPlayV2` is deprecated because NBA.com returns empty JSON for that endpoint.
- `PlayByPlayV3` should be used instead.
- HTTP headers were updated to fix broken NBA.com API requests caused by an outdated user agent.

This repo currently imports and uses:

```python
scoreboardv2.ScoreboardV2
playbyplayv2.PlayByPlayV2
```

Those should not survive the rewrite.

### Current Data Source Problems

- Some adapter methods are declared async in the interface but implemented sync in the concrete adapter.
- Many NBA API calls happen in request or workflow paths without explicit timeout, retry, or source health tracking.
- `get_starting_lineup` does not actually fetch starting lineups; it takes the first five roster entries with a position.
- `GameService` references methods like `get_game` and `get_game_prediction` that are not implemented on the NBA adapter.
- The app treats live external API calls as reliable source-of-truth reads instead of ingesting, caching, validating, and serving local snapshots.
- Current game/injury/odds paths include placeholders.

### Rewrite Principle

External sports APIs must be treated as unreliable inputs.

The API should serve local stored snapshots. Workers should ingest from external sources, validate them, and mark freshness/quality. User-facing requests should not depend on live NBA.com/odds calls succeeding at that exact moment.

### Data Source Modules

Use source adapters behind narrow ports:

```text
NbaScheduleSource
NbaPlayerGameLogSource
NbaTeamGameLogSource
NbaBoxScoreSource
PropLineSource
InjuryNewsSource
MarketOddsSource
```

Each source adapter should return typed source results:

```json
{
  "source": "nba_api.scoreboardv3",
  "fetched_at": "2026-07-01T15:00:00Z",
  "status": "success",
  "data": {},
  "warnings": [],
  "raw_snapshot_id": "..."
}
```

### Required Reliability Features

Every external data adapter should have:

- explicit timeout
- retry with backoff
- rate limiting
- structured errors
- raw response snapshot storage
- freshness metadata
- schema validation
- endpoint health checks
- fallback strategy
- source version tracking

### Source Health Checks

Add a daily or hourly smoke job:

```text
check_nba_schedule_source
check_player_game_log_source
check_team_game_log_source
check_box_score_source
check_prop_line_source
check_news_source
```

Store results:

```text
source_health_checks
  source_name
  checked_at
  status
  latency_ms
  error_message
  sample_entity
  response_shape_hash
```

Expose internally:

```text
GET /v1/admin/data/freshness
GET /v1/admin/data/sources
GET /v1/admin/data/sources/{source_name}/health
```

### Snapshot-First Data Model

Store raw and normalized data separately:

```text
raw_source_snapshots
  source
  endpoint
  params
  fetched_at
  status
  raw_json
  raw_hash

games
players
teams
player_game_logs
team_game_logs
box_scores
prop_lines
injury_reports
```

This allows replaying ingestion after parser changes and debugging why a prediction had bad data.

### Fallback Strategy

For schedule/game status:

1. `nba_api` current V3/live endpoint.
2. Previously stored local schedule snapshot if still relevant.
3. Manual/admin correction.

For player/team game logs:

1. `nba_api` endpoint.
2. Existing local historical table.
3. Backfill job later if source is down.

For prop lines:

1. Primary prop provider adapter.
2. Secondary provider if configured.
3. Last known line with `stale=true`.

For injuries/news:

1. Search/news source.
2. Team/player official source if configured.
3. Empty context with explicit `context_unavailable=true`.

### Model Workflow Impact

Predictions should carry data quality metadata:

```json
{
  "data_quality": {
    "schedule_fresh": true,
    "props_fresh": true,
    "player_logs_fresh": true,
    "context_fresh": false,
    "warnings": ["injury_context_unavailable"]
  }
}
```

If critical data is stale or missing, the workflow should either:

- return no prediction,
- return a low-confidence prediction,
- or require `force=true` with a warning.

### Immediate Library Updates for Rewrite

- Update `nba_api` to the latest compatible version.
- Replace `ScoreboardV2` with `ScoreboardV3` or the current live scoreboard endpoint.
- Replace `PlayByPlayV2` with `PlayByPlayV3`.
- Configure custom headers and timeouts where required.
- Add integration smoke tests that hit a small stable set of known endpoints.
- Add contract tests around parsed response shapes.
