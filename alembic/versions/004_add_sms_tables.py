"""Add SMS Follow-up System tables

Revision ID: 004
Revises: 003
Create Date: 2024-10-27 06:39:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create SMS status enum
    sms_status_enum = postgresql.ENUM(
        'pending', 'sent', 'delivered', 'failed', 'undelivered',
        name='smsstatus',
        create_type=False
    )
    sms_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create SMS type enum
    sms_type_enum = postgresql.ENUM(
        'followup', 'reminder', 'confirmation', 'feedback',
        name='smstype',
        create_type=False
    )
    sms_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Create response sentiment enum
    response_sentiment_enum = postgresql.ENUM(
        'positive', 'neutral', 'negative', 'interested', 'not_interested',
        name='responsesentiment',
        create_type=False
    )
    response_sentiment_enum.create(op.get_bind(), checkfirst=True)
    
    # Create sms_messages table
    op.create_table(
        'sms_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sms_sid', sa.String(100), nullable=False, unique=True),
        sa.Column('message_type', sms_type_enum, nullable=False),
        sa.Column('from_number', sa.String(20), nullable=False),
        sa.Column('to_number', sa.String(20), nullable=False),
        sa.Column('message_body', sa.Text(), nullable=False),
        sa.Column('status', sms_status_enum, nullable=False, server_default='pending'),
        sa.Column('related_call_id', sa.Integer(), nullable=True),
        sa.Column('related_lead_id', sa.Integer(), nullable=True),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('segments', sa.Integer(), server_default='1'),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sms_messages_sms_sid', 'sms_messages', ['sms_sid'])
    op.create_index('ix_sms_messages_to_number', 'sms_messages', ['to_number'])
    op.create_index('ix_sms_messages_status', 'sms_messages', ['status'])
    op.create_index('ix_sms_messages_related_call_id', 'sms_messages', ['related_call_id'])
    op.create_index('ix_sms_messages_related_lead_id', 'sms_messages', ['related_lead_id'])
    
    # Create sms_responses table
    op.create_table(
        'sms_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_sid', sa.String(100), nullable=False, unique=True),
        sa.Column('original_message_id', sa.Integer(), nullable=False),
        sa.Column('from_number', sa.String(20), nullable=False),
        sa.Column('to_number', sa.String(20), nullable=False),
        sa.Column('response_body', sa.Text(), nullable=False),
        sa.Column('sentiment', response_sentiment_enum, nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('intent', sa.String(100), nullable=True),
        sa.Column('keywords', sa.Text(), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['original_message_id'], ['sms_messages.id'])
    )
    op.create_index('ix_sms_responses_message_sid', 'sms_responses', ['message_sid'])
    op.create_index('ix_sms_responses_original_message_id', 'sms_responses', ['original_message_id'])
    
    # Create sms_campaigns table
    op.create_table(
        'sms_campaigns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('message_template', sa.Text(), nullable=False),
        sa.Column('trigger_event', sa.String(50), nullable=False),
        sa.Column('delay_seconds', sa.Integer(), server_default='300'),
        sa.Column('total_sent', sa.Integer(), server_default='0'),
        sa.Column('total_delivered', sa.Integer(), server_default='0'),
        sa.Column('total_responses', sa.Integer(), server_default='0'),
        sa.Column('response_rate', sa.Float(), server_default='0.0'),
        sa.Column('active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create call_sms_correlation table
    op.create_table(
        'call_sms_correlation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('call_id', sa.Integer(), nullable=False),
        sa.Column('sms_message_id', sa.Integer(), nullable=False),
        sa.Column('sms_response_id', sa.Integer(), nullable=True),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('call_to_sms_delay_seconds', sa.Integer(), nullable=True),
        sa.Column('response_time_seconds', sa.Integer(), nullable=True),
        sa.Column('conversion', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sms_message_id'], ['sms_messages.id']),
        sa.ForeignKeyConstraint(['sms_response_id'], ['sms_responses.id'])
    )
    op.create_index('ix_call_sms_correlation_call_id', 'call_sms_correlation', ['call_id'])
    op.create_index('ix_call_sms_correlation_sms_message_id', 'call_sms_correlation', ['sms_message_id'])
    op.create_index('ix_call_sms_correlation_lead_id', 'call_sms_correlation', ['lead_id'])
    
    # Create sms_analytics table
    op.create_table(
        'sms_analytics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('total_sent', sa.Integer(), server_default='0'),
        sa.Column('total_delivered', sa.Integer(), server_default='0'),
        sa.Column('total_failed', sa.Integer(), server_default='0'),
        sa.Column('total_responses', sa.Integer(), server_default='0'),
        sa.Column('response_rate', sa.Float(), server_default='0.0'),
        sa.Column('positive_responses', sa.Integer(), server_default='0'),
        sa.Column('negative_responses', sa.Integer(), server_default='0'),
        sa.Column('neutral_responses', sa.Integer(), server_default='0'),
        sa.Column('conversions', sa.Integer(), server_default='0'),
        sa.Column('conversion_rate', sa.Float(), server_default='0.0'),
        sa.Column('total_cost', sa.Float(), server_default='0.0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sms_analytics_date', 'sms_analytics', ['date'])


def downgrade() -> None:
    op.drop_index('ix_sms_analytics_date', table_name='sms_analytics')
    op.drop_table('sms_analytics')
    
    op.drop_index('ix_call_sms_correlation_lead_id', table_name='call_sms_correlation')
    op.drop_index('ix_call_sms_correlation_sms_message_id', table_name='call_sms_correlation')
    op.drop_index('ix_call_sms_correlation_call_id', table_name='call_sms_correlation')
    op.drop_table('call_sms_correlation')
    
    op.drop_table('sms_campaigns')
    
    op.drop_index('ix_sms_responses_original_message_id', table_name='sms_responses')
    op.drop_index('ix_sms_responses_message_sid', table_name='sms_responses')
    op.drop_table('sms_responses')
    
    op.drop_index('ix_sms_messages_related_lead_id', table_name='sms_messages')
    op.drop_index('ix_sms_messages_related_call_id', table_name='sms_messages')
    op.drop_index('ix_sms_messages_status', table_name='sms_messages')
    op.drop_index('ix_sms_messages_to_number', table_name='sms_messages')
    op.drop_index('ix_sms_messages_sms_sid', table_name='sms_messages')
    op.drop_table('sms_messages')
    
    # Drop enums
    sa.Enum(name='responsesentiment').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='smstype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='smsstatus').drop(op.get_bind(), checkfirst=True)
