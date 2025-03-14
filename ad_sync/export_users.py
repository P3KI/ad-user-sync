from functools import partial
from typing import Any, Dict, Callable


from . import CachedActiveDirectory
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

    def apply(self, source: Dict[str, Any], target: Dict[str, Any]):
        val = source.get(self.source_key)
        target[self.target_key] = self.parse(source[self.source_key]) if val is not None else None


def export_users(config: ExportConfig):
    confed_sub_path = partial(sub_path, config.base_path)
    confed_full_path = partial(full_path, config.base_path)

    query_groups = set(map(confed_full_path, config.search_groups))

    def parse_sub_path(v: str) -> str:
        v = confed_sub_path(v)  # Remove base path
        pos = v.find(",")
        return v[pos + 1 :] if pos >= 0 else ""  # Remove common name if present

    special_attribute_parsers: Dict[str, AttributeParser] = {
        "disabled": AttributeParser("disabled", "userAccountControl", lambda v: (v & 0x02) != 0),
        "accountExpires": AttributeParser("accountExpires", "accountExpires", convert_ad_datetime),
        # Include search groups memberships only, not all groups. Cut off the base path that all search results share.
        "memberOf": AttributeParser("memberOf", "memberOf", lambda v: list(map(confed_sub_path, query_groups.intersection(v)))),
        "subPath": AttributeParser("subPath", "distinguishedName", parse_sub_path),
    }

    attribute_parsers = list(
        map(
            lambda key: special_attribute_parsers.get(key, AttributeParser(key)),
            config.attributes | {"sAMAccountName", "cn", "disabled", "accountExpires", "memberOf"},
        )
    )

    # create a cached active directory instance for accessing AD
    active_directory = CachedActiveDirectory()

    query_attributes = tuple(map(lambda p: p.source_key, attribute_parsers))

    users = []
    for search_path in map(confed_full_path, config.search_sub_paths or [""]):
        users_attributes = active_directory.find_users_attributes(
            attributes=query_attributes,
            groups=tuple(query_groups),
            base_dn=search_path,
        )

        for user_attributes in users_attributes:
            user = {}
            for parser in attribute_parsers:
                parser.apply(user_attributes, user)
            users.append(user)

    return users
