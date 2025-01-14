import logging
from pathlib import Path
from typing import Type

from pydantic import BaseModel, ValidationError

from ..util import format_validation_error


class FileBaseModel(BaseModel):
    @classmethod
    def load[T](cls: Type[T], file: str) -> T:
        file = Path(file).absolute()
        if file.is_file():
            with open(file, "r") as f:
                file_content = f.read()
                if len(file_content.strip()) > 1:
                    try:
                        return cls.model_validate_json(file_content)
                    except ValidationError as e:
                        logging.error(format_validation_error(e, source=str(file)))
                        exit(1)
                else:
                    logging.warning(f"File {file} is empty. Continue with default {cls}.")
        else:
            logging.warning(f"File {file} does not exist. Continue with default {cls}.")
        return cls()

    def save(self, file: str) -> None:
        with open(file, "w") as out:
            out.write(self.model_dump_json(indent=4))
