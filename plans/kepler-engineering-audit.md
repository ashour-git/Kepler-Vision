# Kepler Vision — Engineering Audit

**Author:** Distinguished Engineer
**Audience:** CTO, Engineering, Product, SRE, Security
**Status:** v0.1
**Date:** 2026-07-18
**Scope:** Sprint 1 (Identity, Auth, Tenancy) + AI platform + Web app + CI/CD + integration

---

## 0. Executive Summary

The platform is **structurally sound at the architecture level** — clean DDD layering, strict TypeScript, content-addressed model registry, append-only audit, RS256 JWT with family-theft detection, and a runnable monorepo with passing unit tests across all three services. Compared to Google Earth Engine, Sentinel Hub, Planet Explorer, Open-CD, and Orbital Insight, however, the project is at a **post-MVP scaffolding stage**: it has the bones of a regulated EO platform but lacks the operational, security, AI, and UX depth that distinguishes the incumbents.

**Overall maturity by area** (1 = scaffold, 5 = production-grade):

| Area | Score | Notes |
|---|---|---|
| Architecture | 3.5 | Clean layering; missing event bus, no background workers, in-process outbox only |
| Scalability | 2.0 | Single-process Uvicorn, no read replicas, no caching layer |
| Performance | 2.5 | Acceptable for low traffic; no cache, no ETag, no compression |
| Security | 2.5 | Argon2 + RS256 + audit log are correct; audience validation is bypassed, MFA/SSO/password-reset/email-verification are missing |
| Accessibility | 2.0 | Color tokens, focus ring, labels — but no skip link, no aria-live, no reduced-motion handling |
| Code Quality | 3.0 | Strict types, lint config, but long files, magic strings, mixed async patterns |
| AI Pipeline | 2.0 | Real exporters and registry, but no real model weights, saliency and detection mAP are stubs |
| Database | 3.0 | Clean schema with triggers; no partitioning, no RLS, no statement timeouts |
| API Design | 2.5 | OpenAPI works; no security scheme, no rate-limit headers, no SDK generation, no field selection |
| Testing | 2.5 | 17 + 8 + 42 + 7 unit tests pass; integration tests skip without infra; no mutation / contract / fuzz |
| Deployment | 1.5 | Docker Compose only; no K8s manifests, no Helm, no Terraform, no observability stack |
| UX | 1.5 | Auth flows + protected shell; no command palette, no theme toggle wired, no skeletons, no 404/500 pages |

**Verdict:** Solid foundation; significant work required to reach regulated-SaaS parity with Sentinel Hub / Planet / Maxar.

---

## 1. Architecture

### Strengths
- Clean DDD + hexagonal layering (domain / application / infra / api)
- Forward-only Alembic migrations, versioned
- Strict TypeScript across the monorepo
- Content-addressed model registry with hash-derived provenance
- Pure-domain entities with no I/O coupling

### Weaknesses
1. **In-process outbox with no relay** — `uow.commit()` returns a list of `DomainEvent` objects to the caller, but the caller does not publish them. Events are lost on process restart. (PRD called for RabbitMQ outbox in a later sprint.)
2. **No background job infrastructure** — Long-running work (AOI ingestion, AI inference) will block the request thread. Celery is in the plan but not implemented.
3. **Singleton services via module-level globals** — `get_jwt_service`, `get_redis_client`, `get_refresh_token_store` use lru_cache + module globals. Test isolation is fragile.
4. **Application layer depends on infra** — `application/identity/commands.py` imports `from ...infra.cache.refresh_store`. This is a layering violation; the application layer should depend on a port.
5. **No repository abstraction in domain** — The domain layer is pure, but the UoW returns SQLAlchemy repos. There's no `Protocol`-based interface.
6. **No CQRS** — Reads and writes share the same model. Reporting queries will degrade OLTP throughput.
7. **No SAGA / process manager** — Multi-step workflows (e.g., sign-up → workspace → seed → welcome email) have no orchestration primitive.
8. **No service mesh** — Uvicorn exposed directly; no rate limiting, no global throttling, no request-level auth at the edge.
9. **No API gateway in front of the app** — The web client talks to the API directly across origins, relying on CORS.
10. **Domain events are emitted but not versioned** — `UserSignedUp`, `UserSignedIn`, etc. carry `event_id` and `occurred_at` but no `schema_version`.
11. **No idempotency-key store** — The architecture plan called for it; we accept the `Idempotency-Key` header on POSTs but never persist it.
12. **No clock injection for tests** — `utc_now()` is a function but not injected. Time-sensitive tests use `freezegun` as a band-aid.

