"""Add stable public reference codes to listings."""

import sqlalchemy as sa
from alembic import op


revision = "0002"
down_revision = "0001"


def upgrade():
    op.add_column("listings", sa.Column("reference_code", sa.String(length=20), nullable=True))
    op.execute("""
        WITH ranked AS (
            SELECT id,
                   CASE WHEN normalized->>'opportunity_type' = 'idp' THEN 'idp' ELSE 'ps' END AS prefix,
                   row_number() OVER (
                       PARTITION BY CASE WHEN normalized->>'opportunity_type' = 'idp' THEN 'idp' ELSE 'ps' END
                       ORDER BY first_seen_at, id
                   ) AS serial
            FROM listings
        )
        UPDATE listings
        SET reference_code = ranked.prefix || '-' || lpad(ranked.serial::text, 3, '0')
        FROM ranked
        WHERE listings.id = ranked.id
    """)
    op.alter_column("listings", "reference_code", nullable=False)
    op.create_index("ix_listings_reference_code", "listings", ["reference_code"], unique=True)


def downgrade():
    op.drop_index("ix_listings_reference_code", table_name="listings")
    op.drop_column("listings", "reference_code")
