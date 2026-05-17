from unittest.mock import patch, MagicMock
import pytest
from core.agent_client import AgentClient


@pytest.fixture
def client():
    return AgentClient("192.168.1.1", 5555, "testtoken")


def test_ping_success(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "ok", "hostname": "PC01"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp) as m:
        result = client.ping()
        m.assert_called_once_with(
            "https://192.168.1.1:5555/ping",
            headers={"X-Api-Token": "testtoken", "Content-Type": "application/json"},
            verify=False,
            timeout=10,
        )
    assert result["hostname"] == "PC01"


def test_scan_yara_posts_correct_body(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"matches": []}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp) as m:
        result = client.scan_yara({"rule1": "rule rule1 { condition: false }"}, "C:\\Users")
        _, kwargs = m.call_args
        assert kwargs["json"]["path"] == "C:\\Users"
        assert "rule1" in kwargs["json"]["rules"]
    assert result["matches"] == []


def test_unauthorized_raises(client):
    import requests
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("403")

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(requests.HTTPError):
            client.ping()


def test_hunt_posts_correct_body(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "mutex_found": True,
        "mutex_name": "Global\\TestMutex",
        "hash_matches": [],
        "process_matches": [],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp) as m:
        result = client.hunt({"mutex": "Global\\TestMutex"})
        _, kwargs = m.call_args
        assert kwargs["json"]["mutex"] == "Global\\TestMutex"
    assert result["mutex_found"] is True
    assert result["mutex_name"] == "Global\\TestMutex"


def test_scan_memory_all_returns_matches(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "matches": [{"rule": "Mimikatz_Generic", "file": "C:\\lsass.exe",
                     "pid": 800, "process_name": "lsass.exe"}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp):
        result = client.scan_memory_all({"Mimikatz": "rule Mimikatz_Generic { condition: false }"})
    assert result["matches"][0]["rule"] == "Mimikatz_Generic"
    assert result["matches"][0]["pid"] == 800
