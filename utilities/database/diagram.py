import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from f3_data_models.models import Base
from f3_data_models.utils import get_engine
from sqlalchemy_schemadisplay import create_schema_graph


def create_diagram():
    graph = create_schema_graph(
        engine=get_engine(),
        metadata=Base.metadata,
        show_datatypes=True,
        show_indexes=True,
        rankdir="LR",
        show_column_keys=True,
    )
    graph.write_png("utilities/database/schema.png")


if __name__ == "__main__":
    create_diagram()
