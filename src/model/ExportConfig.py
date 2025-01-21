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
            description=dedent("""
                Mandatory.

                Specifies the user list file for export.
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

                Specifies the distinguished name ("dn") of the location in the active directory under which
                all users and groups are located. If all users and groups are in one place it can be directly specified
                here.
                
                If not `BasePath` should point to the longest parent path shared by all users and the optional `SearchSubPaths`
                option should be used to restrict the recursive search for users.
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
                Mandatory.

                Specifies which security groups a users must be a member of to be included in the export.
                If multiple groups are specified, membership in any of these groups is sufficient.
                Group object paths are relative to `BasePath` and are prepended to form a full dn.
                
                A value of `null` is possible to export all users found regardless of group membership.
                This is only recommended if `SearchSubPaths` restricts the user search sufficiently.  
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
                Optional (but recommended).

                Specifies which attributes of user objects are written to the output file.
                
                Some attributes are always exported because they are needed for the import script to work. 
                These are `sAMAccountName`, `cn`, `disabled`, `accountExpires`, `memberOf`.
                Additional attributes should be specified to transfer more information of the users between domains.
            """),
            examples=[["CN=TransferUsers1", "CN=TransferUsers2"]],
        ),
    ]

    search_sub_paths: Annotated[
        List[str],
        Field(
            title="Search Sub-Paths",
            description=dedent("""
                Optional.

                Specifies which attributes of user objects are written to the output file.
                Some attributes are always exported because they are needed for the import script to work. 
                These are `sAMAccountName`, `cn`, `disabled`, `accountExpires`, `memberOf`.
                Additional attributes should be specified to transfer more information of the users between domains.
            """),
            examples=[["displayName", "givenName", "sn", "mail", "c", "l", "company", "department"]],
        ),
    ]