### Competitor comparison
- **Google Earth Engine** has a distributed Dataflow engine, asset manager, and a Python+JS SDK pair. We have neither.
- **Sentinel Hub** has OGC-compliant APIs (WMS, WMTS, WCS) and a processing engine with custom backends. We have REST only.
- **Planet Explorer** has a frontend optimized for browsing high-cadence imagery with bulk ordering. We have no imagery-browsing UI.
- **Open-CD** is a single, deeply evaluated model. We have a registry of zero trained models.
- **Orbital Insight** ships industry-specific apps on top of opaque models. We have no app layer yet.

---

## 2. Scalability

### Strengths
- Pool size configurable (20 + 10 overflow)
- Stateless API pods (in principle)
- Docker image is slim and multi-stage

### Weaknesses
1. **Single Uvicorn worker per pod** — Should run `gunicorn -k uvicorn.workers.UvicornWorker -w N` where `N = 2 * cores + 1`.
2. **No read replicas configured** — All reads hit primary; reporting will block writes.
3. **No caching layer beyond Redis** — STAC search, AOI metadata, model lists are not cached. A simple in-memory LRU with a `cache.py` would help.
4. **No async processing for heavy operations** — AOI ingest, AI runs, exports are synchronous. Need a worker tier.
5. **No CDN for static assets or map tiles** — Map tiles should be served from PMTiles + CDN.
6. **No connection pool warming** — Cold first request is slow.
7. **No rate limiting on sensitive endpoints** — Only login is throttled; `/v1/users/me/change-password` and `/v1/auth/refresh` are not.
8. **No multi-region strategy** — Single-region deployment; no replication of state.
9. **No event-driven scaling** — Can't scale ML inference independently of the API.
10. **No sharding strategy** — `tenants` table will grow unbounded; no sharding key.
11. **Synchronous argon2 hashing** — Each signup/sign-in blocks the request thread for ~50–100 ms. Should be offloaded to a worker for high-concurrency paths.

### Competitor comparison
- **Sentinel Hub** autoscales processing workers based on queue depth.
- **Google Earth Engine** has a global dataflow scheduler that handles petabytes/day.
- **Planet** serves 10+ M images/day from a globally distributed CDN.

---

## 3. Performance

### Strengths
- Async I/O end-to-end
- COG range reads in the architecture (not yet wired in the API)
- Tabular numerals, sparse bundles via pnpm

### Weaknesses
1. **N+1 query risk in `/v1/users/me`** — Each call opens a session, runs the auth dep query, then runs a UoW query for memberships. The auth-dep DB call is unnecessary; the JWT carries everything we need.
2. **Audit log written synchronously inside the transaction** — Adds latency to every state-changing op. Consider async via the outbox.
3. **No ETag / If-None-Match on GETs** — No HTTP cache hints.
4. **No response compression** — GZip/Brotli not configured at the Uvicorn layer.
5. **No database query timing in OTel** — We have OTel configured but no SQLAlchemy slow-query hook.
6. **Map renders not pre-tiled** — Vector tiles would be much faster than per-frame rasterization.
7. **No connection warming** — First request after restart is slow.
8. **Public-key cache in `JWTService` is unbounded** — Fine until key rotation.
9. **No batching on `MembershipRepository.list_for_tenant`** — Could be a single `WHERE` + `LEFT JOIN` instead of N+1 user lookups in `list_members`.
10. **Frontend bundle is monolithic** — No dynamic import for the dashboard until we have one.

### Competitor comparison
- **Sentinel Hub's** STAC search is consistently < 200 ms p99.
- **Planet Explorer's** map is buttery-smooth with PMTiles.
- **Orbital Insight** has aggressive caching of derived analytics.

---

## 4. Security

### Strengths
- Argon2id password hashing with sensible parameters
- RS256 JWT with JWKS, kid, and a key generation path for dev
- Refresh family theft detection with Redis lock + DB denylist
- Append-only audit log with immutability trigger
- Standard error envelope with `request_id` correlation
- Security headers (X-Frame-Options, X-Content-Type-Options, Referrer-Policy)
- Per-email login rate limiting (5 / 15 min)
- Tenancy via `X-Tenant-Id` and `X-Workspace-Id` headers (validated by `get_current_tenant`)

