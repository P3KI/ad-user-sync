from pathlib import Path
from textwrap import dedent
from typing import Annotated, List, Set

from pydantic import Field

from .FileBaseModel import FileBaseModel


class ExportConfig(FileBaseModel):
    export_file: Annotated[
        Path,
        Field(
            title="Export File",
            description="Path to the user list file for export.",
            examples=["users.json"],
        ),
    ]

    base_path: Annotated[
        str,
        Field(
            title="Base Path",
            description=dedent("""
                Specifies the distinguished name ("dn") of the location in the active directory under which all users and groups are located.
                If not all users and groups are in one place `base_path` should point to the longest parent path shared by all users 
                and the optional `search_sub_paths` option should be used to restrict the recursive search for users.
            """),
            examples=["CN=Users,DC=ad,DC=company,DC=com"],
        ),
    ]

    search_groups: Annotated[
        List[str],
        Field(
            title="Search Groups",
            default_factory=list,
            description=dedent("""
                Specifies which security groups a users must be a member of to be included in the export.
                If multiple groups are specified, membership in any of these groups is sufficient.
                Group object paths are relative to `base_path` and are prepended to form a full dn.
                If not provided all users regardless of group membership are exported (make sure `search_sub_paths` restrictive enough).  
            """),
            examples=[["CN=Transfer", "CN=Test"]],
        ),
    ]

    attributes: Annotated[
        Set[str],
        Field(
            title="Attributes",
            default_factory=set,
            description=dedent("""
                Which additional attributes of user objects should be written to the output file to transfer more information of the users between domains.
                The attributes `sAMAccountName`, `cn`, `disabled`, `accountExpires`, `memberOf` are exported regardless.
            """),
            examples=[["displayName", "givenName", "sn", "mail", "c", "l", "company", "department"]],
        ),
    ]

    search_sub_paths: Annotated[
        List[str] | None,
        Field(
            default=None,
            title="Search Sub-Paths",
            description=dedent("""
                Relative paths to search for user objects in the AD. 
                Use in case not all of `base_path` should be searched recursively. 
                This sub paths are prepended to `base_path` for user search queries to form a full dn.
            """),
            examples=[["CN=TransferUsers1", "CN=TransferUsers2"]],
        ),
    ]
