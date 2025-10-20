from typing import Dict, Iterable


class HookProvider:
    def list(self) -> Iterable[Dict]:
        raise NotImplementedError