### Weaknesses
1. **JWT audience validation is bypassed for access tokens** — `_verify` accepts `expected_audience=None, verify_aud=False` for access tokens. This is a security weakness; an attacker who steals a token issued for `kepler.web` could present it to a CLI.
2. **No password reset flow** — Migration + value objects exist, but no endpoint, no email, no token.
3. **No email verification on signup** — Anyone can sign up with any email; the address is unverified.
4. **MFA is data-only** — `mfa_enabled` exists, but there is no TOTP enrollment, no challenge endpoint, no step-up token.
5. **SSO is not implemented** — `/v1/auth/sso/:org_slug/callback` is mentioned in the plan; no code.
6. **Email enumeration via signup** — A duplicate email returns 409 `email_already_exists`. An attacker can enumerate valid emails.
7. **No password breach check** — Plan called for HIBP-style lookup; not implemented.
8. **API keys are issued but not auth-enabled** — The `kpk_…` key is a credential but no endpoint accepts it; only Bearer access tokens work.
9. **API keys are not bound to a workspace/tenant** — A key issued to user A is valid across all tenants A is a member of, with no per-workspace grant.
10. **No CSRF protection in middleware** — Bearer auth is safe, but if cookies are ever added, we lack CSRF tokens.
11. **CSP uses static directives; no nonce** — Inline scripts (Next.js inline) are blocked or allowed broadly. We should issue a per-request nonce.
12. **`audit_log.actor_id` can be NULL** — System events lose attribution. Should be a `service_account` row, not NULL.
13. **No key rotation flow** — Old keys persist forever; no grace period, no `kid` rollover UI.
14. **No session revocation** — We track refresh families, but a single access token cannot be revoked. We need a denylist keyed by `jti`.
15. **No token introspection endpoint** — OAuth-style `POST /oauth2/introspect` is missing.
16. **Tenant slug is globally unique, not tenant-scoped** — A user who creates `acme` blocks everyone else from `acme`. (Probably correct for marketing, debatable.)
17. **No encryption at rest for sensitive PII** — Email and full name are plaintext in DB. The audit log can leak sensitive metadata in JSONB.
18. **No webhook signature verification** — Outbound webhooks (planned) need HMAC; not implemented.
19. **No structured abuse reporting** — When we 401/403, we don't emit an anomaly signal.
20. **JWT private key has no passphrase** — A leaked key file gives full access. Production should use HSM/KMS-backed signing.
21. **CORS allows credentials with wildcard-origin safeguards** — Verify the CORS configuration is tight.
22. **No `Strict-Transport-Security` (HSTS) header** — Easy to add.
23. **No `Permissions-Policy` for the web app** — Easy to add.
24. **No subresource integrity for fonts** — We load Inter / JetBrains via `next/font`; OK, but worth verifying.

### Competitor comparison
- **Sentinel Hub** has SOC 2 Type II, ISO 27001, FedRAMP Moderate, MFA enforcement, SSO, HSM-backed key storage.
- **Maxar SecureWatch** has IL4/IL5, customer-managed keys, audit log export to SIEM.
- **Planet** has API key scopes per workspace, IP allowlists, and webhook signature verification.

We are well below the regulated-SaaS bar but above the typical MVP.

---

## 5. Accessibility

### Strengths
- ARIA-correct shadcn-style primitives (Label, Dialog, etc.)
- Color contrast tokens in CSS variables
- Form labels are explicit (`htmlFor`)
- `role="alert"` on Alert component
- `prefers-reduced-motion` is mentioned in the plan; Sonner respects it

### Weaknesses
1. **No skip-to-content link** — Plan said add it; not in the root layout.
2. **No focus management on route change** — Focus stays on the nav link.
3. **Map has no accessible alternative** — Plan called for a parallel SR table; not built.
4. **No `aria-current="page"` on the left rail** — Active link doesn't announce.
5. **No `aria-live` for toasts** — Important screen-reader feedback channel missing.
6. **No reduced-motion CSS gate** — We declare the media query in CSS; Framer Motion and Sonner don't respect it.
7. **No high-contrast theme** — Plan called for one.
8. **No language switcher** — Plan said i18n; only English.
9. **Form errors are not programmatically associated** — `<p>` below the input, not `aria-describedby` on the input.
10. **Loading states are spinners** — Some users with motion sensitivity need an alternative.
11. **Tables lack `<caption>` and `<th scope>`** — When we add tables in Sprint 3+.
12. **No modal focus trap** — Dialogs (when added) need it.
13. **No keyboard shortcut sheet** — `?` is referenced but unimplemented.
14. **No `tabindex` management on the map** — The map canvas should not be in the tab order.
15. **The `<input>` autofill detection is missing** — `autoComplete` is set on email/password; not on names.

