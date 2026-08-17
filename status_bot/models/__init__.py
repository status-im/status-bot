from .base import Base
from .message import ReceivedMessage
from .chat import ReceivedChat

MODEL_BY_TABLE: dict[str, type[Base]] = {
    model.__tablename__: model for model in Base.__subclasses__()
}
