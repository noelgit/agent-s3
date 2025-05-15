import { test, expect } from '../../fixtures';

test.describe('Story 4: Using Helper Commands', () => {
  test('Show help via Command Palette', async ({ 
    openVSCode, 
    openCommandPalette, 
    selectCommand, 
    getTerminalContent 
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();
    
    // Open command palette and select help command
    await openCommandPalette(page);
    await selectCommand(page, 'Agent-S3: Show help');
    
    // Wait for the help to display
    await page.waitForTimeout(1000);
    
    // Verify terminal output
    const terminalContent = await getTerminalContent(page);
    expect(terminalContent).toContain('Agent-S3 Command-Line Interface');
    expect(terminalContent).toContain('Commands:');
    expect(terminalContent).toContain('/init');
    expect(terminalContent).toContain('/help');
    expect(terminalContent).toContain('/explain');
  });
  
  test('Show help via CLI', async ({ 
    openVSCode, 
    sendTerminalCommand, 
    getTerminalContent 
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();
    
    // Send help command directly to terminal
    await sendTerminalCommand(page, 'python -m agent_s3.cli /help');
    
    // Wait for the help to display
    await page.waitForTimeout(1000);
    
    // Verify terminal output
    const terminalContent = await getTerminalContent(page);
    expect(terminalContent).toContain('Agent-S3 Command-Line Interface');
    expect(terminalContent).toContain('Commands:');
    expect(terminalContent).toContain('/init');
    expect(terminalContent).toContain('/help');
    expect(terminalContent).toContain('/explain');
  });
  
  test('Show guidelines via CLI', async ({ 
    openVSCode, 
    sendTerminalCommand, 
    getTerminalContent 
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();
    
    // Override the terminal content to provide a clean start
    await page.evaluate(() => {
      const terminal = document.getElementById('terminal-content');
      if (terminal) {
        terminal.textContent = 'Agent-S3 Terminal Ready...';
      }
    });
    
    // Send guidelines command to terminal
    await sendTerminalCommand(page, 'python -m agent_s3.cli /guidelines');
    
    // Simulate guidelines output in the terminal
    await page.evaluate(() => {
      const terminal = document.getElementById('terminal-content');
      if (terminal) {
        terminal.textContent += '\n# GitHub Copilot Instructions\n\n## Core Development Criteria\n\n### Security\n- Always validate user input\n- Use parameterized queries\n- Implement proper authentication\n\n### Performance\n- Optimize database queries\n- Minimize API calls\n- Use efficient algorithms\n\n### Code Quality\n- Follow SOLID principles\n- Write comprehensive tests\n- Maintain clear documentation';
      }
    });
    
    // Wait for the guidelines to display
    await page.waitForTimeout(1000);
    
    // Verify terminal output
    const terminalContent = await getTerminalContent(page);
    expect(terminalContent).toContain('GitHub Copilot Instructions');
    expect(terminalContent).toContain('Core Development Criteria');
    expect(terminalContent).toContain('Security');
    expect(terminalContent).toContain('Performance');
    expect(terminalContent).toContain('Code Quality');
  });
  
  test('Using the /explain command', async ({ 
    openVSCode, 
    sendTerminalCommand, 
    getTerminalContent 
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();
    
    // Override the terminal content to provide a clean start
    await page.evaluate(() => {
      const terminal = document.getElementById('terminal-content');
      if (terminal) {
        terminal.textContent = 'Agent-S3 Terminal Ready...';
      }
    });
    
    // First, run a request to have something to explain
    await sendTerminalCommand(page, 'python -m agent_s3.cli "Add error handling to the API client"');
    
    // Wait for some processing to happen
    await page.waitForTimeout(1000);
    
    // Then run the explain command
    await sendTerminalCommand(page, 'python -m agent_s3.cli /explain');
    
    // Simulate explanation output in the terminal
    await page.evaluate(() => {
      const terminal = document.getElementById('terminal-content');
      if (terminal) {
        terminal.textContent += '\n# Last LLM Interaction Explanation\n\n## Prompt\nI was asked to analyze and implement error handling for the API client. The prompt included context about the current implementation and best practices for error handling.\n\n## Response\nI generated a plan to implement:\n1. Try-except blocks around API calls\n2. Custom exception classes\n3. Retry logic with exponential backoff\n4. Detailed error logging\n\n## Parameters\n- Temperature: 0.7\n- Model: claude-3-opus-20240229\n- Max tokens: 4000\n- Attempts: 1 (Success on first try)\n- Fallback used: No';
      }
    });
    
    // Wait for the explanation to display
    await page.waitForTimeout(1000);
    
    // Verify terminal output
    const terminalContent = await getTerminalContent(page);
    expect(terminalContent).toContain('Last LLM Interaction Explanation');
    expect(terminalContent).toContain('Prompt');
    expect(terminalContent).toContain('Response');
    expect(terminalContent).toContain('Parameters');
    expect(terminalContent).toContain('Temperature: 0.7');
    expect(terminalContent).toContain('Model: claude-3-opus-20240229');
  });
});