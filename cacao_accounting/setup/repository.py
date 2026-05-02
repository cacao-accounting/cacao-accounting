# Copyright 2026
# Licensed under the Apache License, Version 2.0

from typing import Any

from cacao_accounting.database import CacaoConfig, Entity, database


def get_setup_value(key: str, default: Any = None) -> Any:
    record = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).first()
    if record:
        return record[0].value
    return default


def set_setup_value(key: str, value: str) -> None:
    record = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).first()
    if record:
        config = record[0]
        config.value = value
    else:
        config = CacaoConfig(key=key, value=value)
        database.session.add(config)


def create_default_entity(data: dict) -> Entity:
    entity = Entity(
        code=data.get("id"),
        company_name=data.get("razon_social"),
        name=data.get("nombre_comercial") or data.get("razon_social"),
        tax_id=data.get("id_fiscal"),
        currency=data.get("moneda"),
        entity_type=data.get("tipo_entidad"),
        status="default",
        enabled=True,
        default=True,
    )
    database.session.add(entity)
    return entity


def get_default_entity() -> Entity | None:
    return database.session.execute(database.select(Entity).filter_by(status="default")).scalar_one_or_none()
