import argparse
import json
import os
import sys
import time
import webbrowser
from datetime import datetime, timedelta
from logging import Logger
from pathlib import Path
from threading import Lock
from typing import List, Tuple

from pydantic import ValidationError
from bottle import jinja2_template, cached_property
import bottle

from .import_users import import_users
from .active_directory import CatchableADExceptions
from .model import ResolutionList, ResolutionParser, ImportResult, Resolution, EnableResolution, InteractiveImportConfig
from .util import format_validation_error, random_string, KillableThread, find_free_port


def resource_path(relative_path) -> Path:
    if hasattr(sys, '_MEIPASS'):
        return Path(str(os.path.join(sys._MEIPASS, relative_path)))
    return Path(os.path.join(os.path.abspath("."), "templates", relative_path))


bottle.TEMPLATE_PATH.append(resource_path(""))
static_file_path = resource_path("static")

def interactive_import(
    args: argparse.Namespace,
    config: InteractiveImportConfig,
    logger: Logger,
) -> ImportResult:
    session = InteractiveSession(args=args, config=config, logger=logger)

    @bottle.get("/static/<filepath:path>")
    def static(filepath):
        return bottle.static_file(filepath, root=static_file_path)

    @bottle.get("/")
    def get_root():
        session.verify_tag()
        with session:
            if session.current_result_rendered:
                session.run_import()
            return session.render_import_result()

    @bottle.post("/")
    def post_root():
        session.verify_tag()
        with session:
            try:
                new_resolution: Resolution = ResolutionParser.validate_python(bottle.request.forms)
                logger.debug(f"new resolution via POST: {new_resolution.model_dump(exclude={'timestamp'})}")
            except ValidationError as e:
                session.error = format_validation_error(e, source="HTTP POST Form Data")
                return session.render_import_result()
            session.run_import(new_resolution=new_resolution)
            return bottle.redirect(f"/?tag={session.tag}")

    @bottle.get("/export-passwords")
    def export_passwords():
        session.verify_tag()
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
            return json.dumps(
                dict(
                    # tell the browser tab to send the next heartbeat in half timeout (as milliseconds)
                    timeout=config.heartbeat_interval * 1000 if config.heartbeat_interval > 0 else None,
                    # update the message if passwords have been exported
                    set_passwords=len(session.set_passwords),
                    unexported_passwords=session.unexported_passwords,
                    is_active_tab=bottle.request.query.get("tab") == session.last_tab_id,
                )
            )

    return session.start()


