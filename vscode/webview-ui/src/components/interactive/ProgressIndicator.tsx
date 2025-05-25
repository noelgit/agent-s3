import React, { useState } from 'react';
import { vscode } from '../../utilities/vscode';
import './ProgressIndicator.css';

interface Step {
  id: string;
  name: string;
  description?: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  percentage?: number;
}

interface ProgressIndicatorProps {
  title: string;
  percentage: number;
  steps: Step[];
  estimatedTimeRemaining?: number;
  cancelable?: boolean;
  pausable?: boolean;
  stoppable?: boolean;
}

export const ProgressIndicator: React.FC<ProgressIndicatorProps> = ({
  title,
  percentage,
  steps,
  estimatedTimeRemaining,
  cancelable = true,
  pausable = true,
  stoppable = true
}) => {
  const [expandedStep, setExpandedStep] = useState<string | null>(null);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  
  const formatTime = (seconds: number): string => {
    if (seconds < 60) {
      return `${seconds}s`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = seconds % 60;
      return `${minutes}m ${remainingSeconds}s`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const remainingMinutes = Math.floor((seconds % 3600) / 60);
      return `${hours}h ${remainingMinutes}m`;
    }
  };

  const handleToggleStepDetails = (stepId: string) => {
    setExpandedStep(expandedStep === stepId ? null : stepId);
  };

  const handleCancel = () => {
    vscode.postMessage({
      type: 'PROGRESS_RESPONSE',
      content: {
        action: 'cancel'
      }
    });
  };

  const handlePause = () => {
    setIsPaused(true);
    vscode.postMessage({
      type: 'PROGRESS_RESPONSE',
      content: {
        action: 'pause'
      }
    });
  };

  const handleResume = () => {
    setIsPaused(false);
    vscode.postMessage({
      type: 'PROGRESS_RESPONSE',
      content: {
        action: 'resume'
      }
    });
  };

  const handleStop = () => {
    vscode.postMessage({
      type: 'PROGRESS_RESPONSE',
      content: {
        action: 'stop'
      }
    });
  };

  return (
    <div className="progress-indicator">
      <h2 className="progress-title">{title}</h2>
      
      <div className={`progress-bar-container ${isPaused ? 'paused' : ''}`}>
        <div 
          className="progress-bar" 
          style={{ width: `${percentage}%` }}
        ></div>
        <div className="progress-percentage">
          {isPaused && <span className="pause-indicator">⏸️ </span>}
          {Math.round(percentage)}%
        </div>
      </div>
      
      {estimatedTimeRemaining !== undefined && (
        <div className="estimated-time">
          Time remaining: {formatTime(estimatedTimeRemaining)}
        </div>
      )}
      
      <div className="progress-steps">
        {steps.map(step => {
          const isExpanded = expandedStep === step.id;
          
          return (
            <div
              key={step.id}
              className={`progress-step ${step.status} ${isExpanded ? 'expanded' : ''}`}
              onClick={() => handleToggleStepDetails(step.id)}
              role="button"
              tabIndex={0}
              aria-label={`Toggle details for ${step.name}`}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleToggleStepDetails(step.id);
                }
              }}
            >
              <div className="step-header">
                <div
                  className="step-status-icon"
                  role="img"
                  aria-label={
                    step.status === 'completed'
                      ? 'completed'
                      : step.status === 'failed'
                      ? 'failed'
                      : step.status === 'in_progress'
                      ? 'in progress'
                      : 'pending'
                  }
                >
                  {step.status === 'completed' ? '✓' :
                   step.status === 'failed' ? '✗' :
                   step.status === 'in_progress' ? '→' : '○'}
                </div>
                <div className="step-name">{step.name}</div>
                {step.percentage !== undefined && (
                  <div className="step-percentage">{Math.round(step.percentage)}%</div>
                )}
              </div>
              
              {isExpanded && step.description && (
                <div className="step-description">
                  {step.description}
                </div>
              )}
            </div>
          );
        })}
      </div>
      
      <div className="progress-actions">
        {pausable && !isPaused && (
          <button
            className="pause-task"
            onClick={handlePause}
            aria-label="Pause current task"
            title="Pause the workflow execution"
          >
            <span className="button-icon">⏸️</span>
            Pause
          </button>
        )}
        
        {pausable && isPaused && (
          <button
            className="resume-task"
            onClick={handleResume}
            aria-label="Resume current task"
            title="Resume the workflow execution"
          >
            <span className="button-icon">▶️</span>
            Resume
          </button>
        )}
        
        {stoppable && (
          <button
            className="stop-task"
            onClick={handleStop}
            aria-label="Stop current task"
            title="Stop the workflow execution"
          >
            <span className="button-icon">⏹️</span>
            Stop
          </button>
        )}
        
        {cancelable && (
          <button
            className="cancel-task"
            onClick={handleCancel}
            aria-label="Cancel current task"
            title="Cancel the workflow execution"
          >
            <span className="button-icon">❌</span>
            Cancel
          </button>
        )}
      </div>
    </div>
  );
};