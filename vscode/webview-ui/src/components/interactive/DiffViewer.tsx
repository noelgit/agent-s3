import React, { useState } from 'react';
import { vscode } from '../../utilities/vscode';

interface FileDiff {
  path: string;
  before: string;
  after: string;
  hunks?: Array<{
    oldStart: number;
    oldLines: number;
    newStart: number;
    newLines: number;
    lines: string[];
  }>;
}

interface DiffViewerProps {
  files: FileDiff[];
  summary: string;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ files, summary }) => {
  const [currentFileIndex, setCurrentFileIndex] = useState(0);
  const [viewMode, setViewMode] = useState<'split' | 'unified'>('split');
  
  const currentFile = files[currentFileIndex];
  
  const handleApprove = () => {
    vscode.postMessage({
      type: 'DIFF_RESPONSE',
      content: {
        action: 'approve',
        files: files.map(file => file.path)
      }
    });
  };
  
  const handleReject = () => {
    vscode.postMessage({
      type: 'DIFF_RESPONSE',
      content: {
        action: 'reject',
        files: files.map(file => file.path)
      }
    });
  };

  const handleOpenInEditor = () => {
    vscode.postMessage({
      type: 'DIFF_RESPONSE',
      content: {
        action: 'open_in_editor',
        file: currentFile.path
      }
    });
  };

  return (
    <div className="diff-viewer">
      <h2 className="diff-title">Code Changes</h2>
      
      <div className="diff-summary">
        {summary}
      </div>
      
      <div className="diff-controls">
        <div className="file-selector">
          <select 
            value={currentFileIndex}
            onChange={(e) => setCurrentFileIndex(parseInt(e.target.value))}
          >
            {files.map((file, index) => (
              <option key={file.path} value={index}>
                {file.path}
              </option>
            ))}
          </select>
        </div>
        
        <div className="view-mode-selector">
          <button 
            className={viewMode === 'split' ? 'active' : ''} 
            onClick={() => setViewMode('split')}
          >
            Split View
          </button>
          <button 
            className={viewMode === 'unified' ? 'active' : ''} 
            onClick={() => setViewMode('unified')}
          >
            Unified View
          </button>
        </div>
      </div>
      
      <div className={`diff-content ${viewMode}`}>
        {viewMode === 'split' ? (
          <>
            <div className="diff-before">
              <h3>Before</h3>
              <pre><code>{currentFile.before}</code></pre>
            </div>
            <div className="diff-after">
              <h3>After</h3>
              <pre><code>{currentFile.after}</code></pre>
            </div>
          </>
        ) : (
          <div className="diff-unified">
            {currentFile.hunks ? (
              currentFile.hunks.map((hunk, i) => (
                <div key={i} className="diff-hunk">
                  <div className="hunk-header">
                    @@ -{hunk.oldStart},{hunk.oldLines} +{hunk.newStart},{hunk.newLines} @@
                  </div>
                  <pre>
                    {hunk.lines.map((line, j) => {
                      const prefix = line.charAt(0);
                      const lineClass = prefix === '+' ? 'addition' : 
                                        prefix === '-' ? 'deletion' : 'context';
                      return (
                        <div key={j} className={`line ${lineClass}`}>
                          {line}
                        </div>
                      );
                    })}
                  </pre>
                </div>
              ))
            ) : (
              <pre><code>{currentFile.after}</code></pre>
            )}
          </div>
        )}
      </div>
      
      <div className="diff-actions">
        <button className="open-in-editor" onClick={handleOpenInEditor}>
          Open in Editor
        </button>
        <button className="reject-diff" onClick={handleReject}>
          Reject
        </button>
        <button className="approve-diff" onClick={handleApprove}>
          Approve
        </button>
      </div>
    </div>
  );
};