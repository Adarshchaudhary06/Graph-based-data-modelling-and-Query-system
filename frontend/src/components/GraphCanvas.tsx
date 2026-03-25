'use client';

import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import ForceGraph2D, { ForceGraphMethods } from 'react-force-graph-2d';
import { GraphData, GraphNode } from '@/types';

// Theming helper based on our globals.css
const getNodeColor = (label: string): string => {
  switch (label) {
    case 'Customer': return 'var(--node-customer)';
    case 'SalesOrder': return 'var(--node-order)';
    case 'OutboundDelivery': return 'var(--node-delivery)';
    case 'BillingDocument': return 'var(--node-billing)';
    case 'JournalEntry': return 'var(--node-journal)';
    case 'Payment': return 'var(--node-payment)';
    case 'Product': return 'var(--node-product)';
    default: return 'var(--node-default)';
  }
};

const hexToRgba = (hexOrVar: string, alpha: number) => {
  // Very basic approximation for canvas rendering if CSS variables aren't parsed by canvas
  // We'll hardcode the fallback values to ensure the canvas can draw them
  const colorMap: Record<string, string> = {
    'var(--node-customer)': `rgba(147, 51, 234, ${alpha})`,
    'var(--node-order)': `rgba(59, 130, 246, ${alpha})`,
    'var(--node-delivery)': `rgba(14, 165, 233, ${alpha})`,
    'var(--node-billing)': `rgba(245, 158, 11, ${alpha})`,
    'var(--node-journal)': `rgba(16, 185, 129, ${alpha})`,
    'var(--node-payment)': `rgba(5, 150, 105, ${alpha})`,
    'var(--node-product)': `rgba(225, 29, 72, ${alpha})`,
    'var(--node-default)': `rgba(100, 116, 139, ${alpha})`
  };
  return colorMap[hexOrVar] || `rgba(255, 255, 255, ${alpha})`;
};

interface GraphCanvasProps {
  data: GraphData;
  highlightNodes: string[];
  onNodeSelect: (node: GraphNode | null) => void;
}

export function GraphCanvas({ data, highlightNodes, onNodeSelect }: GraphCanvasProps) {
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoverNode, setHoverNode] = useState<GraphNode | null>(null);

  // Resize observer
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(entries => {
      for (let entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height
        });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Zoom to fit on initial load
  useEffect(() => {
    if (data.nodes.length > 0 && fgRef.current) {
      setTimeout(() => {
        fgRef.current?.zoomToFit(400, 50);
      }, 500); // give the physics engine a brief moment to settle
    }
  }, [data.nodes.length]);

  // Handle LLM highlights - zoom to highlighted nodes
  useEffect(() => {
    if (highlightNodes.length > 0 && fgRef.current && data.nodes.length > 0) {
      setTimeout(() => {
        // Zoom to fit all highlighted nodes with 150px padding for context
        fgRef.current?.zoomToFit(800, 150, (node: any) => highlightNodes.includes(node.id));
      }, 300);
    }
  }, [highlightNodes, data.nodes]);

  // Use memoization for highlight set for O(1) lookups during render 
  const highlightSet = useMemo(() => new Set(highlightNodes), [highlightNodes]);

  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const isHighlighted = highlightSet.has(node.id);
    const isHovered = hoverNode?.id === node.id;
    const baseColorVar = getNodeColor(node.label);

    // Adaptive radius - nodes don't grow linear with zoom
    // This keeps them readable without being 'too big'
    let radius = 6 / Math.pow(globalScale, 0.4); 
    if (isHighlighted) radius *= 1.4;
    if (isHovered) radius *= 1.2;

    // Dim non-highlighted nodes if highlights exist
    const isDimmed = highlightSet.size > 0 && !isHighlighted;
    const alpha = isDimmed ? 0.2 : 1.0;

    // Node body
    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
    
    if (isHighlighted) {
      ctx.fillStyle = 'rgba(153, 27, 27, 1)'; // Dark Red
    } else {
      ctx.fillStyle = hexToRgba(baseColorVar, alpha);
    }
    ctx.fill();

    // Outline
    ctx.strokeStyle = isDimmed ? 'rgba(0,0,0,0.05)' : 'rgba(0,0,0,0.8)';
    ctx.lineWidth = 0.5 / globalScale;
    ctx.stroke();

    // Glow effect for highlighted nodes - use a slight red aura
    if (isHighlighted) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius + (3 / globalScale), 0, 2 * Math.PI, false);
      ctx.fillStyle = 'rgba(153, 27, 27, 0.3)';
      ctx.fill();
    }

    // --- Semantic Zoom: Show labels only when zoomed in ---
    if (globalScale > 3 || isHighlighted || isHovered) {
      const label = node.id;
      const fontSize = 12 / globalScale;
      ctx.font = `${fontSize}px Sans-Serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = isDimmed ? 'rgba(0,0,0,0.1)' : 'rgba(0,0,0,0.8)';
      ctx.fillText(label, node.x, node.y + radius + (5 / globalScale));
    }
  }, [highlightSet, hoverNode]);

  const paintLink = useCallback((link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    if (!link.source || !link.target) return;

    const sourceHighlighted = highlightSet.has(link.source.id);
    const targetHighlighted = highlightSet.has(link.target.id);
    const bothHighlighted = sourceHighlighted && targetHighlighted;

    // Dim links unless both ends are highlighted (when highlights are active)
    const isDimmed = highlightSet.size > 0 && !bothHighlighted;

    ctx.beginPath();
    ctx.moveTo(link.source.x, link.source.y);
    ctx.lineTo(link.target.x, link.target.y);

    if (bothHighlighted && highlightSet.size > 0) {
      ctx.strokeStyle = 'rgba(186, 230, 253, 0.9)'; // Light sky blue
      ctx.lineWidth = 4 / globalScale; // Thicker logic
    } else {
      ctx.strokeStyle = isDimmed ? 'rgba(0, 0, 0, 0.05)' : 'rgba(0, 0, 0, 0.15)';
      ctx.lineWidth = 1 / globalScale;
    }

    ctx.stroke();
  }, [highlightSet]);

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>

      {/* HUD Details */}
      <div style={{
        position: 'absolute',
        top: '1rem',
        left: '1rem',
        zIndex: 10,
        pointerEvents: 'none'
      }}>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span>Nodes: {data.nodes.length}</span>
          <span>•</span>
          <span>Edges: {data.links.length}</span>
        </div>
      </div>

      {dimensions.width > 0 && dimensions.height > 0 && (
        <ForceGraph2D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={data as any}
          nodeLabel={(node: any) => {
            const label = node.label;
            const subId = node.billingDocument || node.product || node.salesOrder || node.customer || node.id;
            return `${label}: ${subId}`;
          }}
          nodeRelSize={4}
          nodeCanvasObject={paintNode}
          linkCanvasObject={paintLink}
          onNodeClick={(node: any) => onNodeSelect(node)}
          onNodeHover={(node: any) => setHoverNode(node)}
          linkDirectionalParticles={link => {
            // Animate particles along the edge if both source and target are highlighted
            const s = typeof link.source === 'object' ? link.source.id : link.source;
            const t = typeof link.target === 'object' ? link.target.id : link.target;
            return (highlightSet.has(s) && highlightSet.has(t)) ? 2 : 0;
          }}
          linkDirectionalParticleSpeed={0.01}
          linkDirectionalParticleWidth={2}
          backgroundColor="#f8fafc"
          d3VelocityDecay={0.3} // makes physics settle slightly faster
        />
      )}
    </div>
  );
}
