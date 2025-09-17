from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from textwrap import dedent
from typing import Annotated, Dict, List, Self

from pydantic import Field, BeforeValidator, BaseModel, model_validator, field_serializer

from .FileBaseModel import FileBaseModel
from ..util import ensure_list_values


class LogLevel(StrEnum):
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


class VirtualImportGroup(BaseModel):
    name: Annotated[
        str,
        Field(
            title="Group Name",
            description=dedent("""
                Name of a virtual group. If a users is - according to the imported JSON - member
                of this group, a virtual import is created for a derived account with the given
                `prefix` for this group and for the original or base user instead an import for
                the `altgroup`. The `altgroup` is a *source* group like it would appear in the
                JSON file; not a local group.

                When no `altgroup` is given and the account is not member of another relevant group, the
                base user will not be imported.

                Example use case is to create a separate admin-account for a user and place the standard
                account into the operators group.
            """),
            examples=["CN=p-Administrators"],
        ),
    ]

    prefix: Annotated[
        str,
        Field(
            title="User Name Prefix",
            default="",
            description=dedent("""
                Prefix to add to the virtual imported user mapping that will be used for the virtual import,
                for example, `adm`.
            """),
            examples=["adm"],
        ),
    ]

    suffix: Annotated[
        str,
        Field(
            title="User Name Suffix",
            default="",
            description=dedent("""
                Suffix to add to the virtual imported user mapping that will be used for the virtual import,
                for example, `adm`.
            """),
            examples=["adm"],
        ),
    ]

    altgroup: Annotated[
        str,
        Field(
            title="Alternate Group",
            default=None,
            description=dedent("""
                Assign the original user to this alternate *source* group in addition to the original group,
                which will be assigned to the prefixed user.
                When no altgroup is specified, the original users will not be added to any group.
            """),
            examples=["CN=Operators"],
        ),
    ]

    @model_validator(mode="after")
    def check_prefix_or_suffix(self) -> Self:
        if not (self.suffix or self.prefix):
            raise ValueError(f"Virtual Imports need at least one of prefix or suffix `{self.name}`")
        return self

    @model_validator(mode="after")
    def check_map_to_self(self) -> Self:
        if self.name == self.altgroup:
            raise ValueError(f"Virtual Imports must not map to self `{self.name}` -> `{self.altgroup}`")
        return self


