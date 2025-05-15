import React, { useState } from 'react';
import { vscode } from '../../utilities/vscode';

interface Option {
  id: string;
  label: string;
  description?: string;
}

interface ApprovalRequestProps {
  title: string;
  description: string;
  options: Option[];
  requestId: string;
  timeout?: number;
}

export const ApprovalRequest: React.FC<ApprovalRequestProps> = ({
  title,
  description,
  options,
  requestId,
  timeout
}) => {
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [timeRemaining, setTimeRemaining] = useState<number | null>(
    timeout ? timeout : null
  );

  React.useEffect(() => {
    let timerId: NodeJS.Timeout | null = null;
    
    if (timeout && timeout > 0) {
      timerId = setInterval(() => {
        setTimeRemaining(prev => {
          if (prev !== null && prev > 0) {
            return prev - 1;
          } else {
            // Time's up, select default option
            if (timerId) clearInterval(timerId);
            handleSubmit(options[0].id);
            return 0;
          }
        });
      }, 1000);
    }
    
    return () => {
      if (timerId) clearInterval(timerId);
    };
  }, [timeout, options]);

  const handleSubmit = (optionId: string) => {
    vscode.postMessage({
      type: 'APPROVAL_RESPONSE',
      content: {
        request_id: requestId,
        selected_option: optionId
      }
    });
  };

  return (
    <div className="approval-request">
      <h2 className="approval-title">{title}</h2>
      
      {timeRemaining !== null && (
        <div className="approval-timer">
          Time remaining: {Math.floor(timeRemaining / 60)}:{(timeRemaining % 60).toString().padStart(2, '0')}
        </div>
      )}
      
      <div className="approval-description">
        {description}
      </div>
      
      <div className="approval-options">
        {options.map(option => (
          <div 
            key={option.id} 
            className={`approval-option ${selectedOption === option.id ? 'selected' : ''}`}
            onClick={() => setSelectedOption(option.id)}
          >
            <div className="option-label">{option.label}</div>
            {option.description && (
              <div className="option-description">{option.description}</div>
            )}
          </div>
        ))}
      </div>
      
      <div className="approval-actions">
        <button 
          className="approval-submit"
          disabled={!selectedOption} 
          onClick={() => selectedOption && handleSubmit(selectedOption)}
        >
          Submit
        </button>
      </div>
    </div>
  );
};