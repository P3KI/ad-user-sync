from hmac import HMAC, compare_digest
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


class UserFile:
    path: Path
    hmac: str | None

    def __init__(self, path: Path, hmac: str | None = None):
        self.path = path
        self.hmac = hmac

    def write(self, users: List[Dict[str, Any]]) -> None:
        body = json.dumps(
            dict(
                timestamp=datetime.now().isoformat(),
                users=users,
            ),
            ensure_ascii=False,
            indent=4,
        )

        with open(self.path, "w") as f:
            f.write(body)
            if self.hmac:
                if not body.endswith("\n"):
                    body += "\n"
                mac = HMAC(bytes.fromhex(self.hmac), bytes(body, "utf-8"), hashlib.sha256)
                f.write(mac.hexdigest())

    def read(self) -> List[Dict[str, Any]]:
        with open(self.path) as f:
            body = f.read()

        if self.hmac:
            body, read_mac = body.rsplit("\n", 1)
            read_mac = bytes.fromhex(read_mac)
            calc_mac = HMAC(bytes.fromhex(self.hmac), bytes(body, "utf-8"), hashlib.sha256).digest()
            if not compare_digest(read_mac, calc_mac):
                raise ValueError("MAC verification failed")

        root = json.loads(body)
        return root["users"]
