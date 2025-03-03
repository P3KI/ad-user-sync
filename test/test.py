#!/bin/env/python

import pathlib
import os
import json
import shutil
from datetime import datetime

import dateutil.parser
from dateutil.relativedelta import relativedelta

basePath = pathlib.Path(__file__).parent
testPath = basePath / "cases"


def run_test(test):
    print("Running test {}".format(test))
    os.chdir(test)
    os.remove("Resolutions.json")
    shutil.copy("ResolutionsIn.json", "Resolutions.json")
    os.system("python ../../../user_sync.py import --config ../../import_config.json")
    os.system("python ../../../user_sync.py export --config ../../readback_config.json")

    with open("Expected.json") as f:
        expected_result = json.load(f)
    with open("Readback.json") as f:
        actual_result = json.load(f)

    compare_lists(expected_result, actual_result)


def compare_lists(expected, actual):
    sort_lists(expected)
    sort_lists(actual)

    if len(expected) != len(actual):
        raise AssertionError("Number of imported users differ from expected. Expected: {}\nActual: {}".format(len(expected), len(actual)))

    expected_expiry = datetime.now() + relativedelta(months=1,days=1)

    for i in range(len(expected)):
        compare_users(expected[i], actual[i], expected_expiry)

def compare_users(expected, actual, expected_expiry):
    missing_keys = set(expected.keys()) - set(actual.keys())
    if len(missing_keys) > 0:
        raise AssertionError("Missing user keys: {}".format(missing_keys))

    extra_keys = set(actual.keys()) - set(expected.keys())
    if len(extra_keys) > 0:
        raise AssertionError("Extra user keys: {}".format(extra_keys))

    for key in expected.keys():
        if key == "accountExpires":
            delta = abs((dateutil.parser.parse(actual[key]) - expected_expiry).total_seconds())
            if delta > 600:
                raise AssertionError("User property for '{}' differs: Expected: '{}' Actual: '{}'".format(key, expected[key], actual[key]))
        else:
            if expected[key] != actual[key]:
                raise AssertionError("User property for '{}' differs: Expected: '{}' Actual: '{}'".format(key, expected[key], actual[key]))


def sort_lists(l):
    return l.sort(key=lambda x: x['sAMAccountName'])


for test in testPath.glob("*"):
    run_test(test)

