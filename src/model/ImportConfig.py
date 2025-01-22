from datetime import timedelta
from pathlib import Path
from textwrap import dedent
from typing import Annotated, Dict, List

from pydantic import Field

from .FileBaseModel import FileBaseModel


class ImportConfig(FileBaseModel):
    input_file: Annotated[
        Path,
        Field(
            title="Input File",
            description="Path to the file with the user list to import.",
            examples=["users.json"],
        ),
    ]

    base_path: Annotated[
        str,
        Field(
            title="Base Path",
            description=dedent("""
                The distinguished name ("dn") of the location in the active directory to witch `managed_user_path` and `group_map` are relative.
                Usually this will be the `CN=Users` container of the domain, because pre-existing security groups are located there.
            """),
            examples=["CN=Users,DC=ad,DC=company,DC=com"],
        ),
    ]

    managed_user_path: Annotated[
        str,
        Field(
            default="CN=P3KI Managed",
            title="Managed User Path",
            description=dedent("""
                The location new Active Directory user objects are created.
                The path is relative to `base_path` and is prepended to form a full dn.
                UserSync does NOT create this path within the Active Directory, it must be created manually before running any import.
                The default value `CN=P3KI Managed` is suitable if `base_path` points to the `CN=Users` folder.
                Warning: This path MUST NOT contain any non-managed users otherwise these accounts will be deactivated.   
            """),
            examples=["CN=P3KI Managed"],
        ),
    ]

    group_map: Annotated[
        Dict[str, str],
        Field(
            default_factory=dict,
            title="Group Map",
            description=dedent("""
                Specifies how security group memberships are mapped between source and destination Active Directory.
                It consists of a dictionary with entries formatted as `"<Source AD group>":"<Target AD group>"`.
                Source paths are relative to the `base_path` used in the export configuration file.
                Each one should match one `search_groups` entry in the export configuration.
                Additionally, a `*` entry may be added to specify a group every managed user should be placed in.
                Target paths are relative to the `base_path` used in the import configuration file.
                If not specified, no group memberships will be assigned to managed users.
            """),
            examples=[
                {
                    "CN=Administrators": "CN=p-Administrators",
                    "CN=Operators": "CN=p-Operators",
                    "CN=Viewers": "CN=p-Viewers",
                    "*": "CN=p-Managed",
                }
            ],
        ),
    ]

    restricted_groups: Annotated[
        List[str],
        Field(
            default_factory=list,
            title="Restricted Groups",
            description=dedent("""                
                Specifies groups that may not assigned to any user even though they are listed in `group_map`.
                Joining these groups must be accepted during an interactive session.
            """),
            examples=[["CN=p-Administrators"]],
        ),
    ]

    prefix_account_names: Annotated[
        str,
        Field(
            default="",
            title="Prefix Account Names",
            description=dedent("""                
                A prefix that is added all managed user and common names to avoid conflicts with existing non-managed users.
            """),
            examples=["p-"],
        ),
    ]

    default_expiration: Annotated[
        timedelta,
        Field(
            default="P1M1D",
            title="Default Expiration",
            description=dedent("""                
                Specifies how long managed user accounts should be valid for.
                The expiration date is extended by the specified time every time the import script is done.
                If the source account expiration date is closer than the specified time, the source value is used instead.
                  format:  ISO_8601 - https://en.wikipedia.org/wiki/ISO_8601#Durations
            """),
            examples=["P1M1D"],
            gt=timedelta(days=1),
        ),
    ]

    resolutions_file: Annotated[
        Path,
        Field(
            default="resolutions.json",
            title="Resolved Interactions",
            description=dedent("""
                A file to write rejected interactions to, so they are not asked for every time.
            """),
            examples=["rejections.json"],
        ),
    ]

    log_input_file_content: Annotated[
        bool,
        Field(
            default=False,
            title="Log Input File Content",
            description=dedent("""                
                If set, the content of the input file will be written to the log every time it is evaluated. 
            """),
            examples=[False],
        ),
    ]


class InteractiveImportConfig(ImportConfig):
    port: Annotated[
        int | None,
        Field(
            default=None,
            title="Port",
            description="Port on which the interactive import session is listening. Set to `null` and a random free port will be chosen.",
            examples=[8080, None],
            gt=0,
        ),
    ]

    heartbeat_interval: Annotated[
        float,
        Field(
            default=2,
            title="Heartbeat Interval",
            description="Interval of the heartbeat a browser tab sends in seconds. `0` deactivates tab sync.",
            examples=[2, 0],
            le=10,
            ge=0,
        ),
    ]

    terminate_on_tab_close: Annotated[
        bool,
        Field(
            default=True,
            title="Terminate On Tab Close",
            description="Whether or not the interactive import session should terminate when all browser tabs are closed.",
            examples=[True, False],
        ),
    ]
