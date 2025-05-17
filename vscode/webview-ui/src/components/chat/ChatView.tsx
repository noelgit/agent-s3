import React, { useState, useEffect, useRef } from 'react';
import { vscode } from '../../utilities/vscode';
import './ChatView.css';

// Define types for our chat components
interface ChatMessage {
  id: string;
  type: 'user' | 'agent' | 'system';
  content: string;
  timestamp: Date;
  isComplete: boolean;
}

interface StreamState {
  id: string;
  content: string;
  source: string;
  isThinking: boolean;
}

// Types are defined at the top of the file

interface ChatViewProps {
  messages?: any[]; // Messages passed from parent component
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
  
  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  
  // Effect to handle WebView messages from extension
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const message = event.data;
      
      switch (message.type) {
        case 'LOAD_HISTORY':
          if (Array.isArray(message.history)) {
            setMessages(message.history);
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
          
        case 'STREAM_END':
          handleStreamEnd(message.content);
          break;
          
        case 'TERMINAL_OUTPUT':
          handleTerminalOutput(message.content);
          break;
      }
    };
    
    window.addEventListener('message', handleMessage);
    
    // Notify extension that the webview is ready
    vscode.postMessage({ type: 'webview-ready' });
    
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, []);
  
  // Process external messages from parent component
  useEffect(() => {
    if (!externalMessages.length) return;
    
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
            id: message.id || `chat-${Date.now()}`,
            type: message.content.source === 'user' ? 'user' : 'agent',
            content: message.content.text,
            timestamp: new Date(),
            isComplete: true
          };
          setMessages(prev => [...prev, chatMsg]);
          break;
      }
    });
  }, [externalMessages]);
  
  // Effect to scroll to bottom when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages, activeStreams]);
  
  /**
   * Handle thinking indicator messages
   */
  const handleThinkingIndicator = (content: any) => {
    const { stream_id, source } = content;
    
    setActiveStreams(prev => ({
      ...prev,
      [stream_id]: {
        id: stream_id,
        content: '',
        source: source || 'agent',
        isThinking: true
      }
    }));
    
    setIsAgentResponding(true);
  };
  
  /**
   * Handle stream start messages
   */
  const handleStreamStart = (content: any) => {
    const { stream_id, source } = content;
    
    setActiveStreams(prev => ({
      ...prev,
      [stream_id]: {
        id: stream_id,
        content: '',
        source: source || 'agent',
        isThinking: false
      }
    }));
    
    setIsAgentResponding(true);
  };
  
  /**
   * Handle stream content messages
   */
  const handleStreamContent = (content: any) => {
    const { stream_id, content: streamContent } = content;
    
    setActiveStreams(prev => {
      const stream = prev[stream_id];
      if (!stream) {
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
  };
  
  /**
   * Handle stream end messages
   */
  const handleStreamEnd = (content: any) => {
    const { stream_id } = content;
    
    setActiveStreams(prev => {
      const stream = prev[stream_id];
      if (!stream) {
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
      
      // Remove stream from active streams
      const newStreams = { ...prev };
      delete newStreams[stream_id];
      
      // Check if this was the last active stream
      if (Object.keys(newStreams).length === 0) {
        setIsAgentResponding(false);
      }
      
      return newStreams;
    });
  };
  
  /**
   * Handle terminal output messages
   */
  const handleTerminalOutput = (content: any) => {
    const { text, category } = content;
    
    // Add terminal output as system message
    const newMessage: ChatMessage = {
      id: `terminal-${Date.now()}`,
      type: 'system',
      content: text,
      timestamp: new Date(),
      isComplete: true
    };
    
    setMessages(messages => [...messages, newMessage]);
  };
  
  /**
   * Send a message to the agent
   */
  const sendMessage = () => {
    if (!inputText.trim()) {
      return;
    }
    
    // Create user message
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
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
    
    // Set responding state
    setIsAgentResponding(true);
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
   * Scroll to bottom of messages
   */
  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };
  
  /**
   * Render message content with format (including code blocks, links, etc)
   */
  const renderMessageContent = (content: string) => {
    // For now, just render plain text
    // TODO: Add markdown rendering with syntax highlighting for code blocks
    return content;
  };
  
  return (
    <div className="chat-container">
      <div className="messages-container">
        {messages.map((message) => (
          <div key={message.id} className={`message ${message.type}`}>
            <div className="message-content">
              {renderMessageContent(message.content)}
            </div>
            <div className="message-timestamp">
              {message.timestamp.toLocaleTimeString()}
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
                renderMessageContent(stream.content)
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
