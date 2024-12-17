## About UserSync ##

UserSync is a tool to export users from a Windows Active Directory and import them into another.
For this to make sense two instances of this application must be operated. One on each active directory instance.
As the exported list of users is written to a file,
the user must provide means to transfer this file from the exporting to the importing AD.

## Exporting users ##

To run UserSync in export mode an export configuration file must be created first. By default, it is read from
`UserSync.cfg`, but a different filename can be specified with the `--config CONFIGFILE` option.
To run in export mode specify the `--export USERFILE` option. This must be the last option on the command line.

### Export Configuration ###

The configuration file is written in JSON notation.  It may contain the following settings:

 * `BasePath` is mandatory. It specifies the distinguished name ("dn") of the location in the active directory
    under which all users and groups are located. If all users and groups are in one place it can be directly specified here.
    If not `BasePath` should point to the longest parent path shared by all users and the optional `SearchSubPaths`
    option should be used to restrict the recursive search for users.

    Type: String

    Example:
    ```json
    "BasePath" : "CN=Users,DC=ad,DC=company,DC=com"
    ```


 * `SearchSubPaths` is optional. It specifies relative paths to search for user objects in the AD. 
   Use in case not all of `BasePath` should be searched recursively. 
   This sub paths are prepended to `BasePath` for user search queries to form a full dn.

   Type: Array of String

   Example:
   ```json
   "SearchSubPaths" : ["CN=TransferUsers1", "CN=TransferUsers2"]
   ```
   This will export user objects located in `CN=TransferUsers1,CN=Users,DC=ad,DC=company,DC=com` or `CN=TransferUsers2,CN=Users,DC=ad,DC=company,DC=com`


 * `SearchGroups` is mandatory. It specifies which security groups a users must be a member of to be included in the export.
   If multiple groups are specified, membership in any of these groups is sufficient.
   Group object paths are relative to `BasePath` and are prepended to form a full dn.

   A value of `null` is possible to export all users found regardless of group membership.
   This is only recommended if `SearchSubPaths` restricts the user search sufficiently.  

   Type: Array of String

   Example:
   ```json
   "SearchGroups" : ["CN=Transfer","CN=Test"]
   ```
   This will export users that are members of `CN=Transfer,CN=Users,DC=ad,DC=company,DC=com` or `CN=Test,CN=Users,DC=ad,DC=company,DC=com`

 * `Attributes` is optional (but recommended). It specifies which attributes of user objects are written to the output file.
   Some attributes are always exported because they are needed for the import script to work. 
   These are `sAMAccountName`, `cn`, `disabled`, `accountExpires`, `memberOf`.
   Additional attributes should be specified to transfer more information of the users between domains.

   Type: Array of String

   Example :
   ```json
   "Attributes":[
              "displayName",
              "givenName",
              "sn",
              "mail",
              "c",
              "l",
              "company",
              "department"
   ]
   ```

#### Full file example ####

```json
{
   "BasePath" : "CN=Users,DC=ad,DC=company,DC=com",
   "SearchSubPaths" : [""],
   
   "SearchGroups" : ["CN=Transfer","CN=Test"],
   
   "Attributes":[
             "displayName",
             "givenName",
             "sn",
             "mail",
             "c",
             "l",
             "company",
             "department"
   ]
}
```

### Run example ###

```
UserSync --config Export.cfg --export Users.json
```

## Importing users ##

Import mode creates new active directory users or updates the attributes of previously create ones to match the data found
in the `USERFILE`.
Managed users that have been previously created are never deleted, but deactivated if they are not part of the current `USERFILE`.

To run UserSync in import mode an import configuration file must be created first. By default, it is read from
`UserSync.cfg`, but a different filename can be specified with the `--config CONFIGFILE` option.
The Active Directory path specified using `ManagedUserPath` in the configuration must also be created manually before first use. 
To run in import mode specify the `--import USERFILE` option. This must be the last option on the command line.

### Interactive Actions ###

The import process is not fully automatic. Some actions require manual approval. These are:
   * Imported users are not automatically enabled.
   * Imported users are not automatically assigned any password.
   * Membership to groups specified in config as `RestrictedGroups` is not automatically granted.
   * In case of conflicting user account names or UPN with existing, non-managed, users no managed new user is created.

