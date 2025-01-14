from datetime import timedelta, datetime
from textwrap import dedent
from typing import Annotated, Dict, List, Callable

from pydantic import Field, AfterValidator

from .FileBaseModel import FileBaseModel


def min_timedelta(minimum: timedelta) -> Callable[[timedelta], timedelta]:
    def wrapped_min(value: timedelta) -> timedelta:
        if value < minimum:
            raise ValueError(f"Duration is too short: {value}. (Minimum {minimum})")
        return value

    return wrapped_min


class ImportConfig(FileBaseModel):
    base_path: Annotated[
        str,
        Field(
            alias="BasePath",
            title="BasePath",
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
            alias="ManagedUserPath",
            title="ManagedUserPath",
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
            alias="GroupMap",
            title="GroupMap",
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
            alias="RestrictedGroups",
            title="RestrictedGroups",
            description=dedent("""
                Optional.
                
                Specifies groups that may not assigned to any user even though they are listed in the `GroupMap`.
                
                Instead, these actions are deferred to the `InteractiveActionsOutput` for use with a user interactive
                application.
            """),
            examples=[["CN=p-Administrators"]],
        ),
    ]

    prefix_account_names: Annotated[
        str,
        Field(
            default="",
            alias="PrefixAccountNames",
            title="PrefixAccountNames",
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
            alias="DefaultExpiration",
            title="DefaultExpiration",
            description=dedent("""
                Optional.
                
                Specifies how log managed user accounts should be valid for.
                
                The expiration date is extended by the specified time every time the import script is done.
                If the source account expiration date is closer than the specified time, the source value is
                used instead.
                
                The default value is 1 month and 1 day.
                
                The minimum value is 1 day. 
            """),
            examples=["P1M1D"],
        ),
        AfterValidator(min_timedelta(timedelta(days=1))),
    ]

    interactive_actions_output: Annotated[
        str,
        Field(
            default="Pending.json",
            alias="InteractiveActionsOutput",
            title="InteractiveActionsOutput",
            description=dedent("""
                Optional.
                
                Specifies the file path to write Interactive Actions into.
                
                If the importer can not automatically perform certain actions (See "Interactive Actions" section) 
                it will write them to the file specified here.
            """),
            examples=["Pending.json"],
        ),
    ]

    def full_path(self, sub_path: str = "") -> str:
        # Appends the base path to turn a sub_path into a full path (the distinguished name)
        if len(sub_path) > 0:
            return sub_path + "," + self.base_path
        else:
            return self.base_path

    def prefix_account_name(self, name: str) -> str:
        return self.prefix_account_names + name

    def get_default_expiration_date(self) -> datetime:
        return datetime.now() + self.default_expiration
