#!/usr/bin/env python3
import argparse
import json
import sys


from ad_user_sync.util import document_model
from ad_user_sync.interactive_import import interactive_import, InteractiveImportConfig, import_users
from ad_user_sync.export_users import export_users
from ad_user_sync.model import ImportConfig, ResolutionList, ExportConfig
from ad_user_sync.user_file import UserFile
from ad_user_sync.logger import Logger

arg_parser = argparse.ArgumentParser(
    prog="user-sync.exe",
    description="Import/Export Windows ActiveDirectory user accounts",
    add_help=True,
    exit_on_error=True,
)
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
    default="import_config.json",
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
    default="export_config.json",
    help="Configuration file to use. See README.",
)

export_arg_parser.add_argument("--hmac", dest="hmac", help="Add HMAC to output file using a shared key")

if __name__ == "__main__":
    args = arg_parser.parse_args()
    Logger.init(args.command)

    if args.command == "import":
        if args.interactive:
            config = InteractiveImportConfig.load(
                file=args.config_file, logger=Logger.get(), fallback_default=False, exit_on_fail=True
            )
            config.hmac = args.hmac or config.hmac

            Logger.set_config(config)
            result = interactive_import(
                config=config,
                logger=Logger.get(),
            )

        else:
            config = ImportConfig.load(args.config_file, logger=Logger.get(), fallback_default=False, exit_on_fail=True)
            config.hmac = args.hmac or config.hmac
            Logger.set_config(config)
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
        config = ExportConfig.load(args.config_file, logger=Logger.get(), fallback_default=False, exit_on_fail=True)

        users = export_users(config=config, logger=Logger.get())
        if config.export_file:
            UserFile(path=config.export_file, hmac=args.hmac).write(users)
        else:
            print(json.dumps(users, ensure_ascii=False, indent=4))

    else:
        arg_parser.print_help()

    sys.exit(0)
