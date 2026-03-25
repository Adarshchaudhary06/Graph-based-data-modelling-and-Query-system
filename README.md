# SAP Graph Intelligence: Order-to-Cash (O2C)

An intelligent, high-performance graph exploration platform for SAP Order-to-Cash supply chain data. This system leverages Neo4j AuraDB for graph storage and Llama-3 (via Groq) for natural language Cypher generation and data analysis.

## Overview
This project provides a "Chat-with-Graph" interface that allows supply chain analysts to trace document flows (Sales Orders -> Deliveries -> Billing -> Payments) using natural language. It features a responsive React frontend with a physics-based 2D force-graph visualization.

## Tech Stack

### Database
*   **Neo4j AuraDB**: Cloud-managed graph database.
*   **Cypher**: Query language for complex relationship tracing.

### Backend
*   **FastAPI**: High-performance Python web framework.
*   **LangChain**: Orchestration for LLM routing and Cypher generation.
*   **Groq (Llama-3.1-8b & 3.3-70b)**: Lightning-fast inference for AI queries.

### Frontend
*   **Next.js 14**: Modern React framework.
*   **react-force-graph-2d**: Physics-based graph visualization.
*   **Tailwind CSS**: Utility-first styling with a dark-red high-contrast theme.

##  Dataset
The raw SAP O2C dataset (approx. 1,700 nodes and 8,000 relationships) can be downloaded here:
[Download Data (Google Drive)](https://drive.google.com/file/d/1UqaLbFaveV-3MEuiUrzKydhKmkeC1iAL/view)

Once downloaded, place the JSONL files into the `sap-o2c-data/` directory.

##  Setup Instructions

### 1. Database Setup
1.  Create a free **Neo4j AuraDB** instance.
2.  Install requirements: `pip install neo4j`.
3.  Configure credentials in `neo4j_ingest.py`.
4.  Run ingestion: `python neo4j_ingest.py`.

### 2. Backend Configuration
1.  Navigate to `backend/`.
2.  Install dependencies: `pip install -r requirements.txt`.
3.  Create a `.env` file with:
    ```env
    GROQ_API_KEY=your_groq_key
    NEO4J_URI=bolt+s://your-instance.databases.neo4j.io
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=your_password
    ```
4.  Start server: `uvicorn app.main:app --reload`.

### 3. Frontend Configuration
1.  Navigate to `frontend/`.
2.  Install dependencies: `npm install`.
3.  Start development server: `npm run dev`.

## Features
*   **Supply Chain Tracing**: Trace any Sales Order to its resulting Billing Document.
*   **Product-Plant Mapping**: Query which products are stocked at which plants across the logistics network.
*   **Semantic Highlighting**: AI results are automatically highlighted and zoomed on the graph canvas.
*   **Intelligent Suggestions**: The AI suggests real IDs if it can't find the exact match you requested.
