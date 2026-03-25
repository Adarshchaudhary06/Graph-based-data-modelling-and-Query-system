from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    question: str
    chat_history: Optional[List[Message]] = Field(default_factory=list)

class GraphDataResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    links: List[Dict[str, Any]]