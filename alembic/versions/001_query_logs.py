"""create query_logs table

Revision ID: 001_query_logs
Revises:
Create Date: 2026-05-02
"""

from alembic import op
import sqlalchemy as sa

revision = "001_query_logs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "query_logs",
        sa.Column( "id", sa.UUID(), server_default=sa.text( "gen_random_uuid()" ), primary_key=True ),
        sa.Column( "request_id", sa.UUID(), nullable=False ),
        sa.Column( "store_id", sa.String( 50 ), nullable=False ),
        sa.Column( "user_id", sa.String( 100 ), nullable=True ),
        sa.Column( "session_id", sa.String( 100 ), nullable=False ),
        sa.Column( "client_session_id", sa.String( 100 ), nullable=True ),
        sa.Column( "query", sa.Text(), nullable=False ),
        sa.Column( "intent", sa.String( 20 ), nullable=False ),
        sa.Column( "domain", sa.String( 30 ), server_default="mobile", nullable=False ),
        sa.Column( "applied_filters", sa.JSON(), nullable=True ),
        sa.Column( "result_count", sa.Integer(), server_default="0", nullable=False ),
        sa.Column( "response_status", sa.String( 10 ), nullable=False, default="success" ),
        sa.Column( "latency_ms", sa.Integer(), nullable=False, default=0 ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP( timezone=True ),
            server_default=sa.text( "NOW()" ),
            nullable=False,
        ),
    )

    # ایندکس‌های ضروری برای آنالیتیکس سریع
    op.create_index( "idx_query_logs_store_time", "query_logs", [ "store_id", sa.text( "created_at DESC" ) ] )
    op.create_index( "idx_query_logs_user", "query_logs", [ "user_id" ] )
    op.create_index( "idx_query_logs_intent", "query_logs", [ "intent" ] )


def downgrade() -> None:
    op.drop_index( "idx_query_logs_intent", table_name="query_logs" )
    op.drop_index( "idx_query_logs_user", table_name="query_logs" )
    op.drop_index( "idx_query_logs_store_time", table_name="query_logs" )
    op.drop_table( "query_logs" )
