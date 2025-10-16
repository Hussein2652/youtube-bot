from datetime import datetime


def _ts() -> str:
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


def log(msg: str) -> None:
    print(f"[{_ts()}] INFO  {msg}")


def warn(msg: str) -> None:
    print(f"[{_ts()}] WARN  {msg}")


def err(msg: str) -> None:
    print(f"[{_ts()}] ERROR {msg}")

