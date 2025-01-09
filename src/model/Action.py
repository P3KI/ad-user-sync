from __future__ import annotations

from abc import ABC
from typing import Generic, TypeVar, Annotated, Any, Dict, Tuple, Literal, List

from pydantic import BaseModel, Field, RootModel

R = TypeVar('R')


class BaseAction(BaseModel, Generic[R], ABC):
    type: str
    user: str
    resolved: Annotated[bool, Field(default=False)]
    resolution: Annotated[R | None, Field(default=None)]

    def _compare_attrs(self) -> Tuple[Any, ...]:
        return type(self), self.user

    def __hash__(self) -> int:
        return hash(self._compare_attrs())

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, BaseAction) and self._compare_attrs() == other._compare_attrs()

    def is_savable(self) -> bool:
        return True


class EnableAction(BaseAction[str]):
    type: Literal['enable'] = 'enable'

    def is_savable(self) -> bool:
        # never save passwords to files
        return self.resolution is None


class JoinGroupAction(BaseAction[bool]):
    type: Literal['join_group'] = 'join_group'
    group: str

    def _compare_attrs(self) -> Tuple[Any, ...]:
        return super()._compare_attrs() + (self.group, )


class AccountNameConflictAction(BaseAction[str]):
    type: Literal['name_conflict'] = 'name_conflict'
    account_name: str
    conflict_user: str
    attributes: Dict[str, Any]

    def _compare_attrs(self) -> Tuple[Any, ...]:
        # Don't compare the attributes, they might have changed, but we are still talking about the same user.
        return super()._compare_attrs() + (self.conflict_user, self.account_name)


Action = Annotated[EnableAction | JoinGroupAction | AccountNameConflictAction, Field(discriminator='type')]


class Actions(RootModel[List[Action]]):
    root: Annotated[List[Action], Field(default_factory=list)]

    def add(self, action: Action) -> bool:
        if action not in self.root:
            self.root.append(action)
            return True
        return False

    def __len__(self) -> int:
        return len(self.root)

    @classmethod
    def load(cls, file: str) -> Actions:
        with open(file, "r") as f:
            json_str = f.read()
            if len(json_str) > 1:
                return cls.model_validate_json(json_str)
            else:
                return cls()

    def drop_unresolved(self) -> None:
        self.root = list(filter(lambda a: not a.resolved, self.root))

    def save(self, file):
        savable_actions = Actions(list(filter(lambda a: a.is_savable(), self.root)))
        with open(file, "w") as out:
            out.write(savable_actions.model_dump_json(indent=4))
