import React, { useState, useRef, useEffect } from 'react';
import { ChatMessage as IChatMessage } from '@/types';
import { ChatMessage } from './ChatMessage';
import { Send, Hash } from 'lucide-react';

interface ChatPanelProps {
  messages: IChatMessage[];
  isStreaming: boolean;
  onSendMessage: (msg: string) => void;
}

export function ChatPanel({ messages, isStreaming, onSendMessage }: ChatPanelProps) {
  const [input, setInput] = useState('');
  const endOfMessagesRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isStreaming) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      background: 'var(--surface)',
      borderLeft: '1px solid var(--border)',
    }}>
      {/* Header */}
      <div style={{
        padding: '1rem',
        borderBottom: '1px solid var(--border)',
        background: 'var(--background)'
      }}>
        <h2 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>Chat with Graph</h2>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>Order to Cash Supply Chain</p>
      </div>

      {/* Message List */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {messages.length === 0 ? (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            color: 'var(--text-tertiary)',
            padding: '2rem',
            textAlign: 'center',
            gap: '1rem'
          }}>
            <Hash size={48} opacity={0.3} />
            <div>
              <p style={{ fontWeight: 500, color: 'var(--text-secondary)' }}>Welcome to Graph Query</p>
              <p style={{ fontSize: '0.85rem', marginTop: '0.5rem' }}>Ask natural language questions about your supply chain data.</p>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'center', marginTop: '1rem' }}>
               <button 
                 onClick={() => onSendMessage("Which product has the highest billing amount?")}
                 style={{ fontSize: '0.75rem', padding: '0.4rem 0.75rem', borderRadius: '999px', background: 'var(--surface-hover)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                 Example 1
               </button>
               <button 
                 onClick={() => onSendMessage("Find Sales Orders with broken flows (delivered but not billed)")}
                 style={{ fontSize: '0.75rem', padding: '0.4rem 0.75rem', borderRadius: '999px', background: 'var(--surface-hover)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
                 Example 2
               </button>
            </div>
          </div>
        ) : (
          messages.map(msg => (
            <ChatMessage key={msg.id} message={msg} />
          ))
        )}
        <div ref={endOfMessagesRef} />
      </div>

      {/* Input Area */}
      <div style={{
        padding: '1rem',
        background: 'var(--background)',
        borderTop: '1px solid var(--border)'
      }}>
        <form onSubmit={handleSubmit} style={{
          display: 'flex',
          gap: '0.5rem',
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)',
          padding: '0.5rem',
          boxShadow: 'var(--shadow-sm)'
        }}>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isStreaming ? "Wait for response..." : "Ask a question about the data..."}
            disabled={isStreaming}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: 'var(--text-primary)',
              resize: 'none',
              padding: '0.5rem',
              height: '44px',
              minHeight: '44px',
              fontFamily: 'inherit',
              lineHeight: '1.5'
            }}
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            style={{
              width: '44px',
              height: '44px',
              borderRadius: 'var(--radius-md)',
              background: input.trim() && !isStreaming ? 'var(--primary)' : 'var(--surface-hover)',
              color: input.trim() && !isStreaming ? '#fff' : 'var(--text-tertiary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s',
              cursor: input.trim() && !isStreaming ? 'pointer' : 'not-allowed'
            }}
          >
            <Send size={18} />
          </button>
        </form>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          marginTop: '0.75rem',
          fontSize: '0.7rem',
          color: 'var(--text-tertiary)',
          paddingLeft: '0.5rem'
        }}>
          <div style={{
            width: '6px', height: '6px', borderRadius: '50%',
            background: isStreaming ? 'var(--node-billing)' : 'var(--node-journal)'
          }} />
          {isStreaming ? "Analyzing graph network..." : "Graph Agent is awaiting instructions"}
        </div>
      </div>
    </div>
  );
}
