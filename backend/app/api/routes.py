from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest, GraphDataResponse
from app.services.llm_service import process_chat_stream
from app.services.neo4j_service import neo4j_db

router = APIRouter()

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """Processes questions and streams the response via Server-Sent Events (SSE)."""
    try:
        return StreamingResponse(
            process_chat_stream(request.question, request.chat_history),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/graph-data", response_model=GraphDataResponse)
async def get_graph_data():
    """Fetches a sample of nodes and edges for the React visualization."""
    try:
        # Limit to 300 to prevent browser canvas lag
        data = neo4j_db.get_graph_sample(limit=300)
        return GraphDataResponse(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))