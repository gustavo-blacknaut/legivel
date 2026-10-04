import time
from collections import defaultdict, deque


class LoginThrottle:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self._max_attempts = max_attempts
        self._window = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def is_blocked(self, key: str) -> bool:
        failures = self._failures[key]
        cutoff = time.monotonic() - self._window
        while failures and failures[0] < cutoff:
            failures.popleft()
        return len(failures) >= self._max_attempts

    def record_failure(self, key: str) -> None:
        self._failures[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
