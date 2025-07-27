import os
from dataclasses import dataclass
from typing import List, Tuple, TypeVar

import pg8000
import sqlalchemy
from f3_data_models.models import Base
from google.cloud.sql.connector import Connector, IPTypes
from sqlalchemy import and_

# from sqlalchemy.dialects.mysql import insert
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from utilities import constants


@dataclass
class DatabaseField:
    name: str
    value: object = None


GLOBAL_ENGINE = None
GLOBAL_SESSION = None
GLOBAL_SCHEMA = None


def get_engine(echo=False, schema=None, paxminer_db=True) -> Engine:
    if paxminer_db:
        host = os.environ[constants.PAXMINER_DATABASE_HOST]
        user = os.environ[constants.PAXMINER_DATABASE_USER]
        passwd = os.environ[constants.PAXMINER_DATABASE_PASSWORD]
        database = schema or os.environ[constants.PAXMINER_DATABASE_SCHEMA]
        db_url = f"mysql+pymysql://{user}:{passwd}@{host}:3306/{database}?charset=utf8mb4"
        engine = sqlalchemy.create_engine(db_url, echo=echo)
        return engine
    else:
        host = os.environ[constants.DATABASE_HOST]
        user = os.environ[constants.ADMIN_DATABASE_USER]
        passwd = os.environ[constants.ADMIN_DATABASE_PASSWORD]
        database = schema or os.environ[constants.ADMIN_DATABASE_SCHEMA]
        # db_url = f"mysql+pymysql://{user}:{passwd}@{host}:3306/{database}?charset=utf8mb4"
        # db_url = f"postgresql://{user}:{passwd}@{host}:5432/{database}"

        # engine = sqlalchemy.create_engine(
        #     sqlalchemy.engine.url.URL.create(
        #         drivername="postgresql+pg8000",
        #         username=user,
        #         password=passwd,
        #         database=database,
        #         query={"unix_sock": f"{host}/.s.PGSQL.5432"},
        #     ),
        # )

        if constants.LOCAL_DEVELOPMENT:
            db_url = f"postgresql://{user}:{passwd}@{host}:5432/{database}"
            engine = sqlalchemy.create_engine(db_url, echo=echo)
        else:
            connector = Connector()

            def get_connection():
                conn: pg8000.dbapi.Connection = connector.connect(
                    instance_connection_string=host,
                    driver="pg8000",
                    user=user,
                    password=passwd,
                    db=database,
                    ip_type=IPTypes.PUBLIC,
                )
                return conn

            engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=get_connection, echo=echo)
        return engine


def get_session(echo=False, schema=None, paxminer_db=True):
    if GLOBAL_SESSION:
        return GLOBAL_SESSION

    global GLOBAL_ENGINE, GLOBAL_SCHEMA
    if schema != GLOBAL_SCHEMA or not GLOBAL_ENGINE:
        GLOBAL_ENGINE = get_engine(echo=echo, schema=schema)
        GLOBAL_SCHEMA = schema or os.environ[constants.ADMIN_DATABASE_SCHEMA]
    return sessionmaker()(bind=GLOBAL_ENGINE)


def close_session(session):
    global GLOBAL_SESSION, GLOBAL_ENGINE
    if GLOBAL_SESSION == session:
        if GLOBAL_ENGINE:
            GLOBAL_ENGINE.close()
            GLOBAL_SESSION = None


T = TypeVar("T")


class DbManager:
    def get_record(cls: T, id, schema=None) -> T:
        session = get_session(schema=schema)
        try:
            x = session.query(cls).filter(cls.get_id() == id).first()
            if x:
                session.expunge(x)
            return x
        finally:
            session.rollback()
            close_session(session)

    def find_records(cls: T, filters, schema=None) -> List[T]:
        session = get_session(schema=schema)
        try:
            records = session.query(cls).filter(and_(*filters)).all()
            for r in records:
                session.expunge(r)
            return records
        finally:
            session.rollback()
            close_session(session)

    def find_join_records2(left_cls: T, right_cls: T, filters, schema=None) -> List[Tuple[T]]:
        session = get_session(schema=schema)
        try:
            records = session.query(left_cls, right_cls).join(right_cls).filter(and_(*filters)).all()
            session.expunge_all()
            return records
        finally:
            session.rollback()
            close_session(session)

    def find_join_records3(
        left_cls: T, right_cls1: T, right_cls2: T, filters, schema=None, left_join=False
    ) -> List[Tuple[T]]:
        session = get_session(schema=schema)
        try:
            records = (
                session.query(left_cls, right_cls1, right_cls2)
                .select_from(left_cls)
                .join(right_cls1, isouter=left_join)
                .join(right_cls2, isouter=left_join)
                .filter(and_(*filters))
                .all()
            )
            session.expunge_all()
            return records
        finally:
            session.rollback()
            close_session(session)

    def update_record(cls: T, id, fields, schema=None):
        session = get_session(schema=schema)
        try:
            session.query(cls).filter(cls.get_id() == id).update(fields, synchronize_session="fetch")
            session.flush()
        finally:
            session.commit()
            close_session(session)

    def update_records(cls: T, filters, fields, schema=None):
        session = get_session(schema=schema)
        try:
            session.query(cls).filter(and_(*filters)).update(fields, synchronize_session="fetch")
            session.flush()
        finally:
            session.commit()
            close_session(session)

    def create_record(record: Base, schema=None) -> Base:
        session = get_session(schema=schema)
        try:
            session.add(record)
            session.flush()
            session.expunge(record)
        finally:
            session.commit()
            close_session(session)
            return record  # noqa

    def create_records(records: List[Base], schema=None):
        session = get_session(schema=schema)
        try:
            session.add_all(records)
            session.flush()
            session.expunge_all()
        finally:
            session.commit()
            close_session(session)
            return records  # noqa

    def create_or_ignore(cls: T, records: List[Base], schema=None):
        session = get_session(schema=schema)
        try:
            for record in records:
                record_dict = {k: v for k, v in record.__dict__.items() if k != "_sa_instance_state"}
                stmt = insert(cls).values(record_dict).on_conflict_do_nothing()
                session.execute(stmt)
            session.flush()
        finally:
            session.commit()
            close_session(session)

    def upsert_records(cls, records, schema=None):
        session = get_session(schema=schema)
        try:
            for record in records:
                record_dict = {k: v for k, v in record.__dict__.items() if k != "_sa_instance_state"}
                stmt = insert(cls).values(record_dict)
                update_dict = {c.name: getattr(record, c.name) for c in cls.__table__.columns}
                stmt = stmt.on_conflict_do_update(
                    index_elements=[cls.__table__.primary_key.columns.keys()], set_=update_dict
                )
                session.execute(stmt)
            session.flush()
        finally:
            session.commit()
            close_session(session)

    def delete_record(cls: T, id, schema=None):
        session = get_session(schema=schema)
        try:
            session.query(cls).filter(cls.get_id() == id).delete()
            session.flush()
        finally:
            session.commit()
            close_session(session)

    def delete_records(cls: T, filters, schema=None):
        session = get_session(schema=schema)
        try:
            session.query(cls).filter(and_(*filters)).delete()
            session.flush()
        finally:
            session.commit()
            close_session(session)

    def execute_sql_query(sql_query, schema=None):
        session = get_session(schema=schema)
        try:
            records = session.execute(sql_query)
            return records
        finally:
            close_session(session)
