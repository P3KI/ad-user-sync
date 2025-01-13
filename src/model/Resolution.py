from __future__ import annotations

from abc import ABC
from typing import Generic, TypeVar, Annotated, Literal, List

from pydantic import BaseModel, Field, RootModel


T = TypeVar("T")


class BaseResolution(BaseModel, Generic[T], ABC):
    type: str
    user: str
    value: T


class EnableResolution(BaseResolution[bool]):
    type: Literal["enable"] = "enable"
    password: Annotated[str, Field(default=None, exclude=True)]


class JoinResolution(BaseResolution[bool]):
    type: Literal["join"] = "join"
    group: str


class NameResolution(BaseResolution[str]):
    type: Literal["name"] = "name"


Resolution = Annotated[EnableResolution | JoinResolution | NameResolution, Field(discriminator="type")]


class Resolutions(RootModel[List[Resolution]]):
    root: Annotated[List[Resolution], Field(default_factory=list)]

    def __len__(self) -> int:
        return len(self.root)

    def get_join(self, user: str, group: str) -> JoinResolution | None:
        # get the last join resolution for this user and group
        resolutions = reversed(self.root)
        resolutions = filter(lambda r: isinstance(r, JoinResolution), resolutions)
        resolutions = filter(lambda r: r.user == user, resolutions)
        resolutions = filter(lambda r: r.group == group, resolutions)
        return next(resolutions, None)

    def get_enable(self, user: str) -> EnableResolution | None:
        # get the latest enable resolution for this user
        resolutions = reversed(self.root)
        resolutions = filter(lambda r: isinstance(r, EnableResolution), resolutions)
        resolutions = filter(lambda r: r.user == user, resolutions)
        return next(resolutions, None)

    def get_name(self, user: str) -> NameResolution | None:
        # get the latest name resolution for this user
        resolutions = reversed(self.root)
        resolutions = filter(lambda r: isinstance(r, NameResolution), resolutions)
        resolutions = filter(lambda r: r.user == user, resolutions)
        return next(resolutions, None)

    @classmethod
    def load(cls, file: str) -> Resolutions:
        with open(file, "r") as f:
            json_str = f.read()
            if len(json_str) > 1:
                return cls.model_validate_json(json_str)
            else:
                return cls()

    def save(self, file: str) -> None:
        with open(file, "w") as out:
            out.write(self.model_dump_json(indent=4))
