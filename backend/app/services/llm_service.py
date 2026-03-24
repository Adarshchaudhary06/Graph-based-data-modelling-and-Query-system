import re
import json
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.config import GROQ_API_KEY
from app.services.neo4j_service import neo4j_db

# Initialize Groq Models
router_llm = ChatGroq(api_key=GROQ_API_KEY, model_name="llama-3.1-8b-instant", temperature=0)
coder_llm = ChatGroq(api_key=GROQ_API_KEY, model_name="llama-3.3-70b-versatile", temperature=0)

# --- STATIC SCHEMA INJECTION (Saves 500ms+ latency compared to dynamic fetching) ---
STATIC_SCHEMA = """
Node Labels and Primary Keys:
- Customer {businessPartner: STRING}
- SalesOrder {salesOrder: STRING, totalNetAmount: FLOAT, overallDeliveryStatus: STRING}
  Secondary Labels: :PendingDelivery, :PartiallyDelivered, :FullyDelivered
- OutboundDelivery {deliveryDocument: STRING, overallGoodsMovementStatus: STRING}
  Secondary Labels: :GoodsMovementPending, :GoodsMovementComplete
- BillingDocument {billingDocument: STRING, totalNetAmount: FLOAT, isCancelled: BOOLEAN}
  Secondary Labels: :ActiveBilling, :CancelledBilling
- JournalEntry {accountingDocumentId: STRING}
- Payment {paymentId: STRING}
- Product {product: STRING, productDescription: STRING}

Relationships (Shortcut Flows):
(Customer)-[:PLACED]->(SalesOrder)
(SalesOrder)-[:DELIVERED_VIA]->(OutboundDelivery)
(OutboundDelivery)-[:BILLED_AS]->(BillingDocument)
(BillingDocument)-[:GENERATES]->(JournalEntry)
(JournalEntry)-[:CLEARED_BY]->(Payment)
"""

# --- PROMPTS ---
GUARDRAIL_PROMPT = """You are a strict routing assistant for an SAP Order-to-Cash Graph system.
Classify if the user's question relates to the domain (Customers, Orders, Deliveries, Billing, Payments, Products, Supply Chain).
If related, reply ONLY with "RELEVANT". If unrelated or general knowledge, reply ONLY with "IRRELEVANT"."""

CYPHER_PROMPT = """You are a Neo4j Cypher expert. Convert the user's question to a Cypher query.
Schema:
{schema}

CRITICAL RULES:
1. Prefer shortcut edges: (SalesOrder)-[:DELIVERED_VIA]->(OutboundDelivery)-[:BILLED_AS]->(BillingDocument)
2. Use secondary labels: Match (s:FullyDelivered), (b:ActiveBilling).
3. ALWAYS RETURN THE NODES (e.g., `RETURN so, d, b`), not just properties, so the UI can extract IDs.
4. Respond with ONLY valid Cypher code. No markdown formatting, no explanations."""

ANSWER_PROMPT = """You are an AI assistant for a Supply Chain Graph Database.
Answer the user's question using ONLY the provided database context.
If the context is empty, say "No data was found matching your query."
Keep the answer clear, professional, and highlight key numbers.

Database Context:
{context}
"""

def extract_cypher(text: str) -> str:
    match = re.search(r'```cypher\n(.*?)\n```', text, re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    return text.replace('```cypher', '').replace('```', '').strip()

async def process_chat_stream(question: str, history: list):
    """Async Generator yielding SSE for streaming."""
    
    # 1. Guardrail Check (Llama-3-8b)
    routing_msg = f"{GUARDRAIL_PROMPT}\n\nUser Question: {question}"
    try:
        routing_decision = await router_llm.ainvoke(routing_msg)
        if "IRRELEVANT" in routing_decision.content.upper():
            yield f"data: {json.dumps({'type': 'token', 'content': 'This system is designed to answer questions related to the provided Order-to-Cash dataset only.'})}\n\n"
            yield "data: {\"type\": \"done\"}\n\n"
            return
    except Exception as e:
         yield f"data: {json.dumps({'type': 'error', 'content': 'Failed to reach routing model.'})}\n\n"
         yield "data: {\"type\": \"done\"}\n\n"
         return

    # 2. Build Memory Context (Max 4 turns)
    messages = [SystemMessage(content=CYPHER_PROMPT.format(schema=STATIC_SCHEMA))]
    for msg in history[-4:]:
        if msg.role == "user": messages.append(HumanMessage(content=msg.content))
        else: messages.append(AIMessage(content=msg.content))
    messages.append(HumanMessage(content=question))

    # 3. Cypher Generation & Self-Healing Retry Loop
    db_result = None
    raw_cypher = ""
    max_retries = 1
    
    for attempt in range(max_retries + 1):
        try:
            cypher_response = await coder_llm.ainvoke(messages)
            raw_cypher = extract_cypher(cypher_response.content)
            
            # Execute Cypher
            db_result = neo4j_db.execute_and_extract_nodes(raw_cypher)
            break  # Success! Exit retry loop
            
        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries:
                # Provide error back to LLM for self-correction
                messages.append(AIMessage(content=raw_cypher))
                messages.append(HumanMessage(content=f"This Cypher query failed with error:\n{error_msg}\nFix the query and return ONLY the corrected Cypher code."))
            else:
                yield f"data: {json.dumps({'type': 'error', 'content': 'Failed to generate a valid graph query after retries.'})}\n\n"
                yield "data: {\"type\": \"done\"}\n\n"
                return

    # 4. Handle Empty Results Gracefully
    if not db_result["context"]:
        yield f"data: {json.dumps({'type': 'metadata', 'cypher': raw_cypher, 'highlight_nodes':[]})}\n\n"
        yield f"data: {json.dumps({'type': 'token', 'content': 'No data was found matching your query.'})}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"
        return

    # 5. Yield Metadata (UI Highlighting Data)
    metadata = {
        "type": "metadata",
        "cypher": raw_cypher,
        "highlight_nodes": db_result["highlight_nodes"]
    }
    yield f"data: {json.dumps(metadata)}\n\n"

    # 6. Stream Final Answer (Llama-3-70b)
    answer_messages =[
        SystemMessage(content=ANSWER_PROMPT.format(context=json.dumps(db_result["context"], default=str))),
        HumanMessage(content=question)
    ]
    
    try:
        async for chunk in coder_llm.astream(answer_messages):
            if chunk.content:
                yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': ' Streaming interrupted due to rate limit or connection issue.'})}\n\n"

    # Signal completion
    yield "data: {\"type\": \"done\"}\n\n"