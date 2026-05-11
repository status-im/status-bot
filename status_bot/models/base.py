from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def namespace(prefix: str):
    if not prefix:
        raise ValueError("namespace prefix cannot be empty")

    def decorator(cls):
        new_name = f"{prefix}_{cls.__tablename__}"
        if cls.__table__.name.startswith(f"{prefix}_"):
            return cls
        cls.__tablename__ = new_name
        cls.__table__.name = new_name
        return cls

    return decorator


def model_by_table(table_name: str):
    for mapper in Base.registry.mappers:
        table = mapper.local_table
        if table is not None and table.name == table_name:
            return mapper.class_
    return None
