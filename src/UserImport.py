import sys
import json
from datetime import datetime
from typing import Dict

from dateutil.relativedelta import relativedelta
from pyad.adcontainer import ADContainer
from pyad.adgroup import ADGroup
from pyad.adquery import ADQuery
from pyad.aduser import ADUser
from pyad.pyadexceptions import win32Exception

from src import InteractiveImport
from src.model import ImportConfig

try:
    from pywintypes import com_error
except ImportError:
    # todo: try if this works on windows. if yes: get rid of the pywin32 dependency
    from pyad.pyadexceptions import comException as com_error


# Attributes that can not be applied using ADUser.update_attributes() function, but require special handling
ATTRIBUTE_BLACKLIST = {
    "cn",  # Only used during user creation
    "sAMAccountName",  # Only set during user creation, not updated after wards
    "memberOf",  # Special handling: "memberOf" attribute of users can not be written, must use "member" attribute of groups.
    "distinguishedName",  # should not be exported in the first place, since it is domain specific
    "subPath",  # Currently not used, not a valid AD attribute.
    "disabled",  # Special handling: We only disable, never enable
    "accountExpires",  # Special handling: Need to call ADUser.set_expiration() to set it.
}


# Print error message
def error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


class UserImporter:
    _group_cache: Dict[str, ADGroup]
    config: ImportConfig
    input_file: str

    def __init__(self, input_file: str, config: ImportConfig):
        self._group_cache = {}
        self.config = config
        self.input_file = input_file
        self.user_container = self.get_user_container(config.get("ManagedUserPath", "CN=P3KI Managed"))
        self.group_map = self.make_group_map(config.get("GroupMap", []))
        self.restricted_groups = self.make_group_list(config.get("RestrictedGroups", []))
        self.pending_actions_file = config.get("InteractiveActionsOutput", "Pending.json")

    # Create AD container object from distinguished name.
    def get_user_container(self, sub_path: str):
        dn = self.full_path(sub_path)
        try:
            return ADContainer.from_dn(dn)
        except (com_error, win32Exception) as e:
            error("Error: Loading managed user path from config failed. Does the path exist in AD?")
            error(f"    Path entry: ManagedUserPath : {sub_path}")
            error(f"    Looking for path: {dn}")
            error(f"    {e}")
            exit(2)

    # Create AD group object from distinguished name. Cached.
    def resolve_group(self, dn: str) -> ADGroup:
        group = self._group_cache.get(dn)
        if group is None:
            group = ADGroup.from_dn(dn)
            self._group_cache[dn] = group
        return group

    # Map exported group names to local AD groups
    def map_groups(self, sub_paths):
        ret = []
        for sub_path in sub_paths:
            mapped = self.group_map.get(sub_path, None)
            if mapped:
                ret.append(mapped)

        common = self.group_map.get("*", None)
        if common is not None:
            ret.append(common)

        return ret

    # Create a map for all specified sub-paths to local managed AD Groups.
    def make_group_map(self, group_map):
        ret = {}
        for sub_path in group_map.keys():
            mapped = group_map[sub_path]
            try:
                ret[sub_path] = self.resolve_group(self.config.full_path(mapped))
            except (com_error, win32Exception) as e:
                error("Error: Failed to load group mapping from configuration. Do all specified groups exist in AD?")
                error(f"    Failed at mapping entry: {sub_path} : {mapped}")
                error(f"    Looking for group: {self.config.full_path(mapped)}")
                error(f"    {e}")
                exit(1)

        return ret

    # Create a list of ADGroups from all specified sub-paths.
    def make_group_list(self, group_list):
        ret = set()
        for sub_path in group_list:
            try:
                ret.add(self.resolve_group(self.config.full_path(sub_path)))
            except (com_error, win32Exception) as e:
                error(
                    "Error: Failed to load restricted groups from configuration. Do all specified groups exist in AD?"
                )
                error(f"    Failed at group entry: {sub_path}")
                error(f"    Looking for group: {self.config.full_path(sub_path)}")
                error(f"    {e}")
                exit(1)

        return ret

    def map_name(self, name: str):
        return self.config["PrefixAccountNames"] + name

    # Find an existing AD user by common name (cn)
    def find_user(self, parent: ADContainer, cn: str):
        q = ADQuery()
        q.execute_query(
            attributes=["distinguishedName"],
            where_clause=f"objectClass = 'user' AND cn = '{cn}'",
            base_dn=parent.dn,
        )
        if len(q) == 0:
            return None
        else:
            dn = q.get_single_result()["distinguishedName"]
            return ADUser.from_dn(dn)

    def find_conflicting_user(self, domain: ADContainer, account_name: str):
        q = ADQuery()
        q.execute_query(
            attributes=["distinguishedName"],
            where_clause=f"objectClass = 'user' AND sAMAccountName = '{account_name}'",
            base_dn=domain.dn,
        )
        if len(q) == 0:
            return None
        else:
            dn = q.get_single_result()["distinguishedName"]
            return ADUser.from_dn(dn)

    def run(self):
        # Read users
        with open(self.input_file) as f:
            users = json.load(f)

        print("Users:", users)

        InteractiveImport.load_resolved(self.pending_actions_file)

        # Memberships in all managed groups are collected here.
        group_members = {k: [] for k in self.group_map.values()}

        # Path where all managed users will be created.

        # Managed users currently in AD
        old_users = self.user_container.get_children(recursive=False, filter=[ADUser])

        # All users imported during this run
        new_users = set()

        for user in users:
            parent = self.user_container
            groups = self.map_groups(user["memberOf"])

            # Apply name prefixes, if configured
            cn = self.map_name(user["cn"])
            account_name = self.map_name(user["sAMAccountName"])

            # Extract attribute values, so they can be applied to the target domain.
            attributes = {k: v for k, v in user.items() if k not in ATTRIBUTE_BLACKLIST}

            # Create user or update user attributes
            u = self.find_user(parent, cn)
            if u is None:
                print("Creating user:", cn)
                try:
                    u = parent.create_user(
                        cn,
                        enable=False,
                        optional_attributes=(attributes | {"sAMAccountName": account_name}),
                    )
                except (com_error, win32Exception) as e:
                    conflict_user = self.find_conflicting_user(parent.get_domain(), account_name)
                    if conflict_user:
                        print(f"Failed to create user '{cn}' due to account name already in use: {account_name}")
                        InteractiveImport.add_action(
                            InteractiveImport.UserResolveAccountNameConflict(
                                cn, conflict_user.cn, account_name, attributes
                            )
                        )
                        continue
                    else:
                        error(f"Error: Failed to create user '{cn}' with login name '{attributes['sAMAccountName']}'")
                        error(f"    Does another use with this login name already exists?")
                        error(f"    {e}")
                        exit(3)
            else:
                print("Updating user:", u.cn)
                u.update_attributes(attributes)

            ###
            # Handle special attributes that can not be set via update_attributes, because they require custom logic.
            ###

            # set expiration to at least the default_expiration
            expiration_date = self.config.get_default_expiration_date()
            if user["accountExpires"]:
                account_expires = datetime.fromisoformat(user["accountExpires"])
                if account_expires > expiration_date:
                    expiration_date = account_expires
            u.set_expiration(expiration_date)

            # If the user should be enabled, but is disabled, add an interactive action for it.
            # Do not enable automatically.
            if u._ldap_adsi_obj.AccountDisabled and not user["disabled"]:
                print(f"User {u} not automatically enabled.")
                InteractiveImport.add_action(InteractiveImport.UserEnableAction(u.dn))

            if user["disabled"]:
                u.disable()

            # Collect group membership
            # We can't set group membership for users, instead we have to set user members for groups
            for group in groups:
                group_members[group] += [u]

            # Collect all users from the current import
            new_users.add(u)

        # Apply memberships to managed groups
        for group in group_members:
            old_members = group.get_members(ignore_groups=True)
            new_members = group_members[group]

            removed_members = [u for u in old_members if u not in new_members]
            added_members = [u for u in new_members if u not in old_members]

            if len(removed_members) > 0:
                print(f"Removing users from group '{group.cn}': {removed_members}")
                group.remove_members(removed_members)

            if len(added_members) > 0:
                if group in self.restricted_groups:
                    for u in added_members:
                        print(f"User {u} not automatically adding to restricted group: {group.cn}")
                        InteractiveImport.add_action(InteractiveImport.UserJoinGroupAction(u.dn, group.dn))
                else:
                    print(f"Adding users to group '{group.cn}': {added_members}")
                    group.add_members(added_members)

        removed_users = [u for u in old_users if u not in new_users]
        for u in removed_users:
            print(f"Disabling user: {u.cn} (no longer in import list)")
            u.disable()

        if self.pending_actions_file is not None:
            if InteractiveImport.any_actions():
                print(f"Saving action requiring intervention to {self.pending_actions_file}")
            InteractiveImport.save(self.pending_actions_file)  # Save either way
