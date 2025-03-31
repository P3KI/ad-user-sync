from __future__ import annotations

from logging import Logger
from typing import List, Set, Tuple, Dict, Annotated

from pyad import ADUser, ADGroup
from pydantic import BaseModel, Field, field_serializer, ConfigDict

from .Action import Action


class ImportResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    enabled: Annotated[Set[ADUser], Field(default_factory=set)]
    created: Annotated[Set[ADUser], Field(default_factory=set)]
    updated: Annotated[Set[ADUser], Field(default_factory=set)]
    disabled: Annotated[Set[ADUser], Field(default_factory=set)]
    joined: Annotated[Set[Tuple[ADUser, ADGroup]], Field(default_factory=set)]
    left: Annotated[Set[Tuple[ADUser, ADGroup]], Field(default_factory=set)]
    required_interactions: Annotated[List[Action], Field(default_factory=list)]

    logger : Annotated[Logger, Field(exclude=True, default=None)]

    @field_serializer("enabled", "created", "updated", "disabled")
    def serialize_user_set(self, users: Set[ADUser]) -> List[str]:
        return sorted(map(lambda u: u.cn, users))

    @field_serializer("joined", "left")
    def serialize_user_group_set(self, user_groups: Set[Tuple[ADUser, ADGroup]]) -> List[Dict[str, str]]:
        return list(
            map(
                lambda ug: dict(user=ug[0], group=ug[1]),
                sorted(map(lambda ug: (ug[0].cn, ug[1].cn), user_groups)),
            )
        )

    def require_interaction(self, action: Action):
        self.logger.debug("Manual action required: %s", action)
        self.required_interactions.append(action)

    def add_created(self, user: ADUser) -> None:
        self.created.add(user)

    def add_updated(self, user: ADUser) -> None:
        self.updated.add(user)

    def add_enabled(self, user: ADUser) -> None:
        self.enabled.add(user)
        self.disabled.discard(user)

    def add_disabled(self, user: ADUser) -> None:
        self.disabled.add(user)
        self.enabled.discard(user)

    def add_joined(self, user: ADUser, group: ADGroup) -> None:
        self.joined.add((user, group))
        self.left.discard((user, group))

    def add_left(self, user: ADUser, group: ADGroup) -> None:
        self.left.add((user, group))
        self.joined.discard((user, group))

    def update(self, other: ImportResult):
        self.enabled.difference_update(other.disabled)
        self.disabled.difference_update(other.enabled)
        self.enabled.update(other.enabled)
        self.disabled.update(other.disabled)

        self.joined.difference_update(other.left)
        self.left.difference_update(other.joined)
        self.joined.update(other.joined)
        self.left.update(other.left)

        self.created.update(other.created)
        self.updated.update(other.updated)
        self.required_interactions = list(other.required_interactions)

    def log_required_interactions(self, logger: Logger):
        for action in self.required_interactions:
            logger.info(f"action required: {action.model_dump()}")
