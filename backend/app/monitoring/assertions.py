"""Bounded body evaluation. Actual response values never enter results or errors."""

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.schemas.assertions import AssertionResult, AssertionSnapshot


class EvaluationLimit(ValueError):
    pass


def number(value: str) -> Decimal:
    if len(value) > 64:
        raise EvaluationLimit
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise EvaluationLimit from None
    if not result.is_finite() or result.adjusted() > 100 or result.adjusted() < -100:
        raise EvaluationLimit
    return result


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def parse_json(text: str) -> Any:
    # Preflight bounds parser depth and collection fanout before allocating its object graph.
    depth = separators = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            separators += 1
        elif char in "]}":
            depth -= 1
        elif char in ",:":
            separators += 1
        if depth > 32 or separators > 10000:
            raise EvaluationLimit
    return json.loads(
        text,
        parse_int=number,
        parse_float=number,
        parse_constant=number,
        object_pairs_hook=unique_object,
    )


def resolve(document: Any, pointer: str) -> tuple[bool, Any]:
    current = document
    for encoded in pointer.split("/")[1:] if pointer else ():
        token = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif (
            isinstance(current, list)
            and re.fullmatch(r"0|[1-9][0-9]*", token)
            and len(token) <= 8
            and int(token) < len(current)
        ):
            current = current[int(token)]
        else:
            return False, None
    return True, current


def unavailable(definitions: tuple[AssertionSnapshot, ...]) -> list[dict[str, Any]]:
    return [
        AssertionResult(
            definition=item, status="not_evaluated", reason="response_unavailable"
        ).model_dump(mode="json")
        for item in definitions
    ]


def evaluate(body: bytes, definitions: tuple[AssertionSnapshot, ...]) -> list[dict[str, Any]]:
    try:
        text = body.decode("utf-8", errors="strict")
    except UnicodeError:
        return [
            AssertionResult(definition=item, status="failed", reason="invalid_utf8").model_dump(
                mode="json"
            )
            for item in definitions
        ]
    document = None
    json_error = None
    if any(item.kind == "json_equals" for item in definitions):
        try:
            document = parse_json(text)
        except EvaluationLimit:
            json_error = "evaluation_limit"
        except (ValueError, RecursionError):
            json_error = "invalid_json"
    results = []
    for item in definitions:
        if item.kind == "text_contains":
            reason = (
                "matched"
                if isinstance(item.expected, str) and item.expected in text
                else "text_not_found"
            )
        elif json_error:
            reason = json_error
        else:
            found, actual = resolve(document, item.pointer)
            if isinstance(actual, Decimal) and type(item.expected) in (int, float):
                equal = actual == Decimal(str(item.expected))
            else:
                equal = type(actual) is type(item.expected) and actual == item.expected
            reason = "pointer_missing" if not found else "matched" if equal else "value_mismatch"
        results.append(
            AssertionResult.model_validate(
                dict(
                    definition=item,
                    status="passed" if reason == "matched" else "failed",
                    reason=reason,
                )
            ).model_dump(mode="json")
        )
    return results
