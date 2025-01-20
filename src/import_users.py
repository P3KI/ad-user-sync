import json
from datetime import datetime
from logging import Logger
from typing import Dict, List, Any, Set, Tuple

from pyad import ADGroup, ADUser, win32Exception, ADContainer

from .active_directory import CachedActiveDirectory
from .model import ImportConfig, ResolutionList, Action, NameAction, EnableAction, JoinAction, NameResolution
from .util import not_none


def import_users(
    config: ImportConfig,
    logger: Logger,
    resolutions: ResolutionList = None,
) -> List[Action]:
    # create an empty resolution list if none is provided
    resolutions = resolutions or ResolutionList()

    # create a cached active directory instance for accessing AD
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
    with open(config.input_file) as f:
        users_attributes: List[Dict[str, Any]] = json.load(f)

    if config.log_input_file_content:
        logger.info(f"Input: {json.dumps(users_attributes)}")

    # The path where all managed users will be created. Defined by ManagedUserPath
    user_container = active_directory.get_container(config.full_path(config.managed_user_path))

    # All users imported during this run
    old_users: Set[ADUser] = set(user_container.get_children(recursive=False, filter=[ADUser]))
    current_users: Set[ADUser] = set()  # list of users that are present in the current import list

    # User memberships for all managed groups are collected here
    current_members_by_group: Dict[ADGroup, Set[ADUser]] = {k: set() for k in group_map.values()}

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
            user, name_action = create_user(
                cn=cn,
                account_name=account_name,
                user_attributes=user_attributes,
                name_resolution=resolutions.get_name(cn, account_name),
                active_directory=active_directory,
                user_container=user_container,
                logger=logger,
            )
            if name_action:
                actions.append(name_action)
            if user is None:
                # go to next user to import if creation failed
                continue
        else:
            # update the attributes of existing user
            old_attributes = {k: user.get_attribute(k, False) for k in user_attributes}
            if user_attributes != old_attributes:
                user.update_attributes(user_attributes)
                logger.info(f"{user}: Attributes were updated")

        # add the user to the list of users, present in the current import list
        current_users.add(user)

        # Set expiration
        expiration_date = config.get_default_expiration_date()  # has to be at least the default_expiration
        if account_expires:
            # if `accountExpires` from the input file is longer, apply that instead
            account_expires_date = datetime.fromisoformat(account_expires)
            if account_expires_date > expiration_date:
                expiration_date = account_expires_date
        user.set_expiration(expiration_date)

        # Enable/Disable the User
        existing_user_is_disabled = user._ldap_adsi_obj.AccountDisabled
        if disabled and not existing_user_is_disabled:
            # enabled existing user should be disabled
            user.disable()
            logger.info(f"{user}: Was disabled (disabled attribute set in input file)")
        elif existing_user_is_disabled:
            # enabling a disabled existing user requires a resolved interactive action
            # we do not enable automatically
            enable_resolution = resolutions.get_enable(user.dn)
            if enable_resolution is None:
                # no resolved action was found -> add interactive action
                actions.append(EnableAction(user=user.dn))
            elif enable_resolution.accept is True:
                # resolved action was found and it got accepted
                # todo handle password requirements error
                try:
                    user.set_password(enable_resolution.password)
                    user.enable()
                    logger.info(f"{user}: Was enabled (accepted manually)")
                except win32Exception as e:
                    if e.error_info.get("error_code") != "0x800708c5":
                        raise
                    logger.warning(f"{user}: Manually provided password does not match requirements")
                    actions.append(
                        EnableAction(
                            user=user.dn,
                            error=e.error_info.get("message", "Password does not meet requirements"),
                        )
                    )

            else:
                # resolved action was found and it got rejected
                logger.info(f"{user}: Stays disabled (rejected manually at {enable_resolution.timestamp})")

        # Add user as a member to managed groups for later processing
        # We can't set group membership fora user directly, instead we have to set user members for groups.
        #   1. Add "*" to `member_of` of the user to also map the catch-all group.
        #   2. Map all given groups to local AD groups according to group_map (unmapped groups will be None).
        #   3. Filter out unmapped groups (`None` values).
        #   4. Remove duplicates by collecting groups in a set.
        # Then add the user as a member to every group.
        for user_group in set(filter(not_none, map(group_map.get, member_of + ["*"]))):
            current_members_by_group[user_group].add(user)

    # Update memberships of managed groups
    for group, current_group_members in current_members_by_group.items():
        old_members: Set[ADUser] = set(group.get_members(ignore_groups=True))

        removed_members = old_members - current_group_members

        if len(removed_members) > 0:
            group.remove_members(removed_members)
            for user in removed_members:
                logger.info(f'{user}: Removed from group "{group.cn}" (membership not present in import list)')

        # add members to group that haven't been members before
        if group not in restricted_groups:
            # unrestricted groups can just be joined
            new_members = current_group_members - old_members
            if len(new_members) > 0:
                group.add_members(new_members)
                for user in new_members:
                    logger.info(f'{user}: Joined group "{group.cn}"')
        else:
            # joining a restricted group requires a resolved interactive action
            new_members = []

            # filter the users that are accepted in the restricted group
            for user in current_group_members - old_members:
                # see if there is a resolved action
                join_resolution = resolutions.get_join(user=user.dn, group=group.dn)
                if join_resolution is None:
                    # no resolved action was found  -> add interactive action
                    actions.append(JoinAction(user=user.dn, group=group.dn))
                elif join_resolution.accept is True:
                    # resolved action was found and it was accepted
                    new_members.append(user)
                    logger.info(
                        f'{user}: Not joining group "{group.cn}" ' f"(rejected manually at {join_resolution.timestamp})"
                    )
                else:
                    # resolved action was found and it was rejected
                    logger.info(
                        f'{user}: Not joining restricted group "{group.cn}" '
                        f"(rejected manually at {join_resolution.timestamp})"
                    )

            # add the approved members to the group
            if len(new_members) > 0:
                group.add_members(new_members)
                for user in new_members:
                    logger.info(f'{user}: Joined restricted group "{group.cn}" (accepted manually)')

    # Disable users currently in AD but not in current import list
    removed_users = old_users - current_users
    for user in removed_users:
        user.disable()
        logger.info(f"{user}: Was disabled (user no longer in import list)")

    return actions