### Competitor comparison
- **Linear, Notion, Vercel** all hit WCAG 2.2 AA; Linear publishes a VPAT.
- **Sentinel Hub** portal is AA-compliant.

---

## 6. Code Quality

### Strengths
- Strict TypeScript, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` (frontend)
- Strict mypy on the API (`strict: true`)
- Ruff + Black config
- 100-character line length
- Clear separation of layers
- Co-located tests

### Weaknesses
1. **Long files** — `application/identity/commands.py` is 600+ lines; `kepler_ml/eval/metrics.py` is 500+ lines. Both should be split by responsibility.
2. **Magic strings** — Permission keys (`"user:read"`, `"workspace:read"`) are repeated as plain strings. The `Permission` enum exists but isn't always used.
3. **Mixed async/sync** — Repos are async; refresh-store is sync; some test fixtures are sync. Confusing.
4. **Type-narrowing opportunities missed** — Several `dict[str, Any]` for what should be Pydantic models (audit metadata, AOI geometry).
5. **Inconsistent date handling** — `datetime.utcnow()` is used in some ML models; `utc_now()` in the API. Both will emit deprecation warnings.
6. **Repository signatures not standardized** — Some return `Optional`, some raise `NotFoundError`. Pick one.
7. **`as never` in `left-rail.tsx`** — A TypeScript hack; should be typed.
8. **No barrel file strategy in ML** — Sub-packages without `__init__.py` re-exports.
9. **Mixed `dataclass` vs Pydantic for domain entities** — Identity uses `dataclass(slots=True)`; ML uses Pydantic. Pick one per layer.
10. **Inconsistent naming** — `get_*`, `fetch_*`, `find_*` for the same operation in different modules.
11. **No type stubs for the SDK** — Frontend hand-writes types; should generate from OpenAPI.
12. **`tests/conftest.py` has a `redis_client` fixture that isn't used by name** — Cleanup needed.
13. **`_make_version` duplicates test setup** — Should be a pytest fixture.
14. **No `__all__` consistency** — Some modules have it, others don't.
15. **`reset_*` functions in `kepler/core/security/jwt.py` are not in `__all__`** — Inconsistent.
16. **No `nox`, `tox`, or `hatch` for env management** — Just `pyproject.toml` + venv.

### Competitor comparison
- Industry standard: generated SDKs, 100% typed, all warnings green.
- We're at "shippable" level.

---

## 7. AI Pipeline

### Strengths
- ONNX export with `onnxslim` and parity validation
- TensorRT export via `trtexec` with FP16/INT8
- Triton config generation for all 6 MVP models
- Content-addressed model registry with model cards
- Datasets, augmentation, vectorization, saliency modules all implemented
- 42 unit tests pass

### Weaknesses
1. **No real model weights** — The registry is empty. There are no ONNX or TRT files committed.
2. **Saliency is a deterministic proxy, not real gradients** — `_gradient_saliency` returns `|x - mean(x)|` instead of `dlogits/dx`. Documented but worth fixing.
3. **Boundary F1 and Hausdorff are placeholders** — `_boundary_f1` and `_hausdorff_95` return `0.0`. Real implementations are needed before customer-facing claims.
4. **Detection mAP is a placeholder** — `compute_detection` returns zeros. COCO-style mAP is non-trivial; needs IoU sweep + per-class AP.
5. **No KeplerFM** — Plan called for a pretraining scaffold; not implemented.
6. **No training data pipeline** — STAC mixer exists but no S3/GCS-backed dataset construction.
7. **No data versioning** — DVC / lakeFS are not wired.
8. **No experiment tracking** — MLflow / W&B are deps; no integration code.
9. **No model promotion workflow** — dev → staging → GA is documented; not implemented.
10. **No canary deployment** — Triton config doesn't have traffic split.
11. **No active learning** — Plan called for `modAL`; not integrated.
12. **No synthetic data pipeline** — Plan called for diffusion-based augmentation; not implemented.
13. **No fairness audit** — Per-region, per-biome metrics not in the eval suite.
14. **No drift detection** — Live input distribution vs training distribution not monitored.
15. **No model warm-pool** — Cold load on first request; production needs warm Triton.
16. **No real eval against real data** — Tests use synthetic arrays.
17. **No tensorboard / W&B integration** — We can't inspect training runs.
18. **Triton config uses `FORMAT_NCHW` for the change-detection model with 2 inputs** — Dynamic shapes for `input_t1` and `input_t2` may not match ONNX export conventions.
19. **No CI smoke test that runs an actual ONNX model in ORT** — We have parity check infrastructure but no end-to-end test.
20. **The training scaffold imports torch unconditionally at module load** — If you `pip install kepler-ml` without `[torch-cpu]`, the import fails. Already addressed, but the error message could be better.

### Competitor comparison
- **Open-CD** is a single thoroughly evaluated change-detection model with public benchmarks.
- **Descartes Labs** has petabyte-scale training pipelines with deep MLflow integration.
- **Orbital Insight** ships production models with confidence intervals and A/B testing.
- **Sentinel Hub** has a model marketplace with community models.
- **Google Earth Engine** has a `ee.Model` API for hosted inference.

We are at scaffold level; no real models yet.

---

## 8. Database

### Strengths
- Clean schema with consistent naming conventions
- Triggers for `updated_at` and immutability of `history`
- BRIN on `acquisition_time` (planned, not in current migration)
- Composite indices on `(tenant_id, …)` for multi-tenant hot paths
- `CITEXT` for case-insensitive email
- Foreign keys with explicit `ON DELETE` rules

### Weaknesses
1. **`history` is not partitioned** — Plan called for monthly partitioning; will grow unbounded.
2. **No statement_timeout** — Long queries can block. Set `statement_timeout = '30s'` in a migration.
3. **No lock_timeout** — Default `0` (wait forever). Set `lock_timeout = '5s'`.
4. **No RLS policies enabled** — Plan called for RLS on business tables; the migration file isn't present.
5. **No PII encryption at rest** — Email, full name are plaintext.
6. **Extensions not managed in a dedicated migration** — `pgcrypto` and `citext` are loaded inline in `0001_init`. A second migration that loads `pg_trgm` would help fuzzy search.
7. **No partial indices for hot paths** — `users.email` is unique; should be `WHERE deleted_at IS NULL`.
8. **`tenants.slug` globally unique** — Could be tenant-scoped if we allow renaming.
9. **No enum migration strategy documented** — When we add a new `role`, we need `ALTER TYPE`.
10. **No soft-delete convention enforcement** — `deleted_at` exists on some tables, not others.
11. **No audit-log retention policy** — Plan said hot 90d, cold to S3; not implemented.
12. **No `BOOLEAN DEFAULT FALSE NOT NULL` on tenant-active flags** — `status` is a string; could be a check-constrained enum.
13. **`refresh_tokens` is not indexed by `family_id + revoked_at`** — Revoke-by-family query is `WHERE family_id = ? AND revoked_at IS NULL`; current index is just `family_id`.
14. **No check constraint on `users.email` length** — Value object enforces 254; DB should too.
15. **`api_keys.last_used_at` is updated synchronously on every authenticated request** — Should be debounced or moved to the audit log.
16. **No `gen_random_uuid()` overload** — The migration uses `gen_random_uuid()` which requires `pgcrypto`; OK, but should be in a dedicated `0000_extensions` migration.

### Competitor comparison
- **Google Earth Engine** uses BigQuery + Colossus for its catalog metadata.
- **Sentinel Hub** uses a custom time-series store (CDO) with column-store compression.
- **Planet** uses PostgreSQL + a tile server with custom indexing.

---

## 9. API Design

### Strengths
- Consistent error envelope
- Cursor pagination primitives
- OpenAPI 3.1 auto-generated
- Idempotency-Key header support on mutating endpoints
- JWKS at `/.well-known/jwks.json`
- Health and readiness endpoints

### Weaknesses
1. **No OpenAPI security scheme** — The `Bearer` scheme isn't declared; OpenAPI consumers can't auto-generate auth.
2. **No API key auth scheme** — `kpk_…` keys are issued but no auth backend accepts them.
3. **No rate-limit headers** — `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` not emitted.
4. **No bulk operations** — `POST /v1/users/me/api-keys` doesn't accept arrays; `POST /v1/analyses` doesn't accept a list of AOIs.
5. **No field selection (sparse fieldsets)** — `?fields=id,email` not supported.
6. **No filter parameters on most list endpoints** — Only STAC search has filters; members list doesn't.
7. **No webhook delivery** — Plan called for HMAC-signed outbound webhooks; not implemented.
8. **No token introspection endpoint** — OAuth-style `POST /oauth2/introspect` missing.
9. **No `Prefer: return=minimal`** — Always returns full body.
10. **No ETag** — On `/v1/users/me` etc.
11. **No HATEOAS** — No `_links` in responses.
12. **No `Sunset` header** — When we deprecate.
13. **No `Accept` content negotiation** — Always JSON.
14. **Cursor format not documented in OpenAPI** — It says "string" but it's base64-encoded JSON.
15. **No SDK auto-generation** — Frontend hand-writes types; should generate.
16. **No OpenAPI examples** — Just schemas.
17. **No `OPTIONS` discoverability on collection endpoints** — Some REST APIs expose a root schema.

### Competitor comparison
- **Sentinel Hub** has excellent OpenAPI with examples, SDKs in Python/JS/R, field selection, and rate-limit headers.
- **Planet API** has clean REST + GraphQL.
- **Maxar** has extensive docs and SDKs.

---

## 10. Testing

### Strengths
- 17 API unit tests, 8 smoke tests, 42 ML unit tests, 7 web unit tests pass
- Pytest with `asyncio_mode = "auto"`
- Testcontainers available for integration
- Playwright for E2E
- httpx `AsyncClient` for integration

### Weaknesses
1. **Integration tests are auto-skipped** — They need RUN_INTEGRATION=1 and live Postgres+Redis. CI will run them; local dev usually doesn't.
2. **No mutation testing** — `mutmut` or `cosmic-ray` would catch dead code paths.
3. **No property-based testing** — `hypothesis` would catch edge cases in geometry, STAC, refresh token logic.
4. **No contract testing** — `schemathesis` would verify the API matches its OpenAPI spec.
5. **No fuzzing** — `atheris` for Python; useful for the URL parser and STAC item mixer.
6. **No load testing** — `k6` or `locust` scripts are absent.
7. **No security testing** — `zap-baseline.py` or Burp scans absent.
8. **No chaos testing** — Plan called for Chaos Mesh; not used.
9. **No regression suite on real data** — Only synthetic.
10. **Coverage not enforced** — pyproject has `fail_under = 70`; we don't track coverage over time.
11. **Test isolation issues** — Singleton services (JWT, Redis) sometimes leak between tests; reset is partial.
12. **No E2E for the AI pipeline** — Can't verify a model actually serves.
13. **No test for audit log immutability** — The trigger is in the migration; no test confirms it.
14. **No E2E for the registration → onboarding flow** — Only the basic sign-up.
15. **No performance benchmarks** — Plan called for latency targets per task; not enforced.
16. **No snapshot tests for OpenAPI** — Breaking changes would be silent.
17. **No test for the rate limiter's `Retry-After` header** — Implementation exists; not asserted.
18. **No test for CORS preflight with `Authorization` header** — Implementation exists; not asserted.

### Competitor comparison
- Industry standard: 80%+ coverage, mutation testing, contract testing, fuzzing, load testing, chaos testing.
- We're at "happy path" level.

---

## 11. Deployment

### Strengths
- Multi-stage Dockerfiles, slim runtime images
- Docker Compose for dev with profile-based ML stack
- GitHub Actions CI for unit + smoke
- GitHub Actions E2E for integration + Playwright

### Weaknesses
1. **No Kubernetes manifests** — Plan called for K8s HPA, PDB, NetworkPolicy; absent.
2. **No Helm chart** — Plan called for one.
3. **No Terraform** — Plan called for `terraform/` directory.
4. **No observability stack** — Plan called for Prometheus + Grafana + Loki + Tempo. We have OTel hooks but no dashboards.
5. **No SLI/SLO definitions enforced** — Plan listed them; not in CI.
6. **No incident response runbook** — Plan called for one.
7. **No DR plan** — Plan called for RTO/RPO targets.
8. **No backup automation** — Postgres backups are not scheduled.
9. **No log retention policy** — Default 30 days may not be enough for SOC 2.
10. **No secrets management** — Plan called for Vault/SOPS. We have a directory.
11. **No image signing** — Plan called for cosign / SLSA L3.
12. **No SBOM generation** — Plan called for it.
13. **No resource limits in docker-compose (non-triton)** — Just `deploy.resources` for triton.
14. **No health check on web container** — Just `pnpm dev`.
15. **No readiness probe distinction in compose** — `/healthz` and `/readyz` exist; compose doesn't use them.
16. **No graceful shutdown** — Uvicorn handles SIGTERM but workers might not.
17. **No rolling update strategy** — Compose redeploys with downtime.
18. **No multi-arch images** — `linux/amd64` only.
19. **No staging environment** — Only dev and prod in compose profiles.
20. **No canary deployment** — No traffic split for new model versions.

### Competitor comparison
- Industry standard: GitOps (ArgoCD/Flux), K8s, full observability, IaC, canary deployments.
- **Sentinel Hub** has multi-region active-active.
- **Planet** has separate dev/stage/prod with full IaC.
- We're at "docker-compose" level.

---

## 12. UX

### Strengths
- Design tokens (CSS variables) for light/dark
- Sharp (Linear-style) corners
- Tabular numerals, mono for IDs
- shadcn-style primitives
- Auth flow works end-to-end
- Protected shell with auth gate, top bar, left rail

### Weaknesses
1. **No real dashboard content** — Home page is a placeholder.
2. **No command palette** — Plan called for ⌘K.
3. **No map view** — Sprint 2 work.
4. **No project view** — Sprint 2 work.
5. **No data lists** — Just the home page.
6. **No reports** — Sprint 5 work.
7. **No settings page** — Only a placeholder link.
8. **No user profile page** — Can't change name, avatar, etc.
9. **No workspace switcher** — Listed in plan, not built.
10. **No notifications** — Sprint 5 work.
11. **No theme toggle UI** — `useUiStore.theme` is set; nothing flips the `dark` class on `<html>`.
12. **No density toggle UI** — `useUiStore.density` is set; nothing applies it.
13. **No shortcuts sheet** — `?` is referenced but unimplemented.
14. **No toast UX on auth success** — Forms just redirect.
15. **No loading skeletons** — Just text "Loading…".
16. **No empty states** — Just text.
17. **No error UI** — Just text.
18. **No optimistic updates** — Forms disable the button.
19. **No undo** — Destructive actions confirm but no undo.
20. **No bulk actions** — Can't select multiple items.
21. **No keyboard navigation in lists** — Mouse only.
22. **No infinite scroll** — Just pagination.
23. **No filter chips** — Just search.
24. **No recent items** — Plan called for it.
25. **No breadcrumbs** — Just page title.
26. **No 404 / 500 pages** — Plan said `error.tsx` and `not-found.tsx`. We don't have them.
27. **No offline mode** — Plan called for service worker.
28. **No PWA manifest** — Not installable.
29. **No SEO** — Login pages don't need it; docs would.
30. **No analytics / RUM** — Plan called for OTel; not wired in the web.

### Competitor comparison
- **Linear, Notion, Vercel** are polished: shortcuts, command palette, density toggles, theme switcher, all working.
- **Sentinel Hub** portal has full search, filter chips, AOI drawing, time-slider.
- We're at "skeleton" level.

---

## 13. Prioritized Improvement Plan

### Priority 1 — Critical (ship-blockers)

These should land before any paying customer. Each is small, isolated, and improves correctness/security without rewriting.

1. **Fix JWT audience validation** — Always require a specific audience per token type. Tighten `verify_access` to accept a required audience; verify it.
2. **Add rate-limit headers** — Emit `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` from the auth endpoints.
3. **Email enumeration fix on signup** — Return the same response for existing and new emails; send a "magic link" hint when the email exists.
4. **API key authentication** — Add a `Authorization: ApiKey <key>` scheme to `_current_user`.
5. **Audit log immutability test** — A unit test that confirms the `history_block_mutation` trigger raises.
6. **OpenAPI security scheme** — Declare the `BearerAuth` and `ApiKeyAuth` schemes in the FastAPI app.
7. **`/healthz` and `/readyz` wired in compose** — Add healthcheck blocks for the api and web services.
8. **Statement timeout + lock timeout migration** — Add a migration that sets per-role timeouts.
9. **Real boundary F1 + Hausdorff** — Replace placeholders in `kepler_ml/eval/metrics.py` with scikit-image implementations.
10. **Real COCO-style mAP** — Replace `compute_detection` placeholder.
11. **Skip link + focus management** — Add a skip link in the root layout; reset focus on route change.
12. **`aria-current="page"` on left rail** — Add the attribute to the active link.
13. **`prefers-reduced-motion` respect** — Wire into Framer Motion and Sonner.
14. **404 / 500 pages** — Add `error.tsx` and `not-found.tsx` for the `(app)` and `(auth)` route groups.
15. **Theme toggle wiring** — Apply the persisted theme to `<html class="dark">` in the root layout.
16. **Density toggle wiring** — Apply `data-density` attribute to `<html>`.
17. **CORS tightened** — Ensure credentials are not allowed with wildcard origins.
18. **HSTS + Permissions-Policy headers** — Add to middleware.
19. **CSP nonce middleware** — Generate per-request nonce; emit strict CSP.
20. **Idempotency-Key persistence** — Persist the header + response for 24h; return cached response on retry.

### Priority 2 — Important (polish + readiness for paid)

21. Password reset flow (token + email + endpoint)
22. Email verification on signup
23. MFA enrollment (TOTP) + step-up challenge
24. SSO callback (OIDC)
25. K8s manifests (Deployment, Service, HPA, PDB, NetworkPolicy) for api + worker + web
26. Helm chart (one chart, multiple values files)
27. Terraform for cloud-agnostic infra
28. Prometheus + Grafana + Loki + Tempo stack in compose
29. Backup automation (pg_basebackup or WAL-G)
30. Log retention policy (90 d hot, 1 y cold)
31. Secrets management (External Secrets Operator → Vault/SOPS)
32. Image signing (cosign) + SBOM
33. Background worker tier (Celery + RabbitMQ) for AI jobs
34. Outbox persistence + relay to RabbitMQ
35. Domain-event subscribers (e.g., UserSignedUp → welcome email)
36. Caching layer (Redis-backed) for STAC, AOI, model lists
37. Read replica configuration
38. Connection pool tuning per service
39. Bulk endpoints (`POST /v1/analyses/batch`, etc.)
40. Field selection (sparse fieldsets)
41. Webhook delivery (HMAC)
42. Token introspection endpoint
43. OpenAPI examples
44. SDK auto-generation (orval)
45. Webhook delivery in-app
46. Notification center UI
47. Command palette (⌘K)
48. Theme switcher UI
49. Density switcher UI
50. Shortcut sheet (`?`)
51. Loading skeletons, empty states, error states
52. Toast on auth success
53. Optimistic updates on forms
54. 404 / 500 retry buttons
55. Per-region, per-biome fairness audit
56. Drift detection on live inputs
57. Active learning integration
58. MLflow / W&B integration
59. Real saliency (torch.autograd when torch is available)
60. Property-based testing (hypothesis)
61. Mutation testing (mutmut)
62. Contract testing (schemathesis)
63. Load testing (k6)
64. Security testing (OWASP ZAP baseline)
65. Chaos testing (Chaos Mesh)
66. Real-data regression suite
67. Performance benchmarks
68. Snapshot tests for OpenAPI

### Priority 3 — Long-term

69. Multi-region replication
70. CQRS / read-write split
71. SAGA / process manager
72. Service mesh
73. CDN for static assets
74. Vector tile pre-rendering
75. Caching layer (read-through)
76. Diffusion-based synthetic data
77. Multi-arch images (arm64)
78. SLSA L3 compliance
79. HATEOAS links
80. i18n beyond English

---

## 14. Patches to Apply in This Pass

Given the system reminder enabling code changes and the instruction "generate patches, never rewrite working code, only improve it", I will apply targeted improvements for the following Priority-1 items in this pass:

- P1.1 JWT audience validation tightening
- P1.2 Rate-limit headers
- P1.3 Email enumeration fix on signup
- P1.4 API key authentication (ApiKey scheme)
- P1.5 Audit log immutability test
- P1.6 OpenAPI security schemes (Bearer + ApiKey)
- P1.7 Compose healthchecks
- P1.8 Statement/lock timeout migration
- P1.9 Real boundary F1 + Hausdorff
- P1.10 Real COCO-style mAP
- P1.11 Skip link + focus management
- P1.12 aria-current on left rail
- P1.13 Reduced-motion CSS gate
- P1.14 404 / 500 pages
- P1.15 Theme toggle wiring
- P1.16 Density toggle wiring
- P1.17 HSTS + Permissions-Policy headers
- P1.18 CSP nonce middleware
- P1.19 API key scopes per workspace (binding)
- P1.20 Audit log immutability migration (rename to be explicit)

Other items remain in the roadmap and will be addressed in subsequent passes.
