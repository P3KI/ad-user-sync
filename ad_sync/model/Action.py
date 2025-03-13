from __future__ import annotations

from abc import ABC
from typing import TypeVar, Any, Dict, Literal, Annotated

from pydantic import BaseModel, Field

R = TypeVar("R")


class Action(BaseModel, ABC):
    type: str
    user: str
    error: Annotated[str | None, Field(default=None, exclude=True)]


class EnableAction(Action):
    type: Literal["enable"] = "enable"

class DisableAction(Action):
    type: Literal["disable"] = "disable"
    deleted: bool

class JoinAction(Action):
    type: Literal["join"] = "join"
    group: str

class LeaveAction(Action):
    type: Literal["join"] = "leave"
    group: str


class NameAction(Action):
    type: Literal["name"] = "name"
    name: str
    conflict_user: Annotated[str, Field(exclude=True)]
    input_name: Annotated[str, Field(exclude=True)]
    attributes: Annotated[Dict[str, Any], Field(exclude=True)]
