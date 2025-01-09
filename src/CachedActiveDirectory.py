from typing import Dict, Generic, TypeVar, Callable, Any, Tuple

from pyad.adcontainer import ADContainer
from pyad.adgroup import ADGroup
from pyad.adquery import ADQuery
from pyad.aduser import ADUser
from pyad.pyadexceptions import win32Exception

try:
    from pywintypes import com_error
except ImportError:
    # todo: try if this works on windows. if yes: get rid of the pywin32 dependency
    from pyad.pyadexceptions import comException as com_error

K = TypeVar('K')
T = TypeVar('T')


class ADObjectCache(Generic[K, T]):
    _resolver: Callable[[K], T]
    _cache: Dict[K, T]

    def __init__(self, resolver: Callable[[K], T]) -> None:
        self._resolver = resolver
        self._cache = {}

    def get(self, key: K) -> T:
        if key in self._cache:
            return self._cache[key]

        try:
            value = self._resolver(key)
            self._cache[key] = value
            return value
        except (com_error, win32Exception) as e:
            raise ActiveDirectoryLoadException(message=str(e), query=key, cause=e)


class ActiveDirectoryLoadException(Exception):
    query: str
    message: str
    cause: Any

    def __init__(self, message: str, query: str, cause: Any) -> None:
        self.query = query
        self.message = message
        self.cause = cause

    def __str__(self):
        return f'{self.message}: {self.query}'


def find_single_user(params: Tuple[ADContainer, str]) -> ADUser | None:
    domain, where = params
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


class CachedActiveDirectory:
    _group_cache: ADObjectCache[str, ADGroup]
    _container_cache: ADObjectCache[str, ADContainer]
    _single_user_cache: ADObjectCache[Tuple[ADContainer, str], ADUser | None]

    def __init__(self):
        self._group_cache = ADObjectCache(ADGroup.from_dn)
        self._container_cache = ADObjectCache(ADContainer.from_dn)
        self._single_user_cache = ADObjectCache(find_single_user)

    def find_single_user(self, domain: ADContainer, where: str) -> ADUser | None:
        return self._single_user_cache.get((domain, where))

    def get_group(self, dn: str) -> ADGroup:
        return self._group_cache.get(dn)

    def get_container(self, dn: str) -> ADContainer:
        return self._container_cache.get(dn)

