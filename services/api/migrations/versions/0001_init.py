"""initial identity tables

Revision ID: 0001_init
Revises:
Create Date: 2026-07-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB, UUID

# revision identifiers, used by Alembic.
revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Required extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # --- tenants -----------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("plan", sa.String(32), nullable=False, server_default=sa.text("'free'")),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("region", sa.String(64), nullable=False, server_default=sa.text("'us-central1'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("slug", name="tenants_slug_unique"),
        sa.CheckConstraint("plan IN ('free','pro','enterprise','gov')", name="tenants_plan_check"),
        sa.CheckConstraint("status IN ('active','suspended','deleted')", name="tenants_status_check"),
    )
    op.create_index("ix_tenants_status", "tenants", ["status"])

    # --- users -------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", CITEXT(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("locale", sa.String(16), nullable=False, server_default=sa.text("'en'")),
        sa.Column("timezone", sa.String(64), nullable=False, server_default=sa.text("'UTC'")),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mfa_secret_enc", sa.LargeBinary(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("last_sign_in_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active','invited','disabled','deleted')", name="users_status_check"
        ),
    )
    op.create_index("ix_users_status", "users", ["status"])
    op.create_index("ix_users_last_sign_in_at", "users", ["last_sign_in_at"])

    # --- memberships -------------------------------------------------------
    op.create_table(
        "memberships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default=sa.text("'member'")),
        sa.Column("invited_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("accepted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "tenant_id", name="memberships_user_tenant_unique"),
        sa.CheckConstraint(
            "role IN ('owner','admin','member','analyst','viewer','billing_admin','service')",
            name="memberships_role_check",
        ),
    )
    op.create_index("ix_memberships_tenant_role", "memberships", ["tenant_id", "role"])
    op.create_index("ix_memberships_user", "memberships", ["user_id"])

    # --- api_keys ----------------------------------------------------------
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("scopes", sa.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('active','revoked')", name="api_keys_status_check"),
    )
    op.create_index("ix_api_keys_user", "api_keys", ["user_id"])

    # --- refresh_tokens ----------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("family_id", UUID(as_uuid=True), nullable=False),
        sa.Column("jti", sa.String(64), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_prefix", sa.String(64), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("family_revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_refresh_tokens_user", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family", "refresh_tokens", ["family_id"])
    op.create_index("ix_refresh_tokens_jti", "refresh_tokens", ["jti"])

    # --- history (append-only audit) ---------------------------------------
    op.create_table(
        "history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_type", sa.String(32), nullable=False, server_default=sa.text("'user'")),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ip", INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("actor_type IN ('user','service','system')", name="history_actor_type_check"),
    )
    op.create_index("ix_history_tenant_created", "history", ["tenant_id", "created_at"])
    op.create_index("ix_history_actor", "history", ["actor_id", "created_at"])
    op.create_index("ix_history_resource", "history", ["resource_type", "resource_id", "created_at"])
    op.create_index("ix_history_action", "history", ["action", "created_at"])

    # Triggers: history is append-only.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION history_block_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'history table is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER history_no_update
        BEFORE UPDATE ON history
        FOR EACH ROW EXECUTE FUNCTION history_block_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER history_no_delete
        BEFORE DELETE ON history
        FOR EACH ROW EXECUTE FUNCTION history_block_mutation();
        """
    )

    # Trigger: keep `updated_at` fresh on row updates.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in ("tenants", "users", "memberships", "api_keys", "refresh_tokens"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            """
        )


def downgrade() -> None:
    for table in ("tenants", "users", "memberships", "api_keys", "refresh_tokens"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.execute("DROP TRIGGER IF EXISTS history_no_update ON history")
    op.execute("DROP TRIGGER IF EXISTS history_no_delete ON history")
    op.execute("DROP FUNCTION IF EXISTS history_block_mutation()")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")

    op.drop_index("ix_history_action", table_name="history")
    op.drop_index("ix_history_resource", table_name="history")
    op.drop_index("ix_history_actor", table_name="history")
    op.drop_index("ix_history_tenant_created", table_name="history")
    op.drop_table("history")

    op.drop_index("ix_refresh_tokens_jti", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_family", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_api_keys_user", table_name="api_keys")
    op.drop_table("api_keys")

    op.drop_index("ix_memberships_user", table_name="memberships")
    op.drop_index("ix_memberships_tenant_role", table_name="memberships")
    op.drop_table("memberships")

    op.drop_index("ix_users_last_sign_in_at", table_name="users")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_tenants_status", table_name="tenants")
    op.drop_table("tenants")
