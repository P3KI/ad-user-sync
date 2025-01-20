import json
import time
import webbrowser
from datetime import datetime, timedelta
from logging import Logger
from pathlib import Path
from threading import Lock
from typing import List

from pydantic import ValidationError

from . import ImportConfig, import_users, CatchableADExceptions, Resolution, Action, EnableResolution, EnableAction
from .model import ResolutionList, ResolutionParser

from bottle import jinja2_template
import bottle

from .util import format_validation_error, random_string, KillableThread

bottle.TEMPLATE_PATH.append(Path(__file__).parent.parent / "templates")
static_file_path = Path(__file__).parent.parent / "templates" / "static"


def interactive_import(
    config: ImportConfig,
    logger: Logger,
    port: int = 8080,
):
    state = InteractiveState()

    def run_import(resolutions: ResolutionList):
        try:
            # cache the still required actions in state for logging at eventual termination
            state.actions = import_users(
                config=config,
                resolutions=resolutions,
                logger=logger.getChild("import_users"),
            )
            state.last_error = None
        except CatchableADExceptions as e:
            logger.exception("error during import_users")
            state.last_error = str(e)


    @bottle.get("/static/<filepath:path>")
    def static(filepath):
        return bottle.static_file(filepath, root=static_file_path)

    @bottle.get("/")
    def get_root():
        state.verify_request()
        with state:
            run_import(
                resolutions=ResolutionList.load(config.rejected_actions, logger=logger)
            )
            return state.render_html()

    @bottle.post("/")
    def post_root():
        state.verify_request()
        with state:
            try:
                new_resolution: Resolution = ResolutionParser.validate_python(bottle.request.forms)
                logger.info(f"new resolution via POST: {new_resolution.model_dump(exclude={'timestamp'})}")
            except ValidationError as e:
                return jinja2_template(
                    "resolve.html.jinja",
                    actions=state.actions,
                    tag=state.tag,
                    password_count=len(state.password_resolutions),
                    error=format_validation_error(e, source="HTTP POST Form Data"),
                )

            # append new resolutions to existing
            resolutions = ResolutionList.load(config.rejected_actions, logger=logger)
            # todo
            resolutions.resolutions.append(new_resolution)

            run_import(resolutions=resolutions)

            if new_resolution.is_rejected:
                # save rejections to file
                resolutions.get_rejected().save(config.rejected_actions)
            elif isinstance(new_resolution, EnableResolution):
                # remember newly set password in state if it was actually set (means: there is no more enable action)
                if next(
                    filter(lambda a: isinstance(a, EnableAction) and a.user == new_resolution.user, state.actions),
                    None,
                ) is None:
                    state.password_resolutions.append(new_resolution)

            return state.render_html()

    @bottle.get("/heartbeat")
    def beat_heart():
        state.verify_request()
        with state:  # requesting state as resource sets last request to now
            # tell the browser tab to send the next heartbeat in half timeout (as milliseconds)
            bottle.response.content_type = "application/json"
            return json.dumps((state.timeout / 2).total_seconds() * 1000)

    # start the server thread
    server_thread = KillableThread(
        target=bottle.run,
        kwargs=dict(
            host="localhost",
            port=port,
            quiet=False,
        ),
    )
    server_thread.start()
    url = f"http://localhost:{port}?tag={state.tag}"
    logger.info(f"Interactive import session started: {url}")
    webbrowser.open(url)

    # watch out for terminating events in the main thread
    try:
        while 1:
            if not server_thread.is_alive():
                # the server thread should not end by itself. this is just for good measure
                logger.warning("bottle server was stopped somehow")
                break
            if not state.is_alive():  # state.is_alive() blocks while there are other requests pending
                logger.debug("all browser tabs closed")
                server_thread.terminate()
                break
            time.sleep(500)
    except KeyboardInterrupt:
        logger.debug("received keyboard interrupt")
        server_thread.terminate()

    logger.info("interactive import ended")

    # log the remaining unresolved actions
    for action in state.actions:
        logger.info(f"action still required: {action.model_dump()}")


class InteractiveState:
    tag: str
    mutex: Lock
    resolutions: List[EnableResolution]
    timeout: timedelta

    actions: List[Action]
    last_request: datetime | None
    last_error: str | None = None

    def __init__(self):
        self.tag = random_string(6)
        self.timeout = timedelta(seconds=3)
        self.mutex = Lock()
        self.last_request = None
        self.last_error = None
        self.actions = []
        self.password_resolutions = []

    def is_alive(self) -> bool:
        if self.last_request is None:
            return True
        with self.mutex:
            return datetime.now() - self.last_request <= self.timeout

    def __enter__(self):
        return self.mutex.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        self.last_request = datetime.now()
        self.mutex.__exit__(exc_type, exc_value, traceback)

    def verify_request(self):
        if bottle.request.query.get("tag") != self.tag:
            bottle.abort(401)

    def render_html(self) -> str:
        return jinja2_template(
            "resolve.html.jinja",
            actions=self.actions,
            password_count=len(self.password_resolutions),
            tag=self.tag,
            error=self.last_error,
        )