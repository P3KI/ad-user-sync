from datetime import timedelta, datetime
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
            description=dedent("""
                Mandatory.
                
                Specifies the user list file for import.
            """),
            examples=["Users.json"],
        ),
    ]

    base_path: Annotated[
        str,
        Field(
            title="Base Path",
            description=dedent("""
                Mandatory.
                
                Specifies the distinguished name ("dn") of the location in the active directory to witch `ManagedUserPath`
                and `GroupMap` are relative.
                
                Usually this will be the `CN=Users` container of the domain, because pre-existing security groups are 
                located there.
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
                Optional (but recommended).
    
                Specifies the location (relative to `BasePath`) new Active Directory user objects are created.
                
                The default value is `CN=P3KI Managed` and is suitable if `BasePath` points to the `CN=Users` folder.
                The path is relative to `BasePath` and is prepended to form a full dn.
                UserSync does NOT create this path within the Active Directory, it must be created manually before running
                any import.
                
                *Warning:* This path MUST NOT contain any non-managed users otherwise these accounts will be _DEACTIVATED_.   
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
                Optional (but recommended).
                
                Specifies how security group memberships are mapped between source and destination Active Directory.
   
                It consists of a dictionary object with entries formatted as `"<Source AD group>":"<Target AD group>"`.
                
                * Source paths are relative to the `BasePath` used in the export configuration file.
                
                  Each one should match one `SearchGroups` entry in the export configuration.
                
                  Additionally, a `*` entry may be added to specify a group every managed user should be placed in.
                * Target paths are relative to the `BasePath` used in the import configuration file.
                
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
                Optional.
                
                Specifies groups that may not assigned to any user even though they are listed in the `Group Map`.
                
                Instead, joining these groups must be accepted during an `Interactive Action`.
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
                Optional.
                
                Specifies a prefix that is added all managed user and common names to avoid conflicts with existing
                non-managed users.

                The default is not to prefix names.
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
                Optional.
                
                Specifies how log managed user accounts should be valid for.
                
                The expiration date is extended by the specified time every time the import script is done.
                If the source account expiration date is closer than the specified time, the source value is
                used instead.
                
                Format is (ISO_8601)[https://en.wikipedia.org/wiki/ISO_8601#Durations].
                
                The default value is 1 month and 1 day.
                
                The minimum value is 1 day. 
            """),
            examples=["P1M1D"],
            gt=timedelta(days=1),
        ),
    ]

    resolutions_file: Annotated[
        str,
        Field(
            default="resolutions.json",
            title="Resolved Interactions",
            # todo
            description=dedent("""
                Optional.
                Specifies the file path to write Interactive Actions into.
                
                If the importer can not automatically perform certain actions (See "Interactive Actions" section) 
                it will write them to the file specified here.
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
                Optional.
                
                If set, the content of the input file will be written to the log every time it is evaluated. 
            """),
            examples=[False],
        ),
    ]