from __future__ import annotations
import os
from fastapi import FastAPI, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional
from .db import init_db, get_db
from .models import SaveResponse, SearchResponse
from .storage import save_text, save_json, save_csv_bytes, search_matches
import json
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


app = FastAPI(title="AutoDB", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

@app.post("/save", response_model=SaveResponse)
async def save(
    db: Session = Depends(get_db),
    file: Optional[UploadFile] = File(default=None),
    text: Optional[str] = Form(default=None),
    json_payload: Optional[str] = Form(default=None),
    filename: Optional[str] = Form(default=None),
):
    """
    Flexible ingestion endpoint:
    - Multipart file upload (CSV, JSON, TXT)
    - Or form text
    - Or form json_payload (stringified JSON)
    """
    if file:
        content = await file.read()
        fname = filename or file.filename
        if fname.lower().endswith(".csv"):
            doc_id, chunks = save_csv_bytes(db, content, fname)
            return SaveResponse(message="CSV stored", doc_id=doc_id, chunks=chunks)
        elif fname.lower().endswith(".json"):
            try:
                data = json.loads(content.decode("utf-8"))
            except Exception:
                return SaveResponse(message="Invalid JSON file", doc_id="", chunks=0)
            doc_id, chunks = save_json(db, data, fname)
            return SaveResponse(message="JSON stored", doc_id=doc_id, chunks=chunks)
        else:
            # treat as plain text
            doc_id, chunks = save_text(db, content.decode("utf-8", errors="ignore"), fname, None)
            return SaveResponse(message="Text stored", doc_id=doc_id, chunks=chunks)

    if json_payload:
        try:
            data = json.loads(json_payload)
        except Exception:
            return SaveResponse(message="Invalid JSON payload", doc_id="", chunks=0)
        doc_id, chunks = save_json(db, data, filename)
        return SaveResponse(message="JSON stored", doc_id=doc_id, chunks=chunks)

    if text:
        doc_id, chunks = save_text(db, text, filename, None)
        return SaveResponse(message="Text stored", doc_id=doc_id, chunks=chunks)

    return SaveResponse(message="No input provided", doc_id="", chunks=0)




@app.get("/search", response_model=SearchResponse)
async def search(q: str, db: Session = Depends(get_db)):
    # 1. Retrieve top-k matches from Chroma
    matches, sources = search_matches(q)  # Already returns list of dicts

    if not matches:
        return {"answer": "I couldn’t find anything relevant.", "matches": []}

    # 2. Build context for LLM
    context = "\n\n".join(
        f"Source: {m['source']}\n{m['text']}" for m in matches
    )

    prompt = f"""
    You are AutoDB, an assistant that answers questions based on stored data.

    User question: {q}

    Here are the most relevant pieces of stored data:
    {context}

    Instructions:
    - If any of the retrieved data is relevant, use it to answer the question directly and concisely.
    - If multiple chunks are returned, prefer the ones that explicitly mention the topic in the question.
    - Do not refuse to answer if relevant data exists in the context.
    - Only say: "I don’t know based on current data." if none of the chunks mention the topic at all.
    """

    # 3. Ask OpenAI
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": prompt}],
        temperature=0.2,
    )

    return {
        "answer": response.choices[0].message.content,
        "sources": sources,
        "matches": matches,
    }
