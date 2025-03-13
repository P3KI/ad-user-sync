#!/bin/env/python

import pathlib
import os
import json
import shutil
import sys
from datetime import datetime
import subprocess

import dateutil.parser
import pytest
from dateutil.relativedelta import relativedelta

from pyad import ADGroup, ADUser, win32Exception, ADContainer


basePath = pathlib.Path(__file__).parent
testPath = basePath / "cases"

syncScript     = (basePath / ".." / "user_sync.py").absolute()
importConfig   = (basePath / "import_config.json").absolute()
readbackConfig = (basePath / "readback_config.json").absolute()

tests = list(testPath.glob("*"))
tests.sort()

pytestmark = pytest.mark.parametrize("test", tests)

def test_run(test):
    print("#### Running test {}".format(test))
    os.chdir(test)

    stages = list(test.glob("stage*"))
    stages.sort()
    if len(stages) == 0:
        stages.append(None)

    with open(importConfig) as f:
        config = json.load(f)

    ret = True

    try:
        for stage in stages:
            if stage is not None:
                print("  ## Stage '{}'".format(stage))
                os.chdir(stage)

            shutil.copy("ResolutionsIn.json", "Resolutions.json")
            subprocess.run (["python", syncScript, "import", "--config", importConfig])
            subprocess.run (["python", syncScript, "export", "--config", readbackConfig])
            os.remove("Resolutions.json")


            with open("Expected.json") as f:
                expected_result = json.load(f)
            with open("Readback.json") as f:
                actual_result = json.load(f)


            try:
                compare_lists(expected_result, actual_result)
            finally:
                os.remove("Readback.json")

    finally:
        cleanup(config)


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
                raise AssertionError("User '{}' property for '{}' differs: Expected: '{}' Actual: '{}'".format(actual["cn"], key, expected[key], actual[key]))
        else:
            if expected[key] != actual[key]:
                raise AssertionError("User '{}' property for '{}' differs: Expected: '{}' Actual: '{}'".format(actual["cn"], key, expected[key], actual[key]))


def sort_lists(l):
    return l.sort(key=lambda x: x['sAMAccountName'])


def cleanup(config):
    if len(config.get("managed_user_path", "")) > 0 :
        managed_user_path = config["managed_user_path"] + "," +  config["base_path"]
    else:
        managed_user_path =  config["base_path"]

    managed_user_container = ADContainer.from_dn(managed_user_path)
    for user in managed_user_container.get_children_iter(True, [ADUser]):
        #print("Cleanup user {}".format(user))
        user.delete()
