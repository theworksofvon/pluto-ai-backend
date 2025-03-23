import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from connections import Connections
from routers import router
from agency import Agency
from agents import TwitterAgent, PredictionAgent
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

app.include_router(router)


@app.on_event("startup")
async def startup():
    await Connections.create_connections()
    agency = Agency([PredictionAgent(), TwitterAgent()])
    logger.info(f"Agency initialized successfully and running, {agency}")
    # await agency.run()


@app.on_event("shutdown")
async def shutdown():
    """Perform cleanup operations on shutdown"""
    logger.info("Shutting down Pluto AI API")
    await Connections.close_connections()
    logger.info("Connections closed successfully")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
