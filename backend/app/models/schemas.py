from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    question: str
    chat_history: Optional[List[Message]] = []

class GraphDataResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    links: List[Dict[str, Any]]