from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from models import LogItem
from database import collection

app = FastAPI()

# Allow Chrome Extension to POST to API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev, restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/log")
async def log_data(item: LogItem):
    await collection.insert_one(item.dict())
    return {"message": "Logged successfully"}
