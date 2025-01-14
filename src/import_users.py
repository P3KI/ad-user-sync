import json
from datetime import datetime
from typing import Dict, List, Any, Set

from pyad import ADGroup, ADUser

from .active_directory import CatchableADExceptions, CachedActiveDirectory
from .model import ImportConfig, Resolutions, Action, NameAction, EnableAction, JoinAction


def import_users(
    config: ImportConfig,
    input_file: str,
    resolutions: Resolutions = None,
) -> List[Action]:
    active_directory = CachedActiveDirectory()

    # resolve the config GroupMap form AD
    group_map: Dict[str, ADGroup] = {
        k: active_directory.get_group(config.full_path(v)) for k, v in config.group_map.items()
    }

    # here we will collect the required interactive actions
    actions: List[Action] = []

    # resolve the config RestrictedGroups form AD
    restricted_groups = [active_directory.get_group(config.full_path(v)) for v in config.restricted_groups]

    # Read users form input file
    with open(input_file) as f:
        users_attributes: List[Dict[str, Any]] = json.load(f)

    print(f"Users: {users_attributes}")

    # load resolutions of conflicts
    resolutions = resolutions or Resolutions()

    # The path where all managed users will be created. Defined by ManagedUserPath
    user_container = active_directory.get_container(config.full_path(config.managed_user_path))

    # All users imported during this run
    old_users: Set[ADUser] = set(user_container.get_children(recursive=False, filter=[ADUser]))
    new_users: Set[ADUser] = set()

    # New memberships in all managed groups are collected here.
    new_group_members: Dict[ADGroup, Set[ADUser]] = {k: set() for k in group_map.values()}

    for user_attributes in users_attributes:
        # Remove attributes that can not be applied using ADUser.update_attributes() function
        cn: str = config.prefix_account_name(user_attributes.pop("cn"))  # used as key and for user creation
        account_name: str = config.prefix_account_name(user_attributes.pop("sAMAccountName"))  # used for user creation
        member_of: List[str] = user_attributes.pop("memberOf")  # will be mapped to "member" attribute of groups
        account_expires: str | None = user_attributes.pop("accountExpires", None)  # set via ADUser.set_expiration()
        disabled: bool = user_attributes.pop("disabled", False)  # We only disable via ADUser.disable(), never enable
        user_attributes.pop("subPath", None)  # Currently not used, not a valid AD attribute.
        user_attributes.pop("distinguishedName", None)  # domain specific, should not be exported in the first place

        # Create user or update user attributes
        user = active_directory.find_single_user(user_container, f"cn = '{cn}'")
        if user is None:
            # check if there should be a renaming applied for this user
            name_resolution = resolutions.get_name(cn)
            if name_resolution is not None and name_resolution.accept is True and len(name_resolution.name) > 0:
                account_name = name_resolution.name

            # create a new user
            try:
                user = user_container.create_user(
                    name=cn,
                    enable=False,
                    optional_attributes=user_attributes | {"sAMAccountName": account_name},
                )
                print(f"{user}: Created")
            except CatchableADExceptions:
                # creation failed. check if it was because of a name conflict
                conflict_user = active_directory.find_single_user(
                    domain=user_container.get_domain(),
                    where=f"sAMAccountName = '{account_name}'",
                )
                if conflict_user:
                    # name conflict detected -> add require action
                    actions.append(
                        NameAction(
                            user=cn,
                            attributes=user_attributes,
                            name=account_name,
                            conflict_user=conflict_user.cn,
                        )
                    )
                    # continue with next user to import
                    continue
                else:
                    # it was another problem. re-raise exception
                    raise
        else:
            # update the attributes of existing user
            old_attributes = {k: user.get_attribute(k, False) for k in user_attributes}
            if user_attributes != old_attributes:
                user.update_attributes(user_attributes)
                print(f"{user}: Updated attributes")

        ###
        # Handle special attributes that can not be set via update_attributes, because they require custom logic.
        ###

        # set expiration to at least the default_expiration
        expiration_date = config.get_default_expiration_date()
        if account_expires:
            account_expires_date = datetime.fromisoformat(account_expires)
            if account_expires_date > expiration_date:
                expiration_date = account_expires_date
        user.set_expiration(expiration_date)

        # If the user should be enabled, but is disabled, add an interactive action for it.
        # Do not enable automatically.
        if disabled:
            user.disable()
        elif user._ldap_adsi_obj.AccountDisabled:
            enable_resolution = resolutions.get_enable(user.dn)
            if enable_resolution is None:
                actions.append(EnableAction(user=user.dn))
            elif enable_resolution.accept is True:
                if len(enable_resolution.password):
                    user.set_password(enable_resolution.password)
                    user.enable()
                else:
                    print(f"{user}: Activation requires password")
                    actions.append(EnableAction(user=user.dn))
            else:
                print(f"{user}: User activation was rejected manually ({enable_resolution.timestamp})")

        # Collect group membership
        # We can't set group membership for users, instead we have to set user members for groups
        # We do this for all groups of the user that have a mapping for the local AD and also the
        # GroupMap[*] group if defined.
        user_groups = map(group_map.get, member_of + ["*"])
        for user_group in set(filter(lambda g: g is not None, user_groups)):
            new_group_members[user_group].add(user)

        # Collect all users from the current import
        new_users.add(user)

    # Apply memberships to managed groups
    for group, new_members in new_group_members.items():
        old_members: Set[ADUser] = set(group.get_members(ignore_groups=True))

        removed_members = old_members - new_members

        if len(removed_members) > 0:
            group.remove_members(removed_members)
            for user in removed_members:
                print(f'{user}: Removed from group "{group.cn}"')

        if group not in restricted_groups:
            added_members = new_members - old_members
        else:
            added_members = []
            for user in new_members - old_members:
                join_resolution = resolutions.get_join(user=user.dn, group=group.dn)
                if join_resolution is None:
                    actions.append(JoinAction(user=user.dn, group=group.dn))
                elif join_resolution.accept is True:
                    added_members.append(user)
                else:
                    print(f'{user}: Joining group "{group.cn}" rejected manually ({join_resolution.timestamp})')

        if len(added_members) > 0:
            group.add_members(added_members)
            for user in added_members:
                print(f'{user}: Joined group "{group.cn}"')

    # Managed users currently in AD
    removed_users = old_users - new_users
    for user in removed_users:
        print(f"{user}: Disabled (no longer in import list)")
        user.disable()

    return actions
