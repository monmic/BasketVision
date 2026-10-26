# AGENTS.md — BasketVision

## Project purpose

BasketVision is a basketball video-analysis web application.

Primary workflow:
1. User uploads a local basketball video.
2. Backend creates and orchestrates an asynchronous analysis job.
3. Python computer-vision worker analyzes the selected video range.
4. Results are persisted.
5. Frontend shows progress, detections, statistics, debug artifacts, and a video-linked report.

Long-term goal:

**video → Team A/B → basketball events → statistics → clickable timeline/report**

Do not redesign the architecture unless explicitly requested.

## Repository architecture

Monorepo:
- `frontend/` — React + TypeScript
- `backend/` — ASP.NET Core / .NET 8
- `vision/` — Python CV worker
- PostgreSQL — application/job persistence
- Docker Compose — local and production orchestration
- Caddy — production reverse proxy / HTTPS

Backend owns:
- domain/application logic
- auth and authorization
- roles, subscriptions and entitlements
- game/job lifecycle
- persistence
- APIs and orchestration

Vision worker owns:
- OpenCV / PyTorch / Ultralytics
- person detection/tracking
- ball detection/tracking
- CV diagnostics
- future event inference

Frontend owns:
- public landing page
- auth UI
- video upload
- analysis-range selection
- job controls/progress
- admin UI
- reports/statistics

## Core rules

### General
- Prefer small, targeted changes.
- Reuse existing patterns before creating new abstractions.
- Do not perform unrelated refactors.
- Do not add dependencies unless clearly justified.
- Preserve backward compatibility unless explicitly allowed to break it.
- Do not invent features or data not supported by the application.
- Do not commit secrets, generated videos, debug artifacts, model files, build output, or env files.

### Backend
- .NET owns business rules and orchestration.
- Keep business logic out of controllers when an existing service layer can own it.
- Use existing EF Core patterns and migrations.
- Preserve authorization and ownership checks.
- Roles and subscription plans are separate concepts.
- Authorization roles: e.g. `Admin`, `User`.
- Commercial plans: e.g. `Free`, `Pro`, `Advanced`.
- Feature access must go through entitlements/capabilities/limits.
- Do not scatter checks such as `if plan == Pro`.
- The CV worker must remain unaware of subscription-plan logic.

### Frontend
- Preserve auth and routing behavior.
- Reuse existing components, styling conventions and API clients.
- Public pages may have a distinct visual treatment from the authenticated app.
- Do not make the homepage look like an internal management dashboard.
- Do not present unreleased CV/event features as available.
- Preserve responsive behavior and accessibility.
- Keep bundle growth modest.

### Vision worker
- Do not modify CV unless the task explicitly concerns CV.
- Preserve separation between person and ball model/tracker instances.
- Never reintroduce shared Ultralytics predictor/tracker state between person and ball pipelines.
- Preserve pause/resume/delete and checkpointing.
- Preserve absolute timestamps for selected-range analysis.
- Avoid arbitrary threshold changes without diagnostics or benchmarks.

## Current CV direction

Current work is tracking-first / ball-first.

Important principles:
- person and ball pipelines are independent
- ball processing is more intensive
- ball detection may use full-frame plus tiled fallback
- raw / accepted / rejected candidates are diagnostically useful
- tentative / confirmed / lost states matter
- weak detections may update existing tracks without creating new tracks
- debug images and rejection reasons are part of the diagnostic workflow

Current milestone family: approximately **CV-02.x / CV-02.4**.

Preferred roadmap:
1. reliable person + ball tracking
2. hoop / basket / court context
3. shot attempt
4. made / missed
5. possession
6. rebounds
7. turnover / steal
8. block / assist
9. fouls / violations / timeouts
10. robust Team A / Team B attribution
11. complete reports
12. player identity later

Do not jump directly to a monolithic basketball-event classifier.

## Analysis job behavior

Analysis is asynchronous.

Expected behavior:
- upload must complete before analysis starts
- browser may refresh/close after upload
- job state survives refresh
- current game can be restored from URL
- analysis supports start/end timestamps
- pause saves progress/checkpoint and frees worker
- resume continues from checkpoint
- delete removes analysis job/events/artifacts/checkpoint/range metadata, not game/video unless explicitly requested
- frontend can list background analyses and progress

Do not convert this workflow into synchronous request/response processing.

## Video source rule

BasketVision currently supports **local uploaded video files only**.

Do not add YouTube ingestion, streaming URLs, or arbitrary remote video sources unless explicitly requested.

## Auth / roles / subscriptions

Preserve the existing implementation.

Expected concepts:
- login / refresh / logout
- JWT access token
- refresh-ready session flow
- roles separate from subscriptions
- ownership checks
- usage tracking
- entitlement service
- limits such as analysis capability, advanced events, export, max video duration, analyses/month, concurrent jobs, and storage

