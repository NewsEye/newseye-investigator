"""input/output type column for task table

Revision ID: 379765a68592
Revises: 15d2172622b3
Create Date: 2019-08-08 15:03:43.876808

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '379765a68592'
down_revision = '15d2172622b3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('tasks', sa.Column('input_type', sa.String(length=255), nullable=True))
    op.add_column('tasks', sa.Column('output_type', sa.String(length=255), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('tasks', 'output_type')
    op.drop_column('tasks', 'input_type')
    # ### end Alembic commands ###
