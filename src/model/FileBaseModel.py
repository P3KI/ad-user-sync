import sys
from logging import Logger
from pathlib import Path
from typing import Type

from pydantic import BaseModel, ValidationError

from ..util import format_validation_error


class FileBaseModel(BaseModel):
    @classmethod
    def load[T](
        cls: Type[T],
        file: str | Path,
        logger: Logger,
        exit_on_fail: bool = False,
        fallback_default: bool = True,
        save_default: bool = False,
    ) -> T:
        file = Path(file).absolute()
        if file.is_file():
            with open(file, "r") as f:
                file_content = f.read()
                if len(file_content.strip()) > 1:
                    try:
                        return cls.model_validate_json(file_content)
                    except ValidationError as e:
                        logger.error(format_validation_error(e, source=str(file)))
                        if exit_on_fail:
                            sys.exit(1)
                        else:
                            raise
                else:
                    if fallback_default:
                        logger.debug(f"File {file} is empty. Continue with default {cls.__name__}.")
                    else:
                        logger.warning(f"File {file} is empty. Can not load {cls.__name__}.")
                        if exit_on_fail:
                            sys.exit(1)
                        else:
                            raise FileNotFoundError()
        else:
            if fallback_default:
                logger.debug(f"File {file} does not exist. Continue with default {cls.__name__}.")
            else:
                logger.warning(f"File {file} does not exist. Can not load {cls.__name__}.")
                if exit_on_fail:
                    sys.exit(1)
                else:
                    raise FileNotFoundError()

        instance = cls()
        if save_default:
            instance.save(file)
        return instance

    def save(self, file: str) -> None:
        with open(file, "w") as out:
            out.write(self.model_dump_json(indent=4))
