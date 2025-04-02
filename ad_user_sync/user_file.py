import hmac
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


class UserFile:

    @staticmethod
    def write(filename: Path, hmac_key: str, users: List[Dict[str, Any]]):
        root = {"timestamp": datetime.now().isoformat(), "users": users}
        string = json.dumps(root, ensure_ascii=False, indent=4)

        with open(filename, "w") as f:
            if hmac_key is None:
                f.write(string)
            else:
                if not string.endswith("\n"):
                    string += "\n"
                mac = hmac.new(bytes.fromhex(hmac_key), bytes(string, 'utf-8'), hashlib.sha256)
                f.write(string)
                f.write(mac.hexdigest())

    @staticmethod
    def read(filename: Path, hmac_key: str | None) -> List[Dict[str, Any]]:
        with open(filename) as f:
            data = f.read()

        if hmac_key is None:
            body = data
        else:
            sep = data.rindex("\n")
            body = data[:sep+1]
            read_mac = bytes.fromhex(data[sep + 1:])
            calc_mac = hmac.new(bytes.fromhex(hmac_key), bytes(body, 'utf-8'), hashlib.sha256).digest()
            if not hmac.compare_digest(read_mac, calc_mac):
                raise ValueError("MAC verification failed")

        root = json.loads(body)
        return root["users"]
