from unittest.mock import MagicMock, patch

FAKE_HOST = {"id": "1", "ip": "127.0.0.1", "port": 5555, "token": "tok",
             "name": "TestHost", "last_seen": None, "last_scan": None}


def test_remote_process_list_worker_emits_processes():
    from workers.host_worker import RemoteProcessListWorker
    worker = RemoteProcessListWorker(FAKE_HOST)
    received = []
    worker.done.connect(lambda procs: received.extend(procs))

    fake_client = MagicMock()
    fake_client.list_processes.return_value = {
        "processes": [{"pid": 1, "name": "test.exe", "exe": "C:\\test.exe"}]
    }
    with patch("workers.host_worker.AgentClient", return_value=fake_client):
        worker.run()

    assert len(received) == 1
    assert received[0]["name"] == "test.exe"


def test_remote_mem_scan_worker_emits_results():
    from workers.host_worker import RemoteMemScanWorker
    rules = {"Mimikatz": "rule Mimikatz_Generic { condition: false }"}
    worker = RemoteMemScanWorker(FAKE_HOST, rules)
    results = []
    worker.done.connect(lambda r: results.extend(r))

    fake_client = MagicMock()
    fake_client.scan_memory_all.return_value = {
        "matches": [{"rule": "Mimikatz_Generic", "file": "C:\\lsass.exe",
                     "pid": 800, "process_name": "lsass.exe"}]
    }
    with patch("workers.host_worker.AgentClient", return_value=fake_client):
        worker.run()

    assert len(results) == 1
    assert results[0]["type"] == "MEMORY"
    assert results[0]["rule"] == "Mimikatz_Generic"
    assert results[0]["process_name"] == "lsass.exe"