These cases are written into a file specified by `InteractiveActionsOutput` in config for later use with a
user-interactive application (GUI).

### Import Configuration ###
The configuration file is written in JSON notation. It may contain the following settings:

 * `BasePath` is mandatory. It specifies the distinguished name ("dn") of the location in the active directory
    to witch `ManagedUserPath` and `GroupMap` are relative.
    Usually this will be the `CN=Users` container of the domain, because pre-existing security groups are located there.

    Type: String

    Example:
    ```json
    "BasePath" : "CN=Users,DC=ad,DC=company,DC=com"
    ```

 * `ManagedUserPath` is optional (but recommended). It specifies the location (relative to `BasePath`) new Active Directory user objects are created.
   The default value is `CN=P3KI Managed` and is suitable if `BasePath` points to the `CN=Users` folder.
   The path is relative to `BasePath` and is prepended to form a full dn.
   UserSync does NOT create this path within the Active Directory, it must be created manually before running any import.

   *Warning:* This path MUST NOT contain any non-managed users otherwise these accounts will be _DEACTIVATED_.   

   Type: String

   Example:
   ```
   "ManagedUserPath" : "CN=P3KI Managed"
   ```

 * `GroupMap` is optional (but recommended). It specifies how security group memberships are mapped between source and destination Active Directory.
   
   It consists of a dictionary object with entries formatted as `"<Source AD group>":"<Target AD group>"`.
   
    * Source paths are relative to the `BasePath` used in the export configuration file.
   
      Each one should match one `SearchGroups` entry in the export configuration.
   
      Additionally, a `*` entry may be added to specify a group every managed user should be placed in.
    * Target paths are relative to the `BasePath` used in the import configuration file.

   If not specified, no group memberships will be assigned to managed users.

   Type: Object (key-value-dictionary)

   Example:
   ```
    "GroupMap" : {
        "CN=Administrators" : "CN=p-Administrators",
        "CN=Operators"      : "CN=p-Operators",
        "CN=Viewers"        : "CN=p-Viewers",
        "*"                 : "CN=p-Managed"
    }
   ```
   
 * `RestrictedGroups` is optional. It specifies groups this script may not assign to any user even though they are listed in the `GroupMap`.
   Instead, these actions are deferred to the `InteractiveActionsOutput` for use with a user interactive application.
  
   Type: Array of String
 
   Example:
   ```
   "RestrictedGroups" : ["CN=p-Administrators"],
   ```

 * `PrefixAccountNames` is optional. It specifies a prefix that is added all managed user and common names to avoid conflicts with existing non-managed users.

   The default is not to prefix names.

   Type: String
   
   Example:
   ```
   "PrefixAccountNames" : "p-",
   ```

 * `DefaultExpiration` is optional. It specifies how log managed user accounts should be valid for.
   The expiration date is extended by the specified time every time the import script is done.
   If the source account expiration date is closer than the specified time, the source value is used instead.

   The format is `{"Months" : <months>, "Days" : <days>}`   

   The default is 1 month & 1 day.
   
   Type: Object

   Example:
   ```
    "DefaultExpiration" : {"Months" :  1, "Days" :  1}
   ```

 * `InteractiveActionsOutput` is optional.  It specifies the file path to write Interactive Actions into.
   If the importer can not automatically perform certain actions (See "Interactive Actions" section) it will write them
   to the file specified here.

   Default value: `Pending.json`

   Type: String

   Example:
   ```
   "InteractiveActionsOutput" : "Pending.json"
   ```

#### Full file example ####
```json
{
    "BasePath" : "CN=Users,DC=ad,DC=company,DC=com",
    "ManagedUserPath" : "CN=P3KI Managed",

    "GroupMap" : {
        "CN=t-Administrators" : "CN=p-Administrators",
        "CN=t-Operators"      : "CN=p-Operators",
        "CN=t-Viewers"        : "CN=p-Viewers",
        "*"                   : "CN=p-Managed"
    },
    "RestrictedGroups" : ["CN=p-Administrators"],

    "PrefixAccountNames" : "p-",

    "DefaultExpiration" : {"Months" :  1, "Days" :  1},

    "InteractiveActionsOutput" : "Pending.json"
}
```

### Run example ###

```
UserSync --config Import.cfg --import Users.json
```
