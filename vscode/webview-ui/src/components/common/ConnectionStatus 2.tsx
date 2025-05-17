import React, { useEffect, useState } from 'react';
import './ConnectionStatus.css';

interface ConnectionStatusProps {
  isConnected: boolean;
  onReconnect?: () => void;
}

/**
 * Component for displaying the connection status in the UI
 */
export const ConnectionStatus: React.FC<ConnectionStatusProps> = ({ 
  isConnected,
  onReconnect
}) => {
  const [showStatus, setShowStatus] = useState(false);
  
  // Show status briefly when connection state changes
  useEffect(() => {
    setShowStatus(true);
    
    const timer = setTimeout(() => {
      if (isConnected) {
        setShowStatus(false);
      }
    }, 3000);
    
    return () => clearTimeout(timer);
  }, [isConnected]);
  
  // Always show when disconnected
  useEffect(() => {
    if (!isConnected) {
      setShowStatus(true);
    }
  }, [isConnected]);
  
  // Handle reconnection attempt
  const handleReconnectClick = () => {
    if (onReconnect) {
      onReconnect();
    }
  };
  
  if (!showStatus) {
    return null;
  }
  
  return (
    <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
      {isConnected ? (
        <span>
          <span className="status-indicator connected"></span>
          Connected to Agent-S3
        </span>
      ) : (
        <span>
          <span className="status-indicator disconnected"></span>
          Disconnected
          {onReconnect && (
            <button className="reconnect-button" onClick={handleReconnectClick}>
              Reconnect
            </button>
          )}
        </span>
      )}
    </div>
  );
};
