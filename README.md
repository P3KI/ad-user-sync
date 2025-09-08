## About UserSync ##
UserSync is a tool to export users from a Windows Active Directory and import them into another.
For this to make sense two instances of this application must be operated. One on each active directory instance.
As the exported list of users is written to a file,
the user must provide means to transfer this file from the exporting to the importing AD.


## Exporting
First create a config file. Run `ad-user-sync.exe export --help` to see what parameters are supported.

### Export Users to file
To export users just run:
```
ad-user-sync.exe export
```
By default, the config is read from `export-config.json`, but a different filename can be specified with the 
`--config CONFIG_FILE` option.

## Importing users ##
First create a config file. Run `ad-user-sync.exe import --help` to see what parameters are supported.
The Active Directory path specified using `managed_user_path` in the configuration must also be created manually before first use.

Import mode creates new active directory users or updates the attributes of previously create ones to match the data found
in the `input_file`.

Managed users that have been previously created are never deleted, but deactivated if they are not part of the current `input_file`.


### Importing Users from file 
To import users just run:
```
ad-user-sync.exe import
```
By default, the config is read from `import-config.json`, but a different filename can be specified with the 
`--config CONFIG_FILE` option.


### Interactively importing Users from file 
The import process is not fully automatic. Some actions require manual approval. These are:
   * Imported users are not automatically enabled.
   * Imported users are not automatically assigned any password.
   * Membership to groups specified in config as `restricted_groups` is not automatically granted.
   * In case of conflicting user account names or UPN with existing, non-managed, users no managed new user is created.

These cases can be resolved interactively with the `--interactive` flag:
```
ad-user-sync.exe import --interactive
```

A Browser window should open up and guide you through accepting or rejecting these actions.

Accepted actions are performed instantly, rejected actions are persisted to `resolutions_file` 
so they don't pop up every time. 

### Logging
Logs are written to `stderr` and a summary is written to `stdout`.
Feel free to pipe these outputs wherever you like. 

- Misconfigurations are written on `ERROR`
- Mishandled interactive session usage is written on `WARNING` 
- Missing and empty file messages are written on `WARNING` 
- All actions made to AD are written on `INFO`
- Quite some more stuff is written to `DEBUG`

The used level can be set through the `log_level` config parameter.

## Hash-based message authentication code (HMAC)

A message authentication code can be added to the export output file. This is used to check for a corrupted file when importing.
To add the HMAC specify the `--hmac SHARED_SECRET` option to the export command line:
```
ad-user-sync.exe export --hmac d8b1619ae68eec643255a74014233f6d
```
This will add another line with the calculated to the message authentication code output.
Because it is added as an extra line, the output will _no longer be JSON compliant_.

If a `--hmac` option is specified during export, it *must* also be specified during import and *must* use the exact same shared secret.
```
ad-user-sync.exe import --hmac d8b1619ae68eec643255a74014233f6d
```

## Development
Make sure you got [python >=3.13](https://www.python.org/downloads/) and [poetry](https://python-poetry.org/docs/)
installed on your system.

Install the dependencies to a new virtual environment and activate it run: 
```
poetry install
poetry shell
```

Then execute the `user_sync.py` with arguments like described above.

To build the executable run:
```
poetry build
```


## License

UserSync is dual-licensed:

- **Noncommercial License** (default):  
  You may use, copy, and modify this software **only for noncommercial purposes** under the terms of the [AGPL v3](LICENSE.non-commercial.md).
  Explicitly granted is the permission of running this software, as-is, in corporate settings where the software or the service of running it is not itself commercialized.

- **Commercial License**:  
  If you would like to use this software in a **commercial product, service, or for-profit environment**, you must obtain a commercial license from [P3KI GmbH](https://p3ki.com).

