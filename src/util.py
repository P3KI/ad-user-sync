import random
import string
from typing import Any
import threading
import ctypes
import socket
from contextlib import closing

from pyad import pyadutils
from pydantic import ValidationError


def not_none(v: Any) -> bool:
    return v is not None


def random_string(length: int, letters: str = string.ascii_letters + string.digits) -> str:
    return "".join(random.choice(letters) for _ in range(length))


def format_validation_error(e: ValidationError, source: str = None, indentation: str = "    ") -> str:
    root_message = f"{e.error_count()} errors" if e.error_count() > 1 else "Error"
    root_message += f" while parsing {e.title}"
    if source:
        root_message += f" from {source}"
    root_message += ":"

    error_messages = [root_message]
    for error in e.errors():
        is_root = len(error["loc"]) == 0
        message = indentation

        if not is_root:
            message += " -> ".join(map(str, error["loc"])) + ": "

        message += error["msg"]

        if not is_root:
            value = error.get("input")
            if value:
                message += f" (given: {value})"

        error_messages.append(message)
    return "\n".join(error_messages)


class KillableThread(threading.Thread):
    def get_id(self):
        # returns id of the respective thread
        if hasattr(self, "_thread_id"):
            return self._thread_id
        for id, thread in threading._active.items():
            if thread is self:
                return id

    def terminate(self):
        thread_id = self.get_id()
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(KeyboardInterrupt))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print("Exception raise failure")


def convert_ad_datetime(date: Any):
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


# Appends the base path to turn a subpath into a full path (the distinguished name)
def full_path(base_path: str, path: str = ""):
    if len(path) > 0:
        return f"{path},{base_path}"
    else:
        return base_path


# Removes the base path to turn a distinguished name into a relative path
def sub_path(base_path: str, dn: str) -> str:
    return dn[0 : -len(base_path) - 1] if dn.endswith(base_path) else dn


def find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]
