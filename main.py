import uvicorn
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from connections import Connections
from routers import router
from agency import Agency
from agents import PlayerPredictionAgent, GamePredictionAgent, TwitterAgent, RogueAgent
from logger import logger

app = FastAPI(
    title="Pluto AI",
    description="Pluto AI - Sports Analytics and Prediction API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


app.include_router(router)


@app.on_event("startup")
async def startup():
    logger.info(f"Starting Pluto AI API")
    await Connections.create_connections()
    agency = Agency(
        [PlayerPredictionAgent(), GamePredictionAgent(), TwitterAgent(), RogueAgent()]
    )
    await agency.agents["PlayerPredictionAgent"].execute_task()
    await agency.agents["GamePredictionAgent"].execute_task()
    await agency.agents["PlutoPredictsTwitterAgent"].execute_task()
    await agency.agents["RogueAgent"].execute_task()
    logger.info(f"Agency initialized successfully and running, {agency}")


@app.on_event("shutdown")
async def shutdown():
    """Perform cleanup operations on shutdown"""
    logger.info("Shutting down Pluto AI API")
    await Connections.close_connections()
    logger.info("Connections closed successfully")
