from logging import Logger
from typing import List

from pyad import ADUser

from .Action import Action


class ImportResult:
    enabled: List[ADUser]
    created: List[ADUser]
    updated: List[ADUser]
    disabled: List[ADUser]
    required_interactions: List[Action]

    def __init__(self):
        self.created = []
        self.enabled = []
        self.updated = []
        self.disabled = []
        self.required_interactions = []

    def require_interaction(self, action: Action):
        self.required_interactions.append(action)

    def log_required_interactions(self, logger: Logger):
        for action in self.required_interactions:
            logger.info(f"action still required: {action.model_dump()}")
