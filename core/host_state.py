# Global singleton: which host is currently active in the UI.
# None = local machine. Tabs read this when starting any scan operation.

_current: dict | None = None


def get_current_host() -> dict | None:
    return _current


def set_current_host(host: dict | None) -> None:
    global _current
    _current = host


def is_local() -> bool:
    return _current is None
