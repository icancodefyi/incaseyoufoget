from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
from models import LogItem
from uuid import uuid4
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Load embedding model once
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# Qdrant collection name
QDRANT_COLLECTION = "incaseyouforget_logs"

# Connect to Qdrant Cloud
qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

# Create collection if it doesn't exist
if QDRANT_COLLECTION not in [col.name for col in qdrant.get_collections().collections]:
    qdrant.recreate_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )
    print("✅ Qdrant collection recreated.")

# FastAPI app
app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Embedding fallback logic
def get_best_embedding(item: LogItem) -> list[float]:
    if item.text:
        return embedding_model.encode(item.text).tolist()
    elif item.title:
        return embedding_model.encode(item.title).tolist()
    elif item.url:
        return embedding_model.encode(item.url).tolist()
    return embedding_model.encode("generic memory event").tolist()

# Log endpoint
@app.post("/log")
def log_data(item: LogItem):
    try:
        vector = get_best_embedding(item)

        qdrant.upsert(
            collection_name=QDRANT_COLLECTION,
            points=[
                PointStruct(
                    id=str(uuid4()),
                    vector=vector,
                    payload=item.dict(),
                )
            ],
        )

        return {"message": "Log stored successfully."}

    except Exception as e:
        logging.exception("Error while processing log:")
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/search")
def search_logs(query: str = Query(..., description="Your search text"), limit: int = 5):
    try:
        vector = embedding_model.encode(query).tolist()
        results = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=vector,
            limit=limit,
        )

        return [
            {
                "score": r.score,
                "payload": r.payload
            }
            for r in results
        ]

    except Exception as e:
        logging.exception("Error during search:")
        raise HTTPException(status_code=500, detail=str(e))
