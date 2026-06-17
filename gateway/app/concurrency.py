import asyncio
from contextlib import asynccontextmanager


class QueueFull(Exception):
    pass


class ConcurrencyGate:
    def __init__(self, max_concurrency: int, queue_max: int):
        self.capacity = max_concurrency + queue_max
        self._occupancy = 0
        self._sem = asyncio.Semaphore(max_concurrency)

    @asynccontextmanager
    async def slot(self):
        # Single-threaded asyncio: this check+increment has no await between,
        # so occupancy accounting is race-free.
        if self._occupancy >= self.capacity:
            raise QueueFull("OCR queue is full")
        self._occupancy += 1
        try:
            async with self._sem:
                yield
        finally:
            self._occupancy -= 1
