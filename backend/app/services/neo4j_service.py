from neo4j import GraphDatabase
from app.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

class Neo4jService:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def close(self):
        self.driver.close()

    def _get_stable_id(self, node) -> str:
        """Extracts the stable business key based on the node's label."""
        key_map = {
            "Customer": "businessPartner",
            "Address": "addressId",
            "SalesOrder": "salesOrder",
            "SalesOrderItem": "salesOrderItemId",
            "SalesOrderScheduleLine": "scheduleLineId",
            "OutboundDelivery": "deliveryDocument",
            "OutboundDeliveryItem": "deliveryItemId",
            "BillingDocument": "billingDocument",
            "BillingDocumentItem": "billingItemId",
            "JournalEntry": "accountingDocumentId",
            "Payment": "paymentId",
            "Product": "product",
            "Plant": "plant",
            "StorageLocation": "storageLocationId"
        }
        
        # 1. Try to find the mapped business key
        for label in node.labels:
            if label in key_map and key_map[label] in node:
                return str(node[key_map[label]])
                
        # 2. Fallback to common ID field names
        for fallback_key in["id", "businessPartner", "salesOrder", "deliveryDocument", "billingDocument", "product"]:
            if fallback_key in node:
                return str(node[fallback_key])
                
        # 3. Absolute fallback to internal ID (should rarely happen)
        return str(node.element_id)

    def get_graph_sample(self, limit: int = 150) -> dict:
        """Fetches a sample of the graph for the React UI, using stable IDs."""
        query = "MATCH (n)-[r]->(m) RETURN n, r, m LIMIT $limit"
        nodes = {}
        links =[]
        
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            for record in result:
                n, r, m = record["n"], record["r"], record["m"]
                
                n_id = self._get_stable_id(n)
                m_id = self._get_stable_id(m)
                
                nodes[n_id] = {"id": n_id, "labels": list(n.labels), "properties": dict(n)}
                nodes[m_id] = {"id": m_id, "labels": list(m.labels), "properties": dict(m)}
                
                links.append({
                    "source": n_id,
                    "target": m_id,
                    "type": r.type
                })
                
        return {"nodes": list(nodes.values()), "links": links}

    def execute_and_extract_nodes(self, cypher_query: str) -> dict:
        """Executes Cypher, returns DB context AND stable business keys for UI highlighting."""
        highlight_nodes = set()
        formatted_results =[]
        
        # We DO NOT catch the exception here. We let it bubble up to llm_service 
        # so the LLM can self-correct Syntax Errors.
        with self.driver.session() as session:
            result = session.run(cypher_query)
            for record in result:
                formatted_record = {}
                for key, value in record.items():
                    if hasattr(value, 'element_id') and hasattr(value, 'labels'):
                        highlight_nodes.add(self._get_stable_id(value))
                        formatted_record[key] = dict(value)
                    elif hasattr(value, 'type'):
                        formatted_record[key] = dict(value)
                    elif isinstance(value, list):
                        formatted_record[key] =[]
                        for item in value:
                            if hasattr(item, 'element_id') and hasattr(item, 'labels'):
                                highlight_nodes.add(self._get_stable_id(item))
                                formatted_record[key].append(dict(item))
                            else:
                                formatted_record[key].append(item)
                    else:
                        formatted_record[key] = value
                
                formatted_results.append(formatted_record)
                
        return {
            "context": formatted_results,
            "highlight_nodes": list(highlight_nodes)
        }

# Singleton instance
neo4j_db = Neo4jService()