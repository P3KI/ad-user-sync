from logging import Logger
from typing import Dict, List, Any, Set
from pywintypes import com_error
from pyad import ADGroup, ADUser, win32Exception, ADContainer

from .model import ImportConfig
from .active_directory import CachedActiveDirectory
from .util import full_path, not_none
import subprocess


def ask(prompt: str, default: str = "N", choices={"Y": ["Y", "y", "yes"], "N": ["n", "N", "No"]}):
    prompt = prompt + " " + "|".join(choices.keys()) + f"? [{default}] "
    while True:
        result = input(prompt)
        if not result:
            return default
        for k, v in choices.items():
            if result in v:
                return k


def check_setup(
    config: ImportConfig,
    logger: Logger,
) -> None:
    logger.debug("Starting check_setup")

    # create a cached active directory instance for accessing AD
    active_directory = CachedActiveDirectory(logger)

    # helper function to resolve groups from ad according to config
    def get_group(g: str) -> ADGroup:
        p = full_path(config.group_path, g)
        logger.debug(f"Loading ad group {p}...")
        try:
            group = active_directory.get_group(p)
        except:
            logger.error("Cannot load group")
            return None
        logger.debug("...AD group loaded.")
        return group

    groups = set(sum(config.group_map.values(), []))
    existing_groups = {g for g in groups if get_group(g)}
    missing = groups - existing_groups
    if missing:
        print(f"Missing groups:\n\t{'\n\t'.join(missing)}")
        for g in missing:
            result = ask(f"Create group {g[3:]}")
            if result == "Y":
                logger.debug(f"Creating group {g[3:]}")
                active_directory.get_container(config.group_path).create_group(g[3:])
                logger.info(f"Created group {g[3:]}")
    else:
        print("All groups from import config present in local AD")

    dn = config.managed_user_path
    try:
        active_directory.get_container(dn, logger)

        print(f"Container for managed users in AD exists: {dn}")
    except:
        print(f"Cannot locate container for managed users in AD: {dn}")
        idx: int = dn.find(",")
        if idx < 0:
            logger.error(f"Cannot locate parent in dn {dn}")
            raise ValueError(f"User path {dn} not found")
        parent_dn = dn[idx + 1 :]
        cn: str = dn[3:idx]
        # cannot create ou in "Users" via pyad - Powershell does the job
        command = [
            "powershell",
            "-Command",
            "New-ADObject",
            "-Name",
            f'"{cn}"',
            "-Type",
            "container",
            "-Path",
            f'"{parent_dn}"',
        ]
        print("Executing PowerShell code to create container")
        print(" ".join(command[2:]))
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0:
            print("Success:", result.stdout)
        else:
            print("Error:", result.stderr)
