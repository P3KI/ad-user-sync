#!/usr/bin/env python3
import argparse
import json
import logging
import sys
from logging import getLogger

from ad_sync.util import document_model
from ad_sync import interactive_import, InteractiveImportConfig, import_users, ImportConfig, ResolutionList, ExportConfig, export_users
from ad_sync.user_file import UserFile

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

import_arg_parser.add_argument("--hmac",
                               dest="hmac_key",
                               help="Verify HMAC on the input file using a shared key")

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

export_arg_parser.add_argument("--hmac",
                               dest="hmac_key",
                               help="Add HMAC to output file using a shared key")

if __name__ == "__main__":
    args = arg_parser.parse_args()

    logger = getLogger()
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers:
        logger.removeHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(name)-11s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(console_handler)

    if args.command == "import":

        if args.interactive:
            logger.name = "interactive"
            config = InteractiveImportConfig.load(
                file=args.config_file,
                logger=logger,
                fallback_default=False,
                exit_on_fail=True
            )
            logger.setLevel(logging.getLevelNamesMapping()[config.log_level])
            result = interactive_import(
                args=args,
                config=config,
                logger=logger,
            )

        else:
            logger.name = "import"
            config = ImportConfig.load(args.config_file, logger=logger, fallback_default=False, exit_on_fail=True)
            logger.setLevel(logging.getLevelNamesMapping()[config.log_level])
            result = import_users(
                args=args,
                config=config,
                logger=logger,
                resolutions=ResolutionList.load(
                    file=config.resolutions_file,
                    logger=logger,
                    save_default=True,
                    exit_on_fail=True,
                ),
            )

        # write the result to stdout
        print(result.model_dump_json(indent=4))
    elif args.command == "export":
        logger.name = "export"
        config = ExportConfig.load(args.config_file, logger=logger, fallback_default=False, exit_on_fail=True)

        users = export_users(config=config)
        if config.export_file:
            with open(config.export_file, "w") as f:
                UserFile.write(config.export_file, args.hmac_key, users)
        else:
            print(json.dumps(users, ensure_ascii=False, indent=4))

    sys.exit(0)
