import argparse
import json
from datetime import datetime
from logging import Logger
from typing import Dict, List, Any, Set

from pywintypes import com_error
from pyad import ADGroup, ADUser, win32Exception, ADContainer

from .active_directory import CachedActiveDirectory
from .model import ImportConfig, ResolutionList, NameAction, EnableAction, JoinAction, NameResolution, ImportResult
from .model.Action import DisableAction, LeaveAction
from .util import not_none, full_path, union
from .user_file import UserFile


def import_users(
        args: argparse.Namespace,
        config: ImportConfig,
        logger: Logger,
        resolutions: ResolutionList = None,
) -> ImportResult:
    result = ImportResult()
    result.logger = logger
    # create an empty resolution list if none is provided
    resolutions = resolutions or ResolutionList()

    # create a cached active directory instance for accessing AD
    active_directory = CachedActiveDirectory(logger)
    def get_group(g: str) -> ADGroup:
        return active_directory.get_group(full_path(config.group_path, g))

    # resolve the config GroupMap form AD
    group_map: Dict[str, Set[ADGroup]] = {}
    for source_group, target_groups in config.group_map.items():
        group_map[source_group] = set(map(get_group, target_groups))
    logger.debug(f"{len(group_map)} group mappings loaded")

    # resolve the config RestrictedGroups form AD
    restricted_groups = [active_directory.get_group(full_path(config.group_path, v)) for v in config.restricted_groups]
    restricted_groups = set(map(get_group, config.restricted_groups))

    # Read users form input file
    users_attributes: List[Dict[str, Any]] = UserFile.read(config.input_file, args.hmac_key)

    if config.log_input_file_content:
        logger.info(f"Input: {json.dumps(users_attributes)}")
    else:
        logger.info("Input: Importing %s users", len(users_attributes))

    # The path where all managed users will be created. Defined by ManagedUserPath
    user_container = active_directory.get_container(config.managed_user_path)

    # All users imported during this run
    current_users: Set[ADUser] = set()  # list of users that are present in the current import list

    # User memberships for all managed groups are collected here
    current_members_by_group: Dict[ADGroup, Set[ADUser]] = {k: set() for k in set().union(*group_map.values()) }

    for user_attributes in users_attributes:
        # Remove attributes that can not be applied using ADUser.update_attributes() function
        cn: str = config.prefix_common_names + user_attributes.pop("cn")  # used as key and for user creation
        account_name: str = user_attributes.pop("sAMAccountName")  # used for user creation
        member_of: List[str] = user_attributes.pop("memberOf")  # will be mapped to "member" attribute of groups
        account_expires: str | None = user_attributes.pop("accountExpires", None)  # set via ADUser.set_expiration()
        disable: bool = user_attributes.pop("disabled", False)  # We only disable via ADUser.disable(), never enable
        user_attributes.pop("subPath", None)  # Currently not used, not a valid AD attribute.
        user_attributes.pop("distinguishedName", None)  # domain specific, should not be exported in the first place

        logger.debug("==== Importing %s ====", cn)
        # Retrieve existing user, if present

        name_resolution = resolutions.get_name(cn, account_name)
        # If the user selected to resolve a name conflict by taking over the existing account, we need to search for that
        if (name_resolution is not None) and name_resolution.is_accepted and name_resolution.take_over_account:
            user = active_directory.find_single_user(user_container.get_domain(), f"sAMAccountName = '{account_name}'")
        else:
            user = active_directory.find_single_user(user_container, f"cn = '{cn}'")

        # Handle disabled users
        if disable:
            if user is None:
                # User does not exist locally (manually deleted or never created), just ignore it.
                continue
            else:
                logger.debug("%s: User disabled import", user.cn)
                handle_disabled_user(logger, resolutions, result, user, False)

        # Create user or update user attributes
        if user is None:
            user = create_user(
                cn=cn,
                account_name=account_name,
                user_attributes=user_attributes,
                name_resolution=resolutions.get_name(cn, account_name),
                active_directory=active_directory,
                user_container=user_container,
                logger=logger,
                result=result,
            )
            if user is None:
                # go to next user to import if creation failed
                continue
        else:
            if user.parent_container != user_container:
                user.move(user_container)

            if user.get_attribute("cn", False) != cn:
                try:
                    user.rename(cn, False)
                    # HACK: `ADObject.rename()` crashes out because `self.get_attribute("distinguishedName")` does still return the old dn for unknown reasons.
                    #      Catch it and update the user object manually.
                except com_error as ex:
                    if (ex.excepinfo[5] & 0xFFFFFFFF) == 0x80072030:
                        user = ADUser.from_dn("CN=" + cn + "," + user_container.dn)
                    else:
                        raise

            # update the attributes of existing user
            old_attributes = {k: user.get_attribute(k, False) for k in user_attributes}
            if user_attributes != old_attributes:
                user.update_attributes(user_attributes)
                result.add_updated(user)
                logger.info(f"{user.cn}: Attributes were updated")
            else:
                logger.debug("%s: Attributes unchanged", user.cn)

        # add the user to the list of users, present in the current import list
        current_users.add(user)

        if not disable:
            # Extend expiration (disabled users in the import are left to expire)
            user.set_expiration(datetime.now() + config.expiration_time)

            # Enable the User
            if is_disabled(user):
                # enabling a disabled existing user requires a resolved interactive action
                # we do not enable automatically
                enable_resolution = resolutions.get_enable(user.cn)
                if enable_resolution is None:
                    # no resolved action was found -> add interactive action
                    result.require_interaction(EnableAction(user=user.cn))
                elif enable_resolution.accept is True:
                    # resolved action was found and it got accepted
                    try:
                        user.set_password(enable_resolution.password)
                        update_user_password_settings(user, config)
                        user.enable()
                        result.add_enabled(user)
                        logger.info(f"{user.cn}: Was enabled (accepted manually)")
                    except win32Exception as e:
                        if e.error_info.get("error_code") != "0x800708c5":
                            raise
                        logger.debug(f"{user.cn}: Manually provided password does not match requirements")
                        result.require_interaction(
                            EnableAction(
                                user=user.cn,
                                error=e.error_info.get("message", "Password does not meet requirements"),
                            )
                        )

                else:
                    # resolved action was found and it got rejected
                    logger.debug(f"{user.cn}: Stays disabled (rejected manually at {enable_resolution.timestamp})")

        # Add user as a member to managed groups for later processing
        # We can't set group membership for a user directly, instead we have to set user members for groups.
        #   1. Add "*" to `member_of` of the user to also map the catch-all group.
        #   2. Map all given groups to local AD groups according to group_map (unmapped groups will be None).
        #   3. Filter out unmapped groups (`None` values).
        #   4. Remove duplicates by collecting groups in a set.
        # Then add the user as a member to every group.
        for user_group in set().union(*map(group_map.get, member_of + ["*"])):
            current_members_by_group[user_group].add(user)

    logger.debug("==== Updating group memberships ====")

    # Update memberships of managed groups
    for group, current_group_members in current_members_by_group.items():
        old_members: Set[ADUser] = set(group.get_members(ignore_groups=True))

        # remove users from group if the user is still in the import file, but no longer has the group membership
        removed_members = (old_members - current_group_members) & current_users
        if len(removed_members) > 0:
            # group.remove_members(removed_members)
            for user in removed_members:
                logger.info(f'{user.cn}: Removed from group "{group.cn}" (membership not present in import list)')
                leave_resolution = resolutions.get_leave(user=user.cn, group=group.cn)
                if leave_resolution is None:
                    result.require_interaction(LeaveAction(user=user.cn, group=group.cn))
                elif leave_resolution.accept is True:
                    group.remove_members([user])
                    result.add_left(user, group)

        # add members to group that haven't been members before
        if group not in restricted_groups:
            # unrestricted groups can just be joined
            new_members = current_group_members - old_members
            if len(new_members) > 0:
                group.add_members(new_members)
                for user in new_members:
                    logger.info(f'{user.cn}: Joined group "{group.cn}"')
                    result.add_joined(user, group)
        else:
            # joining a restricted group requires a resolved interactive action
            new_members = []

            # filter the users that are accepted in the restricted group
            for user in current_group_members - old_members:
                # see if there is a resolved action
                join_resolution = resolutions.get_join(user=user.cn, group=group.cn)
                if join_resolution is None:
                    # no resolved action was found  -> add interactive action
                    result.require_interaction(JoinAction(user=user.cn, group=group.cn))
                elif join_resolution.accept is True:
                    # resolved action was found and it was accepted
                    new_members.append(user)
                else:
                    # resolved action was found and it was rejected
                    logger.debug(
                        f'{user.cn}: Not joining restricted group "{group.cn}" '
                        f"(rejected manually at {join_resolution.timestamp})"
                    )

            # add the approved members to the group
            if len(new_members) > 0:
                group.add_members(new_members)
                for user in new_members:
                    logger.info(f'{user.cn}: Joined restricted group "{group.cn}" (accepted manually)')
                    result.add_joined(user, group)

    logger.debug("==== Looking for orphaned user accounts ====")
    # Check of existing users that are not in the import file.
    missing_users = active_directory.find_users(user_container) - current_users
    logger.debug("Found %i orphaned accounts", len(missing_users))
    for user in missing_users:
        logger.debug("%s: User account no longer in import", user.cn)
        handle_disabled_user(logger, resolutions, result, user, True)

    return result


