
import json
import jsonpickle

INTERACTIVE_IMPORT_ACTIONS = []

class Action:
    def __init__(self, user, action):
        self.user = user
        self.action = action

class UserEnableAction(Action):
    def __init__(self, user):
        super().__init__(user, "enable")

class UserJoinGroupAction(Action):
    def __init__(self, user, group):
        super().__init__(user, "join-group")
        self.group = group


def any_actions() -> bool:
    len(INTERACTIVE_IMPORT_ACTIONS) > 0

def add_action(action : Action):
    INTERACTIVE_IMPORT_ACTIONS.append(action)

def load(file):
    with open(file, "w") as input:
        global INTERACTIVE_IMPORT_ACTIONS
        INTERACTIVE_IMPORT_ACTIONS = jsonpickle.decide(input.read())

def save(file):
    with open(file, "w") as out:
        out.write(jsonpickle.dumps(INTERACTIVE_IMPORT_ACTIONS, indent=4))
