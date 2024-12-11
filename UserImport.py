#!/usr/bin/env python3

import sys
from pyad import adcontainer, addomain, aduser, adquery, adgroup, pyadutils, pyadexceptions
import json
import argparse
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pywintypes import com_error
import pywintypes

parser = argparse.ArgumentParser(
                    prog='UserImport',
                    description='Import user accounts into Windows ActiveDirectory')

parser.add_argument('-i', '--input', default="Users.json", help="File containing the users to import")
parser.add_argument('-c', '--config', default = "ImportConfig.json", help="Import configuration file")

args = parser.parse_args()

print("Args:", args)

## Print error message
def error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

## Appends the base path to turn a subpath into a full path (the distinguished name)
def full_path(subpath : str = ""):
    if len(subpath) > 0:
        return subpath + "," + BASE_PATH
    else:
        return BASE_PATH

## Create AD container object from distinguished name.
def get_user_container(sub_path : str):
    try:
        dn = full_path(sub_path)
        container = adcontainer.ADContainer.from_dn(dn)
    except (com_error, pyadexceptions.win32Exception) as e:
        error("Error: Loading managed user path from config failed. Does the path exist in AD?")
        error("       Path entry: ManagedUserPath :", sub_path)
        error("       Looking for path:", dn)
        error("      ", e)
        exit(2)

    return container


GROUPS = {}
## Create AD group object from distinguished name. Cached.
def get_group(dn : str):
    group = GROUPS.get(dn, None)
    if group is None:
        group = adgroup.ADGroup.from_dn(dn)
        GROUPS[dn] = group

    return group

## Map exported group names to local AD groups
def map_groups(sub_paths):
    ret = []
    for sub_path in sub_paths:
        mapped = GROUP_MAP.get(sub_path, None)
        if mapped:
            ret.append(mapped)

    common = GROUP_MAP.get("*", None)
    if common is not None:
        ret.append(common)

    return ret

## Create a map for all specified sub-paths to local managed AD Groups.
## Used by map_groups() but also be the main code to turn it into a list of all managed groups
def make_group_map(group_map):
    ret = {}
    for sub_path in group_map.keys():
        mapped = group_map[sub_path]
        try:
            ret[sub_path] = get_group(full_path(mapped))
        except (com_error, pyadexceptions.win32Exception) as e:
            error("Error: Failed to load group mapping from configuration. Do all specified groups exist in AD?")
            error("       Failed at mapping entry:", sub_path, ":", mapped)
            error("       Looking for group:", full_path(mapped))
            error("      ", e)
            exit(1)

    return ret

def make_expiration_date(cfg):
    years = 0
    months = 1
    days = 1

    if cfg is not None:
        years = cfg.get("Years", 0)
        months = cfg.get("Months", 0)
        days = cfg.get("Days", 0)

    now = datetime.now()

    expiration = now + relativedelta(years = years, months = months, days = days)
    min        = now + relativedelta(days = 1)

    if expiration <= min:
        error("Managed user expiration time is very short, ensure this is the intended setting:", cfg)

    return expiration

def map_name(name : str):
    return CONFIG["PrefixAccountNames"] + name


# Find an existing AD user by common name (cn)
def find_user(parent : adcontainer.ADContainer, cn : str):
    q = adquery.ADQuery()
    q.execute_query(attributes=["distinguishedName"], where_clause="objectClass = 'user' AND cn = '" + cn + "'", base_dn=parent.dn)
    if q.get_row_count() == 0:
        return None
    else:
        dn = q.get_single_result()["distinguishedName"]
        return aduser.ADUser.from_dn(dn)


## Attributes that can not be applied using ADUser.update_attributes() function, but require special handling
ATTRIBUTE_BLACKLIST = {
    "cn"               , # Only used during user creation
    "memberOf"         , # Special handling: "memberOf" attribute of users can not be written, must use "member" attribute of groups.
    "distinguishedName", # should not be exported in the first place, since it is domain specific
    "subPath"          , # Currently not used, not a valid AD attribute.
    "disabled"         , # Special handling: We only disable, never enable
    "accountExpires"   , # Special handling: Need to call ADUser.set_expiration() to set it.
}

# Read config
with open(args.config) as cfg:
    CONFIG = json.load(cfg)

BASE_PATH          = CONFIG["BasePath"]
USER_CONTAINER     = get_user_container(CONFIG.get("ManagedUserPath", "CN=P3KI Managed"))
GROUP_MAP          = make_group_map(CONFIG.get("GroupMap", []))

DEFAULT_EXPIRATION = make_expiration_date(CONFIG.get("DefaultExpiration", "default"))

print("Config:", CONFIG)

#Read users
with open(args.input) as input:
    USERS = json.load(input)

print("Users:", USERS)

# Memberships in all managed groups are collected here.
group_members = {k: [] for k in GROUP_MAP.values()}

# Path where all managed users will be created.

# Managed users currently in AD
old_users = USER_CONTAINER.get_children(recursive=False, filter = [aduser.ADUser])

# All users imported during this run
new_users = set()

for user in USERS:
    parent = USER_CONTAINER
    groups = map_groups(user["memberOf"])

    #Apply name prefixes, if configured
    cn = map_name(user["cn"])
    user["sAMAccountName"] = map_name(user["sAMAccountName"])

    # Extract attribute values so they can be applied to the target domain.
    attributes = {k: v for k, v in user.items() if k not in ATTRIBUTE_BLACKLIST}

    # Create user or update user attributes
    u = find_user(parent, cn)
    if u is None:
        print("Creating user:", cn)
        try:
            u = parent.create_user(cn, enable=False, optional_attributes=attributes)
        except (com_error, pyadexceptions.win32Exception) as e:
            error("Error: Failed to create user '" + cn + "' with login name '" + attributes["sAMAccountName"] + "'")
            error("       Does another use with this login name already exists?")
            error("      ", e)
            exit(3)
    else:
        print("Updating user:", u.cn)
        u.update_attributes(attributes)

    ###
    # Handle special attributes that can not be set via update_attributes, because they require custom logic.
    ###
    if user["accountExpires"]:
        user_expiration = datetime.fromisoformat(user["accountExpires"])
        if (DEFAULT_EXPIRATION is datetime) and (user_expiration > DEFAULT_EXPIRATION): #Limit to DEFAULT_EXPIRATION date
            u.set_expiration(DEFAULT_EXPIRATION)
        else:
            u.set_expiration(user_expiration)
    else:
        u.set_expiration(DEFAULT_EXPIRATION)


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
    added_members   = [u for u in new_members if u not in old_members]

    if len(removed_members) > 0:
        print("Removing users from group '" + group.cn + "' :", removed_members)
        group.remove_members(removed_members)

    if len(added_members) > 0:
        print("Adding users to group '" + group.cn + "' :", added_members)
        group.add_members(added_members)


removed_users = [u for u in old_users if u not in new_users]
for u in removed_users:
    print("Disabling user:", u.cn, "(no longer in import list)")
    u.disable()