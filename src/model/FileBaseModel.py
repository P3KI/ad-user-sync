import logging
import os
from typing import Type

from pydantic import BaseModel


class FileBaseModel(BaseModel):
    @classmethod
    def load[T](cls: Type[T], file: str) -> T:
        if os.path.isfile(file):
            with open(file, "r") as f:
                file_content = f.read()
                if len(file_content) > 1:
                    return cls.model_validate_json(file_content)
                else:
                    logging.warning(f"File {file} is empty. Continue with default {cls}")
        else:
            logging.warning(f"File {file} does not exist. Continue with default {cls}")
        return cls()

    def save(self, file: str) -> None:
        with open(file, "w") as out:
            out.write(self.model_dump_json(indent=4))
