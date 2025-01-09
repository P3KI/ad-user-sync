
from pyad.pyadexceptions import win32Exception

try:
    from pywintypes import com_error
except ImportError:
    # todo: try if this works on windows. if yes: get rid of the pywin32 dependency
    from pyad.pyadexceptions import comException as com_error

CatchableADExceptions = (com_error, win32Exception)
