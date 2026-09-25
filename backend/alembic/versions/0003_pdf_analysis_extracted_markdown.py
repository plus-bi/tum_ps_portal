"""Add extracted markdown pages to pdf_analysis."""

import sqlalchemy as sa
from alembic import op


revision = "0003"
down_revision = "0002"


def upgrade():
    op.add_column("pdf_analysis", sa.Column("extracted_markdown_pages", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("pdf_analysis", "extracted_markdown_pages")
