from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.database import init_db
from app.api.routes import auth, recordings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Audio Recorder API",
    description="API for recording, storing, and playing audio files",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(auth.router)
app.include_router(recordings.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
