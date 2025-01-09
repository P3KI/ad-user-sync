import sys
import json
from datetime import datetime
from typing import Dict, List, Any, Set

from pyad.adgroup import ADGroup
from pyad.aduser import ADUser


from src import InteractiveImport
from src.active_directory import CatchableADExceptions
from src.active_directory.CachedActiveDirectory import CachedActiveDirectory
from src.model import ImportConfig


def import_users(
    config: ImportConfig,
    input_file: str,
    active_directory: CachedActiveDirectory,
):
    # resolve the config GroupMap form AD
    group_map: Dict[str, ADGroup] = {
        k: active_directory.get_group(config.full_path(v))
        for k, v in config.group_map.items()
    }

    # resolve the config RestrictedGroups form AD
    restricted_groups = [
        active_directory.get_group(config.full_path(v))
        for v in config.restricted_groups
    ]

    # Read users form input file
    with open(input_file) as f:
        users_attributes: List[Dict[str, Any]] = json.load(f)

    print("Users:", users_attributes)

    InteractiveImport.load_resolved(config.pending_actions_file)

    # The path where all managed users will be created. Defined by ManagedUserPath
    user_container = active_directory.get_container(config.full_path(config.managed_user_path))

    # New memberships in all managed groups are collected here.
    new_group_members: Dict[ADGroup, Set[ADUser]] = {k: set() for k in group_map.values()}

    # All users imported during this run
    new_users: Set[ADUser] = set()

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
            print(f"Creating user: {cn}")
            try:
                user = user_container.create_user(
                    name=cn,
                    enable=False,
                    optional_attributes=user_attributes | {"sAMAccountName": account_name},
                )
            except CatchableADExceptions:
                conflict_user = active_directory.find_single_user(
                    domain=user_container.get_domain(),
                    where=f"sAMAccountName = '{account_name}'",
                )
                if conflict_user:
                    print(f"Action required: User '{cn}' account name conflict: {account_name}")
                    InteractiveImport.add_action(
                        InteractiveImport.UserResolveAccountNameConflict(
                            cn, conflict_user.cn, account_name, user_attributes
                        )
                    )
                    continue
                else:
                    raise
        else:
            print(f"Updating user: {cn}")
            user.update_attributes(user_attributes)

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
            print(f"User {user} not automatically enabled.")
            InteractiveImport.add_action(InteractiveImport.UserEnableAction(user.dn))

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
        added_members = new_members - old_members

        if len(removed_members) > 0:
            print(f"Removing users from group '{group.cn}': {removed_members}")
            group.remove_members(removed_members)

        if len(added_members) > 0:
            if group in restricted_groups:
                for user in added_members:
                    print(f"User {user} not automatically adding to restricted group: {group.cn}")
                    InteractiveImport.add_action(InteractiveImport.UserJoinGroupAction(user.dn, group.dn))
            else:
                print(f"Adding users to group '{group.cn}': {added_members}")
                group.add_members(added_members)

    # Managed users currently in AD
    old_users: Set[ADUser] = set(user_container.get_children(recursive=False, filter=[ADUser]))
    removed_users = old_users - new_users
    for user in removed_users:
        print(f"Disabling user: {user.cn} (no longer in import list)")
        user.disable()

    if config.pending_actions_file is not None:
        if InteractiveImport.any_actions():
            print(f"Saving required actions to {config.pending_actions_file}")
        InteractiveImport.save(config.pending_actions_file)  # Save either way
