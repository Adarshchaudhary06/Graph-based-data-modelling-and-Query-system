import { useState, useRef, useCallback } from 'react';
import { ChatMessage, SSEEvent } from '@/types';

const API_URL = 'http://localhost:8000/api/chat';

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [highlightedNodes, setHighlightedNodes] = useState<string[]>([]);
  
  // Ref to reliably access latest messages inside the async stream reader
  const messagesRef = useRef<ChatMessage[]>([]);
  
  const addMessage = useCallback((msg: ChatMessage) => {
    setMessages(prev => {
      const newMsgs = [...prev, msg];
      messagesRef.current = newMsgs;
      return newMsgs;
    });
  }, []);

  const updateLastMessage = useCallback((updates: Partial<ChatMessage>) => {
    setMessages(prev => {
      if (prev.length === 0) return prev;
      const newMsgs = [...prev];
      const lastIndex = newMsgs.length - 1;
      newMsgs[lastIndex] = { ...newMsgs[lastIndex], ...updates };
      messagesRef.current = newMsgs;
      return newMsgs;
    });
  }, []);

  const sendMessage = async (question: string) => {
    if (!question.trim() || isStreaming) return;

    // 1. Add user message
    addMessage({
      id: Date.now().toString(),
      role: 'user',
      content: question,
    });

    // 2. Add placeholder assistant message
    const assistantMsgId = (Date.now() + 1).toString();
    addMessage({
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    });

    setIsStreaming(true);
    setHighlightedNodes([]);

    try {
      // Prepare history for backend format ({role: "user" | "assistant", content: string})
      // Only send up to the last 4 turns to match backend memory window
      const chat_history = messagesRef.current
        .slice(-8) // last 8 messages = 4 turns
        .filter(m => !m.isStreaming && m.id !== assistantMsgId && m.role !== 'user' ? m.content.length > 0 : true)
        .map(m => ({ role: m.role, content: m.content }));

      const res = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({
          question,
          chat_history
        }),
      });

      if (!res.ok) {
        throw new Error(`API Error: ${res.statusText}`);
      }

      if (!res.body) {
        throw new Error('ReadableStream not supported in this browser.');
      }

      // Read SSE stream
      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      
      let done = false;
      let textChunk = '';

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          textChunk += decoder.decode(value, { stream: true });
          
          // Process fully formed SSE events from the chunk
          const events = textChunk.split('\n\n');
          textChunk = events.pop() || ''; // Keep incomplete part for next iteration

          for (const eventStr of events) {
            if (eventStr.startsWith('data: ')) {
              const dataStr = eventStr.replace('data: ', '').trim();
              if (!dataStr) continue;

              try {
                const event: SSEEvent = JSON.parse(dataStr);

                if (event.type === 'metadata') {
                  updateLastMessage({
                    rawCypher: event.cypher,
                    highlightNodes: event.highlight_nodes
                  });
                  if (event.highlight_nodes) {
                    setHighlightedNodes(event.highlight_nodes);
                  }
                } 
                else if (event.type === 'token') {
                  setMessages(prev => {
                    if (prev.length === 0) return prev;
                    const newMsgs = [...prev];
                    const lastIndex = newMsgs.length - 1;
                    const curLast = newMsgs[lastIndex];
                    
                    newMsgs[lastIndex] = {
                      ...curLast,
                      content: curLast.content + (event.content || '')
                    };
                    return newMsgs;
                  });
                }
                else if (event.type === 'error') {
                  updateLastMessage({
                    content: `**Error:** ${event.content}`,
                    isError: true,
                    isStreaming: false
                  });
                }
                else if (event.type === 'done') {
                  updateLastMessage({ isStreaming: false });
                  setIsStreaming(false);
                  done = true; // Break loop
                }
              } catch (parseError) {
                console.error("Error parsing SSE JSON:", dataStr, parseError);
              }
            }
          }
        }
      }
      
    } catch (error: any) {
      console.error("Chat Error:", error);
      updateLastMessage({
        content: `**Connection Error:** ${error.message || 'Could not reach backend.'}`,
        isError: true,
        isStreaming: false
      });
      setIsStreaming(false);
    }
  };

  return {
    messages,
    isStreaming,
    highlightedNodes,
    sendMessage
  };
}
