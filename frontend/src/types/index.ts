export interface GraphNode {
  id: string; // The primary key (e.g. salesOrder, deliveryDocument)
  label: string; // e.g., 'Customer', 'SalesOrder'
  properties: Record<string, any>;
  connections?: number;
  highlighted?: boolean;
}

export interface GraphLink {
  source: string; // id of source
  target: string; // id of target
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
  rawCypher?: string;
  highlightNodes?: string[];
  isError?: boolean;
}

export interface SSEEvent {
  type: 'metadata' | 'token' | 'error' | 'done';
  cypher?: string;
  highlight_nodes?: string[];
  content?: string;
}
