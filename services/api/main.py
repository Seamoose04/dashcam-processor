from fastapi import FastAPI
from database import db

app = FastAPI(
    title="Dashcam Final Data API",
    version="0.1.0"
)

@app.get("/")
def root():
    return {
        "status": "ok",
        "time": str(db.test())
    }
