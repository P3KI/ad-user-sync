import json
import time
import webbrowser
from datetime import datetime, timedelta
from logging import Logger
from pathlib import Path
from threading import Lock
from typing import List, Tuple

from pydantic import ValidationError

from . import ImportConfig, import_users, CatchableADExceptions, Resolution, Action, EnableResolution, EnableAction
from .import_users import ImportResult
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
    session = InteractiveSession(config=config, logger=logger)

    @bottle.get("/static/<filepath:path>")
    def static(filepath):
        return bottle.static_file(filepath, root=static_file_path)

    @bottle.get("/")
    def get_root():
        session.verify_tag()
        with session:
            session.run_import()
            return session.render_html()

    @bottle.post("/")
    def post_root():
        session.verify_tag()
        with session:
            try:
                new_resolution: Resolution = ResolutionParser.validate_python(bottle.request.forms)
                logger.info(f"new resolution via POST: {new_resolution.model_dump(exclude={'timestamp'})}")
            except ValidationError as e:
                session.error = format_validation_error(e, source="HTTP POST Form Data")
                return session.render_html()
            session.run_import(new_resolution=new_resolution)
            return session.render_html()

    @bottle.get("/export-passwords")
    def export_passwords():
        filename = f"new-ad-passwords_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        bottle.response.headers["Content-Type"] = "text/plain"
        bottle.response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        session.exported_passwords = len(session.set_passwords)
        return "\n".join(map(":".join, session.set_passwords)) + "\n"

    @bottle.get("/heartbeat")
    def beat_heart():
        session.verify_tag()
        with session:  # requesting session as resource sets last request to now
            bottle.response.content_type = "application/json"
            return json.dumps(dict(
                # tell the browser tab to send the next heartbeat in half timeout (as milliseconds)
                timeout=(session.timeout / 2).total_seconds() * 1000,
                # update the message if passwords have been exported
                set_passwords=len(session.set_passwords),
                unexported_passwords=len(session.set_passwords) - session.exported_passwords,
                is_active_tab=bottle.request.query.get("tab") == session.last_tab_id,
            ))

    # start the bottle thread
    bottle_thread = KillableThread(
        target=bottle.run,
        kwargs=dict(
            host="localhost",
            port=port,
            quiet=False,
        ),
    )
    bottle_thread.start()
    url = f"http://localhost:{port}?tag={session.tag}"
    logger.info(f"Interactive import session started: {url}")
    webbrowser.open(url)

    # watch out for terminating events in the main thread
    try:
        while 1:
            if not bottle_thread.is_alive():
                # the server thread should not end by itself. this is just for good measure
                logger.warning("bottle server was stopped somehow")
                break
            if not session.is_alive():  # state.is_alive() blocks while there are other requests pending
                logger.debug("all browser tabs closed")
                bottle_thread.terminate()
                break
            time.sleep(500)
    except KeyboardInterrupt:
        logger.debug("received keyboard interrupt")
        bottle_thread.terminate()

    logger.info("interactive import ended")

    # log the remaining unresolved actions
    for action in session.import_result.required_interactions:
        logger.info(f"action still required: {action.model_dump()}")


class InteractiveSession:
    config: ImportConfig
    logger: Logger
    tag: str
    mutex: Lock
    timeout: timedelta

    last_request: datetime | None
    last_tab_id: str | None
    set_passwords: List[Tuple[str, str]]
    exported_passwords: int

    error: str | None
    import_result: ImportResult | None

    def __init__(self, config: ImportConfig, logger: Logger):
        self.tag = random_string(6)
        self.config = config
        self.logger = logger
        self.timeout = timedelta(seconds=3)
        self.mutex = Lock()
        self.last_request = None
        self.error = None
        self.import_result = None
        self.set_passwords = []
        self.exported_passwords = 0

    def is_alive(self) -> bool:
        if self.last_request is None:
            return True
        with self.mutex:
            return datetime.now() - self.last_request <= self.timeout

    def __enter__(self):
        res = self.mutex.__enter__()
        self.error = None
        return res

    def __exit__(self, exc_type, exc_value, traceback):
        self.last_request = datetime.now()
        self.mutex.__exit__(exc_type, exc_value, traceback)

    def verify_tag(self):
        if bottle.request.query.get("tag") != self.tag:
            bottle.abort(401)

    def run_import(self, new_resolution: Resolution | None = None) -> None:
        resolutions = ResolutionList.load(file=self.config.resolutions_file, logger=self.logger)
        if new_resolution is not None:
            resolutions.append(new_resolution)
        try:
            self.import_result = import_users(
                config=self.config,
                resolutions=resolutions,
                logger=self.logger.getChild("import_users"),
            )
            self.error = None
        except CatchableADExceptions as e:
            self.logger.exception("error during import_users")
            self.import_result = None
            self.error = str(e)
            return

        # handle persistence of new_resolution
        if new_resolution is not None:
            if new_resolution.is_rejected:
                # save rejections to file
                if self.config.resolutions_file is not None:
                    resolutions.get_rejected().save(self.config.resolutions_file)
            elif isinstance(new_resolution, EnableResolution):
                # remember newly set password in state if it was actually set
                enabled_user = next(filter(lambda u: u.dn == new_resolution.user, self.import_result.enabled), None)
                if enabled_user is not None:
                    account_name_attributes = enabled_user.get_attribute("sAMAccountName")
                    account_name = enabled_user.dn if len(account_name_attributes) != 1 else account_name_attributes[0]
                    self.set_passwords.append((account_name, new_resolution.password))

    def render_html(self) -> str:
        self.last_tab_id = random_string(6)
        return jinja2_template(
            "resolve.html.jinja",
            actions=self.import_result.required_interactions if self.import_result else [],
            password_count=len(self.set_passwords),
            tag=self.tag,
            tab_id=self.last_tab_id,
            error=self.error,
        )
