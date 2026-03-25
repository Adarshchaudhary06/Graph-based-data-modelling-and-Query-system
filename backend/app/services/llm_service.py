import re
import json
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.config import GROQ_API_KEY
from app.services.neo4j_service import neo4j_db

# Initialize Groq Models
router_llm = ChatGroq(api_key=GROQ_API_KEY, model_name="llama-3.1-8b-instant", temperature=0)
coder_llm = ChatGroq(api_key=GROQ_API_KEY, model_name="llama-3.3-70b-versatile", temperature=0)

# --- STATIC SCHEMA INJECTION (Micro & Macro Levels) ---
STATIC_SCHEMA = """
Node Labels:
- Customer {businessPartner: STRING, fullName: STRING}
- SalesOrder {salesOrder: STRING, totalNetAmount: FLOAT} (Labels: :PendingDelivery, :PartiallyDelivered, :FullyDelivered)
- SalesOrderItem {salesOrderItemId: STRING}
- OutboundDelivery {deliveryDocument: STRING} (Labels: :GoodsMovementPending, :GoodsMovementComplete)
- OutboundDeliveryItem {deliveryItemId: STRING}
- BillingDocument {billingDocument: STRING, totalNetAmount: FLOAT} (Labels: :ActiveBilling, :CancelledBilling)
- BillingDocumentItem {billingItemId: STRING}
- JournalEntry {accountingDocumentId: STRING, amountInTransactionCurrency: FLOAT}
- Payment {paymentId: STRING, amountInTransactionCurrency: FLOAT}
- Product {product: STRING, productDescription: STRING}
- Plant {plant: STRING, plantName: STRING}
- StorageLocation {storageLocationId: STRING, plant: STRING}

Relationships (Tracing):
(Customer)-[:PLACED]->(SalesOrder)
(SalesOrder)-[:HAS_ITEM]->(SalesOrderItem)
(SalesOrderItem)-[:REFERENCES]->(Product)
(SalesOrderItem)-[:PRODUCED_AT]->(Plant)
(OutboundDelivery)-[:HAS_DELIVERY_ITEM]->(OutboundDeliveryItem)
(OutboundDeliveryItem)-[:FULFILLS]->(SalesOrderItem)
(OutboundDeliveryItem)-[:SHIPPED_FROM]->(Plant)
(OutboundDeliveryItem)-[:STORED_AT]->(StorageLocation)
(BillingDocument)-[:HAS_BILLING_ITEM]->(BillingDocumentItem)
(BillingDocumentItem)-[:BILLS_MATERIAL]->(Product)
(BillingDocumentItem)-[:REFERENCES_DELIVERY]->(OutboundDelivery)
(BillingDocument)-[:GENERATES]->(JournalEntry)
(JournalEntry)-[:CLEARED_BY]->(Payment)
(Product)-[:STOCKED_AT]->(Plant)

Macro Shortcuts:
(SalesOrder)-[:DELIVERED_VIA]->(OutboundDelivery)
(OutboundDelivery)-[:BILLED_AS]->(BillingDocument)
"""

# --- PROMPTS ---
GUARDRAIL_PROMPT = """You are a strict routing assistant for an SAP Order-to-Cash Graph system.
Classify if the user's question relates to the domain (Customers, Orders, Deliveries, Billing, Payments, Products, Plants, Supply Chain, Logistics).
If the question is even remotely related to these business topics, reply ONLY with "RELEVANT". 
If it is completely unrelated (e.g. poetry, coding help, general history), reply ONLY with "IRRELEVANT"."""

