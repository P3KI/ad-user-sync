#!/usr/bin/env python3
import argparse
import json
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
            from src import interactive_import, InteractiveImportConfig

            logger.name = "interactive"
            result = interactive_import(
                config=InteractiveImportConfig.load(
                    file=args.config_file,
                    logger=logger,
                    exit_on_fail=True,
                ),
                logger=logger,
            )

        else:
            from src import import_users, ImportConfig, ResolutionList

            logger.name = "import"
            config = ImportConfig.load(args.config_file, logger=logger, exit_on_fail=True)
            result = import_users(
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
        from src import ExportConfig, export_users

        logger.name = "export"
        config = ExportConfig.load(args.config_file, logger=logger, exit_on_fail=True)

        users = export_users(config=config)
        # if config.output_file:
        #     with open(config.export_file, "w") as f:
        #         json.dump(users, f, ensure_ascii=False, indent=4)
        # else:
        print(json.dumps(users, ensure_ascii=False, indent=4))

    exit(0)