def create_user(
    cn: str,
    account_name: str,
    user_attributes: Dict[str, Any],
    name_resolution: NameResolution | None,
    active_directory: CachedActiveDirectory,
    user_container: ADContainer,
    logger: Logger,
) -> Tuple[ADUser | None, NameAction | None]:
    # check if there should be a renaming applied for this user
    if name_resolution is not None and name_resolution.is_accepted:
        new_account_name = name_resolution.new_name
    else:
        new_account_name = account_name

    # create a new user
    try:
        user = user_container.create_user(
            name=cn,
            enable=False,
            optional_attributes=user_attributes | {"sAMAccountName": new_account_name},
        )
        if account_name == new_account_name:
            logger.info(f"{user}: Was created")
        else:
            logger.info(f"{user}: Was created with renamed account name ({account_name} -> {new_account_name})")

        return user, None
    except win32Exception as e:
        # creation failed. check if it was because of a name conflict
        if e.error_info.get("error_code") != "0x80071392":
            # it was another problem. re-raise exception
            raise

        conflict_user = active_directory.find_single_user(
            domain=user_container.get_domain(),
            where=f"sAMAccountName = '{new_account_name}'",
        )
        if conflict_user is None:
            # it was another problem. re-raise exception
            raise

        # name conflict detected -> add required action
        # the action should refer to the account_name from the import file, not a previous renaming
        previous_error = None
        if account_name != new_account_name:
            conflict_user = active_directory.find_single_user(
                domain=user_container.get_domain(),
                where=f"sAMAccountName = '{account_name}'",
            )

            # edge case:
            if conflict_user is None:
                # seems that the original account name is available in the meantime
                logger.warning(
                    f"Account renaming applied for {cn} ({account_name} -> {new_account_name}) "
                    f"which gave another name conflict. But the original account name seems to be "
                    f"available in the meantime."
                )
                return create_user(
                    cn=cn,
                    account_name=account_name,
                    user_attributes=user_attributes,
                    name_resolution=None,
                    active_directory=active_directory,
                    user_container=user_container,
                    logger=logger,
                )

            previous_error = f"Account name {new_account_name} is already in use too ({conflict_user.dn})."

        return None, NameAction(
            user=cn,
            attributes=user_attributes,
            name=account_name,
            input_name=new_account_name,
            conflict_user=conflict_user.dn,
            error=previous_error,
        )