def handle_disabled_user(logger: Logger, resolutions: ResolutionList, result: ImportResult, user: ADUser,
                         deleted: bool):
    # Don't disable user automatically, use interaction.
    if not is_disabled(user):
        disable_resolution = resolutions.get_disable(user.cn)
        if disable_resolution is None:
            # No resolution was found -> Add interactive action
            result.require_interaction(DisableAction(user=user.cn, deleted=deleted))
        elif disable_resolution.accept is True:
            # Disable action was accepted -> Disable user
            result.add_disabled(user)
            user.disable()
            logger.info(f"{user.cn}: Was disabled (accepted manually)")
        else:
            logger.info(f"{user.cn}: Disabled user is left to expire")


def is_disabled(user: ADUser) -> bool:
    return user._ldap_adsi_obj.AccountDisabled


def create_user(
        cn: str,
        account_name: str,
        user_attributes: Dict[str, Any],
        name_resolution: NameResolution | None,
        active_directory: CachedActiveDirectory,
        user_container: ADContainer,
        logger: Logger,
        result: ImportResult,
) -> ADUser | None:
    # check if there should be a renaming applied for this user
    if name_resolution is not None and name_resolution.is_accepted:
        new_account_name = name_resolution.new_name
        logger.debug("Creating new user %s (renamed from %s)...", new_account_name, account_name)
    else:
        new_account_name = account_name
        logger.debug("Creating new user %s...", account_name)

    # create a new user
    try:
        attrs: Dict[str, Any] = user_attributes | {"sAMAccountName": new_account_name}
        if not "userPrincipalName" in attrs:
            # Work around incorrect default UPN set by pyad, by always setting it explicitly.
            attrs["userPrincipalName"] = f"{new_account_name}@{user_container.get_domain().get_default_upn()}"

        user = user_container.create_user(
            name=cn,
            enable=False,
            optional_attributes=attrs,
        )
        result.add_created(user)
        if account_name == new_account_name:
            logger.info(f"{user.cn}: Was created")
        else:
            logger.info(f"{user.cn}: Was created with renamed account name ({account_name} -> {new_account_name})")

        return user

    except win32Exception as e:
        # creation failed. check if it was because of a cn conflict
        conflict_user = active_directory.find_single_user(None, f"cn = '{cn}'")
        if conflict_user is not None:
            logger.error(f"Unmanaged user with same cn exists: {cn}")
            return None

        # creation failed. check if it was because of a name conflict
        conflict_user = active_directory.find_single_user(
            parent=None,  # user_container.get_domain(),
            where=f"sAMAccountName = '{new_account_name}'",
        )
        if conflict_user is not None:
            # name conflict detected -> add required action
            # the action should refer to the account_name from the import file, not a previous renaming
            logger.debug("User %s with the same account name ('%s') found.", conflict_user.dn, new_account_name)

            previous_error = None
            if account_name != new_account_name:
                conflict_user = active_directory.find_single_user(
                    parent=user_container.get_domain(),
                    where=f"sAMAccountName = '{account_name}'",
                )

                # edge case:
                if conflict_user is None:
                    # seems that the original account name is available in the meantime
                    logger.debug(
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
                        result=result,
                    )

                previous_error = f"Account name {new_account_name} is already in use too ({conflict_user.cn})."

            if name_resolution is None or name_resolution.is_accepted:
                result.require_interaction(
                    NameAction(
                        user=cn,
                        attributes=user_attributes,
                        name=account_name,
                        input_name=new_account_name,
                        conflict_user=conflict_user.cn,
                        error=previous_error,
                    )
                )
            return None

        # it was another problem. re-raise exception
        raise


