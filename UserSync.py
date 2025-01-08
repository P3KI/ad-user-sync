#!/usr/bin/env python3

import argparse
import json
import sys

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="UserImport",
        description="Import/Export Windows ActiveDirectory user accounts",
    )

    parser.add_argument(
        "--config",
        "-c",
        default="UserSync.cfg",
        help="Configuration file to use. See README.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--export",
        "-e",
        "-o",
        action="store_true",
        help="Export Mode: File to write user account data to",
    )
    group.add_argument(
        "--import",
        "-i",
        action="store_true",
        help="Import Mode: File containing the users to import",
    )
    group.add_argument(
        "--resolve",
        "-r",
        action="store_true",
        help="Import Mode: File containing the users to import",
    )
    parser.add_argument("user_file", nargs=1, help="User list file for import/export")

    args = parser.parse_args()

    try:
        # Read config
        with open(args.config) as cfg:
            config = json.load(cfg)
    except FileNotFoundError:
        print(f"Error: Config file '{args.config}' not found.", file=sys.stderr)
        exit(1)

    print("Args:", args)

    if args.export:
        from src.UserExport import UserExporter

        exporter = UserExporter(file=args.user_file[0], config=config)
        exporter.run()

    elif vars(args)["import"]:
        from src.UserImport import UserImporter

        importer = UserImporter(file=args.user_file[0], config=config)
        importer.run()
