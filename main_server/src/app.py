from fastapi import FastAPI

from src.api.routes import router as api_router

app = FastAPI(title="Dashcam Main Server", version="0.1.0")
app.include_router(api_router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}
