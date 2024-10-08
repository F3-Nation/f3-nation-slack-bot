"""remove slack_id from org

Revision ID: 7b27e4a83947
Revises: 31c60a870c78
Create Date: 2024-09-30 06:50:47.937074

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b27e4a83947"
down_revision: Union[str, None] = "31c60a870c78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("orgs", "slack_id")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("orgs", sa.Column("slack_id", sa.VARCHAR(length=30), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
