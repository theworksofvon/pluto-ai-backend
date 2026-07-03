# Agent Rewrite Plan

This repo should be rewritten as a model-grounded NBA player prop prediction system. Do not preserve the old route structure, custom agent framework, Supabase coupling, or personality-based agents.

## Product Goal

Build a local/self-hostable service that:

- ingests NBA games, player logs, team data, prop lines, and context
- builds point-in-time features
- runs a base statistical/ML model
- lets an LLM agree with or adjust the base model using latest context
- stores predictions, evidence, model versions, prompt versions, and data freshness
- serves stored predictions to a frontend
- evaluates predictions after games complete

## Architecture

Use a modular monolith with clear boundaries:

```text
api      -> FastAPI routes
worker   -> scheduled ingest/predict/evaluate jobs
workflows -> use cases
domain   -> pure prediction/evaluation logic
adapters -> external APIs, DB, LLMs, model registry
```

Use ports/adapters only at real external boundaries:

- NBA data source
- prop/odds source
- news/context source
- LLM provider
- database repositories
- model registry
- job runner
- clock/time

Avoid a generic multi-agent framework. The workflow can use multiple LLM calls, but they are just steps, not personalities.

## Core Workflow

```text
GeneratePlayerPropPrediction
  -> load game/player/prop line
  -> build feature snapshot
  -> run base model
  -> fetch/extract latest context
  -> LLM agrees or adjusts
  -> apply adjustment guardrails
  -> persist prediction run
  -> return final prediction
```

Store both:

- base model prediction
- final LLM-adjusted prediction

This is required so we can measure whether the LLM improves or hurts the model.

## Data Reliability Comes First

Focus first on making adapters work reliably.

External sports APIs should be treated as unreliable. The API should serve local stored snapshots. Workers should fetch, validate, store, and mark freshness.

Adapter requirements:

- timeout
- retry/backoff
- rate limiting
- typed parsed output
- raw response snapshot
- freshness metadata
- source health check
- fallback behavior

`nba_api` must be revisited. The repo is locked to `nba_api 1.8.0`; latest checked release was `1.11.4`. Replace deprecated `ScoreboardV2` and `PlayByPlayV2` usage with current V3/live endpoints.

## Dataset Rewrite

Replace the current CSV-first dataset scripts with an ingest/build pipeline.

Target flow:

```text
ingest raw data -> normalize DB tables -> build feature snapshots -> train/backtest
```

One training row should represent:

```text
player + game + stat_type + as_of_time
```

Features must only use data available before prediction time.

## Modeling Direction

Start with baselines, then improve.

Baselines:

- last 5 average
- last 10 average
- season average
- weighted recent average
- prop line baseline

Candidate models:

- Ridge / ElasticNet
- HistGradientBoostingRegressor
- RandomForestRegressor
- optional XGBoost/LightGBM
- quantile/conformal interval models
- classifier for probability actual > line

Use time-based backtesting, not random splits.

Track:

- MAE/RMSE
- range hit rate
- over/under accuracy
- calibration
- model-only vs LLM-adjusted performance

## API Shape

Main public concepts:

```text
GET  /v1/slate/today
GET  /v1/games/{game_id}
GET  /v1/games/{game_id}/props
GET  /v1/predictions
GET  /v1/predictions/{prediction_id}
POST /v1/predictions/player-prop
GET  /v1/analytics/summary
```

Admin/job concepts:

```text
POST /v1/admin/jobs/ingest
POST /v1/admin/jobs/build-features
POST /v1/admin/jobs/generate-predictions
POST /v1/admin/jobs/evaluate
GET  /v1/admin/data/freshness
```

## Remove

Do not carry forward:

- `agency/`
- personality/tendency agents
- Twitter/rogue agents
- Supabase
- Resend
- custom JSON parser
- provider passthrough routes
- `/prompt-pluto`
- mutable CSVs as app state
- old linear model pickles as production models

## First Implementation Slice

Build the new app beside the old code:

```text
app/
  api/
  worker/
  workflows/
  domain/
  adapters/
  ml/
```

First vertical slice:

1. reliable NBA schedule/player log adapter smoke tests
2. local DB tables for games, players, prop lines, predictions
3. feature snapshot builder for one stat type
4. baseline model prediction
5. LLM adjustment call with structured output
6. `POST /v1/predictions/player-prop`
7. `GET /v1/predictions`
