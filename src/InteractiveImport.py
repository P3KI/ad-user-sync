import jsonpickle

INTERACTIVE_IMPORT_ACTIONS = []


class Action:
    def __init__(self, user, action, resolved=False):
        self.user = user
        self.action = action
        self.resolved = resolved

    def __hash__(self):
        return hash((self.user, self.action))

    def __eq__(self, other):
        return isinstance(other, Action) and self.user == other.user and self.action == other.action


class UserEnableAction(Action):
    def __init__(self, user, resolved=False):
        super().__init__(user, "enable", resolved)


class UserJoinGroupAction(Action):
    def __init__(self, user, group):
        super().__init__(user, "join-group")
        self.group = group

    def __hash__(self):
        return hash((super, self.user, self.action))

    def __eq__(self, other):
        return isinstance(other, UserJoinGroupAction) and self.group == other.group and super().__eq__(other)


class UserResolveAccountNameConflict(Action):
    def __init__(self, user, conflict_user, account_name, attributes, resolved=False):
        super().__init__(user, "name-conflict", resolved)
        self.conflict_user = conflict_user
        self.account_name = account_name
        self.attributes = attributes

    def __hash__(self):
        return hash(
            (super, self.conflict_user, self.account_name)
        )  # Don't hash the attributes, they might have changed, but we are still talking about the same user.

    def __eq__(self, other):
        return (
            isinstance(other, UserResolveAccountNameConflict)
            and self.conflict_user == other.conflict_user
            and self.account_name == other.account_name
            and super().__eq__(other)
        )


def any_actions() -> bool:
    return len(INTERACTIVE_IMPORT_ACTIONS) > 0


def add_action(action: Action):
    try:  # Check if we already have an equivalent action
        INTERACTIVE_IMPORT_ACTIONS.index(action)

    except ValueError:
        INTERACTIVE_IMPORT_ACTIONS.append(action)


def load_resolved(file):
    with open(file, "r") as input:
        global INTERACTIVE_IMPORT_ACTIONS
        json_str = input.read()
        if len(json_str) > 1:
            actions = jsonpickle.decode(json_str)
            INTERACTIVE_IMPORT_ACTIONS = [a for a in actions if a.resolved]
        else:
            INTERACTIVE_IMPORT_ACTIONS = []


def save(file):
    with open(file, "w") as out:
        out.write(jsonpickle.dumps(INTERACTIVE_IMPORT_ACTIONS, indent=4))
