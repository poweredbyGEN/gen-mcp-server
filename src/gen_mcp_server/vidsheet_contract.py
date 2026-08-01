"""Artifact-backed Vidsheet constraints for the hosted MCP surface.

Rails generates ``vidsheet-operations-schema.json`` from the routes and
write-path validations.  This module deliberately derives the model-facing
constraints from that *wire* contract instead of maintaining another list in
the MCP server.  It fails closed: a damaged, non-wire, or markerless artifact
must prevent the hosted server from advertising an unsafe Vidsheet tool.

The wire contract includes editor ordering fields.  Those fields are real
Rails inputs but are not model-facing inputs: callers use named reorder tools
with an ordered ID list, while this server derives the integer positions.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


ARTIFACT_PATH = Path(__file__).with_name("contracts") / "vidsheet-operations-schema.json"
_MIN_ORDERING_ENTITIES = 3
_ORDERING_SHAPED_FIELD = re.compile(r"position|z_index|zindex|sort_order|\\brank\\b", re.IGNORECASE)


class VidsheetContractError(RuntimeError):
    """The vendored Rails contract cannot safely constrain MCP tools."""


def _singularize(name: str) -> str:
    return name[:-3] + "y" if name.endswith("ies") else name[:-1] if name.endswith("s") else name


def _entity_for(key_path: list[str], root_key: str) -> str:
    for key in reversed(key_path):
        if key.endswith("_attributes"):
            return _singularize(key.removesuffix("_attributes"))
    return _singularize(root_key)


def _walk_fields(
    node: Any,
    key_path: list[str],
    root_key: str,
    fields: list[tuple[str, str, dict[str, Any]]],
) -> None:
    if not isinstance(node, dict):
        return
    for name, sub in (node.get("properties") or {}).items():
        if isinstance(sub, dict) and sub.get("x-params-wrapper-discarded") is True:
            continue
        schema = sub if isinstance(sub, dict) else {}
        fields.append((_entity_for(key_path, root_key), name, schema))
        _walk_fields(schema, [*key_path, name], root_key, fields)
    for branch in ("anyOf", "oneOf", "allOf"):
        for sub in node.get(branch) or []:
            _walk_fields(sub, key_path, root_key, fields)
    if isinstance(node.get("items"), dict):
        _walk_fields(node["items"], key_path, root_key, fields)


def _request_fields(artifact: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    fields: list[tuple[str, str, dict[str, Any]]] = []
    for path_item in artifact["paths"].values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            schema = (
                operation.get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema")
            )
            if not isinstance(schema, dict):
                continue
            roots = list((schema.get("properties") or {}).keys())
            wrapper_key = schema.get("x-params-wrapper")
            operation_id = operation.get("operationId")
            operation_entity = (
                _entity_from_operation(operation_id)
                if isinstance(operation_id, str)
                else ""
            )
            root_key = (
                wrapper_key
                if isinstance(wrapper_key, str) and wrapper_key
                else roots[0]
                if len(roots) == 1
                else operation_entity
            )
            _walk_fields(schema, [], root_key, fields)
    return fields


def _entity_from_operation(operation_id: str) -> str:
    return operation_id.rsplit(".", 1)[0]


@lru_cache(maxsize=1)
def _derived() -> tuple[dict[str, frozenset[str]], dict[tuple[str, str], tuple[str, ...]]]:
    try:
        artifact = json.loads(ARTIFACT_PATH.read_text())
    except FileNotFoundError as exc:
        raise VidsheetContractError(f"Vidsheet wire artifact is missing: {ARTIFACT_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise VidsheetContractError(f"Vidsheet wire artifact is unparseable: {ARTIFACT_PATH}") from exc

    if artifact.get("x-contract-level") != "wire":
        raise VidsheetContractError("Vidsheet artifact is not the Rails wire contract")
    paths = artifact.get("paths")
    if not isinstance(paths, dict):
        raise VidsheetContractError("Vidsheet wire artifact has no paths")

    ordering: dict[str, set[str]] = {}
    enums: dict[tuple[str, str], tuple[str, ...]] = {}
    unmarked_ordering: list[str] = []
    for entity, field, schema in _request_fields(artifact):
        if schema.get("x-ordering-axis") is True:
            ordering.setdefault(entity, set()).add(field)
        elif _ORDERING_SHAPED_FIELD.search(field) and field not in ("composition", "positioning"):
            unmarked_ordering.append(f"{entity}.{field}")
        enum = schema.get("enum")
        if isinstance(enum, list):
            values = tuple(value for value in enum if isinstance(value, str))
            if values:
                key = (entity, field)
                previous = enums.get(key)
                if previous is not None and previous != values:
                    raise VidsheetContractError(
                        f"wire enum conflict for {entity}.{field}: {previous} != {values}"
                    )
                enums[key] = values

    if unmarked_ordering:
        raise VidsheetContractError(
            "wire artifact exposes ordering-shaped fields without an x-ordering-axis marker: "
            f"{sorted(set(unmarked_ordering))}"
        )
    if len(ordering) < _MIN_ORDERING_ENTITIES:
        raise VidsheetContractError(
            "wire artifact has too few x-ordering-axis entities; refusing to expose model-facing tools"
        )
    return ({entity: frozenset(fields) for entity, fields in ordering.items()}, enums)


def ordering_axis_fields() -> dict[str, frozenset[str]]:
    return _derived()[0]


def enum_values(entity: str, field: str) -> tuple[str, ...]:
    try:
        return _derived()[1][(entity, field)]
    except KeyError as exc:
        known = sorted(f"{known_entity}.{known_field}" for known_entity, known_field in _derived()[1])
        raise VidsheetContractError(
            f"no Rails wire enum for {entity}.{field}; known enums: {known}"
        ) from exc


def require_enum_value(entity: str, field: str, value: str) -> str:
    allowed = enum_values(entity, field)
    if value not in allowed:
        raise ValueError(f"{entity}.{field} must be one of: {', '.join(allowed)}")
    return value


def model_facing_fields(entity: str, fields: set[str]) -> set[str]:
    """Reject wire ordering inputs before a Vidsheet tool is published.

    Keeping this explicit makes accidental reintroduction of ``position`` a
    startup/test failure rather than another quietly divergent MCP schema.
    """
    blocked = fields & ordering_axis_fields().get(entity, frozenset())
    if blocked:
        raise VidsheetContractError(
            f"model-facing {entity} tool exposes Rails ordering field(s): {sorted(blocked)}"
        )
    return fields
