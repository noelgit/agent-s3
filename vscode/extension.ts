/**
 * Open the interactive components view.
 */
function openInteractiveView() {
  // Create or show the interactive webview panel
  const panel = interactiveWebviewManager.createOrShowPanel();
  
  // Set up message handler for the interactive webview
  interactiveWebviewManager.setMessageHandler((message) => {
    console.log('Received message from interactive webview:', message);
    
    // Handle messages from the interactive components
    if (message.type) {
      switch (message.type) {
        case 'APPROVAL_RESPONSE':
          // Forward response to backend
          backendConnection.sendMessage({
            type: 'interactive_response',
            response_type: 'approval',
            request_id: message.content.request_id,
            selected_option: message.content.selected_option
          });
          break;
          
        case 'DIFF_RESPONSE':
          // Forward response to backend
          backendConnection.sendMessage({
            type: 'interactive_response',
            response_type: 'diff',
            action: message.content.action,
            files: message.content.files,
            file: message.content.file
          });
          break;
          
        case 'PROGRESS_RESPONSE':
          // Forward response to backend
          backendConnection.sendMessage({
            type: 'interactive_response',
            response_type: 'progress',
            action: message.content.action
          });
          break;
          
        case 'webview-ready':
          // Send any pending interactive components
          // This could be fetched from a cache or state
          console.log('Interactive webview is ready');
          break;
      }
    }
  });
}

// Add the interactive component handling to the backend connection
const originalProcessMessage = BackendConnection.prototype.processMessage;
BackendConnection.prototype.processMessage = function(message: any): void {
  const { type } = message;
  
  // Handle interactive components
  switch (type) {
    case 'INTERACTIVE_APPROVAL':
    case 'INTERACTIVE_DIFF':
    case 'PROGRESS_INDICATOR':
      // Show the interactive panel if not already visible
      const panel = interactiveWebviewManager.createOrShowPanel();
      
      // Forward the message to the webview
      interactiveWebviewManager.postMessage(message);
      return;
  }
  
  // Call the original method for other message types
  originalProcessMessage.call(this, message);
};