import React, { useState, useEffect, useRef, useCallback } from 'react';
import { vscode } from '../../utilities/vscode';
import { marked } from 'marked';
import hljs from 'highlight.js';
import DOMPurify from 'dompurify';
import './ChatView.css';

// Configure markdown parser with syntax highlighting
(marked as any).setOptions({
  highlight: (code: string, lang: string) => {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value;
    }
    return hljs.highlightAuto(code).value;
  }
});

// Define types for our chat components
interface ChatMessage {
  id: string;
  type: 'user' | 'agent' | 'system';
  content: string;
  timestamp: Date | string;
  isComplete: boolean;
}

interface StreamState {
  id: string;
  content: string;
  source: string;
  isThinking: boolean;
  components: InteractiveComponent[];
}

interface InteractiveComponent {
  action: string;
  label: string;
  placeholder?: string;
}

interface ExternalMessage {
  id?: string;
  type: string;
  content: any;
}

// Types are defined at the top of the file

interface ChatViewProps {
  messages?: ExternalMessage[]; // Messages passed from parent component
}

/**
 * Chat View component for real-time streaming interaction with Agent-S3
 */
export const ChatView: React.FC<ChatViewProps> = ({ messages: externalMessages = [] }) => {
  // State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [isAgentResponding, setIsAgentResponding] = useState(false);
  const [activeStreams, setActiveStreams] = useState<Record<string, StreamState>>({});
  const [hasMore, setHasMore] = useState(false);
  
  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * Generate unique message ID to avoid collisions
   */
  const generateMessageId = useCallback(() => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`, []);

  /**
   * Handle thinking indicator messages
   */
  const handleThinkingIndicator = useCallback((content: any) => {
    const { stream_id, source } = content;
    
    setActiveStreams(prev => ({
      ...prev,
      [stream_id]: {
        id: stream_id,
        content: '',
        source: source || 'agent',
        isThinking: true,
        components: []
      }
    }));
    
    setIsAgentResponding(true);
  }, []);

  /**
   * Handle stream start messages
   */
  const handleStreamStart = useCallback((content: any) => {
    const { stream_id, source } = content;
    
    setActiveStreams(prev => ({
      ...prev,
      [stream_id]: {
        id: stream_id,
        content: '',
        source: source || 'agent',
        isThinking: false,
        components: []
      }
    }));
    
    setIsAgentResponding(true);
  }, []);

  /**
   * Handle stream content messages
   */
  const handleStreamContent = useCallback((content: any) => {
    const { stream_id, content: streamContent } = content;
    
    setActiveStreams(prev => {
      const stream = prev[stream_id];
      if (!stream) {
        console.warn(`Stream ${stream_id} not found for content update`);
        return prev;
      }
      
      return {
        ...prev,
        [stream_id]: {
          ...stream,
          content: stream.content + streamContent,
          isThinking: false
        }
      };
    });
  }, []);

  const handleStreamInteractive = useCallback((content: any) => {
    const { stream_id, component } = content;
    setActiveStreams(prev => {
      const stream = prev[stream_id];
      if (!stream) {
        console.warn(`Stream ${stream_id} not found for interactive component`);
        return prev;
      }
      return {
        ...prev,
        [stream_id]: {
          ...stream,
          components: [...(stream.components || []), component]
        }
      };
    });
  }, []);

  /**
   * Handle stream end messages
   */
  const handleStreamEnd = useCallback((content: any) => {
    const { stream_id } = content;
    
    setActiveStreams(prev => {
      const stream = prev[stream_id];
      if (!stream) {
        console.warn(`Stream ${stream_id} not found for stream end`);
        return prev;
      }
      
      // Create a new message from the stream
      const newMessage: ChatMessage = {
        id: stream_id,
        type: 'agent',
        content: stream.content,
        timestamp: new Date(),
        isComplete: true
      };
      
      // Add message to history
      setMessages(messages => [...messages, newMessage]);
      
      // Remove stream from active streams using destructuring
      const { [stream_id]: removedStream, ...remaining } = prev;
      
      // Check if this was the last active stream
      if (Object.keys(remaining).length === 0) {
        setIsAgentResponding(false);
      }
      
      return remaining;
    });
  }, []);

  /**
   * Handle terminal output messages
   */
  const handleTerminalOutput = useCallback((content: any) => {
    const { text } = content;
    
    // Add terminal output as system message
    const newMessage: ChatMessage = {
      id: generateMessageId(),
      type: 'system',
      content: text,
      timestamp: new Date(),
      isComplete: true
    };
    
    setMessages(messages => [...messages, newMessage]);
  }, [generateMessageId]);

  /**
   * Handle command result messages
   */
  const handleCommandResult = useCallback((content: any) => {
    console.log('ChatView handleCommandResult called with:', content);
    const { result, success } = content;
    
    // Skip intermediate "Processing..." messages
    if (result === 'Processing...' && success === null) {
      return;
    }
    
    // Format the result content for better display
    let formattedResult = result;
    
    // If it looks like structured output, format it nicely
    if (typeof result === 'string' && result.length > 100) {
      // Add code block formatting for long outputs
      formattedResult = `\`\`\`\n${result}\n\`\`\``;
    }
    
    // Add command result as agent message
    const newMessage: ChatMessage = {
      id: generateMessageId(),
      type: success === false ? 'system' : 'agent',
      content: success === false ? `❌ ${formattedResult}` : formattedResult,
      timestamp: new Date(),
      isComplete: true
    };
    
    console.log('Adding command result message:', newMessage);
    setMessages(messages => [...messages, newMessage]);
    
    // CRITICAL FIX: Reset responding state when command completes
    setIsAgentResponding(false);
  }, [generateMessageId]);
  
  // Effect to handle WebView messages from extension
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      try {
        const message = event.data;
        console.log('ChatView received message:', message.type, message);
        
        switch (message.type) {
          case 'LOAD_HISTORY':
            if (Array.isArray(message.history)) {
              setMessages(prev => [...message.history, ...prev]);
              setHasMore(message.has_more);
            }
            break;
            
          case 'THINKING_INDICATOR':
            handleThinkingIndicator(message.content);
            break;
            
          case 'STREAM_START':
            handleStreamStart(message.content);
            break;
            
          case 'STREAM_CONTENT':
            handleStreamContent(message.content);
            break;

          case 'STREAM_INTERACTIVE':
            handleStreamInteractive(message.content);
            break;
            
          case 'STREAM_END':
            handleStreamEnd(message.content);
            break;
            
          case 'TERMINAL_OUTPUT':
            handleTerminalOutput(message.content);
            break;
            
          case 'COMMAND_RESULT':
            handleCommandResult(message.content);
            break;
        }
      } catch (error) {
        console.error('Error processing message:', error, event.data);
      }
    };
    
    window.addEventListener('message', handleMessage);
    
    // Notify extension that the webview is ready
    vscode.postMessage({ type: 'webview-ready' });
    
    return () => {
      window.removeEventListener('message', handleMessage);
      // Cleanup safety timeout to prevent memory leaks
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [handleThinkingIndicator, handleStreamStart, handleStreamContent, handleStreamInteractive, handleStreamEnd, handleTerminalOutput, handleCommandResult]);
  
  // Process external messages from parent component
  useEffect(() => {
    if (!externalMessages.length) return;
    
    try {
      externalMessages.forEach(message => {
        switch (message.type) {
          case 'THINKING_INDICATOR':
            handleThinkingIndicator(message.content);
            break;
            
          case 'STREAM_START':
            handleStreamStart(message.content);
            break;
            
          case 'STREAM_CONTENT':
            handleStreamContent(message.content);
            break;
            
          case 'STREAM_END':
            handleStreamEnd(message.content);
            break;
            
          case 'TERMINAL_OUTPUT':
            handleTerminalOutput(message.content);
            break;
            
          case 'CHAT_MESSAGE':
            // Handle chat messages from other sources
            const chatMsg: ChatMessage = {
              id: message.id || generateMessageId(),
              type: message.content.source === 'user' ? 'user' : 'agent',
              content: message.content.text,
              timestamp: new Date(),
              isComplete: true
            };
            setMessages(prev => [...prev, chatMsg]);
            
            // Reset responding state when we get an agent message
            if (message.content.source === 'agent') {
              setIsAgentResponding(false);
            }
            break;
        }
      });
    } catch (error) {
      console.error('Error processing external messages:', error, externalMessages);
    }
  }, [externalMessages, generateMessageId, handleThinkingIndicator, handleStreamStart, handleStreamContent, handleStreamEnd, handleTerminalOutput]);
   /**
   * Scroll to bottom of messages
   */
  const scrollToBottom = useCallback(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  /**
   * Debounced scroll to prevent excessive scrolling during rapid updates
   */
  const debouncedScrollToBottom = useCallback(() => {
    // Simple debouncing - cancel previous timeout and set new one
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(scrollToBottom, 100);
  }, [scrollToBottom]);

  // Effect to scroll to bottom when messages change
  useEffect(() => {
    debouncedScrollToBottom();
  }, [messages, activeStreams, debouncedScrollToBottom]);

  /**
   * Send a message to the agent
   */
  const sendMessage = () => {
    if (!inputText.trim()) {
      return;
    }
    
    // Create user message
    const userMessage: ChatMessage = {
      id: generateMessageId(),
      type: 'user',
      content: inputText,
      timestamp: new Date(),
      isComplete: true
    };
    
    // Add to messages
    setMessages([...messages, userMessage]);
    
    // Send to extension
    vscode.postMessage({
      type: 'send',
      text: inputText
    });
    
    // Clear input
    setInputText('');
    
    // Focus input
    if (inputRef.current) {
      inputRef.current.focus();
    }
    
    // Set responding state with timeout safety net
    setIsAgentResponding(true);
    
    // Clear any existing timeout and set new one
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    
    // Safety timeout - reset responding state after 60 seconds if no response
    timeoutRef.current = setTimeout(() => {
      setIsAgentResponding(false);
      timeoutRef.current = null;
    }, 60000);
  };

  /**
   * Handle input key press
   */
  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };
  
  /**
   * Render message content with format (including code blocks, links, etc)
   */
  const renderMessageContent = (content: string) => {
    const rawHtml = marked.parse(content) as string;
    const cleanHtml = DOMPurify.sanitize(rawHtml, {
      ADD_TAGS: ['button', 'input'],
      ADD_ATTR: ['data-action', 'type', 'placeholder']
    });
    return <span dangerouslySetInnerHTML={{ __html: cleanHtml }} />;
  };
  
  return (
    <div className="chat-container">
      <div className="messages-container">
        {hasMore && (
          <button
            className="load-more"
            onClick={() => vscode.postMessage({ type: 'REQUEST_MORE_HISTORY', already: messages.length })}
          >
            Load More
          </button>
        )}
        {messages.map((message) => (
          <div key={message.id} className={`message ${message.type}`}>
            <div className="message-content">
              {renderMessageContent(message.content)}
            </div>
            <div className="message-timestamp">
              {new Date(message.timestamp).toLocaleTimeString()}
            </div>
          </div>
        ))}
        
        {/* Render active streams */}
        {Object.values(activeStreams).map((stream) => (
          <div key={stream.id} className="message agent streaming">
            <div className="message-content">
              {stream.isThinking ? (
                <div
                  className="thinking-indicator"
                  role="status"
                  aria-label="Agent is thinking"
                >
                  <span className="dot" aria-hidden="true"></span>
                  <span className="dot" aria-hidden="true"></span>
                  <span className="dot" aria-hidden="true"></span>
                </div>
              ) : (
                <>
                  {renderMessageContent(stream.content)}
                  {stream.components.map((comp, idx) => (
                    <button
                      key={idx}
                      data-action={comp.action}
                      onClick={() =>
                        vscode.postMessage({
                          type: 'interactive_component',
                          component: comp
                        })
                      }
                    >
                      {comp.label || comp.placeholder}
                    </button>
                  ))}
                </>
              )}
            </div>
          </div>
        ))}
        
        <div ref={messagesEndRef} />
      </div>
      
      <div className="input-container">
        <textarea
          ref={inputRef}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type a message..."
          disabled={isAgentResponding}
          aria-label="Chat message input"
        />
        <button
          onClick={sendMessage}
          disabled={!inputText.trim() || isAgentResponding}
          aria-label="Send message"
        >
          Send
        </button>
      </div>
    </div>
  );
};
