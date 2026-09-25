"""Add review_flags to pdf_profile_extractions."""

import sqlalchemy as sa
from alembic import op


revision = "0005"
down_revision = "0004"


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("pdf_profile_extractions")}
    if "review_flags" not in columns:  # 0001/0004 create the table from the current models on a fresh database
        op.add_column("pdf_profile_extractions",
                      sa.Column("review_flags", sa.JSON(), nullable=False, server_default="[]"))


def downgrade():
    op.drop_column("pdf_profile_extractions", "review_flags")