class InteractiveSession:
    # general
    args: argparse.Namespace
    config: InteractiveImportConfig
    logger: Logger
    tag: str
    mutex: Lock
    timeout: timedelta | None  # time after which this session detects tabs as closed

    # last import_users result
    error: str | None
    result: ImportResult
    set_passwords: List[Tuple[str, str]]

    # runtime state
    last_request: datetime | None
    last_tab_id: str | None
    current_result_rendered: bool
    exported_passwords: int
    port: int

    def __init__(self, args: argparse.Namespace, config: InteractiveImportConfig, logger: Logger):
        self.args = args
        self.config = config
        self.logger = logger
        self.tag = random_string(6)
        self.mutex = Lock()
        self.timeout = None
        if self.config.heartbeat_interval > 0:
            self.timeout = timedelta(seconds=self.config.heartbeat_interval * 1.5)

        self.error = None
        self.result = ImportResult()
        self.result.logger = logger
        self.set_passwords = []
        self.last_request = None
        self.last_tab_id = None
        self.current_result_rendered = True
        self.exported_passwords = 0
        self.port = find_free_port() if self.config.port is None else self.config.port


    @property
    def unexported_passwords(self) -> int:
        return len(self.set_passwords) - self.exported_passwords

    @property
    def has_unexported_passwords(self) -> bool:
        return self.unexported_passwords > 0

    @property
    def url(self) -> str:
        return f"http://localhost:{self.port}?tag={self.tag}"

    def __enter__(self):
        res = self.mutex.__enter__()
        self.error = None
        return res

    def __exit__(self, exc_type, exc_value, traceback):
        self.last_request = datetime.now()
        self.mutex.__exit__(exc_type, exc_value, traceback)

    def has_open_browser_tabs(self) -> bool:
        if self.last_request is None or self.timeout is None:
            return True
        with self.mutex:
            return datetime.now() - self.last_request <= self.timeout

    def verify_tag(self):
        if bottle.request.query.get("tag") != self.tag:
            bottle.abort(401)

    def run_import(self, new_resolution: Resolution | None = None) -> None:
        resolutions = ResolutionList.load(file=self.config.resolutions_file, logger=self.logger, save_default=True)
        if new_resolution is not None:
            resolutions.append(new_resolution)
        try:
            self.result.update(
                import_users(
                    args=self.args,
                    config=self.config,
                    resolutions=resolutions,
                    logger=self.logger.getChild("import"),
                )
            )
            self.error = None
            self.current_result_rendered = False
        except CatchableADExceptions as e:
            self.logger.exception("error during import_users")
            self.error = str(e)
            self.current_result_rendered = False
            return

        # handle persistence of new_resolution
        if new_resolution is not None:
            if new_resolution.is_rejected:
                # save rejections to file
                if self.config.resolutions_file is not None:
                    resolutions.get_rejected().save(self.config.resolutions_file)
            elif isinstance(new_resolution, EnableResolution):
                # remember newly set password in state if it was actually set
                enabled_user = next(filter(lambda u: u.cn == new_resolution.user, self.result.enabled), None)
                if enabled_user is not None:
                    account_name_attributes = enabled_user.get_attribute("sAMAccountName")
                    account_name = enabled_user.cn if len(account_name_attributes) != 1 else account_name_attributes[0]
                    self.set_passwords.append((account_name, new_resolution.password))

    def render_import_result(self) -> str:
        self.last_tab_id = random_string(6)
        self.current_result_rendered = True
        actions = self.result.required_interactions if self.result else []
        actions.sort(key = lambda a: a.user)
        return jinja2_template(
            "resolve.html.jinja",
            actions=actions,
            password_count=len(self.set_passwords),
            password_word_count=self.config.password_word_count,
            tag=self.tag,
            tab_id=self.last_tab_id,
            error=self.error,
        )

    def start(self) -> ImportResult:
        # start the bottle thread
        bottle_thread = KillableThread(
            target=bottle.run,
            kwargs=dict(
                host="localhost",
                port=self.port,
                quiet=True,
            ),
        )
        bottle_thread.start()

        self.logger.warning(f"session started: {self.url}")
        webbrowser.open(self.url)

        # watch out for terminating events in the main thread
        self._wait_for_terminating_events(bottle_thread)
        bottle_thread.terminate()
        bottle_thread.join(timeout=5)
        self.logger.warning("session ended")
        return self.result

    def _wait_for_terminating_events(
        self,
        bottle_thread: KillableThread,
        terminated_once_while_unexported: bool = False,
        tabs_closed_detected: bool = False,
    ) -> None:
        try:
            while 1:
                if not bottle_thread.is_alive():
                    # the server thread should not end by itself. this is just for good measure
                    self.logger.error("bottle server was stopped somehow")
                    return

                if self.has_open_browser_tabs():  # has_open_browser_tabs() blocks while there are pending requests
                    tabs_closed_detected = False
                else:
                    if not tabs_closed_detected:
                        self.logger.debug("all browser tabs were closed")

                    if self.config.terminate_on_browser_close:
                        if not self.has_unexported_passwords:
                            return
                        elif not tabs_closed_detected:
                            self.logger.warning(
                                f"All browser tabs were closed, but there are unexported passwords.\n"
                                f"Open {self.url} to export passwords or ctrl-c to exit."
                            )
                            terminated_once_while_unexported = True
                    tabs_closed_detected = True

                if not self.has_unexported_passwords:
                    terminated_once_while_unexported = False
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.logger.debug("received keyboard interrupt")
            if self.has_unexported_passwords and not terminated_once_while_unexported:
                self.logger.warning(
                    f"Are you sure you want to exit? There are unexported passwords.\n"
                    f"Open {self.url} to export passwords or ctrl-c again to terminate."
                )
                self._wait_for_terminating_events(
                    bottle_thread=bottle_thread,
                    terminated_once_while_unexported=True,
                    tabs_closed_detected=tabs_closed_detected,
                )
