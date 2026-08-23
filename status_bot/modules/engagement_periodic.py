import logging
from sqlalchemy import and_, or_

from prometheus_client import Counter
from datetime import datetime, timedelta
from status_bot.modules.base import BaseModule, ModuleType
from status_bot.models import ContactRequest, message

logger = logging.getLogger(__name__)


def get_all_contact_to_contact(db_session, delay):
    threshold_timestamp = datetime.utcnow() - timedelta(days=delay)

    return db_session.query(ContactRequest).filter(
        and_(
            ContactRequest.requestTimestamp < threshold_timestamp,
            ContactRequest.other_field < delay
        )
    ).all()

class PeriodicEngagement(BaseModule):

    DESCRIPTION = """
        This module send period message to the contact.
        It's design to maintain activity to new user joining the application
    """
    @property
    def module_type(self) -> ModuleType:
        return ModuleType.PERIODIC

    def on_start(self):
        logger.info("Starting module PeriodicEngagement")
        self._verify_mandatory_config(["messages"])


    def execute(self):
        if self.ctx.db is None:
            return
        logger.info("Executing module PeriodicEngagement")
        planned_messages = self.ctx.config.settings.get("messages", [])
        for planned_message in planned_messages:
            _delay = planned_message.get("delay")
            _message = planned_message.get("message")
            with self.ctx.db.session() as session:
                contacts = get_all_contact_to_contact(session, _delay)
                for c in contacts:
                    self.ctx.account.send_message(
                        chat_id=c.public_key, message=_message)
                    c.last_engagement_message = _delay
                    session.merge(c)
                    session.commit()
                    self._counter.labels(delay=_delay).inc()

    def register_metrics(self) -> None:
        self._counter = Counter(
            "status_bot_engagement_periodic",
            "Total Message send by delay",
            ["delay"]
        )
