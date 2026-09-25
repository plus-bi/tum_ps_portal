"""Add pdf_profile_extractions for LLM project-profile results."""

import sqlalchemy as sa
from alembic import op


revision = "0004"
down_revision = "0003"


def upgrade():
    # 0001 runs create_all from the current models, so a fresh database already has the table.
    if sa.inspect(op.get_bind()).has_table("pdf_profile_extractions"):
        return
    op.create_table(
        "pdf_profile_extractions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("model_deployment", sa.String(120), nullable=False),
        sa.Column("reasoning_effort", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False),
        sa.Column("coverage", sa.JSON(), nullable=True),
        sa.Column("evidence_issues", sa.JSON(), nullable=False),
        sa.Column("document", sa.JSON(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pdf_profile_extractions_content_hash", "pdf_profile_extractions", ["content_hash"])


def downgrade():
    op.drop_index("ix_pdf_profile_extractions_content_hash", table_name="pdf_profile_extractions")
    op.drop_table("pdf_profile_extractions")
