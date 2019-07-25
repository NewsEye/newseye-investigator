"""proper structure of foreign keys

Revision ID: 0c6e8efa05f7
Revises: fd6994125112
Create Date: 2019-07-24 09:01:46.421024

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0c6e8efa05f7'
down_revision = 'fd6994125112'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('tasks_result_id_fkey', 'tasks', type_='foreignkey')
    op.drop_constraint('tasks_report_id_fkey', 'tasks', type_='foreignkey')
    op.drop_column('tasks', 'report_id')
    op.drop_column('tasks', 'result_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('tasks', sa.Column('result_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('tasks', sa.Column('report_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key('tasks_report_id_fkey', 'tasks', 'reports', ['report_id'], ['id'])
    op.create_foreign_key('tasks_result_id_fkey', 'tasks', 'results', ['result_id'], ['id'])
    # ### end Alembic commands ###