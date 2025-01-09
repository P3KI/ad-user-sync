from __future__ import annotations

from abc import ABC
from typing import TypeVar, Any, Dict, Literal

from pydantic import BaseModel

R = TypeVar("R")


class Action(BaseModel, ABC):
    type: str
    user: str


class EnableAction(Action):
    type: Literal["enable"] = "enable"
    # todo: requires password?


class JoinAction(Action):
    type: Literal["join"] = "join"
    group: str


class NameAction(Action):
    type: Literal["name"] = "name"
    name: str
    conflict_user: str
    attributes: Dict[str, Any]
