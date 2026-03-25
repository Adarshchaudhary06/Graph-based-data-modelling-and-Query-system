import React from 'react';

interface CypherDebugPanelProps {
  cypher: string;
}

export function CypherDebugPanel({ cypher }: CypherDebugPanelProps) {
  if (!cypher) return null;

  return (
    <details style={{
      marginTop: '0.75rem',
      background: 'var(--surface-hover)',
      borderRadius: 'var(--radius-md)',
      border: '1px solid var(--border)',
      overflow: 'hidden'
    }}>
      <summary style={{
        padding: '0.5rem 0.75rem',
        fontSize: '0.75rem',
        fontWeight: 600,
        color: 'var(--text-secondary)',
        cursor: 'pointer',
        userSelect: 'none',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem'
      }}>
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="16 18 22 12 16 6"></polyline>
          <polyline points="8 6 2 12 8 18"></polyline>
        </svg>
        View Generated Cypher
      </summary>
      <div style={{
        padding: '0.75rem',
        borderTop: '1px solid var(--border)',
        overflowX: 'auto'
      }}>
        <pre style={{
          margin: 0,
          fontFamily: 'Consolas, Monaco, monospace',
          fontSize: '0.75rem',
          color: '#d8b4fe',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all'
        }}>
          {cypher}
        </pre>
      </div>
    </details>
  );
}
