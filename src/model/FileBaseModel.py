import os
from typing import Type

from pydantic import BaseModel


class FileBaseModel(BaseModel):
    @classmethod
    def load[T](cls: Type[T], file: str) -> T:
        if os.path.isfile(file):
            with open(file, "r") as f:
                json_str = f.read()
                if len(json_str) > 1:
                    return cls.model_validate_json(json_str)
        return cls()

    def save(self, file: str) -> None:
        with open(file, "w") as out:
            out.write(self.model_dump_json(indent=4))
