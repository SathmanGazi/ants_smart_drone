from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.events import broker
from app.services.job_manager import job_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/jobs/{job_id}")
async def job_socket(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()

    job = await job_manager.get(job_id)
    if job is None:
        await websocket.send_json({"type": "error", "error": "job not found"})
        await websocket.close()
        return

    # Immediately send current snapshot so late subscribers don't miss state.
    await websocket.send_json(
        {
            "type": "snapshot",
            "status": job.status.value,
            "progress": job.progress.model_dump(),
            "error": job.error,
        }
    )

    queue = await broker.subscribe(job_id)
    try:
        while True:
            # Race: either a new event arrives, or the client disconnects.
            recv_task = asyncio.create_task(websocket.receive_text())
            event_task = asyncio.create_task(queue.get())
            done, pending = await asyncio.wait(
                {recv_task, event_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()

            if recv_task in done:
                try:
                    recv_task.result()
                except WebSocketDisconnect:
                    break
                except Exception:
                    break
                # We accept pings but ignore content.
                continue

            payload = event_task.result()
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WS error for job %s", job_id)
    finally:
        await broker.unsubscribe(job_id, queue)
        try:
            await websocket.close()
        except Exception:
            pass
