from __future__ import annotations

from abc import ABC
from typing import Generic, TypeVar, Annotated, Any, Dict, Tuple, Literal, List

from pydantic import BaseModel, Field, RootModel


T = TypeVar('T')


class BaseResolution(BaseModel, Generic[T], ABC):
    type: str
    user: str
    value: T


class EnableResolution(BaseResolution[bool]):
    type: Literal['enable'] = 'enable'
    password: Annotated[str, Field(default=None, exclude=True)]


class JoinResolution(BaseResolution[bool]):
    type: Literal['join'] = 'join'
    group: str


class NameResolution(BaseResolution[str]):
    type: Literal['name'] = 'name'


Resolution = Annotated[EnableResolution | JoinResolution | NameResolution, Field(discriminator='type')]


class Resolutions(RootModel[List[Resolution]]):
    root: Annotated[List[Resolution], Field(default_factory=list)]

    def __len__(self) -> int:
        return len(self.root)

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

