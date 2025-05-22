import { test, expect } from '../fixtures';

test.describe('Story 2: Making a Code Change Request', () => {
  test('Make change request via Command Palette', async ({ 
    openVSCode, 
    openCommandPalette, 
    selectCommand, 
    getTerminalContent,
    waitForProgress 
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();
    
    // Open command palette and select make change request command
    await openCommandPalette(page);
    await selectCommand(page, 'Agent-S3: Make change request');
    
    // Enter the change request in the input box
    await page.fill('#request-input', 'Add unit tests for the code generator module');
    await page.click('#request-ok');
    
    // Wait for the planning phase to start
    await page.waitForTimeout(1000);
    
    // Simulate progress updates
    await waitForProgress(page, 'planning', 'started');
    await page.waitForTimeout(500);
    await waitForProgress(page, 'planning', 'plan_generated');
    await page.waitForTimeout(500);
    await waitForProgress(page, 'prompt_approval', 'waiting');
    
    // Verify terminal output
    const terminalContent = await getTerminalContent(page);
    expect(terminalContent).toContain('Processing request: Add unit tests for the code generator module');
    expect(terminalContent).toContain('Starting planning phase');
    expect(terminalContent).toContain('Phase: planning, Status: plan_generated');
  });
  
  test('Make change request via status bar item', async ({ 
    openVSCode, 
    clickStatusBarItem, 
    getTerminalContent,
    waitForProgress 
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();
    
    // Click the Agent-S3 status bar item
    await clickStatusBarItem(page, 'agent-s3');
    
    // Enter the change request in the input box
    await page.fill('#request-input', 'Implement error handling for API calls');
    await page.click('#request-ok');
    
    // Wait for the planning phase to start
    await page.waitForTimeout(1000);
    
    // Simulate progress updates
    await waitForProgress(page, 'planning', 'started');
    await page.waitForTimeout(500);
    await waitForProgress(page, 'planning', 'plan_generated');
    await page.waitForTimeout(500);
    await waitForProgress(page, 'prompt_approval', 'waiting');
    
    // Verify terminal output
    const terminalContent = await getTerminalContent(page);
    expect(terminalContent).toContain('Processing request: Implement error handling for API calls');
    expect(terminalContent).toContain('Starting planning phase');
    expect(terminalContent).toContain('Phase: planning, Status: plan_generated');
  });
  
  test('Make change request via CLI', async ({ 
    openVSCode, 
    sendTerminalCommand, 
    getTerminalContent,
    waitForProgress 
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();
    
    // Send change request command directly to terminal
    await sendTerminalCommand(page, 'python -m agent_s3.cli "Refactor the authentication module"');
    
    // Wait for the planning phase to start
    await page.waitForTimeout(1000);
    
    // Simulate progress updates
    await waitForProgress(page, 'planning', 'started');
    await page.waitForTimeout(500);
    await waitForProgress(page, 'planning', 'plan_generated');
    await page.waitForTimeout(500);
    await waitForProgress(page, 'prompt_approval', 'waiting');
    
    // Verify terminal output
    const terminalContent = await getTerminalContent(page);
    expect(terminalContent).toContain('Processing request: Refactor the authentication module');
    expect(terminalContent).toContain('Starting planning phase');
    expect(terminalContent).toContain('Phase: planning, Status: plan_generated');
  });
  
  test('Complete change request workflow with plan approval', async ({ 
    openVSCode, 
    sendTerminalCommand, 
    getTerminalContent,
    waitForProgress 
  }) => {
    // Open VS Code simulation
    const page = await openVSCode();
    
    // Send change request command directly to terminal
    await sendTerminalCommand(page, 'python -m agent_s3.cli "Add documentation to the file_tool module"');
    
    // Wait for the planning phase to start
    await page.waitForTimeout(1000);
    
    // Simulate progress updates for the full workflow
    await waitForProgress(page, 'planning', 'started');
    await page.waitForTimeout(500);
    await waitForProgress(page, 'planning', 'plan_generated');
    await page.waitForTimeout(500);
    await waitForProgress(page, 'prompt_approval', 'waiting');
    
    // Simulate user plan approval
    await page.evaluate(() => {
      const terminal = document.getElementById('terminal-content');
      if (terminal) {
        terminal.textContent += '\nDo you approve this plan? (y/n/edit): y';
      }
    });
    await page.waitForTimeout(500);
    await waitForProgress(page, 'prompt_approval', 'approved');
    
    // Simulate code generation phase
    await page.waitForTimeout(500);
    await waitForProgress(page, 'code_generation', 'started');
    await page.waitForTimeout(500);
    await waitForProgress(page, 'execution', 'generating');
    
    // Simulate user code approval
    await page.evaluate(() => {
      const terminal = document.getElementById('terminal-content');
      if (terminal) {
        terminal.textContent += '\nDo you approve these changes? (y/n): y';
      }
    });
    await page.waitForTimeout(500);
    await waitForProgress(page, 'execution', 'applying');
    await page.waitForTimeout(500);
    await waitForProgress(page, 'execution', 'testing');
    await page.waitForTimeout(500);
    await waitForProgress(page, 'code_generation', 'completed');
    
    // Verify the terminal contains all the expected workflow messages
    const terminalContent = await getTerminalContent(page);
    expect(terminalContent).toContain('Processing request: Add documentation to the file_tool module');
    expect(terminalContent).toContain('Phase: planning, Status: plan_generated');
    expect(terminalContent).toContain('Do you approve this plan? (y/n/edit): y');
    expect(terminalContent).toContain('Phase: prompt_approval, Status: approved');
    expect(terminalContent).toContain('Phase: code_generation, Status: started');
    expect(terminalContent).toContain('Phase: execution, Status: generating');
    expect(terminalContent).toContain('Do you approve these changes? (y/n): y');
    expect(terminalContent).toContain('Phase: execution, Status: testing');
    expect(terminalContent).toContain('Phase: code_generation, Status: completed');
  });
});