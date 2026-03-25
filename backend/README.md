
# Backend Architecture & Engineering Document
**Project:** SAP Order-to-Cash (O2C) Graph AI Query System  
**Role:** Forward Deployed Engineer Assignment  

---

## 1. Executive Summary
This document outlines the backend architecture for a Graph-Based Data Modeling and Conversational Query System. The backend acts as the orchestration layer between a React-based frontend visualization, a Neo4j Graph Database containing SAP O2C supply chain data, and high-speed Large Language Models (LLMs) hosted on Groq.

The system natively translates Natural Language to Cypher (NL2Cypher), executes the queries against the graph, extracts referenced business keys for UI node highlighting, and streams data-backed answers back to the user in real-time via Server-Sent Events (SSE).

---

## 2. Technology Stack & Rationale

| Technology | Purpose | Engineering Rationale (The "Why") |
| :--- | :--- | :--- |
| **Python 3.10+** | Core Language | Python is the undisputed industry standard for AI orchestration. It provides native support for LangChain, advanced asynchronous execution, and rapid iteration capabilities compared to statically typed languages like Go or Java. |
| **FastAPI** | API Framework | Chosen for its native `async/await` support, which is critical for I/O bound tasks (waiting on LLMs and Database queries). It easily supports Server-Sent Events (SSE) for streaming and auto-generates OpenAPI documentation. |
| **Neo4j (AuraDB)** | Graph Database | Relational databases require expensive recursive CTEs to trace an O2C flow. Neo4j handles multi-hop semantic traversals (Order → Delivery → Invoice) in O(1) time via pointer chasing. |
| **Groq (Llama-3)** | LLM Provider | Groq's LPU architecture provides ~300 tokens/second inference. This enables near-instantaneous Cypher query generation and makes the token-streaming experience incredibly fluid for the user. |
| **LangChain Core** | AI Orchestration | Used for Prompt Templating and Message state management. *Note: We purposefully bypassed LangChain's rigid `GraphCypherQAChain` in favor of a custom asynchronous pipeline to achieve fine-grained control over business key extraction and SSE streaming.* |
| **Poetry** | Dependency Management | Ensures deterministic builds and standardizes the environment setup, demonstrating modern Python engineering practices over standard `pip/requirements.txt`. |

---

## 3. Architectural Patterns

The backend strictly follows **Domain-Driven Design (DDD)** principles to separate routing, database execution, and AI orchestration.

```text
backend/
├── app/
│   ├── main.py              # Application entry point & CORS configuration
│   ├── config.py            # Environment variable loading (NEO4J_URI, GROQ_API_KEY)
│   ├── api/
│   │   └── routes.py        # HTTP/SSE endpoint definitions
│   ├── models/
│   │   └── schemas.py       # Pydantic models for strict I/O validation
│   └── services/
│       ├── neo4j_service.py # Database connection & query execution
│       └── llm_service.py   # Groq orchestration, prompting, & streaming
```

**Reasoning:** By isolating the Neo4j driver logic from the LLM logic, we make the system highly testable. If we ever want to switch the database (e.g., to Amazon Neptune) or the LLM provider (e.g., to OpenAI), we only need to modify a single isolated service file. `config.py` centralizes all credential loading, ensuring no secrets are scattered across service files.

---

## 4. Core Workflows (The "Brain")

The most complex component of this backend is the `/api/chat` endpoint. It executes a 6-step asynchronous pipeline designed to minimize latency and maximize accuracy.

### 4.1 Dual-Model LLM Orchestration
To optimize for both speed and cost/compute, the backend utilizes two different models simultaneously:
1. **The Router (`llama3-8b`)**: A lightweight, blazing-fast model handles **Semantic Guardrails**. It analyzes the user prompt to ensure it relates to the O2C domain. If the prompt is an injection attack or unrelated (e.g., "Write a poem"), the pipeline short-circuits instantly.
2. **The Coder (`llama3-70b`)**: A massive, highly capable reasoning model handles the complex task of reading the Neo4j schema, understanding conversation history, and writing precise Cypher code.

### 4.2 The Natural Language to Cypher (NL2Cypher) Pipeline
1. **Schema Injection:** The graph schema (node labels, relationship types, key properties) is pre-defined as a constant string in `llm_service.py` and injected directly into the system prompt on every request. This avoids expensive `CALL apoc.meta.schema()` metadata queries against AuraDB, which can time out on cold instances and add 500ms+ of latency.
2. **Contextual Memory (Sliding Window):** The last 4 conversation turns (~2,000 tokens) are appended to the prompt, allowing users to ask follow-up questions (e.g., User: "Trace order 123", LLM: *answers*, User: "Did it have any journal entries?"). The window is capped at 4 turns to stay within Groq's optimal latency range while keeping the total prompt under the model's effective context.
3. **Cypher Generation & Execution:** The LLM generates the Cypher code. The backend intercepts this code and executes it securely against Neo4j.

