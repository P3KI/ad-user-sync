from __future__ import annotations

from abc import ABC
from datetime import datetime
from typing import TypeVar, Annotated, Literal, List, Iterable, Type

from pydantic import BaseModel, Field, TypeAdapter

from .FileBaseModel import FileBaseModel


class BaseResolution(BaseModel, ABC):
    type: str
    user: str
    accept: Annotated[bool | None, Field(default=None)]
    timestamp: Annotated[datetime, Field(default_factory=lambda: datetime.now().astimezone())]

    @property
    def is_resolved(self) -> bool:
        return self.accept is not None

    @property
    def is_accepted(self) -> bool:
        return self.accept is True

    @property
    def is_rejected(self) -> bool:
        return self.accept is False


class EnableResolution(BaseResolution):
    type: Literal["enable"] = "enable"
    password: Annotated[str | None, Field(default="", exclude=True)]


class JoinResolution(BaseResolution):
    type: Literal["join"] = "join"
    group: str


class NameResolution(BaseResolution):
    type: Literal["name"] = "name"
    name: str
    new_name: Annotated[str | None, Field(default="", exclude=True)]


Resolution = Annotated[EnableResolution | JoinResolution | NameResolution, Field(discriminator="type")]
ResolutionParser = TypeAdapter(Resolution)

R = TypeVar("R", bound=Resolution)


class ResolutionList(FileBaseModel):
    resolutions: Annotated[List[Resolution], Field(default_factory=list)]

    def __len__(self) -> int:
        return len(self.resolutions)

    def __add__(self, other: ResolutionList) -> ResolutionList:
        return ResolutionList(resolutions=self.resolutions + other.resolutions)

    def _filter[R](self, cls: Type[R], user: str) -> Iterable[R]:
        resolutions = reversed(self.resolutions)
        resolutions = filter(lambda r: isinstance(r, cls), resolutions)
        resolutions = filter(lambda r: r.is_resolved, resolutions)
        return filter(lambda r: r.user == user, resolutions)

    def get_enable(self, user: str) -> EnableResolution | None:
        # get the latest enable resolution for this user
        return next(iter(self._filter(EnableResolution, user)), None)

    def get_join(self, user: str, group: str) -> JoinResolution | None:
        # get the last join resolution for this user and group
        resolutions = filter(lambda r: r.group == group, self._filter(JoinResolution, user))
        return next(resolutions, None)

    def get_name(self, user: str, name: str) -> NameResolution | None:
        # get the latest name resolution for this user
        resolutions = filter(lambda r: r.name == name, self._filter(NameResolution, user))
        return next(resolutions, None)

    def get_rejected(self) -> ResolutionList:
        return ResolutionList(resolutions=list(filter(lambda r: r.is_rejected, self.resolutions)))
