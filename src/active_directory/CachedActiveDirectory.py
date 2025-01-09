from functools import lru_cache

from pyad.adcontainer import ADContainer
from pyad.adgroup import ADGroup
from pyad.adquery import ADQuery
from pyad.aduser import ADUser


class CachedActiveDirectory:
    @lru_cache(maxsize=None)
    def find_single_user(self, domain: ADContainer, where: str) -> ADUser | None:
        query = ADQuery()
        query.execute_query(
            attributes=["distinguishedName"],
            where_clause=f"objectClass = 'user' AND {where}",
            base_dn=domain.dn,
        )
        if query.get_row_count() == 0:
            return None

        dn = query.get_single_result()["distinguishedName"]
        return ADUser.from_dn(dn)

    @lru_cache(maxsize=None)
    def get_group(self, dn: str) -> ADGroup:
        return ADGroup.from_dn(dn)

    @lru_cache(maxsize=None)
    def get_container(self, dn: str) -> ADContainer:
        return ADContainer.from_dn(dn)
