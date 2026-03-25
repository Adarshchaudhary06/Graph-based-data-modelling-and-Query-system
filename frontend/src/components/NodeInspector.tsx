import React from 'react';
import { GraphNode } from '@/types';
import { X, Network } from 'lucide-react';

interface NodeInspectorProps {
  node: GraphNode | null;
  onClose: () => void;
}

// Ensure the ID keys aren't displayed redundantly
const IGNORED_PROPERTIES = ['id', 'element_id'];

export function NodeInspector({ node, onClose }: NodeInspectorProps) {
  if (!node) return null;

  // Filter out system properties and long empty values
  const visibleProps = Object.entries(node.properties || {}).filter(
    ([key, val]) => !IGNORED_PROPERTIES.includes(key) && val !== null && val !== ""
  );

  return (
    <div className="glass" style={{
      position: 'absolute',
      bottom: '24px',
      left: '24px',
      width: '320px',
      borderRadius: 'var(--radius-lg)',
      boxShadow: 'var(--shadow-lg)',
      zIndex: 100,
      overflow: 'hidden',
      animation: 'slideUp 0.3s ease-out forwards',
    }}>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}} />
      
      {/* Header */}
      <div style={{
        padding: '1rem',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        background: 'rgba(0,0,0,0.03)'
      }}>
        <div>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            {node.label || 'Entity'}
          </h3>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.25rem', fontFamily: 'monospace' }}>
            ID: {node.id}
          </div>
        </div>
        <button 
          onClick={onClose}
          style={{ 
            color: 'var(--text-tertiary)', 
            padding: '4px',
            borderRadius: '4px',
          }}
          onMouseOver={e => (e.currentTarget.style.background = 'var(--surface-hover)')}
          onMouseOut={e => (e.currentTarget.style.background = 'transparent')}
        >
          <X size={16} />
        </button>
      </div>

      {/* Content */}
      <div style={{
        padding: '1rem',
        maxHeight: '300px',
        overflowY: 'auto'
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          
          {visibleProps.map(([key, value]) => (
            <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
              <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)' }}>
                {key.replace(/([A-Z])/g, ' $1').trim()}
              </span>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-primary)', wordBreak: 'break-word' }}>
                {String(value)}
              </span>
            </div>
          ))}

          {/* Connection Stats */}
          {node.connections !== undefined && (
            <div style={{ 
              marginTop: '0.5rem', 
              paddingTop: '0.75rem', 
              borderTop: '1px dashed var(--border)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              color: 'var(--primary)',
              fontSize: '0.85rem'
            }}>
              <Network size={14} />
              <span>{node.connections} Edge Connections</span>
            </div>
          )}
          
        </div>
      </div>
    </div>
  );
}
