#!/usr/bin/env python3

import argparse
import json
import sys

from pydantic import BaseModel

arg_parser = argparse.ArgumentParser(
    prog="UserImport",
    description="Import/Export Windows ActiveDirectory user accounts",
)

arg_parser.add_argument(
    "--config",
    "-c",
    default="UserSync.cfg",
    help="Configuration file to use. See README.",
)

arg_group = arg_parser.add_mutually_exclusive_group(required=True)

arg_group.add_argument(
    "--export",
    "-e",
    "-o",
    action="store_true",
    help="Export Mode: File to write user account data to",
)
arg_group.add_argument(
    "--import",
    "-i",
    action="store_true",
    help="Import Mode: File containing the users to import",
)
arg_group.add_argument(
    "--interactive",
    "-r",
    action="store_true",
    help="Import Mode: File containing the users to import",
)
arg_parser.add_argument(
    "user_file",
    nargs=1,
    help="User list file for import/export",
)


if __name__ == "__main__":
    args = arg_parser.parse_args()

    try:
        with open(args.config, "r") as f:
            config_json_str = f.read()

    except FileNotFoundError:
        print(f"Error: Config file '{args.config}' not found.", file=sys.stderr)
        exit(1)

    print(f"Args: {args}")

    if args.export:
        from src.UserExport import UserExporter

        exporter = UserExporter(file=args.user_file[0], config=config)
        exporter.run()

    elif vars(args)["import"]:
        from src import import_users, ImportConfig

        actions = import_users(
            config=ImportConfig.model_validate_json(config_json_str),
            input_file=args.user_file[0],
        )

        print(json.dumps(list(map(BaseModel.model_dump, actions)), indent=4))

    elif vars(args)["interactive"]:
        from src import ImportConfig, interactive_import
        interactive_import(
            config=ImportConfig.model_validate_json(config_json_str),
            input_file=args.user_file[0],
        )