from typing import Type, Tuple

from pyad import win32Exception

CatchableADExceptions: Tuple[Type[BaseException], ...]

try:
    from pywintypes import com_error

    CatchableADExceptions = (com_error, win32Exception)
except ImportError:
    # excepting this error makes development on linux possible
    CatchableADExceptions = ()
