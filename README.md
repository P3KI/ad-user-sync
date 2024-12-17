== About UserSync ==

UserSync is a tool to export users from a Windows Active Directory and import them into another.
For this to make sense two instances of this application must be operated. One on each active directory instance.
As the exported list of users is written to a file,
the user must provide means to transfer this file from the exporting to the importing AD.

=== Exporting users ===

To run UserSync in export mode an export configuration file must be created first. By default it is read from
`UserSync.cfg`, but a different filename can be specified with the `--config CONFIGFILE` option.


==== Export Configuration ====

The configuration file is written in JSON notation. It contains 4 settings, of which 2 are mandatory.

 * `BasePath` is mandatory. It Specifies the distinguished name ("dn") of the location in the active directory
    under which all users and groups are located. If all users and groups are in one place it can be directly specified here.
    If not `BasePath` should point to the longest parent path shared by all users and the optional `SearchSubPaths`
    option should be used to restrict the recursive search for users.

    Type: String.

    Example:
    ```
    "BasePath" : "CN=Users,DC=ad,DC=company,DC=com",
    ```


 * `SearchSubPaths` is optional. It specifies relative paths to search for user objects in the AD. 
   Use in case not all of `BasePath` should be searched recursively. 
   This sub paths are prepended to `BasePath` for user search queries to form a full dn.

   Type: Array of String.

   Example:
   ```
   "SearchSubPaths" : ["CN=TransferUsers1", "CN=TransferUsers2"],
   ```
   This will export user objects located in `CN=TransferUsers1,CN=Users,DC=ad,DC=company,DC=com` or `CN=TransferUsers2,CN=Users,DC=ad,DC=company,DC=com`


 * `SearchGroups` is mandatory. It specifies which security groups a users must be a member of to be included in the export.
   If multiple groups are specified, membership in any of these groups is sufficient.
   Group object paths are relative to `BasePath` and are prepended to form a full dn.

   Type: Array of String.

   Example:
   ```
   "SearchGroups" : ["CN=Transfer","CN=Test"],
   ```
   This will export users that are members of `CN=Transfer,CN=Users,DC=ad,DC=company,DC=com` or `CN=Test,CN=Users,DC=ad,DC=company,DC=com`

 * `Attributes` is optional (but recommended). It specifies which attributes of user objects are written to the output file.
   Some attributes are always exported because they are needed for the import script to work. 
   These are `sAMAccountName`, `cn`, `disabled`, `accountExpires`, `memberOf`.
   Additional attributes should be specified to transfer more information of the users between domains.

   Example :
   ```
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

==== Full file example ====

```    
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
```
