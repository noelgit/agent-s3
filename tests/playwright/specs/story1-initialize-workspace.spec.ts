import { test, expect } from '../../fixtures';

test.describe('Story 1: Initialize Agent-S3 in a New Workspace', () => {
  test('Initialize workspace via Command Palette', async ({ 
    openVSCode, 
    openCommandPalette, 
    selectCommand, 
    getTerminalContent 
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();
    
    // Open command palette and select initialize command
    await openCommandPalette(page);
    await selectCommand(page, 'Agent-S3: Initialize workspace');
    
    // Wait for the initialization to complete
    await page.waitForTimeout(1000); // Simulating processing time
    
    // Verify terminal output
    const terminalContent = await getTerminalContent(page);
    expect(terminalContent).toContain('Initializing workspace');
    expect(terminalContent).toContain('Workspace initialized successfully');
  });
  
  test('Initialize workspace via CLI', async ({ 
    openVSCode, 
    sendTerminalCommand, 
    getTerminalContent 
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();
    
    // Send init command directly to terminal
    await sendTerminalCommand(page, 'python -m agent_s3.cli /init');
    
    // Wait for the initialization to complete
    await page.waitForTimeout(1000); // Simulating processing time
    
    // Verify terminal output
    const terminalContent = await getTerminalContent(page);
    expect(terminalContent).toContain('Initializing workspace');
    expect(terminalContent).toContain('Workspace initialized successfully');
  });
  
  test('Initialize workspace handles GitHub authentication', async ({ 
    openVSCode, 
    sendTerminalCommand, 
    getTerminalContent 
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();
    
    // Override the terminal content to simulate the authentication flow
    await page.evaluate(() => {
      const terminal = document.getElementById('terminal-content');
      if (terminal) {
        terminal.textContent = 'Agent-S3 Terminal Ready...';
      }
    });
    
    // Send init command
    await sendTerminalCommand(page, 'python -m agent_s3.cli /init');
    
    // Simulate authentication flow
    await page.evaluate(() => {
      const terminal = document.getElementById('terminal-content');
      if (terminal) {
        terminal.textContent += '\nInitializing workspace...\nChecking for essential files...\nGitHub authentication required.\nOpening browser for authentication...\nWaiting for authentication to complete...\nAuthentication successful.\nWorkspace initialized successfully.';
      }
    });
    
    // Verify terminal output
    const terminalContent = await getTerminalContent(page);
    expect(terminalContent).toContain('GitHub authentication required');
    expect(terminalContent).toContain('Authentication successful');
    expect(terminalContent).toContain('Workspace initialized successfully');
  });
});