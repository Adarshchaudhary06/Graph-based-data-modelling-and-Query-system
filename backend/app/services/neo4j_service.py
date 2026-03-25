from neo4j import GraphDatabase
from app.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

class Neo4jService:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            NEO4J_URI, 
            auth=(NEO4J_USER, NEO4J_PASSWORD),
            max_connection_lifetime=300, # AuraDB requires proactive connection rotation
            connection_timeout=30.0
        )

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

    def get_graph_sample(self, limit: int = None) -> dict:
        """Fetches the entire graph (or a limited sample) for the React UI."""
        limit_clause = f"LIMIT {limit}" if limit else ""
        
        # 1. Fetch all connected relationships
        query_rels = f"MATCH (n)-[r]->(m) RETURN n, r, m {limit_clause}"
        # 2. Fetch all nodes (to catch orphans)
        query_nodes = f"MATCH (n) RETURN n {limit_clause}"
        
        nodes = {}
        links = []
        
        with self.driver.session() as session:
            # First, pull everything with a relationship
            rel_result = session.run(query_rels)
            for record in rel_result:
                n, r, m = record["n"], record["r"], record["m"]
                n_id, m_id = self._get_stable_id(n), self._get_stable_id(m)
                
                if n_id not in nodes: nodes[n_id] = {"id": n_id, "labels": list(n.labels), "properties": dict(n)}
                if m_id not in nodes: nodes[m_id] = {"id": m_id, "labels": list(m.labels), "properties": dict(m)}
                
                links.append({"source": n_id, "target": m_id, "type": r.type})
            
            # Second, pull strictly all nodes to ensure orphans show up
            node_result = session.run(query_nodes)
            for record in node_result:
                n = record["n"]
                n_id = self._get_stable_id(n)
                if n_id not in nodes:
                    nodes[n_id] = {"id": n_id, "labels": list(n.labels), "properties": dict(n)}
                
        return {"nodes": list(nodes.values()), "links": links}

    def execute_and_extract_nodes(self, cypher_query: str) -> dict:
        """Executes Cypher in read-only mode, returns DB context AND stable business keys for UI highlighting."""
        highlight_nodes = set()
        formatted_results = []
        
        def _read_tx(tx):
            return list(tx.run(cypher_query))

        with self.driver.session() as session:
            # FORCE READ ONLY TRANSACTION
            result = session.execute_read(_read_tx)
            
            for record in result:
                formatted_record = {}
                for key, value in record.items():
                    if hasattr(value, 'element_id') and hasattr(value, 'labels'):
                        highlight_nodes.add(self._get_stable_id(value))
                        formatted_record[key] = dict(value)
                    elif hasattr(value, 'type'):
                        formatted_record[key] = dict(value)
                    elif isinstance(value, list):
                        formatted_record[key] = []
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

    def get_sample_ids(self, label: str, property_name: str, limit: int = 3) -> list:
        """Fetches a few valid IDs for a given node label to help the AI suggest examples."""
        query = f"MATCH (n:{label}) RETURN n.{property_name} AS id LIMIT {limit}"
        try:
            with self.driver.session() as session:
                result = session.execute_read(lambda tx: list(tx.run(query)))
                return [str(record["id"]) for record in result if record["id"]]
        except:
            return []

# Singleton instance
neo4j_db = Neo4jService()