class ImportConfig(FileBaseModel):
    input_file: Annotated[
        Path,
        Field(
            title="Input File",
            description="Path to the file with the user list to import.",
            examples=["users.json"],
        ),
    ]

    group_path: Annotated[
        str,
        Field(
            title="Group Base Path",
            description=dedent("""
                The distinguished name ("dn") of the location in the active directory to witch `group_map` entries are relative.
                Usually this will be the `CN=Users` container of the domain, because pre-existing security groups are located there.
            """),
            examples=["CN=Users,DC=ad,DC=company,DC=com"],
        ),
    ]

    managed_user_path: Annotated[
        str,
        Field(
            title="Managed User Path",
            description=dedent("""
                The distinguished name ("dn") of the location where new Active Directory user objects are created.
                UserSync does NOT create this path within the Active Directory, it must be created manually before running any import.
                Warning: This path MUST NOT contain any non-managed users otherwise these accounts will be deactivated.   
            """),
            examples=["CN=P3KI Managed,CN=Users,DC=ad,DC=company,DC=com"],
        ),
    ]

    group_map: Annotated[
        Dict[str, List[str]],
        Field(
            default_factory=dict,
            title="Group Map",
            description=dedent("""
                Specifies how security group memberships are mapped between source and destination Active Directory.
                It consists of a dictionary with entries formatted as `"<Source AD group>":["<Target AD group 1>","<Target AD group 2>"...]`.
                Source paths are relative to the `group_path` used in the export configuration file.
                Each one should match one `search_groups` entry in the export configuration.
                Additionally, a `*` entry may be added to specify a group every managed user should be placed in.
                Target AD groups may be a single group or list of multiple groups.
                Target paths are relative to the `group_path` used in the import configuration file. 
                If not specified, no group memberships will be assigned to managed users.
            """),
            examples=[
                {
                    "CN=Administrators": ["CN=p-Administrators"],
                    "CN=Operators": ["CN=p-Operators"],
                    "CN=Viewers": ["CN=p-Viewers"],
                    "*": ["CN=p-Managed"],
                }
            ],
        ),
        BeforeValidator(ensure_list_values),
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

    virtual_imports: Annotated[
        List[VirtualImportGroup],
        Field(
            default_factory=dict,
            title="Restricted Groups Mapping",
            description=dedent("""
                For these groups, the user gets separate account with a prefix to the user name for the
                restricted group and the unprefixed user is assigned the alternative group.
            """),
        ),
    ]

    prefix_common_names: Annotated[
        str,
        Field(
            default="P3KI ",
            title="Prefix Common Names",
            description=dedent("""                
                A prefix that is added all managed common names to avoid conflicts with existing non-managed users.
            """),
            examples=["P3KI "],
            min_length=2,
        ),
    ]

    expiration_time: Annotated[
        timedelta,
        Field(
            default="P1M1D",
            title="Expiration Time",
            description=dedent("""                
                Specifies how long managed user accounts should be valid for.
                The expiration date is extended by the specified time every time the import script is done.
                  format:  ISO_8601 - https://en.wikipedia.org/wiki/ISO_8601#Durations
            """),
            examples=["P1M1D"],
            gt=timedelta(days=1),
        ),
    ]

    expiration_hour: Annotated[
        int,
        Field(
            default=23,
            title="Expiration time, hour",
            description=dedent("""
                Wall clock hour [0..23] when expiration will become effective. Uses timezone of directory controller!
            """),
            examples=["23", "12", "9"],
            gt=0,
            lt=23,
        ),
    ]

    expiration_minute: Annotated[
        int,
        Field(
            default=59,
            title="Expiration time, minute",
            description=dedent("""
                Wall clock minute [0..59] when expiration will become effective.
            """),
            examples=["0", "5", "15", "59"],
            gt=0,
            lt=59,
        ),
    ]

    users_can_not_change_password: Annotated[
        bool,
        Field(
            default=False,
            title="Managed Users can not change the password set for them",
            description=dedent("""                
                If set to true, managed users will not be able to change their password.
                This user account flag will be applied when setting a user password during interactive import.  
            """),
            examples=[False],
        ),
    ]

    users_must_change_password: Annotated[
        bool,
        Field(
            default=False,
            title="Managed Users must change the password on first login",
            description=dedent("""
                If set to true, managed users must change their password on the first login after interactive import.
                This user account flag will be applied when setting a user password during interactive import.  
            """),
            examples=[False],
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
            examples=["resolutions.json"],
        ),
    ]

    hmac: Annotated[
        str | None,
        Field(
            default=None,
            title="HMAC Key",
            description=dedent("""
                Verify HMAC on the input file using a shared key.
                This is used to check for a corrupted users file.
                Can be overridden by passing the `--hmac` command line parameter.
            """),
        ),
    ]

    log_file: Annotated[
        str,
        Field(
            default=None,
            title="Log file",
            description=dedent("""
                Sets the file to write log message into. 
            """),
            examples=["import.log"],
        ),
    ]

    log_level: Annotated[
        LogLevel,
        Field(
            default=LogLevel.DEBUG,
            title="Log Level",
            description=dedent("""
                Sets the Log Level. 
            """),
            examples=["INFO"],
        ),
    ]
    log_max_bytes: Annotated[
        int,
        Field(
            default=1048576,
            title="Log file maximum size before rotation",
            description=dedent("""
                Sets the maximum size (in bytes) of the log file before rotating it and starting a new one. Default: 1048576 byte (1MiB) 
            """),
            examples=[1048576],
        ),
    ]
    log_backup_count: Annotated[
        int,
        Field(
            default=10,
            title="Log file maximum number of backup files kept",
            description=dedent("""
                Sets the maximum number of backup files kept before deleting. Default: 10 
            """),
            examples=[10],
        ),
    ]
    log_windows: Annotated[
        bool,
        Field(
            default=False,
            title="Log to Windows event log",
            description=dedent("""
                If set to true, events are written to the windows event log. 
            """),
            examples=[10],
        ),
    ]

    @field_serializer("expiration_time")
    def serialize_expiration_time(self, expiration_time: str, _info):
        return expiration_time

    @model_validator(mode="after")
    def check_virtual_imports(self) -> Self:
        if self.virtual_imports:
            alt_groups = {i.altgroup for i in self.virtual_imports if i.altgroup}
            for i in self.virtual_imports:
                if i.name in alt_groups:
                    raise ValueError(f"Virtual imports must not cascade: `{i.name}` -> {i.altgroup}")
            for i in alt_groups:
                if i not in self.group_map:
                    raise ValueError(f"Virtual import altgroup `{i}` does not map to any mapped (lhs) group!")
        return self


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
            description="Interval of the heartbeat a browser tab sends in seconds. `0` deactivates browser sync.",
            examples=[2, 0],
            le=10,
            ge=0,
        ),
    ]

    terminate_on_browser_close: Annotated[
        bool,
        Field(
            default=True,
            title="Terminate On Tab Close",
            description="""
                Whether or not the interactive import session should terminate when all browser tabs are closed.
                There will be a confirmation prompt if there are unexported passwords.
            """,
            examples=[True, False],
        ),
    ]

    password_wordlist: Annotated[
        Path,
        Field(
            default="wordlist_de.txt",
            title="Password Word List",
            description="Number of words sampled from the password list to generate a password.",
            examples=[3],
        ),
    ]

    password_word_count: Annotated[
        int,
        Field(
            default=3,
            title="Password Word Count",
            description="Number of words sampled from the password list to generate a password.",
            examples=[3],
        ),
    ]

    password_suffix: Annotated[
        str,
        Field(
            default="",
            title="Password Suffix",
            description="Static suffix appended to any generated password.",
            examples=["$#39"],
        ),
    ]
