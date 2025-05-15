import React, { useEffect, useState } from 'react';
import { vscode } from './utilities/vscode';
import { ApprovalRequest } from './components/interactive/ApprovalRequest';
import { DiffViewer } from './components/interactive/DiffViewer';
import { ProgressIndicator } from './components/interactive/ProgressIndicator';
import { ChatView } from './components/chat/ChatView';
import './App.css';

// Import types from our types directory (we'll reference it in tsconfig.json)
interface MessageData {
  type: string;
  content: any;
  id?: string;
}

function App() {
  const [messages, setMessages] = useState<MessageData[]>([]);

  useEffect(() => {
    // Handle messages from the extension
    const messageListener = (event: MessageEvent) => {
      const message = event.data;
      
      // Process incoming message
      if (message.type) {
        setMessages((prev: MessageData[]) => [...prev, message]);
      }
    };

    window.addEventListener('message', messageListener);
    
    // Signal to VS Code that the webview is ready
    vscode.postMessage({ type: 'webview-ready' });

    return () => {
      window.removeEventListener('message', messageListener);
    };
  }, []);

  const renderInteractiveComponent = (message: MessageData) => {
    switch (message.type) {
      case 'INTERACTIVE_APPROVAL':
        return (
          <ApprovalRequest
            key={message.id}
            title={message.content.title}
            description={message.content.description}
            options={message.content.options}
            requestId={message.content.request_id}
            timeout={message.content.timeout}
          />
        );
      case 'INTERACTIVE_DIFF':
        return (
          <DiffViewer
            key={message.id}
            files={message.content.files}
            summary={message.content.summary}
          />
        );
      case 'PROGRESS_INDICATOR':
        return (
          <ProgressIndicator
            key={message.id}
            title={message.content.title}
            percentage={message.content.percentage}
            steps={message.content.steps}
            estimatedTimeRemaining={message.content.estimated_time_remaining}
          />
        );
      default:
        return null;
    }
  };

  const [activeView, setActiveView] = useState<'interactive' | 'chat'>('chat');

  return (
    <div className="app">
      <header className="app-header">
        <h1>Agent-S3</h1>
        <div className="view-switcher">
          <button
            className={activeView === 'chat' ? 'active' : ''}
            onClick={() => setActiveView('chat')}
          >
            Chat
          </button>
          <button
            className={activeView === 'interactive' ? 'active' : ''}
            onClick={() => setActiveView('interactive')}
          >
            Interactive Components
          </button>
        </div>
      </header>
      <main className="app-content">
        {activeView === 'interactive' ? (
          messages.map(renderInteractiveComponent)
        ) : (
          <ChatView messages={messages.filter(m => 
            m.type === 'THINKING_INDICATOR' || 
            m.type === 'STREAM_START' || 
            m.type === 'STREAM_CONTENT' || 
            m.type === 'STREAM_END' || 
            m.type === 'TERMINAL_OUTPUT' ||
            m.type === 'CHAT_MESSAGE'
          )} />
        )}
      </main>
    </div>
  );
}

export default App;