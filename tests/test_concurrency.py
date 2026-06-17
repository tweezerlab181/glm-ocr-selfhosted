import asyncio

import pytest

from app.concurrency import ConcurrencyGate, QueueFull


@pytest.mark.asyncio
async def test_single_slot_runs():
    gate = ConcurrencyGate(max_concurrency=1, queue_max=1)
    async with gate.slot():
        pass  # no exception


@pytest.mark.asyncio
async def test_rejects_when_capacity_exceeded():
    gate = ConcurrencyGate(max_concurrency=1, queue_max=1)  # capacity == 2
    release = asyncio.Event()
    entered = asyncio.Semaphore(0)

    async def worker():
        async with gate.slot():
            entered.release()
            await release.wait()

    t1 = asyncio.create_task(worker())   # occupancy 1, in-flight
    await entered.acquire()
    t2 = asyncio.create_task(worker())   # occupancy 2, queued on semaphore
    await asyncio.sleep(0.05)

    with pytest.raises(QueueFull):       # capacity full -> reject
        async with gate.slot():
            pass

    release.set()
    await asyncio.gather(t1, t2)
