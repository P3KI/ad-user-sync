from functools import lru_cache
from logging import Logger, getLogger
from typing import List, Dict, Any, Iterable, Set

from pyad import ADContainer, ADGroup, ADQuery, ADUser


class CachedActiveDirectory:
    def __init__(self, logger: Logger):
        self.logger = logger

    @lru_cache(maxsize=None)
    def find_single_user(self, parent: ADContainer | None, where: str) -> ADUser | None:
        self.logger.debug(
            "Finding existing user account for %s in %s...", where, parent.dn if parent else "(entire domain)"
        )
        query = ADQuery()
        query.execute_query(
            attributes=["distinguishedName"],
            where_clause=f"objectClass = 'user' AND {where}",
            base_dn=parent.dn if parent else None,
        )
        if len(query) == 0:
            self.logger.debug("... Not present.")
            return None

        dn = query.get_single_result()["distinguishedName"]
        self.logger.debug("... Found %s.", dn)

        return ADUser.from_dn(dn)

    @lru_cache(maxsize=None)
    def find_users(self, parent: ADContainer) -> Set[ADUser]:
        return set(parent.get_children_iter(recursive=True, filter=[ADUser]))

    @lru_cache(maxsize=None)
    def find_users_attributes(
        self,
        attributes: Iterable[str],
        base_dn: str,
        groups: Iterable[str] | None,
    ) -> List[Dict[str, Any]]:
        where = "objectClass = 'user'"
        if groups is not None:
            groups = list(groups)
            if len(groups) > 0:
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
        return self.get_group_uncached(dn)

    def get_group_uncached(self, dn: str) -> ADGroup:
        return ADGroup.from_dn(dn)

    @lru_cache(maxsize=None)
    def get_container(self, dn: str, logger: Logger | None = None) -> ADContainer:
        try:
            return ADContainer.from_dn(dn)
        except:
            if not logger:
                logger: Logger = getLogger(__name__)
            logger.debug(f"Container `{dn}` not found")
            idx: int = dn.find(",")
            if idx < 0:
                logger.error(f"Cannot locate parent in dn {dn}")
                raise ValueError(f"User path {dn} not found")
            cn: str = dn[3:idx]
            # cannot create ou in "Users" via pyad - Powershell does the job
            raise ValueError(
                f'Please run following Powershell:\nNew-ADObject -Name "{cn}" -Type container -Path "{dn}"'
            )
