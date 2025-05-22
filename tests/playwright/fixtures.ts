import { test as base } from '@playwright/test';
import type { Page } from '@playwright/test';

// VSCode Simulation fixture
export type VSCodeFixture = {
  openVSCode: () => Promise<Page>;
  openCommandPalette: (page: Page) => Promise<void>;
  selectCommand: (page: Page, command: string) => Promise<void>;
  getTerminalContent: (page: Page) => Promise<string>;
  sendTerminalCommand: (page: Page, command: string) => Promise<void>;
  clickStatusBarItem: (page: Page, itemName: string) => Promise<void>;
  openChatWindow: (page: Page) => Promise<void>;
  sendChatMessage: (page: Page, message: string) => Promise<void>;
  getChatHistory: (page: Page) => Promise<string[]>;
  waitForProgress: (page: Page, phase: string, status: string) => Promise<void>;
};

// Define the test with our custom fixture
export const test = base.extend({
  openVSCode: async ({ page }, use) => {
    // This is a simulation since actual VS Code extension testing requires 
    // the VS Code Extension Testing API which is beyond the scope of Playwright
    const openVSCode = async () => {
      await page.goto('about:blank');
      // Simulate VS Code appearance
      await page.setContent(`
        <div id="vscode-app" style="height: 100vh; display: flex; flex-direction: column;">
          <div id="titlebar" style="height: 30px; background: #333; color: white; display: flex; align-items: center; padding: 0 10px;">
            Visual Studio Code
          </div>
          <div id="main" style="display: flex; flex: 1; overflow: hidden;">
            <div id="sidebar" style="width: 50px; background: #252526;"></div>
            <div id="editor-container" style="flex: 1; display: flex; flex-direction: column;">
              <div id="editor" style="flex: 1; background: #1e1e1e; color: #d4d4d4; padding: 10px; font-family: monospace;">// Welcome to VS Code simulation</div>
              <div id="terminal" style="height: 200px; background: #1e1e1e; color: #d4d4d4; border-top: 1px solid #454545; padding: 10px; font-family: monospace; white-space: pre; overflow: auto;">
                <div id="terminal-content">Agent-S3 Terminal Ready...</div>
                <div id="terminal-input" contenteditable="true" style="outline: none; border: none;"></div>
              </div>
            </div>
          </div>
          <div id="statusbar" style="height: 22px; background: #007acc; color: white; display: flex; align-items: center; padding: 0 10px;">
            <div class="status-item" data-name="agent-s3" style="margin-right: 10px; cursor: pointer;">$(sparkle) Agent-S3</div>
          </div>
        </div>
      `);
      
      // Add chat UI container (initially hidden)
      await page.evaluate(() => {
        const chatContainer = document.createElement('div');
        chatContainer.id = 'chat-container';
        chatContainer.style.position = 'absolute';
        chatContainer.style.top = '50px';
        chatContainer.style.right = '20px';
        chatContainer.style.width = '300px';
        chatContainer.style.height = '400px';
        chatContainer.style.background = '#252526';
        chatContainer.style.border = '1px solid #454545';
        chatContainer.style.display = 'none';
        chatContainer.style.flexDirection = 'column';
        chatContainer.style.zIndex = '1000';
        
        chatContainer.innerHTML = `
          <div id="chat-title" style="padding: 8px; background: #333; color: white; font-weight: bold;">Agent-S3 Chat</div>
          <div id="chat-messages" style="flex: 1; overflow-y: auto; padding: 10px;"></div>
          <div id="chat-input-container" style="padding: 10px; border-top: 1px solid #454545; display: flex;">
            <input id="chat-input" type="text" placeholder="Type a message..." 
                   style="flex: 1; background: #3c3c3c; color: white; border: none; padding: 5px;">
            <button id="chat-send" style="margin-left: 5px; background: #007acc; color: white; border: none; padding: 5px 10px;">Send</button>
          </div>
        `;
        
        document.body.appendChild(chatContainer);
      });
      
      return page;
    };

    await use(openVSCode);
  },

  openCommandPalette: async ({}, use) => {
    const openCommandPalette = async (page: Page) => {
      // Simulate opening command palette with Ctrl+Shift+P
      await page.evaluate(() => {
        const palette = document.createElement('div');
        palette.id = 'command-palette';
        palette.style.position = 'absolute';
        palette.style.top = '100px';
        palette.style.left = '50%';
        palette.style.transform = 'translateX(-50%)';
        palette.style.width = '500px';
        palette.style.background = '#252526';
        palette.style.border = '1px solid #454545';
        palette.style.zIndex = '1000';
        
        palette.innerHTML = `
          <div style="padding: 10px;">
            <input id="command-input" type="text" placeholder="Type a command..." 
                   style="width: 100%; background: #3c3c3c; color: white; border: none; padding: 5px;">
            <div id="command-list" style="margin-top: 10px; max-height: 300px; overflow-y: auto;"></div>
          </div>
        `;
        
        document.body.appendChild(palette);
        
        // Add some default commands
        const commandList = document.getElementById('command-list');
        const commands = [
          'Agent-S3: Initialize workspace',
          'Agent-S3: Make change request',
          'Agent-S3: Show help',
          'Agent-S3: Open Chat Window'
        ];
        
        commands.forEach(cmd => {
          const cmdEl = document.createElement('div');
          cmdEl.className = 'command-item';
          cmdEl.textContent = cmd;
          cmdEl.style.padding = '5px';
          cmdEl.style.cursor = 'pointer';
          cmdEl.style.color = 'white';
          cmdEl.addEventListener('mouseover', () => {
            cmdEl.style.background = '#04395e';
          });
          cmdEl.addEventListener('mouseout', () => {
            cmdEl.style.background = 'transparent';
          });
          commandList?.appendChild(cmdEl);
        });
      });
    };

    await use(openCommandPalette);
  },

  selectCommand: async ({}, use) => {
    const selectCommand = async (page: Page, command: string) => {
      // Find and click the command
      await page.click(`text="${command}"`);
      
      // Dismiss command palette
      await page.evaluate(() => {
        const palette = document.getElementById('command-palette');
        if (palette) {
          palette.remove();
        }
      });
      
      // Simulate the execution effects based on the command
      if (command === 'Agent-S3: Initialize workspace') {
        await page.evaluate(() => {
          const terminal = document.getElementById('terminal-content');
          if (terminal) {
            terminal.textContent += '\n$ python -m agent_s3.cli /init\nInitializing workspace...\nChecking for essential files...\nWorkspace initialized successfully.';
          }
        });
      } else if (command === 'Agent-S3: Make change request') {
        await page.evaluate(() => {
          // Create an input box
          const inputBox = document.createElement('div');
          inputBox.id = 'input-box';
          inputBox.style.position = 'absolute';
          inputBox.style.top = '100px';
          inputBox.style.left = '50%';
          inputBox.style.transform = 'translateX(-50%)';
          inputBox.style.width = '500px';
          inputBox.style.padding = '10px';
          inputBox.style.background = '#252526';
          inputBox.style.border = '1px solid #454545';
          inputBox.style.zIndex = '1000';
          
          inputBox.innerHTML = `
            <div style="margin-bottom: 10px; color: white;">Enter your change request:</div>
            <input id="request-input" type="text" 
                   style="width: 100%; background: #3c3c3c; color: white; border: none; padding: 5px;">
            <div style="display: flex; justify-content: flex-end; margin-top: 10px;">
              <button id="request-cancel" style="margin-right: 5px; background: #3c3c3c; color: white; border: none; padding: 5px 10px;">Cancel</button>
              <button id="request-ok" style="background: #007acc; color: white; border: none; padding: 5px 10px;">OK</button>
            </div>
          `;
          
          document.body.appendChild(inputBox);
          
          // Focus the input
          const input = document.getElementById('request-input') as HTMLInputElement;
          if (input) {
            input.focus();
          }
          
          // Set up button listeners
          const okButton = document.getElementById('request-ok');
          const cancelButton = document.getElementById('request-cancel');
          
          if (okButton) {
            okButton.addEventListener('click', () => {
              if (input && input.value) {
                const terminal = document.getElementById('terminal-content');
                if (terminal) {
                  terminal.textContent += `\n$ python -m agent_s3.cli "${input.value}"\nProcessing request: ${input.value}\nStarting planning phase...`;
                }
                inputBox.remove();
              }
            });
          }
          
          if (cancelButton) {
            cancelButton.addEventListener('click', () => {
              inputBox.remove();
            });
          }
        });
      } else if (command === 'Agent-S3: Open Chat Window') {
        await page.evaluate(() => {
          const chatContainer = document.getElementById('chat-container');
          if (chatContainer) {
            chatContainer.style.display = 'flex';
          }
        });
      } else if (command === 'Agent-S3: Show help') {
        await page.evaluate(() => {
          const terminal = document.getElementById('terminal-content');
          if (terminal) {
            terminal.textContent += '\n$ python -m agent_s3.cli /help\n\nAgent-S3 Command-Line Interface\n\nCommands:\n  agent-s3 <prompt>        - Process a change request\n  agent-s3 /init           - Initialize the workspace\n  agent-s3 /help           - Display this help message\n  agent-s3 /config         - Show current configuration\n  agent-s3 /reload-llm-config - Reload LLM configuration\n  agent-s3 /explain        - Explain the last LLM interaction';
          }
        });
      }
    };

    await use(selectCommand);
  },

  getTerminalContent: async ({}, use) => {
    const getTerminalContent = async (page: Page) => {
      return page.evaluate(() => {
        const terminal = document.getElementById('terminal-content');
        return terminal ? terminal.textContent || '' : '';
      });
    };

    await use(getTerminalContent);
  },

  sendTerminalCommand: async ({}, use) => {
    const sendTerminalCommand = async (page: Page, command: string) => {
      // Type the command in the terminal
      await page.evaluate((cmd) => {
        const input = document.getElementById('terminal-input');
        if (input) {
          input.textContent = cmd;
        }
      }, command);
      
      // Simulate pressing Enter
      await page.evaluate((cmd) => {
        const terminal = document.getElementById('terminal-content');
        if (terminal) {
          terminal.textContent += `\n$ ${cmd}\n`;
          
          // Simulate command execution
          if (cmd.includes('/init')) {
            terminal.textContent += 'Initializing workspace...\nChecking for essential files...\nWorkspace initialized successfully.';
          } else if (cmd.includes('/help')) {
            terminal.textContent += '\nAgent-S3 Command-Line Interface\n\nCommands:\n  agent-s3 <prompt>        - Process a change request\n  agent-s3 /init           - Initialize the workspace\n  agent-s3 /help           - Display this help message\n  agent-s3 /config         - Show current configuration\n  agent-s3 /reload-llm-config - Reload LLM configuration\n  agent-s3 /explain        - Explain the last LLM interaction';
          } else if (cmd.startsWith('python -m agent_s3.cli "')) {
            const request = cmd.match(/"(.+)"/)?.[1] || '';
            terminal.textContent += `Processing request: ${request}\nStarting planning phase...`;
          }
        }
        
        // Clear the input field
        const input = document.getElementById('terminal-input');
        if (input) {
          input.textContent = '';
        }
      }, command);
    };

    await use(sendTerminalCommand);
  },

  clickStatusBarItem: async ({}, use) => {
    const clickStatusBarItem = async (page: Page, itemName: string) => {
      await page.click(`.status-item[data-name="${itemName}"]`);
      
      // Simulate opening the input box when clicking the Agent-S3 status bar item
      if (itemName === 'agent-s3') {
        await page.evaluate(() => {
          // Create an input box
          const inputBox = document.createElement('div');
          inputBox.id = 'input-box';
          inputBox.style.position = 'absolute';
          inputBox.style.top = '100px';
          inputBox.style.left = '50%';
          inputBox.style.transform = 'translateX(-50%)';
          inputBox.style.width = '500px';
          inputBox.style.padding = '10px';
          inputBox.style.background = '#252526';
          inputBox.style.border = '1px solid #454545';
          inputBox.style.zIndex = '1000';
          
          inputBox.innerHTML = `
            <div style="margin-bottom: 10px; color: white;">Enter your change request:</div>
            <input id="request-input" type="text" 
                   style="width: 100%; background: #3c3c3c; color: white; border: none; padding: 5px;">
            <div style="display: flex; justify-content: flex-end; margin-top: 10px;">
              <button id="request-cancel" style="margin-right: 5px; background: #3c3c3c; color: white; border: none; padding: 5px 10px;">Cancel</button>
              <button id="request-ok" style="background: #007acc; color: white; border: none; padding: 5px 10px;">OK</button>
            </div>
          `;
          
          document.body.appendChild(inputBox);
          
          // Focus the input
          const input = document.getElementById('request-input') as HTMLInputElement;
          if (input) {
            input.focus();
          }
          
          // Set up button listeners
          const okButton = document.getElementById('request-ok');
          const cancelButton = document.getElementById('request-cancel');
          
          if (okButton) {
            okButton.addEventListener('click', () => {
              if (input && input.value) {
                const terminal = document.getElementById('terminal-content');
                if (terminal) {
                  terminal.textContent += `\n$ python -m agent_s3.cli "${input.value}"\nProcessing request: ${input.value}\nStarting planning phase...`;
                }
                inputBox.remove();
              }
            });
          }
          
          if (cancelButton) {
            cancelButton.addEventListener('click', () => {
              inputBox.remove();
            });
          }
        });
      }
    };

    await use(clickStatusBarItem);
  },

  openChatWindow: async ({}, use) => {
    const openChatWindow = async (page: Page) => {
      await page.evaluate(() => {
        const chatContainer = document.getElementById('chat-container');
        if (chatContainer) {
          chatContainer.style.display = 'flex';
        }
      });
    };

    await use(openChatWindow);
  },

  sendChatMessage: async ({}, use) => {
    const sendChatMessage = async (page: Page, message: string) => {
      // Type the message
      await page.fill('#chat-input', message);
      
      // Click send button
      await page.click('#chat-send');
      
      // Simulate message being added to chat
      await page.evaluate((msg) => {
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
          // Add user message
          const userMsg = document.createElement('div');
          userMsg.className = 'chat-message user-message';
          userMsg.textContent = msg;
          userMsg.style.marginBottom = '10px';
          userMsg.style.padding = '8px';
          userMsg.style.background = '#2d4d5b';
          userMsg.style.borderRadius = '5px';
          userMsg.style.alignSelf = 'flex-end';
          userMsg.style.maxWidth = '80%';
          chatMessages.appendChild(userMsg);
          
          // Also add to terminal
          const terminal = document.getElementById('terminal-content');
          if (terminal) {
            if (msg.startsWith('/')) {
              terminal.textContent += `\n$ python -m agent_s3.cli ${msg}\n`;
              
              // Simulate command response
              if (msg === '/help') {
                terminal.textContent += 'Agent-S3 Command-Line Interface\n\nCommands:\n  agent-s3 <prompt>        - Process a change request\n  agent-s3 /init           - Initialize the workspace\n  agent-s3 /help           - Display this help message\n  agent-s3 /config         - Show current configuration\n  agent-s3 /reload-llm-config - Reload LLM configuration\n  agent-s3 /explain        - Explain the last LLM interaction';
              } else if (msg === '/init') {
                terminal.textContent += 'Initializing workspace...\nChecking for essential files...\nWorkspace initialized successfully.';
              }
            } else {
              terminal.textContent += `\n$ python -m agent_s3.cli "${msg}"\nProcessing request: ${msg}\nStarting planning phase...\n`;
            }
          }
          
          // Simulate agent response after a delay
          setTimeout(() => {
            const agentMsg = document.createElement('div');
            agentMsg.className = 'chat-message agent-message';
            agentMsg.textContent = msg.startsWith('/') 
              ? 'Command processed. Check the terminal for output.' 
              : 'I\'ll help you with that request. See the terminal for details on my progress.';
            agentMsg.style.marginBottom = '10px';
            agentMsg.style.padding = '8px';
            agentMsg.style.background = '#3c3c3c';
            agentMsg.style.borderRadius = '5px';
            agentMsg.style.alignSelf = 'flex-start';
            agentMsg.style.maxWidth = '80%';
            chatMessages.appendChild(agentMsg);
            
            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
          }, 500);
        }
      }, message);
    };

    await use(sendChatMessage);
  },

  getChatHistory: async ({}, use) => {
    const getChatHistory = async (page: Page) => {
      return page.evaluate(() => {
        const chatMessages = document.getElementById('chat-messages');
        const messages: string[] = [];
        
        if (chatMessages) {
          const messageElements = chatMessages.querySelectorAll('.chat-message');
          messageElements.forEach(el => {
            messages.push(el.textContent || '');
          });
        }
        
        return messages;
      });
    };

    await use(getChatHistory);
  },

  waitForProgress: async ({}, use) => {
    const waitForProgress = async (page: Page, phase: string, status: string) => {
      // Update status bar to reflect progress
      await page.evaluate((p, s) => {
        const statusBar = document.querySelector('.status-item[data-name="agent-s3"]');
        if (statusBar) {
          statusBar.textContent = `$(sparkle) Agent-S3: ${p} - ${s}`;
        }
        
        // Also update terminal with progress info
        const terminal = document.getElementById('terminal-content');
        if (terminal) {
          terminal.textContent += `\n[Progress] Phase: ${p}, Status: ${s}`;
        }
      }, phase, status);
    };

    await use(waitForProgress);
  },
});

export { expect } from '@playwright/test';