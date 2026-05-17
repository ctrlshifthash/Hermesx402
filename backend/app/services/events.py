"""In-process pub/sub hub for live run streaming over WebSockets.

A run worker publishes timeline events; WebSocket connections subscribed to a
run id receive them. A bounded ring buffer per run lets a client that connects
mid-run replay recent events (so the live timeline isn't empty on reconnect).

For multi-process deployments this hub is swapped for Redis pub/sub — the
publish/subscribe surface is identical (documented in README "Path to real").
"""
from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import Any

_MAX_REPLAY = 200


class EventHub:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._history: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=_MAX_REPLAY)
        )
        self._lock = asyncio.Lock()

    async def publish(self, run_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            self._history[run_id].append(event)
            queues = list(self._subs.get(run_id, ()))
        for q in queues:
            # Drop on slow consumers rather than block the worker.
            if not q.full():
                q.put_nowait(event)

    async def subscribe(self, run_id: str) -> tuple[asyncio.Queue, list[dict]]:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        async with self._lock:
            self._subs[run_id].add(q)
            replay = list(self._history.get(run_id, ()))
        return q, replay

    async def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            self._subs.get(run_id, set()).discard(q)


hub = EventHub()
