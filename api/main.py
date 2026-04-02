from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from api.routes import query as query_router
from api.routes import report as report_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("OSINTForge API starting up")
    yield
    logger.info("OSINTForge API shutting down")


app = FastAPI(
    title       = "OSINTForge API",
    description = "Multi-agent LLM swarm for OSINT synthesis",
    version     = "1.0.0",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(query_router.router)
app.include_router(report_router.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "OSINTForge"}
