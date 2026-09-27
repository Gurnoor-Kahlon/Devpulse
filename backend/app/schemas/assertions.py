import math
import re
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

Scalar = StrictStr | StrictBool | StrictInt | StrictFloat | None


class AssertionDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["text_contains", "json_equals"]
    pointer: Annotated[str, Field(max_length=512)] = ""
    expected: Scalar

    @model_validator(mode="after")
    def bounded(self) -> Self:
        for value in (self.pointer, self.expected):
            if isinstance(value, str):
                try:
                    value.encode("utf-8")
                except UnicodeError:
                    raise ValueError("Use valid Unicode") from None
                if "\x00" in value or len(value) > 1024:
                    raise ValueError("Invalid string")
        if isinstance(self.expected, (int, float)) and not isinstance(self.expected, bool):
            if abs(self.expected) > 9007199254740991 or not math.isfinite(self.expected):
                raise ValueError("Number out of range")
        if self.kind == "text_contains":
            if self.pointer or not isinstance(self.expected, str) or not self.expected:
                raise ValueError("Text containment requires non-empty text and no pointer")
        elif (
            (self.pointer and not self.pointer.startswith("/"))
            or re.search(r"~(?![01])", self.pointer)
            or self.pointer.count("/") > 32
        ):
            raise ValueError("Invalid JSON Pointer")
        return self


class AssertionSnapshot(AssertionDefinition):
    id: UUID


class AssertionResult(BaseModel):
    definition: AssertionSnapshot
    status: Literal["passed", "failed", "not_evaluated"]
    reason: Literal[
        "matched",
        "text_not_found",
        "pointer_missing",
        "value_mismatch",
        "invalid_json",
        "invalid_utf8",
        "evaluation_limit",
        "response_unavailable",
    ]


class AssertionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    configuration_version: Annotated[int, Field(strict=True, ge=1, le=2147483647)]
    items: Annotated[list[AssertionDefinition], Field(max_length=10)]


class AssertionPage(BaseModel):
    monitor_id: UUID
    configuration_version: int
    method: Literal["GET", "HEAD"]
    items: list[AssertionSnapshot]
