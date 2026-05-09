import json
import os
import uuid
from pathlib import Path

_override = os.environ.get("HOSTS_FILE_OVERRIDE")
HOSTS_FILE = Path(_override) if _override else (
    Path(os.path.dirname(os.path.abspath(__file__))).parent / "hosts.json"
)


def load_hosts() -> list:
    if not HOSTS_FILE.exists():
        return []
    try:
        with open(HOSTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_hosts(hosts: list) -> None:
    with open(HOSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(hosts, f, ensure_ascii=False, indent=2)


def add_host(name: str, ip: str, port: int, token: str) -> dict:
    hosts = load_hosts()
    entry = {
        "id":        str(uuid.uuid4()),
        "name":      name,
        "ip":        ip,
        "port":      port,
        "token":     token,
        "last_seen": None,
        "last_scan": None,
    }
    hosts.append(entry)
    save_hosts(hosts)
    return entry


def update_host(host_id: str, **fields) -> None:
    hosts = load_hosts()
    for h in hosts:
        if h["id"] == host_id:
            h.update(fields)
            break
    save_hosts(hosts)


def remove_host(host_id: str) -> None:
    save_hosts([h for h in load_hosts() if h["id"] != host_id])
