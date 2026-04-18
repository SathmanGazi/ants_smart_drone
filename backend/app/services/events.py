from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Dict, Set


class EventBroker:
    """
    Minimal in-process pub/sub. Each job_id gets a topic; WebSocket
    connections subscribe to the topic and receive JSON-serialisable
    payloads pushed from the processor.

    Swap this for Redis Pub/Sub when moving to multi-process workers —
    the interface (publish / subscribe / unsubscribe) stays the same.
    """

    def __init__(self) -> None:
        self._subs: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, topic: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subs[topic].add(q)
        return q

    async def unsubscribe(self, topic: str, q: asyncio.Queue) -> None:
        async with self._lock:
            if topic in self._subs:
                self._subs[topic].discard(q)
                if not self._subs[topic]:
                    self._subs.pop(topic, None)

    async def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        # Snapshot subscribers so we don't hold the lock while enqueuing.
        async with self._lock:
            targets = list(self._subs.get(topic, ()))
        for q in targets:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                # Slow consumer — drop oldest and retry once.
                try:
                    q.get_nowait()
                    q.put_nowait(payload)
                except Exception:
                    pass


broker = EventBroker()
