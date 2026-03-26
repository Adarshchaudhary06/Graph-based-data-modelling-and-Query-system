'use client';

import { useState } from 'react';
import { useGraphData } from '@/hooks/useGraphData';
import { useChat } from '@/hooks/useChat';
import dynamic from 'next/dynamic';

const GraphCanvas = dynamic(() => import('@/components/GraphCanvas').then(mod => mod.GraphCanvas), {
  ssr: false,
});
import { ChatPanel } from '@/components/ChatPanel';
import { NodeInspector } from '@/components/NodeInspector';
import { GraphNode } from '@/types';
import { Loader2, AlertCircle } from 'lucide-react';

export default function Home() {
  const { data: graphData, loading: graphLoading, error: graphError } = useGraphData();
  const { messages, isStreaming, highlightedNodes, sendMessage } = useChat();
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  return (
    <div style={{
      display: 'flex',
      height: '100%',
      width: '100vw',
      overflow: 'hidden'
    }}>
      
      {/* Left Pane: Graph Visualization */}
      <div style={{
        flex: '1 1 65%',
        position: 'relative',
        background: 'var(--background)'
      }}>
        {graphLoading && (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(248, 250, 252, 0.8)', zIndex: 50,
            gap: '1rem', color: 'var(--text-secondary)'
          }}>
            <Loader2 className="animate-spin" size={32} />
            <p>Loading Supply Chain Graph may take 1-2 minutes...</p>
          </div>
        )}

        {graphError && (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(248, 250, 252, 0.95)', zIndex: 50,
            gap: '1rem', color: 'var(--node-product)'
          }}>
            <AlertCircle size={48} />
            <p style={{ fontWeight: 600 }}>Failed to load graph data</p>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>{graphError}</p>
            <p style={{ fontSize: '0.75rem', marginTop: '1rem' }}>Ensure the FastAPI backend is running on port 8000.</p>
          </div>
        )}

        {!graphLoading && !graphError && (
          <GraphCanvas 
            data={graphData} 
            highlightNodes={highlightedNodes} 
            onNodeSelect={(node) => setSelectedNode(node)}
          />
        )}

        <NodeInspector 
          node={selectedNode} 
          onClose={() => setSelectedNode(null)} 
        />
      </div>

      {/* Right Pane: Chat Interface */}
      <div style={{
        flex: '0 0 35%',
        minWidth: '350px',
        maxWidth: '500px',
        height: '100%',
        boxShadow: '-4px 0 15px rgba(0,0,0,0.1)',
        zIndex: 20
      }}>
        <ChatPanel 
          messages={messages}
          isStreaming={isStreaming}
          onSendMessage={sendMessage}
        />
      </div>
      
    </div>
  );
}
