# Kepler Vision

AI-powered Earth Observation platform.

## Repository structure

```
kepler-vision/
├── apps/
│   └── web/                    # Next.js 15 frontend (App Router)
├── services/
│   └── api/                    # FastAPI backend (DDD + hexagonal)
└── packages/
    ├── tsconfig/               # Shared TypeScript base config
    └── eslint-config/          # Shared ESLint config
```

## Quick start (dev)

```bash
# 1. Install dependencies
pnpm install

# 2. Start infrastructure (Postgres, Redis, MailHog)
docker compose -f services/api/docker-compose.yml up -d

# 3. Backend
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn kepler.main:app --reload --port 8000

# 4. Frontend (in another terminal)
cd apps/web
pnpm dev
```

Visit:
- API: <http://localhost:8000/docs>
- Web: <http://localhost:3000>
- MailHog: <http://localhost:8025>

## Stack

**Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2, argon2-cffi, PyJWT (RS256), Redis, structlog, OpenTelemetry.

**Frontend:** Next.js 15 (App Router, RSC), TypeScript strict, Tailwind CSS, shadcn/ui, TanStack Query, React Hook Form + Zod, Zustand, MapLibre, Framer Motion.

## Status

Currently implementing **Sprint 1 — Identity, Auth, Tenancy**.

See `/plans/` for the full architecture and sprint plan.
