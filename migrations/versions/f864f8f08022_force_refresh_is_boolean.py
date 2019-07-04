"""force refresh is boolean

Revision ID: f864f8f08022
Revises: 3b8dc8150ff2
Create Date: 2019-06-26 11:20:17.077109

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f864f8f08022'
down_revision = '3b8dc8150ff2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('tasks', 'force_refresh')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('tasks', sa.Column('force_refresh', sa.VARCHAR(length=255), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
