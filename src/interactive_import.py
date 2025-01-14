from logging import Logger
from pathlib import Path

from pydantic import ValidationError

from . import ImportConfig, import_users, CatchableADExceptions
from .model import ResolutionList

from bottle import route, run, jinja2_template, post, request
import bottle

from .util import format_validation_error

bottle.TEMPLATE_PATH.append(Path(__file__).parent.parent / "templates")


def interactive_import(
    config: ImportConfig,
    logger: Logger,
    port: int = 8080,
):
    @route("/")
    def get_root():
        try:
            actions = import_users(
                config=config,
                resolutions=ResolutionList.load(config.rejected_actions, logger=logger),
                logger=logger.getChild("import_users"),
            )
            return jinja2_template("resolve.html.jinja", actions=actions)
        except CatchableADExceptions as e:
            logger.exception("error during import_users")
            return jinja2_template("error.html.jinja", err=e)

    @post("/")
    def post_root():
        # parse the POSTed form values to actual resolution objects
        # the form keys have the format {{idx}}.{{prop}} where all props of one action have the same idx
        resolution_props_by_idx = {}
        for key, val in request.forms.items():
            idx, prop = key.split(".")
            resolution_props_by_idx.setdefault(idx, {})[prop] = val
        resolution_props = list(map(lambda x: x[1], sorted(resolution_props_by_idx.items())))
        try:
            new_resolutions = ResolutionList(resolutions=resolution_props)
        except ValidationError as e:
            error_msg = format_validation_error(e, source="HTTP POST Form Data")
            logger.error(error_msg)
            return jinja2_template("error.html.jinja", err=error_msg)

        # append new resolutions to existing
        resolutions = ResolutionList.load(config.rejected_actions, logger=logger) + new_resolutions

        # save rejections
        resolutions.get_rejected().save(config.rejected_actions)

        # apply resolutions
        try:
            actions = import_users(
                config=config,
                resolutions=resolutions,
                logger=logger.getChild("import_users"),
            )
        except Exception as e:
            logger.exception("Got exception on import_users")
            return jinja2_template("error.html.jinja", err=e)

        # return new action interactive form
        return jinja2_template("resolve.html.jinja", actions=actions)

    run(host="localhost", port=port)
