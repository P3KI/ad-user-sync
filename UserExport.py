#!/usr/bin/env python3

from pyad import adquery, pyadutils
import json
import argparse

parser = argparse.ArgumentParser(
                    prog='UserExport',
                    description='Export user accounts from Windows ActiveDirectory into a JSON file')

parser.add_argument('-o', '--output', default="Users.json", help="File to write user account data to")
parser.add_argument('-c', '--config', default = "ExportConfig.json", help="Export configuration file")

args = parser.parse_args()

print("Args:", args)


class ADProperty:
    def __init__(self, name, special = None):
        self.name = name
        if special is None:
            self.attribute = name
            self.filter_function = None
        else:
            self.attribute = special["ldapAttribute"]
            self.filter_function = special["filter"]


    def filter(self, value):
        if self.filter_function is not None:
            return self.filter_function(value)
        else:
            return value

def filter_date(date):
    # https://web.archive.org/web/20171214045055/http://docs.activestate.com/activepython/2.6/pywin32/html/com/help/active_directory.html#time
    # "Time in active directory is stored in a 64 bit integer that keeps track of the number of 100-nanosecond intervals which have passed since January 1, 1601.
    # The 64-bit value uses 2 32 bit parts to store the time."

    ts = pyadutils.convert_bigint(date)
    if ts == 0: #If no expire date is set, the date object will convert to 0
        return None
    elif ts == 0x7fffffffffffffff: #Or to MAX_INT64, not sure why.
        return None
    else:
        return pyadutils.convert_datetime(date).isoformat()

def filter_sub_path(dn):
    #Remove base path
    ret = sub_path(dn)
    #Remove common name
    pos = ret.find(",")
    if pos >= 0:
        ret = ret[pos+1:]
    else:
        ret = ""

    return ret

def filter_groups(groups): #Filter out the groups sub-path. Cut off the base path that all search results share.
    if groups is None:
        return []

    groups = [sub_path(x) for x in groups]

    # #Only export the groups we are interested in
    # if GROUPS is not None and len(GROUPS) > 0:
    #     groups = [g for g in groups if g in GROUPS]

    return groups

def filter_disabled(uac_flags):
    ACCOUNTDISABLE = 0x02
    return (uac_flags & ACCOUNTDISABLE) != 0

SPECIAL_ATTRIBUTES = {
    "subPath"        : {"ldapAttribute" : "distinguishedName", "filter" : filter_sub_path},
    "accountExpires" : {"ldapAttribute" : "accountExpires",    "filter" : filter_date},
    "memberOf"       : {"ldapAttribute" : "memberOf",          "filter" : filter_groups},
    "disabled"       : {"ldapAttribute" : "userAccountControl","filter" : filter_disabled}
}


## Appends the base path to turn a subpath into a full path (the distinguished name)
def full_path(subpath : str = ""):
    if len(subpath) > 0:
        return subpath + "," + BASE_PATH
    else:
        return BASE_PATH

## Removes the base path to turn a distinguished name into a relative path
def sub_path(dn):
    return dn[0:-len(BASE_PATH) - 1] if dn.endswith(BASE_PATH) else dn



def build_group_filter(groups_dn):
    group_dns = [("memberOf='" + full_path(g) + "'" ) for g in groups_dn]
    return "(" + (" OR ".join(group_dns)) + ")"


def get_users_in_path(subpath, groups):
    attributes = list(map(lambda p: p.attribute, ATTRIBUTES))

    user_filter = "objectClass = 'user'"
    if groups is not None and len(groups) > 0:
        user_filter += " AND " + build_group_filter(groups)

    #print(user_filter)

    q = adquery.ADQuery()
    q.execute_query(attributes=attributes, where_clause=user_filter, base_dn=full_path(subpath))

    users = []
    for row in q.get_results():
        user = {}
        for attr in ATTRIBUTES:
            value = attr.filter(row[attr.attribute])
            user[attr.name] = value

        users.append(user)

    return users


def get_users(search_paths, search_groups):
    users = []
    for search_path in search_paths:
        users += get_users_in_path(search_path, search_groups)

    return users


with open(args.config) as f:
    CONFIG = json.load(f)

BASE_PATH   = CONFIG["BasePath"]
ATTRIBUTES  = [ADProperty(a, SPECIAL_ATTRIBUTES.get(a, None)) for a in CONFIG["Attributes"]]
SUB_PATHS   = CONFIG.get("SearchSubPaths", [""])
GROUPS      = CONFIG.get("SearchGroups", None)

users = get_users(SUB_PATHS, GROUPS)

for user in users:
    print(user)

with open(args.output, "w") as out:
    json.dump(users, out, ensure_ascii=False, indent=4)
