from pathlib import Path
from textwrap import dedent
from typing import Annotated, List, Set

from pydantic import Field

from .FileBaseModel import FileBaseModel


class ExportConfig(FileBaseModel):
    export_file: Annotated[
        Path | None,
        Field(
            default=None,
            title="Export File",
            description="Path to the user list file for export. If not provided, the result will be printed to `stdout`.",
            examples=["users.json"],
        ),
    ]

    user_path: Annotated[
        str,
        Field(
            title="User Base Path",
            description=dedent("""
                Specifies the distinguished name ("dn") of the location in the active directory under which all relevant users are located.
                If not all users are in one place `user_path` should point to the longest parent path shared by all users.
            """),
            examples=["CN=Users,DC=ad,DC=company,DC=com"],
        ),
    ]

    group_path: Annotated[
        str,
        Field(
            title="Group Base Path",
            description=dedent("""
                Specifies the distinguished name ("dn") of the location in the active directory under which all groups listed in `search_groups` are located.
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
                Group object paths are relative to `group_path` and are prepended to form a full dn.
                If not provided all users in `user_path` regardless of group membership are exported (make sure `user_path` restrictive enough).  
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

    hmac: Annotated[
        str | None,
        Field(
            default=None,
            title="HMAC Key",
            description=dedent("""
                A message authentication code can be added to the export output file.
                This is used to check for a corrupted file when importing.
                Can be overridden by passing the `--hmac` command line parameter.
            """),
        ),
    ]
