from functools import lru_cache
from typing import List, Dict, Any, Tuple

from pyad import ADContainer, ADGroup, ADQuery, ADUser


class CachedActiveDirectory:
    @lru_cache(maxsize=None)
    def find_single_user(self, domain: ADContainer | None, where: str) -> ADUser | None:
        query = ADQuery()
        query.execute_query(
            attributes=["distinguishedName"],
            where_clause=f"objectClass = 'user' AND {where}",
            base_dn=domain.dn if domain else None,
        )
        if len(query) == 0:
            return None

        dn = query.get_single_result()["distinguishedName"]
        return ADUser.from_dn(dn)

    @lru_cache(maxsize=None)
    def find_users_attributes(
        self,
        attributes: Tuple[str],
        base_dn: str,
        groups: Tuple[str] | None,
    ) -> List[Dict[str, Any]]:
        where = "objectClass = 'user'"
        if groups and len(groups) > 0:
            group_dns = map(lambda g: f"memberOf='{g}'", groups)
            where += f" AND ({' OR '.join(group_dns)})"
        query = ADQuery()
        query.execute_query(
            attributes=list(attributes),
            where_clause=where,
            base_dn=base_dn,
        )
        if len(query) == 0:
            return []
        return list(query.get_results())

    @lru_cache(maxsize=None)
    def get_group(self, dn: str) -> ADGroup:
        return ADGroup.from_dn(dn)

    @lru_cache(maxsize=None)
    def get_container(self, dn: str) -> ADContainer:
        return ADContainer.from_dn(dn)
