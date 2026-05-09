import os, json, pytest
from pathlib import Path

os.environ["HOSTS_FILE_OVERRIDE"] = str(Path(__file__).parent / "hosts_test.json")
import importlib
import core.hosts_config as hc
importlib.reload(hc)

def setup_function():
    if hc.HOSTS_FILE.exists():
        hc.HOSTS_FILE.unlink()

def test_load_empty():
    assert hc.load_hosts() == []

def test_add_and_load():
    h = hc.add_host("TEST", "10.0.0.1", 5555, "abc123")
    hosts = hc.load_hosts()
    assert len(hosts) == 1
    assert hosts[0]["ip"] == "10.0.0.1"
    assert hosts[0]["name"] == "TEST"
    assert "id" in hosts[0]

def test_update_host():
    h = hc.add_host("SRV", "10.0.0.2", 5555, "tok")
    hc.update_host(h["id"], last_seen="2026-01-01")
    updated = [x for x in hc.load_hosts() if x["id"] == h["id"]][0]
    assert updated["last_seen"] == "2026-01-01"

def test_remove_host():
    h = hc.add_host("DEL", "10.0.0.3", 5555, "tok")
    hc.remove_host(h["id"])
    assert all(x["id"] != h["id"] for x in hc.load_hosts())

def teardown_function():
    if hc.HOSTS_FILE.exists():
        hc.HOSTS_FILE.unlink()
