import random
import string
from typing import Any
import threading
import ctypes

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
