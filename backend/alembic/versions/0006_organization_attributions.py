"""Add versioned offer-level organization attributions."""

import sqlalchemy as sa
from alembic import op


revision = "0006"
down_revision = "0005"


def upgrade():
    if sa.inspect(op.get_bind()).has_table("organization_attributions"):
        return
    op.create_table(
        "organization_attributions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("listing_id", sa.Uuid(), sa.ForeignKey("listings.id"), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("extractor_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("academic_units", sa.JSON(), nullable=False),
        sa.Column("project_partners", sa.JSON(), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("listing_id", "content_hash", "extractor_version"),
    )
    op.create_index("ix_organization_attributions_listing_id", "organization_attributions", ["listing_id"])
    op.create_index("ix_organization_attributions_content_hash", "organization_attributions", ["content_hash"])


def downgrade():
    op.drop_index("ix_organization_attributions_content_hash", table_name="organization_attributions")
    op.drop_index("ix_organization_attributions_listing_id", table_name="organization_attributions")
    op.drop_table("organization_attributions")
