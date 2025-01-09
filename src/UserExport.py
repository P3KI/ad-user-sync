from pyad import pyadutils
import json

from pyad.adquery import ADQuery

# import argparse

# parser = argparse.ArgumentParser(
#                     prog='UserExport',
#                     description='Export user accounts from Windows ActiveDirectory into a JSON file')
#
# parser.add_argument('-o', '--output', default="Users.json", help="File to write user account data to")
# parser.add_argument('-c', '--config', default = "ExportConfig.json", help="Export configuration file")
#
# args = parser.parse_args()
#
# print("Args:", args)

REQUIRED_ATTRIBUTES = {"sAMAccountName", "cn", "disabled", "accountExpires", "memberOf"}


class ADProperty:
    def __init__(self, parent, name, special=None):
        self.parent = parent
        self.name = name
        if special is None:
            self.attribute = name
            self.filter_function = None
        else:
            self.attribute = special["ldapAttribute"]
            self.filter_function = special["filter"]

    def filter(self, value):
        if self.filter_function is not None:
            return self.filter_function(self.parent, value)
        else:
            return value


class UserExporter:
    def __init__(self, file, config):
        self.config = config
        self.base_path = config["BasePath"]
        self.attributes = [
            ADProperty(self, a, UserExporter.SPECIAL_ATTRIBUTES.get(a, None))
            for a in set(config.get("Attributes", [])).union(REQUIRED_ATTRIBUTES)
        ]
        self.sub_paths = config.get("SearchSubPaths", [""])
        self.groups = config.get("SearchGroups", None)
        self.output_file = file

        print([a.name for a in self.attributes])

    def filter_date(self, date):
        # https://web.archive.org/web/20171214045055/http://docs.activestate.com/activepython/2.6/pywin32/html/com/help/active_directory.html#time
        # "Time in active directory is stored in a 64-bit integer that keeps track of the number of 100-nanosecond
        # intervals which have passed since January 1, 1601. The 64-bit value uses 2 32 bit parts to store the time."

        ts = pyadutils.convert_bigint(date)
        if ts == 0:  # If no expire date is set, the date object will convert to 0
            return None
        elif ts == 0x7FFFFFFFFFFFFFFF:  # Or to MAX_INT64, not sure why.
            return None
        else:
            return pyadutils.convert_datetime(date).isoformat()

    def filter_sub_path(self, dn):
        # Remove base path
        ret = self.sub_path(dn)
        # Remove common name
        pos = ret.find(",")
        if pos >= 0:
            ret = ret[pos + 1 :]
        else:
            ret = ""

        return ret

    # Filter out the groups sub-path. Cut off the base path that all search results share.
    def filter_groups(self, groups):
        if groups is None:
            return []

        groups = [self.sub_path(x) for x in groups]

        # #Only export the groups we are interested in
        # if self.groups is not None and len(self.groups) > 0:
        #     groups = [g for g in groups if g in self.groups]

        return groups

    def filter_disabled(self, uac_flags):
        return (uac_flags & self.UAC_ACCOUNTDISABLE) != 0

    # Appends the base path to turn a subpath into a full path (the distinguished name)
    def full_path(self, sub_path: str = ""):
        if len(sub_path) > 0:
            return f"{sub_path},{self.base_path}"
        else:
            return self.base_path

    # Removes the base path to turn a distinguished name into a relative path
    def sub_path(self, dn):
        return dn[0 : -len(self.base_path) - 1] if dn.endswith(self.base_path) else dn

    def build_group_filter(self, groups_dn):
        group_dns = [f"memberOf='{self.full_path(g)}'" for g in groups_dn]
        return f"({' OR '.join(group_dns)})"

    def get_users_in_path(self, sub_path, groups):
        attributes = list(map(lambda p: p.attribute, self.attributes))

        user_filter = "objectClass = 'user'"
        if groups is not None and len(groups) > 0:
            user_filter += " AND " + self.build_group_filter(groups)

        # print(user_filter)

        q = ADQuery()
        q.execute_query(attributes=attributes, where_clause=user_filter, base_dn=self.full_path(sub_path))

        users = []
        for row in q.get_results():
            user = {}
            for attr in self.attributes:
                value = attr.filter(row[attr.attribute])
                user[attr.name] = value

            users.append(user)

        return users

    def get_users(self, search_paths, search_groups):
        users = []
        for search_path in search_paths:
            users += self.get_users_in_path(search_path, search_groups)

        return users

    def run(self):
        users = self.get_users(self.sub_paths, self.groups)

        for user in users:
            print(user)

        with open(self.output_file, "w") as out:
            json.dump(users, out, ensure_ascii=False, indent=4)

    SPECIAL_ATTRIBUTES = {
        "subPath": {"ldapAttribute": "distinguishedName", "filter": filter_sub_path},
        "accountExpires": {"ldapAttribute": "accountExpires", "filter": filter_date},
        "memberOf": {"ldapAttribute": "memberOf", "filter": filter_groups},
        "disabled": {"ldapAttribute": "userAccountControl", "filter": filter_disabled},
    }
    UAC_ACCOUNTDISABLE = 0x02
