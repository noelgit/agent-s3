jest.mock('vscode', () => ({
  workspace: {
    workspaceFolders: [{ uri: { fsPath: '/tmp' } }],
    getConfiguration: () => ({ get: () => 10 }),
    fs: { readFile: jest.fn(() => Promise.reject(new Error('no file'))) }
  },
  window: {
    showInformationMessage: jest.fn(),
    showWarningMessage: jest.fn(),
    showErrorMessage: jest.fn(),
    createTerminal: jest.fn(() => ({ show: jest.fn() }))
  },
  Uri: { joinPath: jest.fn(() => ({ fsPath: '/tmp/.agent_s3_http_connection.json' })) },
  commands: { registerCommand: jest.fn() },
  EventEmitter: jest.fn().mockImplementation(() => ({ event: jest.fn(), fire: jest.fn(), dispose: jest.fn() }))
}), { virtual: true });

const { executeAgentCommand, tryHttpCommand } = require('../extension');
const vscode = require('vscode');

const mockedVscode = vscode;

describe('HTTP command timeout handling', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn(url => {
      if (url.includes('/health')) {
        return Promise.resolve({ ok: true });
      }
      return Promise.reject({ name: 'AbortError' });
    });
    process.env.AGENT_S3_HTTP_TIMEOUT = '1';
  });

  test('tryHttpCommand returns processing result on timeout', async () => {
    const result = await tryHttpCommand('/help');
    expect(result).toEqual({ result: 'Processing...', output: '', success: null });
  });

  test('executeAgentCommand shows processing notice and resolves', async () => {
    await expect(executeAgentCommand('/help')).resolves.toBeUndefined();
    expect(mockedVscode.window.showInformationMessage).toHaveBeenCalledWith('Processing...');
    expect(mockedVscode.window.showErrorMessage).not.toHaveBeenCalled();
  });
});
