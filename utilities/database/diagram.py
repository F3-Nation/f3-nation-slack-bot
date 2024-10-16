import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from sqlalchemy_schemadisplay import create_schema_graph

from utilities.database import get_engine
from utilities.database.orm import BaseClass


def create_diagram():
    graph = create_schema_graph(
        engine=get_engine(),
        metadata=BaseClass.metadata,
        show_datatypes=True,
        show_indexes=True,
        rankdir="LR",
        show_column_keys=True,
    )
    graph.write_png("utilities/database/schema.png")


if __name__ == "__main__":
    create_diagram()
