from unittest.mock import patch, MagicMock
import pytest
from workers.host_worker import RemoteInfoWorker


INFO_PAYLOAD = {
    "cpu_percent": 42.5,
    "ram_total":   8 * 1024**3,
    "ram_used":    4 * 1024**3,
    "ram_percent": 50.0,
    "disk_total":  100 * 1024**3,
    "disk_used":   60 * 1024**3,
    "disk_percent": 60.0,
    "boot_time":   1_700_000_000.0,
    "os":          "Windows-10-10.0.19041",
    "users":       ["DOMAIN\\alice"],
}


def test_remote_info_worker_emits_done(qtbot):
    host = {"ip": "192.168.1.1", "port": 5555, "token": "tok"}
    worker = RemoteInfoWorker(host)

    received = []
    worker.done.connect(received.append)

    mock_resp = MagicMock()
    mock_resp.json.return_value = INFO_PAYLOAD
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        with qtbot.waitSignal(worker.done, timeout=3000):
            worker.start()

    assert len(received) == 1
    assert received[0]["cpu_percent"] == 42.5
    assert received[0]["os"] == "Windows-10-10.0.19041"


def test_remote_info_worker_emits_error_on_failure(qtbot):
    host = {"ip": "192.168.1.1", "port": 5555, "token": "tok"}
    worker = RemoteInfoWorker(host)

    errors = []
    worker.error.connect(errors.append)

    import requests as req
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = req.HTTPError("403")

    with patch("requests.get", return_value=mock_resp):
        with qtbot.waitSignal(worker.error, timeout=3000):
            worker.start()

    assert len(errors) == 1
