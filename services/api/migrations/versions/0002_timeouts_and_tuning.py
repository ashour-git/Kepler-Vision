"""Per-role statement and lock timeouts.

Sets safe defaults for the application role. Adjusts autovacuum tuning
for high-write tables. Idempotent.

Revision ID: 0002_timeouts_and_tuning
Revises: 0001_init
Create Date: 2026-07-18
"""

from __future__ import annotations

from alembic import op

revision = "0002_timeouts_and_tuning"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The default `kepler` role is created by the docker-compose init
    # script. We attach statement and lock timeouts to it. These are
    # applied per-session unless overridden.
    op.execute("ALTER ROLE kepler SET statement_timeout = '30s'")
    op.execute("ALTER ROLE kepler SET lock_timeout = '5s'")
    op.execute("ALTER ROLE kepler SET idle_in_transaction_session_timeout = '60s'")
    # Reasonable default for the API role's statement timeout when ad-hoc
    # queries (e.g., psql) are run.
    op.execute("ALTER ROLE kepler SET client_min_messages = 'WARNING'")

    # Autovacuum tuning for `history` (append-only, high churn).
    op.execute(
        """
        ALTER TABLE history SET (
            autovacuum_vacuum_scale_factor = 0.05,
            autovacuum_analyze_scale_factor = 0.02,
            autovacuum_vacuum_cost_limit = 2000
        )
        """
    )
    # autovacuum_vacuum_scale_factor = 0.05 means vacuum triggers at 5% dead
    # tuples (default 20% is too lazy for append-mostly tables).
    op.execute(
        """
        ALTER TABLE refresh_tokens SET (
            autovacuum_vacuum_scale_factor = 0.1,
            autovacuum_analyze_scale_factor = 0.05
        )
        """
    )
    op.execute(
        """
        ALTER TABLE api_keys SET (
            autovacuum_vacuum_scale_factor = 0.1,
            autovacuum_analyze_scale_factor = 0.05
        )
        """
    )

    # Add a BRIN index on `history.created_at` for time-range scans.
    op.execute("CREATE INDEX IF NOT EXISTS ix_history_created_brin ON history USING BRIN (created_at)")

    # Add a partial unique index on users.email WHERE deleted_at IS NULL.
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_active ON users (email) WHERE deleted_at IS NULL")

    # Add a composite index on refresh_tokens(family_id, revoked_at)
    # for revoke-by-family scans.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_family_revoked ON refresh_tokens (family_id, revoked_at)"
    )


def downgrade() -> None:
    op.execute("ALTER ROLE kepler RESET statement_timeout")
    op.execute("ALTER ROLE kepler RESET lock_timeout")
    op.execute("ALTER ROLE kepler RESET idle_in_transaction_session_timeout")
    op.execute("ALTER ROLE kepler RESET client_min_messages")
    op.execute("DROP INDEX IF EXISTS ix_history_created_brin")
    op.execute("DROP INDEX IF EXISTS uq_users_email_active")
    op.execute("DROP INDEX IF EXISTS ix_refresh_tokens_family_revoked")
