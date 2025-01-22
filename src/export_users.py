from functools import partial
from typing import Any, Dict, Callable

from pyad import ADQuery
import json


from .model import ExportConfig
from .util import convert_ad_datetime, full_path, sub_path


class AttributeParser:
    target_key: str
    source_key: str
    parse: Callable[[Any], Any]

    def __init__(self, key: str, source_key: str = None, parse: Callable[[Any], Any] = lambda value: value) -> None:
        self.target_key = key
        self.source_key = source_key if source_key is not None else key
        self.parse = parse


def export_users(config: ExportConfig):
    config_sub_path = partial(sub_path, config.base_path)

    def parse_sub_path(v: str) -> str:
        v = config_sub_path(v)  # Remove base path
        pos = v.find(",")
        return v[pos + 1 :] if pos >= 0 else ""  # Remove common name if present

    special_attribute_parsers: Dict[str, AttributeParser] = {
        "disabled": AttributeParser("disabled", "userAccountControl", lambda v: (v & 0x02) != 0),
        "accountExpires": AttributeParser("accountExpires", "accountExpires", convert_ad_datetime),
        # Filter out the groups sub-path. Cut off the base path that all search results share.
        "memberOf": AttributeParser("memberOf", "memberOf", lambda v: list(map(config_sub_path, v))),
        "subPath": AttributeParser("subPath", "distinguishedName", parse_sub_path),
    }

    attribute_parsers = list(
        map(
            lambda key: special_attribute_parsers.get(key, AttributeParser(key)),
            config.attributes | {"sAMAccountName", "cn", "disabled", "accountExpires", "memberOf"},
        )
    )
    query_attributes = list(map(lambda p: p.source_key, attribute_parsers))

    users = []
    for search_path in config.sub_paths:
        user_filter = "objectClass = 'user'"
        if len(config.search_groups) > 0:
            group_dns = map(lambda g: f"memberOf='{full_path(config.base_path, g)}'", config.search_groups)
            user_filter += f" AND ({' OR '.join(group_dns)})"

        query = ADQuery()
        query.execute_query(
            attributes=query_attributes,
            where_clause=user_filter,
            base_dn=full_path(config.base_path, search_path),
        )

        for row in query.get_results():
            user = {}
            for parser in attribute_parsers:
                user[parser.target_key] = parser.parse(row[parser.source_key])
            users.append(user)

    return users
