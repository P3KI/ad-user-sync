import logging
from pathlib import Path
from typing import Dict, List, Any, Set

from . import ImportConfig, import_users, CachedActiveDirectory, CatchableADExceptions
from .model import Resolutions, Action

from bottle import route, run, jinja2_template, post, request
import bottle

bottle.TEMPLATE_PATH.append(Path(__file__).parent.parent / 'templates')


def interactive_import(
    config: ImportConfig,
    input_file: str,
    port: int = 8080,
):

    @route('/')
    def index():
        try:
            actions = import_users(
                config=config,
                input_file=input_file,
                resolutions=Resolutions.load(config.interactive_actions_output),
            )
            return jinja2_template('resolve.html.jinja', actions=actions)
        except CatchableADExceptions as e:
            logging.exception("error during import_users")
            return jinja2_template('error.html.jinja', err=e)

    @post('/')
    def index():
        # parse the POSTed form values to actual resolution objects
        # the form keys have the format {{idx}}.{{prop}} where all props of one action have the same idx
        resolution_props_by_idx = {}
        for key, val in request.forms.items():
            idx, prop = key.split('.')
            resolution_props_by_idx.setdefault(idx, {})[prop] = val
        resolution_props = list(map(lambda x: x[1], sorted(resolution_props_by_idx.items())))
        new_resolutions = Resolutions(resolutions=resolution_props)

        # append new resolutions to existing
        resolutions = Resolutions.load(config.interactive_actions_output) + new_resolutions

        # save rejections
        resolutions.get_rejected().save(config.interactive_actions_output)

        # apply resolutions
        try:
            actions = import_users(
                config=config,
                input_file=input_file,
                resolutions=resolutions,
            )
        except Exception as e:
            logging.exception('Got exception on main handler')
            return jinja2_template('error.html.jinja', err=e)

        # return new action interactive form
        return jinja2_template('resolve.html.jinja', actions=actions)

    run(host='localhost', port=port)

