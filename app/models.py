from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, Any, List

class SaveResponse(BaseModel):
    message: str
    doc_id: str
    chunks: int

class SearchResponse(BaseModel):
    answer: str
    sources: List[str] = Field(default_factory=list)
    matches: List[Dict[str, Any]] = Field(default_factory=list)
