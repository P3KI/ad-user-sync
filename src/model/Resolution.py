from __future__ import annotations

from abc import ABC
from typing import Generic, TypeVar, Annotated, Literal, List, Iterable, Type

from pydantic import BaseModel, Field, RootModel


T = TypeVar("T")


class BaseResolution(BaseModel, ABC):
    type: str
    user: str
    accept: Annotated[bool | None, Field(default=None)]

    @property
    def is_resolved(self) -> bool:
        return self.accept is not None


class EnableResolution(BaseResolution):
    type: Literal["enable"] = "enable"
    password: Annotated[str | None, Field(default="", exclude=True)]


class JoinResolution(BaseResolution):
    type: Literal["join"] = "join"
    group: str


class NameResolution(BaseResolution):
    type: Literal["name"] = "name"
    name: Annotated[str | None, Field(default="", exclude=True)]


Resolution = Annotated[EnableResolution | JoinResolution | NameResolution, Field(discriminator="type")]


class Resolutions(RootModel[List[Resolution]]):

    root: Annotated[List[Resolution], Field(default_factory=list)]

    def __len__(self) -> int:
        return len(self.root)

    def _filter(self, cls: Type[Resolution], user: str) -> Iterable[Resolution]:
        resolutions = reversed(self.root)
        resolutions = filter(lambda r: isinstance(r, cls), resolutions)
        resolutions = filter(lambda r: r.is_resolved, resolutions)
        return filter(lambda r: r.user == user, resolutions)

    def get_join(self, user: str, group: str) -> JoinResolution | None:
        # get the last join resolution for this user and group
        resolutions = filter(lambda r: r.group == group, self._filter(JoinResolution, user))
        return next(resolutions, None)

    def get_enable(self, user: str) -> EnableResolution | None:
        # get the latest enable resolution for this user
        return next(self._filter(EnableResolution, user), None)

    def get_name(self, user: str) -> NameResolution | None:
        # get the latest name resolution for this user
        return next(self._filter(NameResolution, user), None)

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
