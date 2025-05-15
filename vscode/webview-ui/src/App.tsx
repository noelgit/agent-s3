import React, { useEffect, useState } from 'react';
import { vscode } from './utilities/vscode';
import { ApprovalRequest } from './components/interactive/ApprovalRequest';
import { DiffViewer } from './components/interactive/DiffViewer';
import { ProgressIndicator } from './components/interactive/ProgressIndicator';
import './App.css';

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
        setMessages(prev => [...prev, message]);
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

  return (
    <div className="app">
      <header className="app-header">
        <h1>Agent-S3 Interactive View</h1>
      </header>
      <main className="app-content">
        {messages.map(renderInteractiveComponent)}
      </main>
    </div>
  );
}

export default App;