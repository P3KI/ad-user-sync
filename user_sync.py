#!/usr/bin/env python3
import argparse
import logging
from logging import getLogger


arg_parser = argparse.ArgumentParser(
    prog="user_sync.py",
    description="Import/Export Windows ActiveDirectory user accounts",
    add_help=True,
    exit_on_error=True,
)
subparsers = arg_parser.add_subparsers(dest="command", help="Available commands")

import_arg_parser = subparsers.add_parser("import", help="Import Users")
import_arg_parser.add_argument(
    "--config",
    dest="config_file",
    default="ImportConfig.json",
    help="Configuration file to use. See README.",
)
import_arg_parser.add_argument(
    "--interactive",
    action="store_true",
    help="Start an interactive import session",
)

export_arg_parser = subparsers.add_parser("export", help="Export Users")
export_arg_parser.add_argument(
    "--config",
    dest="config_file",
    default="ExportConfig.json",
    help="Configuration file to use. See README.",
)

if __name__ == "__main__":
    args = arg_parser.parse_args()

    # Print Args
    print(f"Args: {args}")

    logger = getLogger(args.command)
    logger.setLevel(logging.DEBUG)

    if args.command == "import":
        from src import ImportConfig

        config = ImportConfig.load(args.config_file, logger=logger, exit_on_fail=True)

        if args.interactive:
            from src import interactive_import

            result = interactive_import(config=config, logger=logger)
        else:
            from src import import_users

            result = import_users(config=config, logger=logger)

        # log the remaining unresolved actions
        result.log_required_interactions(logger=logger)
    elif args.command == "export":
        from src import ExportConfig, export_users

        config = ExportConfig.load(args.config_file, logger=logger, exit_on_fail=True)

        export_users(config=config)
