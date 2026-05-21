from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from time import perf_counter


class FPSCounter:
    """Small rolling FPS helper for live video overlays."""

    def __init__(self, window_size: int = 30) -> None:
        self._times: deque[float] = deque(maxlen=window_size)
        self._last_time = perf_counter()

    def update(self) -> float:
        now = perf_counter()
        delta = now - self._last_time
        self._last_time = now

        if delta > 0:
            self._times.append(1.0 / delta)

        if not self._times:
            return 0.0

        return sum(self._times) / len(self._times)


@dataclass
class StableCounter:
    """Returns the most common value in a short rolling window."""

    window_size: int = 7
    _values: deque[int] = field(init=False)

    def __post_init__(self) -> None:
        self._values = deque(maxlen=self.window_size)

    def update(self, value: int) -> int:
        self._values.append(value)
        counts = Counter(self._values)
        return counts.most_common(1)[0][0]

    def clear(self) -> None:
        self._values.clear()