### 4.3 Node Highlighting & Payload Segregation (Solving the UI Challenge)
To fulfill the requirement of *highlighting nodes referenced in responses*, the backend performs a specific data extraction step:
- When the Cypher query executes, `neo4j_service` inspects every returned record.
- If a record contains a Neo4j Node object, the backend extracts its **stable business key property** (e.g., `salesOrder`, `deliveryDocument`, `billingDocument`) from the node's properties and saves it to a `highlight_nodes` array.
- These business keys are used by the frontend graph library (e.g., neovis.js, react-force-graph) to identify and highlight the correct nodes. Neo4j's internal `element_id` is intentionally avoided — it is an unstable, session-scoped identifier not suitable for cross-session UI state.
- Only the human-readable properties are passed back to the LLM to generate the final English answer.

### 4.4 Server-Sent Events (SSE) Streaming
Instead of a standard REST request where the user waits 5–10 seconds for the entire process to finish, we implemented an `async generator` using FastAPI's `StreamingResponse`.

**The Streaming Payload Sequence:**

```json
// Event 1 — metadata (sent immediately after query execution)
{"type": "metadata", "cypher": "MATCH (so:SalesOrder {salesOrder: '740556'})...", "highlight_nodes": ["740556", "80738076", "90504298"]}

// Events 2..N — LLM tokens streamed as generated
{"type": "token", "content": "Order 740556 was "}
{"type": "token", "content": "delivered via outbound delivery 80738076..."}

// Final event — closes the SSE connection
{"type": "done"}
```

The UI uses the `metadata` event instantly to highlight the relevant graph path, then renders the natural language answer token-by-token as it arrives.

---

## 5. Error Handling & Retry Strategy

Robust error handling is critical for production reliability. The backend implements a multi-layer strategy:

| Failure Scenario | Handling Strategy |
| :--- | :--- |
| **LLM generates invalid Cypher** | Catch the `CypherSyntaxError` from Neo4j, append the error message to the prompt, and retry the Cypher generation call once with the instruction `"Fix the following Cypher error: ..."` |
| **Neo4j returns 0 results** | Detect empty result set and yield a graceful `metadata` event with `"highlight_nodes": []`, then prompt the LLM to respond with `"No data was found matching your query."` |
| **Groq rate limit (HTTP 429)** | Catch the exception, yield `{"type": "error", "content": "LLM rate limit hit, please retry in a moment."}` and close the stream. |
| **Neo4j connection timeout** | Surface as an HTTP 503 with a user-readable message. The driver is initialized once at startup; reconnection is handled by the Neo4j driver's built-in retry logic. |

---

## 6. Security & Guardrails

To address the **"Guardrails"** evaluation criterion, the backend employs a multi-layered defense:

1. **Semantic Routing (Pre-computation):** As mentioned, `llama3-8b` acts as a gatekeeper. Off-topic questions never reach the database or the heavier LLM.
2. **Read-Only Database Credentials:** The Neo4j user provided to the backend is configured with strictly `READ` permissions. Even if a user manages to prompt-inject a `DELETE` or `MERGE` Cypher statement, the database will reject the transaction at the authorization layer.
3. **Pydantic Validation:** All incoming requests are strictly validated using Pydantic schemas, preventing payload manipulation.
4. **No Dynamic Credential Loading at Request Time:** All secrets are loaded once at startup via `config.py`, avoiding repeated environment lookups and reducing attack surface.

---

## 7. Alignment with Assignment Evaluation Criteria

| Evaluation Criteria | How the Backend Addresses It |
| :--- | :--- |
| **Code Quality & Architecture** | Modular DDD structure, clear separation of concerns, Pydantic type-safety, and usage of modern Python async/await patterns. |
| **Database / Storage Choice** | Neo4j selected over PostgreSQL due to its native handling of deep O2C traversals and seamless integration with Graph-based LLM prompts. |
| **LLM Integration & Prompting** | Custom system prompts that teach the LLM to use Graph "Shortcut Edges" (e.g., `[:DELIVERED_VIA]`) and Secondary Status Labels (`:FullyDelivered`) to prevent hallucinations and W-shaped traversal failures. |
| **Guardrails** | Implemented an LLM-based router that strictly classifies inputs and rejects out-of-domain requests before touching the primary query engine. |
| **Bonus: NL to Graph Query** | Built a highly customized Llama-3-70b Cypher generation engine with schema injection and error-retry loop. |
| **Bonus: Node Highlighting** | Intercepts stable business key properties during query execution and passes them to the UI via streaming metadata. |
| **Bonus: Streaming** | Implemented Server-Sent Events (SSE) for instantaneous UX feedback with a structured 3-event payload schema. |
| **Bonus: Conversation Memory** | Integrated a 4-turn sliding context window into the Pydantic schema and injected into the chat prompt. |