Never hardcode production secrets.
Seed admin/demo credentials must come from environment configuration only.

## Public site / SEO

Production canonical domain:

`https://basketvision.it`

Rules:
- `www.basketvision.it` permanently redirects to non-www
- homepage is indexable
- private/app routes such as login/admin/dashboard/report are `noindex`
- preserve `robots.txt`
- preserve `sitemap.xml`
- preserve canonical metadata
- preserve Open Graph metadata
- preserve structured data
- do not remove SEO protections when changing routing/layout

Public copy must describe only features that really exist.

## Production architecture

Production runs via Docker Compose.

Public traffic:

`Internet → Caddy → web/api`

Only Caddy should expose ports `80` and `443`.
Do not expose PostgreSQL or API directly.

Caddy routing:
- `/api/*` → API
- `/auth/*` → API
- everything else → frontend
- `www` → permanent redirect to non-www

Normal updates do not require `docker compose down`.

Typical full update:

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.production ps
```

Targeted builds:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build api web
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build worker
```

Config-only recreation:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d worker
```

Never use `docker system prune --volumes` in production.

## Production host constraints

Current VM is CPU-only with approximately:
- 2 CPU cores
- 12 GB RAM

Treat CPU as the likely CV bottleneck.
Do not assume GPU/CUDA.

When optimizing CV:
- benchmark the same input/range before and after
- report elapsed time and quality impact
- prefer configuration changes before architectural rewrites
- avoid silent quality degradation

## Git hygiene

Do not commit:
- `.env`
- `.env.production`
- secrets/passwords/signing keys
- DB data
- uploaded videos
- generated analysis/debug artifacts
- model weights
- `node_modules`
- `bin`
- `obj`
- virtualenvs
- `__pycache__`
- IDE state
- build output

Use `.env.production.example` for placeholders only.


## Continuation policy

When there is an existing documented work queue, TODO list, roadmap, review file, or clearly identified next task:

- Treat the queue as one continuous task, not as a sequence of user-confirmed checkpoints.
- Do not stop after completing a single queue item.
- Continue automatically with the next actionable item.
- Do not wait for user messages such as `OK`, `continue`, `proceed`, or `proseguiamo`.
- Progress/status updates are informational and are not turn-ending checkpoints.
- After completing an item, actively inspect the documented queue for the next actionable item before deciding to stop.
- If one item is blocked, continue with other independent actionable items when possible.
- Do not declare `Done` merely because the current subtask is complete.

Stop only when one of these conditions is true:

- the documented queue is exhausted;
- all remaining items are genuinely blocked by the same external dependency;
- the next action requires a product/design decision that cannot be safely inferred from repository context;
- an action requires explicit user approval for safety or permissions;
- continuing would exceed the explicitly stated task scope.

When blocked:

- state exactly what blocks continuation;
- identify which remaining queue items are affected;
- state whether any independent work can still proceed;
- request user action only when it is actually necessary.

Otherwise, keep working through the queue and provide one final summary only after reaching a real stopping condition.

## Codex task protocol

Optimize for **minimal exploration and minimal token usage**.

Before changing code:
1. Read this file.
2. Inspect only files/directories relevant to the task.
3. Search for an existing implementation/pattern before creating a new one.
4. Do not recursively inspect unrelated subsystems.
5. Do not restate the whole architecture unless needed.

During implementation:
- Keep scope narrow.
- Avoid unrelated cleanup.
- Avoid renames unless useful for the task.
- Do not reformat unrelated files.
- Prefer extending existing services/components over parallel infrastructure.
- If the repository clearly answers an assumption, proceed instead of asking.
- If ambiguity does not block a safe implementation, choose the smallest compatible solution.

Validation:
- Run only checks relevant to the touched area unless the change crosses boundaries.
- Frontend: use repository-standard build/test commands.
- Backend: `dotnet build` and focused `dotnet test`.
- Vision: run focused Python/tracker tests first.
- Compose: `docker compose -f docker-compose.prod.yml --env-file .env.production config`.
- Avoid expensive full Docker rebuilds for small isolated changes unless necessary.

Final response:
Report only:
1. what changed
2. files/areas changed
3. validations run and result
4. migrations/config changes, if any
5. remaining TODO/blockers, if any

Do not provide a long retrospective unless explicitly requested.

## Preferred task prompt format

```text
Task: <goal>

Scope:
- <allowed area>
- do not touch <excluded area>

Requirements:
- <requirement>
- <requirement>

Validation:
- <specific checks>
```

If scope is explicit, respect it strictly.

## Definition of done

A task is done when:
- requested behavior is implemented
- architecture boundaries are respected
- affected build/tests pass
- no unrelated subsystem was modified
- no secrets/private data were introduced
- production-impacting config/migration changes are explicitly reported
- user-facing claims match features that actually exist
