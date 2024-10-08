"""generalize org_x_slack

Revision ID: 31c60a870c78
Revises: 46155d043b4c
Create Date: 2024-09-30 06:20:24.771746

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "31c60a870c78"
down_revision: Union[str, None] = "46155d043b4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.rename_table("orgs_x_slack_spaces", "orgs_x_slack")
    op.alter_column("orgs_x_slack", "slack_space_team_id", new_column_name="slack_id")
    op.drop_constraint("orgs_x_slack_spaces_slack_space_team_id_fkey", "orgs_x_slack", type_="foreignkey")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("orgs_x_slack", "slack_id", new_column_name="slack_space_team_id")
    op.rename_table("orgs_x_slack", "orgs_x_slack_spaces")
    op.create_foreign_key(
        "orgs_x_slack_spaces_slack_space_team_id_fkey", "orgs_x_slack", "slack_spaces", ["slack_id"], ["team_id"]
    )
    # ### end Alembic commands ###
