from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, validator

# only used for vscode intelliSense
# ref: https://github.com/microsoft/python-language-server/issues/1898
if TYPE_CHECKING:
    import dataclasses

    static_check_init_args = dataclasses.dataclass
else:

    def static_check_init_args(cls):
        return cls


@static_check_init_args
class VisConfig(BaseModel):

    ignore_trio: bool = True
    print_task_tree: bool = True
    log_overwrite_if_exists: bool = True
    log_filename: str = "./logs.json"

    @validator("log_filename")
    def log_file_should_not_be_overwritten_unless_required(cls, filename: str, values):
        if Path(filename).exists() and values["log_overwrite_if_exists"] is False:
            raise ValueError(
                f"[trio-vis] file exists with overwrite set to false:{filename}"
            )
