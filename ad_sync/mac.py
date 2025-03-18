import hmac
import hashlib

def writes_with_mac(file, hmac_key : str, string : str):
    if hmac_key is None:
        file.write(string)
    else:
        if not string.endswith("\n"):
            string += "\n"
        mac = hmac.new(bytes.fromhex(hmac_key), bytes(string, 'utf-8'), hashlib.sha256)
        file.write(string)
        file.write(mac.hexdigest())


def read_with_mac(file, hmac_key) -> str:
    data = file.read()
    if hmac_key is None:
        return data

    sep = data.rindex("\n")
    body = data[:sep+1]
    read_mac = bytes.fromhex(data[sep + 1:])
    calc_mac = hmac.new(bytes.fromhex(hmac_key), bytes(body, 'utf-8'), hashlib.sha256).digest()
    if not hmac.compare_digest(read_mac, calc_mac):
        raise ValueError("MAC verification failed")

    return body