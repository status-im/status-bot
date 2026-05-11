import datetime

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, Integer, String, select

from status_bot import Base, namespace
from status_bot.database import Database
from status_bot.models import model_by_table
from status_bot.modules.base import ModuleConfig, ModuleContext
from status_bot.modules.communities_monitoring import CommunitiesMonitoring


@namespace("mymodule")
class Visit(Base):
    __tablename__ = "visit"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String, nullable=False)
    visitor = Column(String, nullable=True)
    seen_at = Column(DateTime, nullable=False)


def _database() -> Database:
    db = Database("sqlite", host="", port=0, user="", password="", name=":memory:", schema="public")
    return db


def test_namespaced_model_registered_after_database_creation_is_picked_up():
    db = _database()

    db.create_tables()

    with db.session() as session:
        created = sa.inspect(session.connection()).get_table_names()

    assert "mymodule_visit" in created
    assert "visit" not in created


def test_orm_round_trip_for_namespaced_model():
    db = _database()
    db.create_tables()

    with db.session() as session:
        session.add(Visit(chat_id="chat-1", visitor="alice", seen_at=datetime.datetime(2024, 1, 1, 12, 0, 0)))
        session.commit()

    with db.session() as session:
        visits = session.execute(select(Visit)).scalars().all()

    assert len(visits) == 1
    assert visits[0].chat_id == "chat-1"
    assert visits[0].visitor == "alice"
    assert visits[0].seen_at == datetime.datetime(2024, 1, 1, 12, 0, 0)


def test_model_by_table_resolves_namespaced_and_late_registered():
    assert model_by_table("mymodule_visit") is Visit
    assert model_by_table("received_messages") is not None
    assert model_by_table("visit") is None
    assert model_by_table("unknown_table") is None


def test_communities_monitoring_without_database_does_not_raise():
    ctx = ModuleContext(
        account=None,
        config=ModuleConfig(name="communities_monitoring"),
        db=None,
    )
    module = CommunitiesMonitoring(ctx)

    module.execute()