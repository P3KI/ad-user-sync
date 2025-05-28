#!/usr/bin/env python3
import argparse
import json
import sys
import importlib.metadata

from ad_user_sync.util import document_model
from ad_user_sync.interactive_import import interactive_import, InteractiveImportConfig, import_users
from ad_user_sync.export_users import export_users
from ad_user_sync.model import ImportConfig, ResolutionList, ExportConfig
from ad_user_sync.user_file import UserFile
from ad_user_sync.logger import Logger
from ad_user_sync.embedded_config import EmbeddedConfig

arg_parser = argparse.ArgumentParser(
    prog="ad-user-sync.exe",
    description="Import/Export Windows ActiveDirectory user accounts",
    add_help=True,
    exit_on_error=True,
)
arg_parser.add_argument("--version",
                        action='store_true',
                        dest="version",
                        help="Print version information and exit")

subparsers = arg_parser.add_subparsers(dest="command", help="Available commands")

import_arg_parser = subparsers.add_parser(
    name="import",
    help="Import Users",
    epilog=f"The CONFIG_FILE should contain a JSON object with the following values:\n\n{document_model(InteractiveImportConfig)}",
    formatter_class=argparse.RawTextHelpFormatter,
)
import_arg_parser.add_argument(
    "--config",
    dest="config_file",
    default=None,
    help="Configuration file to use.",
)
import_arg_parser.add_argument(
    "--interactive",
    action="store_true",
    help="Start an interactive import session",
)

import_arg_parser.add_argument("--hmac", dest="hmac", help="Verify HMAC on the input file using a shared key")


export_arg_parser = subparsers.add_parser(
    name="export",
    help="Export Users",
    epilog=f"The CONFIG_FILE should contain a JSON object with the following values:\n\n{document_model(ExportConfig)}",
    formatter_class=argparse.RawTextHelpFormatter,
)
export_arg_parser.add_argument(
    "--config",
    dest="config_file",
    default=None,
    help="Configuration file to use. See README.",
)

export_arg_parser.add_argument("--hmac", dest="hmac", help="Add HMAC to output file using a shared key")

def get_version():
    try:
        return importlib.metadata.version('ad-user-sync')
    except importlib.metadata.PackageNotFoundError:
        return "(unknown)"

if __name__ == "__main__":
    args = arg_parser.parse_args()
    Logger.init(args.command)

    embedded_config = EmbeddedConfig(Logger.get())

    if args.version:
        print(f"AD User Sync version: {get_version()}")

    elif args.command == "import":
        config_file = args.config_file or "import_config.json"
        if args.interactive:
            if embedded_config.import_config is None or args.config_file is not None:
                Logger.get().info("Using config: %s", config_file)
                config = InteractiveImportConfig.load(file=config_file, logger=Logger.get(), fallback_default=False, exit_on_fail=True)
            else:
                Logger.get().info("Using embedded config")
                config = embedded_config.import_config

            config.hmac = args.hmac or config.hmac

            Logger.set_config(config)
            Logger.get().info(f"Starting AD User Sync version: {get_version()}")
            result = interactive_import(
                config=config,
                logger=Logger.get(),
            )

        else:
            if embedded_config.import_config is None or args.config_file is not None:
                Logger.get().info("Using config: %s", config_file)
                config = ImportConfig.load(config_file, logger=Logger.get(), fallback_default=False, exit_on_fail=True)
            else:
                Logger.get().info("Using embedded config")
                config = embedded_config.import_config

            config.hmac = args.hmac or config.hmac
            Logger.set_config(config)
            Logger.get().info(f"Starting AD User Sync version: {get_version()}")
            result = import_users(
                config=config,
                logger=Logger.get(),
                resolutions=ResolutionList.load(
                    file=config.resolutions_file,
                    logger=Logger.get(),
                    save_default=True,
                    exit_on_fail=True,
                ),
            )

        # write the result to stdout
        print(result.model_dump_json(indent=4))
    elif args.command == "export":
        config_file = args.config_file or "export_config.json"
        if embedded_config.export_config is None or args.config_file is not None:
            Logger.get().info("Using config: %s", config_file)
            config = ExportConfig.load(config_file, logger=Logger.get(), fallback_default=False, exit_on_fail=True)
        else:
            Logger.get().info("Using embedded config")
            config = embedded_config.export_config


        config.hmac = args.hmac or config.hmac

        users = export_users(config=config, logger=Logger.get())
        if config.export_file:
            UserFile(path=config.export_file, hmac=config.hmac).write(users)
        else:
            print(json.dumps(users, ensure_ascii=False, indent=4))

    else:
        arg_parser.print_help()

    sys.exit(0)
