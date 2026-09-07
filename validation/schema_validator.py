"""Standard-library JSON Schema validation for MarketFlow AI outputs.

The validator implements the Draft 2020-12 keywords used by the existing
MarketFlow schemas. It performs no model, API, or report-generation work.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def validate_json_schema(
    instance: Any, schema_path: str | Path
) -> dict[str, Any]:
    """Validate an instance and return clear, path-based error messages."""
    path = Path(schema_path).resolve()
    schema = _load_schema(path)
    errors: list[str] = []
    _validate(instance, schema, schema, path, "$", errors)
    return {"valid": not errors, "errors": errors}


def _validate(
    instance: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    schema_path: Path,
    instance_path: str,
    errors: list[str],
) -> None:
    if "$ref" in schema:
        resolved, resolved_root, resolved_path = _resolve_ref(
            schema["$ref"], root_schema, schema_path
        )
        _validate(
            instance,
            resolved,
            resolved_root,
            resolved_path,
            instance_path,
            errors,
        )

    if "const" in schema and instance != schema["const"]:
        errors.append(
            f"{instance_path}: expected constant {schema['const']!r}, got {instance!r}"
        )

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(
            f"{instance_path}: value {instance!r} is not in {schema['enum']!r}"
        )

    if "type" in schema and not _matches_type(instance, schema["type"]):
        errors.append(
            f"{instance_path}: expected type {schema['type']!r}, "
            f"got {_json_type(instance)!r}"
        )
        return

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{instance_path}: missing required field {key!r}")

        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in instance:
                _validate(
                    instance[key],
                    child_schema,
                    root_schema,
                    schema_path,
                    f"{instance_path}.{key}",
                    errors,
                )

        if schema.get("additionalProperties") is False:
            unexpected = sorted(set(instance).difference(properties))
            for key in unexpected:
                errors.append(
                    f"{instance_path}: additional field {key!r} is not allowed"
                )

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(
                f"{instance_path}: expected at least {schema['minItems']} items, "
                f"got {len(instance)}"
            )
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(
                f"{instance_path}: expected at most {schema['maxItems']} items, "
                f"got {len(instance)}"
            )
        if schema.get("uniqueItems"):
            serialized = [
                json.dumps(item, ensure_ascii=False, sort_keys=True)
                for item in instance
            ]
            if len(serialized) != len(set(serialized)):
                errors.append(f"{instance_path}: array items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                _validate(
                    item,
                    item_schema,
                    root_schema,
                    schema_path,
                    f"{instance_path}[{index}]",
                    errors,
                )

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(
                f"{instance_path}: string must have at least "
                f"{schema['minLength']} characters"
            )
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(
                f"{instance_path}: value {instance!r} does not match "
                f"pattern {schema['pattern']!r}"
            )
        if schema.get("format") == "date-time" and not _is_datetime(instance):
            errors.append(f"{instance_path}: value is not a valid date-time")

    if _is_number(instance):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(
                f"{instance_path}: value must be >= {schema['minimum']}"
            )
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(
                f"{instance_path}: value must be <= {schema['maximum']}"
            )

    for child_schema in schema.get("allOf", []):
        _validate(
            instance,
            child_schema,
            root_schema,
            schema_path,
            instance_path,
            errors,
        )

    any_of = schema.get("anyOf")
    if any_of:
        valid_branch = False
        for child_schema in any_of:
            branch_errors: list[str] = []
            _validate(
                instance,
                child_schema,
                root_schema,
                schema_path,
                instance_path,
                branch_errors,
            )
            if not branch_errors:
                valid_branch = True
                break
        if not valid_branch:
            errors.append(f"{instance_path}: value does not satisfy anyOf")

    if_schema = schema.get("if")
    if isinstance(if_schema, dict):
        condition_errors: list[str] = []
        _validate(
            instance,
            if_schema,
            root_schema,
            schema_path,
            instance_path,
            condition_errors,
        )
        if not condition_errors and isinstance(schema.get("then"), dict):
            _validate(
                instance,
                schema["then"],
                root_schema,
                schema_path,
                instance_path,
                errors,
            )


def _resolve_ref(
    reference: str, root_schema: dict[str, Any], schema_path: Path
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    file_part, separator, fragment = reference.partition("#")
    if file_part:
        target_path = (schema_path.parent / file_part).resolve()
        target_root = _load_schema(target_path)
    else:
        target_path = schema_path
        target_root = root_schema

    target: Any = target_root
    if separator and fragment:
        if not fragment.startswith("/"):
            raise ValueError(f"Unsupported JSON Schema reference: {reference}")
        for token in fragment.lstrip("/").split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            target = target[token]
    if not isinstance(target, dict):
        raise ValueError(f"Schema reference is not an object: {reference}")
    return target, target_root, target_path


def _load_schema(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Schema file does not exist: {path}")
    with path.open("r", encoding="utf-8") as file:
        schema = json.load(file)
    if not isinstance(schema, dict):
        raise ValueError(f"Schema root must be an object: {path}")
    return schema


def _matches_type(instance: Any, expected: str | list[str]) -> bool:
    expected_types = [expected] if isinstance(expected, str) else expected
    actual_type = _json_type(instance)
    return any(
        actual_type == item or (item == "number" and actual_type == "integer")
        for item in expected_types
    )


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return "T" in value
