from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from sentence_transformers import SentenceTransformer
from models import LogItem
from pydantic import BaseModel
from uuid import uuid4
import logging
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime
import google.generativeai as genai

# Load .env variables
load_dotenv()

# ========== MongoDB Setup ==========
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client["incaseyouforget"]
waitlist_collection = mongo_db["waitlist"]

# ========== Qdrant Setup ==========
QDRANT_COLLECTION = "incaseyouforget_logs"
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

if QDRANT_COLLECTION not in [col.name for col in qdrant.get_collections().collections]:
    qdrant.recreate_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )
    print("✅ Qdrant collection recreated.")

# ========== Gemini Setup ==========
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# ========== FastAPI App Setup ==========
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== Pydantic Models ==========
class ChatRequest(BaseModel):
    query: str

class WaitlistEntry(BaseModel):
    fullName: str
    email: str
    company: str | None = None

# ========== Embedding Utility ==========
def get_best_embedding(item: LogItem) -> list[float]:
    if item.text:
        return embedding_model.encode(item.text).tolist()
    elif item.title:
        return embedding_model.encode(item.title).tolist()
    elif item.url:
        return embedding_model.encode(item.url).tolist()
    return embedding_model.encode("generic memory event").tolist()

# ========== Endpoints ==========

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


@app.post("/chat")
def chat_with_ai(request: ChatRequest):
    try:
        vector = embedding_model.encode(request.query).tolist()
        results = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=vector,
            limit=5,
        )

        if not results:
            return {
                "response": "I don't have any relevant memories about that. Try browsing some websites or copying some text first, and then ask me again!",
                "found_memories": 0
            }

        context_items = []
        for r in results:
            payload = r.payload
            score = r.score

            if payload.get('type') == 'url_visit':
                context_items.append(f"Visited: '{payload.get('title', 'Unknown')}' at {payload.get('url', '')} (score: {score:.2f})")
            elif payload.get('type') == 'copy_event':
                snippet = payload.get('text', '')[:100]
                context_items.append(f"Copied: '{snippet}' from {payload.get('url', '')} (score: {score:.2f})")
            else:
                context_items.append(f"Memory: {payload} (score: {score:.2f})")

        prompt = f"""
You are a personal assistant that helps the user reflect on their digital memory log.

User's question: "{request.query}"

Relevant memory entries:
{chr(10).join(f"- {item}" for item in context_items)}

Instructions:
- Only use the information above.
- If nothing is relevant, respond with: 
  "I don’t have any relevant information about that right now."
- Format your reply with clear headings, bullet points, or numbered steps when possible.
- Always sound thoughtful and helpful. Avoid hallucinating facts or assuming context beyond the data.

Now provide a structured and helpful response to the user.
"""

        gemini_response = model.generate_content(prompt)
        reply = gemini_response.text

        return {
            "response": reply,
            "found_memories": len(results),
            "query": request.query
        }

    except Exception as e:
        logging.exception("Error during Gemini chat:")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/waitlist")
def join_waitlist(entry: WaitlistEntry):
    try:
        existing = waitlist_collection.find_one({"email": entry.email})
        if existing:
            raise HTTPException(status_code=409, detail="This email is already on the waitlist.")

        waitlist_collection.insert_one({
            "fullName": entry.fullName,
            "email": entry.email,
            "company": entry.company,
            "joinedAt": datetime.utcnow()
        })

        return {"message": "Successfully joined the waitlist!"}

    except Exception as e:
        logging.exception("Error during waitlist signup:")
        raise HTTPException(status_code=500, detail="Internal server error")
