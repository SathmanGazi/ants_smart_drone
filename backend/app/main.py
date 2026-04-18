from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import jobs, websocket
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="Smart Drone Traffic Analyzer",
    version="0.1.0",
    description="Upload drone footage, detect and track vehicles, export reports.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(websocket.router)


@app.get("/health", tags=["meta"])
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/", tags=["meta"])
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "name": "Smart Drone Traffic Analyzer",
            "docs": "/docs",
            "endpoints": {
                "create_job": "POST /jobs",
                "get_job": "GET /jobs/{job_id}",
                "get_result": "GET /jobs/{job_id}/result",
                "video": "GET /jobs/{job_id}/video",
                "csv": "GET /jobs/{job_id}/report.csv",
                "xlsx": "GET /jobs/{job_id}/report.xlsx",
                "socket": "WS /ws/jobs/{job_id}",
            },
        }
    )
