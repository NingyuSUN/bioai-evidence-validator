"""Strict configuration parsing shared by policy and adapter boundaries."""
from __future__ import annotations

import yaml


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ValueError("Configuration keys must be strings")
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_mapping(data: bytes, label: str) -> dict:
    try:
        value = yaml.load(data, Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid {label} YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def nonblank(value) -> bool:
    return isinstance(value, str) and bool(value.strip())
