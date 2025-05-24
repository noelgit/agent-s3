import { test, expect } from "../fixtures";

test.describe("Story 3: Interacting via the Chat UI", () => {
  test("Open chat window via Command Palette", async ({
    openVSCode,
    openCommandPalette,
    selectCommand,
    openChatWindow,
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();

    // Open command palette and select chat window command
    await openCommandPalette(page);
    await selectCommand(page, "Agent-S3: Open Chat Window");

    // Verify the chat window is visible
    const isChatVisible = await page.evaluate(() => {
      const chatContainer = document.getElementById("chat-container");
      return (
        chatContainer && (chatContainer as HTMLElement).style.display === "flex"
      );
    });

    expect(isChatVisible).toBe(true);
  });

  test("Send command via Chat UI", async ({
    openVSCode,
    openChatWindow,
    sendChatMessage,
    getChatHistory,
    getTerminalContent,
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();

    // Open chat window
    await openChatWindow(page);

    // Send a command message
    await sendChatMessage(page, "/help");

    // Wait for the response
    await page.waitForTimeout(1000);

    // Verify chat history
    const chatHistory = await getChatHistory(page);
    expect(chatHistory.length).toBe(2); // User message + agent response
    expect(chatHistory[0]).toBe("/help");
    expect(chatHistory[1]).toContain("Command processed");

    // Verify terminal content
    const terminalContent = await getTerminalContent(page);
    expect(terminalContent).toContain("python -m agent_s3.cli /help");
    expect(terminalContent).toContain("Agent-S3 Command-Line Interface");
  });

  test("Send change request via Chat UI", async ({
    openVSCode,
    openChatWindow,
    sendChatMessage,
    getChatHistory,
    getTerminalContent,
    waitForProgress,
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();

    // Open chat window
    await openChatWindow(page);

    // Send a change request message
    await sendChatMessage(page, "Add input validation to the login form");

    // Wait for the response
    await page.waitForTimeout(1000);

    // Verify chat history
    const chatHistory = await getChatHistory(page);
    expect(chatHistory.length).toBe(2); // User message + agent response
    expect(chatHistory[0]).toBe("Add input validation to the login form");
    expect(chatHistory[1]).toContain("I'll help you with that request");

    // Verify terminal content shows the command was executed
    const terminalContent = await getTerminalContent(page);
    expect(terminalContent).toContain(
      'python -m agent_s3.cli "Add input validation to the login form"',
    );
    expect(terminalContent).toContain(
      "Processing request: Add input validation to the login form",
    );

    // Simulate progress updates
    await waitForProgress(page, "planning", "started");
    await page.waitForTimeout(500);
    await waitForProgress(page, "planning", "plan_generated");

    // Check terminal again to verify progress updates
    const updatedTerminalContent = await getTerminalContent(page);
    expect(updatedTerminalContent).toContain(
      "Phase: planning, Status: started",
    );
    expect(updatedTerminalContent).toContain(
      "Phase: planning, Status: plan_generated",
    );
  });

  test("Saving and loading chat history", async ({
    openVSCode,
    openChatWindow,
    sendChatMessage,
    getChatHistory,
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();

    // Open chat window
    await openChatWindow(page);

    // Send multiple messages
    await sendChatMessage(page, "Hello Agent-S3");
    await page.waitForTimeout(600);
    await sendChatMessage(page, "Can you help me improve error handling?");
    await page.waitForTimeout(600);
    await sendChatMessage(page, "/guidelines");
    await page.waitForTimeout(600);

    // Verify chat history has all messages
    const chatHistory = await getChatHistory(page);
    expect(chatHistory.length).toBe(6); // 3 user messages + 3 agent responses

    // Simulate closing and reopening the chat window (which should maintain history)
    await page.evaluate(() => {
      const chatContainer = document.getElementById("chat-container");
      if (chatContainer) {
        chatContainer.style.display = "none";
      }
    });

    // Verify chat is hidden
    const isChatHidden = await page.evaluate(() => {
      const chatContainer = document.getElementById("chat-container");
      return (
        chatContainer && (chatContainer as HTMLElement).style.display === "none"
      );
    });
    expect(isChatHidden).toBe(true);

    // Reopen chat window
    await openChatWindow(page);

    // Verify history is still there
    const reloadedChatHistory = await getChatHistory(page);
    expect(reloadedChatHistory.length).toBe(6);
    expect(reloadedChatHistory[0]).toBe("Hello Agent-S3");
    expect(reloadedChatHistory[2]).toBe(
      "Can you help me improve error handling?",
    );
    expect(reloadedChatHistory[4]).toBe("/guidelines");
  });
});
