import { useState, useEffect } from 'react';
import { GraphData } from '@/types';

// The backend endpoint
const API_URL = 'http://localhost:8000/api/graph-data';

export function useGraphData() {
  const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchGraph() {
      try {
        setLoading(true);
        const res = await fetch(API_URL);
        
        if (!res.ok) {
          throw new Error(`Failed to fetch graph: ${res.statusText}`);
        }
        
        const json: GraphData = await res.json();
        
        // react-force-graph mutates the source/target links natively,
        // but it requires them to point to node ids initially.
        // Our backend already provides {"source": "id1", "target": "id2"}
        // so we just pass it straight through.
        setData(json);
        setError(null);
      } catch (err: any) {
        console.error("Error fetching graph data:", err);
        setError(err.message || "Unknown error occurred");
      } finally {
        setLoading(false);
      }
    }

    fetchGraph();
  }, []);

  return { data, loading, error };
}