def update_user_password_settings(user: ADUser, config: ImportConfig):
    if config.users_must_change_password:
        user.force_pwd_change_on_login()

    set_user_cant_change_password(user, config.users_can_not_change_password)

    user.set_user_account_control_setting("PASSWD_NOTREQD", False)


# Based on https://blog.steamsprocket.org.uk/2011/07/04/user-cannot-change-password-using-python/
# and https://learn.microsoft.com/en-us/windows/win32/adsi/modifying-user-cannot-change-password-ldap-provider
# A users ability to change its password is not a simple AD attribute,
# instead it is a permission governed by the user objects ACL (Access Control List).
# (This means we could technically give permission to change this users password to other users.)
# The relevant ACL entries is selected by GUID (ObjectType) and user (Trustee)
# We change the permission entry for the user to which the ACL belongs (self) and the all users entry (everyone).
def set_user_cant_change_password(user: ADUser, disallow_change_password: bool):
    import win32security

    GUID_CHANGE_PASSWORD = '{ab721a53-1e2f-11d0-9819-00aa0040529b}'
    SID_SELF = "S-1-5-10"  # The user to which this ACL is attached
    SID_EVERYONE = "S-1-1-0"  # Every user on the system

    selfAccount = win32security.LookupAccountSid(None, win32security.GetBinarySid(SID_SELF))
    everyoneAccount = win32security.LookupAccountSid(None, win32security.GetBinarySid(SID_EVERYONE))
    # Format the same way as ACL entries (<domain>\<name>)
    selfName = ("%s\\%s" % (selfAccount[1], selfAccount[0])).strip('\\')
    everyoneName = ("%s\\%s" % (everyoneAccount[1], everyoneAccount[0])).strip('\\')

    user_priv = user._ldap_adsi_obj
    security_descriptor = user_priv.ntSecurityDescriptor
    acl = security_descriptor.DiscretionaryAcl

    for entry in acl:
        if entry.ObjectType.lower() == GUID_CHANGE_PASSWORD:
            if entry.Trustee == selfName or entry.Trustee == everyoneName:
                if disallow_change_password:
                    entry.AceType = win32security.ACCESS_DENIED_OBJECT_ACE_TYPE
                else:
                    entry.AceType = win32security.ACCESS_ALLOWED_OBJECT_ACE_TYPE

    security_descriptor.DiscretionaryAcl = acl
    user_priv.ntSecurityDescriptor = security_descriptor