CYPHER_PROMPT = """You are a Neo4j Cypher expert. Convert the user's question to a Cypher query.
Schema:
{schema}

CRITICAL RULES:
1. Always RETURN the actual nodes (e.g., `RETURN so, d, p`), not just properties, so the UI can highlight them.
2. If the user asks for a document trace but DOES NOT provide an ID, DO NOT use a placeholder like 'X'. Instead, write a query to return 5 example nodes so the user can pick one.
   Example: `MATCH (b:BillingDocument) RETURN b LIMIT 5`
3. Respond with ONLY valid Cypher code within a ```cypher code block. No explanations.

EXAMPLES:
- "Trace billing doc 90504255": 
  MATCH (b:BillingDocument {{billingDocument: '90504255'}}) OPTIONAL MATCH (so:SalesOrder)-[:DELIVERED_VIA]->(d:OutboundDelivery)-[:BILLED_AS]->(b) RETURN so, d, b
- "Trace sales order 740506":
  MATCH (so:SalesOrder {{salesOrder: '740506'}}) OPTIONAL MATCH (so)-[:DELIVERED_VIA]->(d:OutboundDelivery) OPTIONAL MATCH (d)-[:BILLED_AS]->(b:BillingDocument) RETURN so, d, b
- "Products at Plant 1010":
  MATCH (p:Product)-[:STOCKED_AT]->(pl:Plant {{plant: '1010'}}) RETURN p, pl
- "Orders delivered but not billed":
  MATCH (so:SalesOrder)-[:DELIVERED_VIA]->(d:OutboundDelivery) WHERE NOT (d)-[:BILLED_AS]->(:BillingDocument) RETURN so, d LIMIT 5"""

ANSWER_PROMPT = """You are an AI assistant for a Supply Chain Graph Database.
Answer the user's question using the provided database context.
If nodes were found but they have no specific properties, say "I found X matching nodes in the database. You can see them highlighted in the graph."
Otherwise, summarize the results clearly.
If the context is completely empty, say "No data was found matching your query."

Database Context:
{context}
"""

def extract_cypher(text: str) -> str:
    # Look for any block of code, even if not tagged 'cypher'
    match = re.search(r'```(?:cypher)?\s+(.*?)\s+```', text, re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    # Fallback to lines that look like Cypher
    lines = [l.strip() for l in text.split('\n') if l.strip() and not l.startswith('--') and not l.startswith('//')]
    return " ".join(lines).strip()

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
    max_retries = 2
    
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

    # Ensure db_result is initialized even if all retries failed and didn't return early
    # This handles a theoretical edge case where the loop finishes without db_result being set
    # (though the 'return' in the else block should prevent this if retries fail).
    if db_result is None:
        db_result = {"context": [], "highlight_nodes": []}

    # 4. Handle Empty Results & Suggest IDs
    # If BOTH context and highlight_nodes are empty, then we say no data found
    if not db_result["context"] and not db_result["highlight_nodes"]:
        suggestion = ""
        # Heuristic: If prompt mentioned Billing/Order but returned nothing, suggest real IDs
        query_str = str(raw_cypher)
        # Check for the primary entry point in the query to provide better suggestions
        if "SalesOrder" in query_str and "740506" in query_str or "salesOrder" in query_str.lower():
            ids = neo4j_db.get_sample_ids("SalesOrder", "salesOrder")
            if ids: suggestion = f" I couldn't find that Sales Order. Try one of these valid IDs: {', '.join(ids)}."
        elif "BillingDocument" in query_str:
            ids = neo4j_db.get_sample_ids("BillingDocument", "billingDocument")
            if ids: suggestion = f" I couldn't find that document. Try one of these valid IDs: {', '.join(ids)}."
        elif "Plant" in query_str:
            ids = neo4j_db.get_sample_ids("Plant", "plant")
            if ids: suggestion = f" I couldn't find that Plant. Try one of these valid IDs: {', '.join(ids)}."
        elif "Product" in query_str:
            ids = neo4j_db.get_sample_ids("Product", "product")
            if ids: suggestion = f" I couldn't find that Product. Try one of these valid IDs: {', '.join(ids)}."

        yield f"data: {json.dumps({'type': 'metadata', 'cypher': raw_cypher, 'highlight_nodes': []})}\n\n"
        yield f"data: {json.dumps({'type': 'token', 'content': f'No data found matching your query.{suggestion}'})}\n\n"
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
    final_context = db_result["context"]
    # Check if context is a truthy but data-empty list: [{}, {}]
    is_empty_list = isinstance(final_context, list) and all(not d for d in final_context if isinstance(d, dict))

    if (not final_context or is_empty_list) and db_result.get("highlight_nodes"):
        final_context = f"SUCCESS: Found {len(db_result['highlight_nodes'])} matching nodes in the database. Their IDs are visible in the graph highlighting."

    answer_messages =[
        SystemMessage(content=ANSWER_PROMPT.format(context=json.dumps(final_context, default=str))),
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