from datetime import datetime

import pytz
from f3_data_models.utils import get_session
from sqlalchemy import text

from utilities.database.orm.paxminer import get_pm_engine
from utilities.database.paxminer_migration import run_paxminer_migration


def check_and_run_paxminer_migration():
    check_paxminer_sql = """
    select ss.settings->'org_id' as org_id, ss.workspace_name, ss.settings->>'paxminer_schema' as paxminer_schema
    from slack_spaces ss
    inner join orgs_x_slack_spaces oxss
    on ss.id = oxss.slack_space_id
    left join
    (select e.region_org_id, e.region_name,
        max(case when e.meta->>'source'='paxminer_import' then 1 else 0 end) as paxminer_migrated_ind,
        count(*) as event_count
    from event_instance_expanded e
    group by 1,2) e
    on oxss.org_id = e.region_org_id
    where coalesce(e.paxminer_migrated_ind, 0) = 0
        and ss.settings->>'paxminer_schema' is not null
        and ss.settings->>'migration_date' <= CURRENT_DATE::text
    ;
    """
    current_hour = datetime.now(pytz.timezone("US/Central")).hour
    if current_hour == 23:
        print("Starting Paxminer migration checks...")
        migrated_paxminer_schemas = set()
        with get_session() as session:
            result = session.execute(text(check_paxminer_sql))
            orgs_to_migrate = result.fetchall()
            for row in orgs_to_migrate:
                org_id = row["org_id"]
                workspace_name = row["workspace_name"]
                print(f"Running Paxminer migration for org_id: {org_id}, workspace: {workspace_name}")
                try:
                    run_paxminer_migration(org_id=org_id)
                    migrated_paxminer_schemas.add(row["paxminer_schema"])
                    print(f"Successfully completed Paxminer migration for org_id: {org_id}")
                except Exception as e:
                    print(f"Error during Paxminer migration for org_id: {org_id}: {e}")
        if migrated_paxminer_schemas:
            engine = get_pm_engine(schema="paxminer")
            with engine.connect() as conn:
                for schema in migrated_paxminer_schemas:
                    try:
                        conn.execute(
                            f"update regions set active = 0, scrape_backblasts = 0, send_pax_charts = 0, send_ao_leaderboard = 0, send_q_charts = 0, send_region_leaderboard = 0 where schema_name = '{schema}';"  # noqa
                        )
                        print(f"Deactivated Paxminer schema: {schema}")
                    except Exception as e:
                        print(f"Error deactivating Paxminer schema {schema}: {e}")
        print("Paxminer migration checks complete.")
