// Test the batch message handling by manually processing a batch message
const batchMessage = {
  "type": "batch",
  "messages": [
    {
      "id": "ff00ca97-f647-40b3-81ed-211c4dcaf6d6",
      "type": "command_result",
      "content": {
        "request_id": "test-help-1748774370259",
        "command": "/help",
        "result": "Available commands:\n/init: Initialize workspace\n/plan <description>: Generate a development plan\n/test [filter]: Run tests (optional filter)\n/debug: Debug last test failure\n/terminal <command>: Execute terminal command\n/personas: Create/update personas.md\n/guidelines: Create/update copilot-instructions.md\n/design <objective>: Create a design document\n/design-auto <objective>: Auto-approve design workflow\n/implement: Implement a design from design.txt\n/continue: Continue implementation\n/deploy [design_file]: Deploy an application\n/config: Show current configuration\n/reload-llm-config: Reload LLM configuration\n/explain: Explain the last LLM interaction\n/request <prompt>: Full change request (plan + execution)\n/tasks: List active tasks that can be resumed\n/clear <task_id>: Clear a specific task state\n/db <command>: Database operations (schema, query, test, etc.)\n/help [command]: Show available commands\n\nType /help <command> for more information on a specific command.",
        "success": true
      },
      "timestamp": "2025-06-01T18:39:30.267177"
    }
  ],
  "timestamp": 1748774370.3682508
};

console.log('Testing batch message processing...');

// Simulate the batch processing logic from the WebSocket client
function processSingleMessage(message) {
    const type = message.type;
    console.log(`Processing message type: ${type}`);
    
    if (type === 'command_result') {
        console.log('✅ Found command_result in batch!');
        console.log('Command:', message.content.command);
        console.log('Success:', message.content.success);
        console.log('Result length:', message.content.result.length);
        console.log('First 100 chars:', message.content.result.substring(0, 100));
        return true;
    }
    return false;
}

// Test batch processing
if (batchMessage.type === "batch" && batchMessage.messages && Array.isArray(batchMessage.messages)) {
    console.log(`✅ Batch message detected with ${batchMessage.messages.length} messages`);
    
    let foundCommandResult = false;
    batchMessage.messages.forEach((batchedMessage) => {
        if (processSingleMessage(batchedMessage)) {
            foundCommandResult = true;
        }
    });
    
    if (foundCommandResult) {
        console.log('🎉 SUCCESS: Batch processing extracted command_result correctly!');
    } else {
        console.log('❌ FAILED: No command_result found in batch');
    }
} else {
    console.log('❌ FAILED: Not a valid batch message');
}