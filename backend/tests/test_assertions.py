import asyncio
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.monitoring.assertions import evaluate
from app.monitoring.executor import execute_probe
from app.schemas.assertions import AssertionDefinition, AssertionSnapshot, AssertionUpdate
from tests.probe_fixtures import fixture_server, fixture_settings


def definition(kind="json_equals", pointer="/ok", expected=True):
    return AssertionSnapshot(id=uuid4(), kind=kind, pointer=pointer, expected=expected)


@pytest.mark.parametrize(
    ("body", "pointer", "expected", "reason"),
    [
        (b'{"ok":true}', "/ok", True, "matched"),
        (b'{"ok":1}', "/ok", True, "value_mismatch"),
        (b'{"ok":true}', "/ok", 1, "value_mismatch"),
        (b'{"ok":"1"}', "/ok", 1, "value_mismatch"),
        (b'{"ok":1.0}', "/ok", 1, "matched"),
        (b'{"ok":null}', "/ok", None, "matched"),
        (b"{}", "/ok", None, "pointer_missing"),
        (b"null", "", None, "matched"),
        (b'{"a/b":{"~key":[42]}}', "/a~1b/~0key/0", 42, "matched"),
        (b'{"":7}', "/", 7, "matched"),
        (b"[7]", "/00", 7, "pointer_missing"),
        (b"[7]", "/-", 7, "pointer_missing"),
        (b"[7]", "/1", 7, "pointer_missing"),
        (b'{"ok":{}}', "/ok", None, "value_mismatch"),
        (b'{"ok":true,"ok":false}', "/ok", True, "invalid_json"),
        (b"{secret-body-canary", "/ok", True, "invalid_json"),
        (b"\xff", "/ok", True, "invalid_utf8"),
        (b"[" * 33 + b"0" + b"]" * 33, "", 0, "evaluation_limit"),
        (b"[" + b"0," * 10001 + b"0]", "", 0, "evaluation_limit"),
        (b"9" * 65, "", 0, "evaluation_limit"),
        (b"1e999999999999999999999999", "", 0, "evaluation_limit"),
        (b"NaN", "", 0, "evaluation_limit"),
        (b"Infinity", "", 0, "evaluation_limit"),
    ],
)
def test_typed_json_pointer_and_bounded_parsing(body, pointer, expected, reason):
    item = definition(pointer=pointer, expected=expected)
    result = evaluate(body, (item,))[0]
    assert result["reason"] == reason
    assert result["status"] == ("passed" if reason == "matched" else "failed")
    assert result["definition"] == item.model_dump(mode="json")
    assert set(result) == {"definition", "status", "reason"}
    assert "secret-body-canary" not in json.dumps(result)


def test_text_is_case_sensitive_utf8_and_independent_of_json_parsing():
    items = (
        definition("text_contains", "", "café"),
        definition("text_contains", "", "CAFÉ"),
        definition(),
    )
    results = evaluate("not JSON: café".encode(), items)
    assert [item["reason"] for item in results] == ["matched", "text_not_found", "invalid_json"]


@pytest.mark.parametrize(
    "changes",
    [
        {"pointer": "#/ok"},
        {"pointer": "ok"},
        {"pointer": "/~2"},
        {"pointer": "/" * 33},
        {"pointer": "/" + "a" * 512},
        {"expected": []},
        {"expected": {}},
        {"expected": float("inf")},
        {"expected": 10**400},
        {"expected": "\ud800"},
        {"expected": "\x00"},
        {"expected": "x" * 1025},
        {"kind": "regex"},
        {"kind": "text_contains", "pointer": "", "expected": ""},
        {"kind": "text_contains", "pointer": "", "expected": True},
        {"kind": "text_contains", "pointer": "/x", "expected": "x"},
    ],
)
def test_invalid_definitions(changes):
    with pytest.raises(ValidationError):
        AssertionDefinition.model_validate(
            {"kind": "json_equals", "pointer": "/ok", "expected": True, **changes}
        )


def test_definition_count_is_bounded():
    with pytest.raises(ValidationError):
        AssertionUpdate(configuration_version=1, items=[definition()] * 11)


@pytest.mark.parametrize(
    ("route", "item", "code", "reason"),
    [
        ("/ok", definition(), None, "matched"),
        ("/ok", definition(expected=False), "assertion_failed", "value_mismatch"),
        ("/fail", definition(expected=False), "unexpected_status", "value_mismatch"),
        ("/json", definition(), "assertion_failed", "invalid_json"),
        ("/gzip", definition("text_contains", "", "hello"), None, "matched"),
        ("/bomb", definition(), "response_too_large", "response_unavailable"),
        ("/truncated", definition(), "invalid_response", "response_unavailable"),
        ("/slow", definition(), "timeout", "response_unavailable"),
    ],
)
def test_real_body_evaluation_preserves_transport_bounds(route, item, code, reason):
    with fixture_server() as (server, _):
        result = asyncio.run(
            execute_probe(
                f"http://127.0.0.1:{server.server_port}{route}",
                "GET",
                200,
                1,
                fixture_settings(server),
                assertions=(item,),
            )
        )
    assert result.error_code == code
    assert result.outcome == ("success" if code is None else "failure")
    assert result.assertion_results[0]["reason"] == reason
    assert "response-secret-canary" not in repr(result)
