import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CypherDebugPanel } from './CypherDebugPanel';
import { ChatMessage as IChatMessage } from '@/types';
import { User, Cpu } from 'lucide-react';

interface ChatMessageProps {
  message: IChatMessage;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div style={{
      display: 'flex',
      gap: '1rem',
      padding: '1rem',
      background: isUser ? 'transparent' : 'var(--surface)',
      borderBottom: isUser ? 'none' : '1px solid var(--border)',
    }}>
      
      {/* Avatar */}
      <div style={{
        width: '32px',
        height: '32px',
        borderRadius: '50%',
        background: isUser ? 'var(--text-tertiary)' : 'linear-gradient(135deg, var(--primary), #8b5cf6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'white',
        flexShrink: 0
      }}>
        {isUser ? <User size={18} /> : <Cpu size={18} />}
      </div>

      {/* Content Area */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          marginBottom: '0.25rem'
        }}>
          <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
            {isUser ? 'You' : 'Graph Agent'}
          </span>
          {message.isStreaming && (
            <span style={{
              fontSize: '0.7rem',
              color: 'var(--primary)',
              background: 'rgba(59, 130, 246, 0.1)',
              padding: '0.1rem 0.4rem',
              borderRadius: '999px',
              animation: 'pulse 1.5s infinite'
            }}>
              thinking...
            </span>
          )}
        </div>
        
        {/* Markdown Body */}
        <div className="prose">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Debug Panel (Assistant only) */}
        {!isUser && message.rawCypher && (
          <CypherDebugPanel cypher={message.rawCypher} />
        )}
      </div>
      
    </div>
  );
}
