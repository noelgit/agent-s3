import React, { useState } from 'react';
import { vscode } from '../../utilities/vscode';

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
}

export const ProgressIndicator: React.FC<ProgressIndicatorProps> = ({
  title,
  percentage,
  steps,
  estimatedTimeRemaining
}) => {
  const [expandedStep, setExpandedStep] = useState<string | null>(null);
  
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

  return (
    <div className="progress-indicator">
      <h2 className="progress-title">{title}</h2>
      
      <div className="progress-bar-container">
        <div 
          className="progress-bar" 
          style={{ width: `${percentage}%` }}
        ></div>
        <div className="progress-percentage">{Math.round(percentage)}%</div>
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
            >
              <div className="step-header">
                <div className="step-status-icon">
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
        <button className="cancel-task" onClick={handleCancel}>
          Cancel Task
        </button>
      </div>
    </div>
  );
};