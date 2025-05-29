import * as vscode from "vscode";
import { ChatHistoryEntry } from "./types/message";
import { CHAT_HISTORY_KEY } from "./constants";

interface TaskEntry {
  name: string;
  status: "completed" | "failed" | "running";
  timestamp?: string;
}

/**
 * Tree item for Agent-S3 explorer views
 */
export class Agent3TreeItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly collapsibleState: vscode.TreeItemCollapsibleState,
    public readonly command?: vscode.Command,
    public readonly iconPath?: vscode.ThemeIcon | vscode.Uri | { light: vscode.Uri; dark: vscode.Uri },
    public readonly tooltip?: string,
    public readonly contextValue?: string
  ) {
    super(label, collapsibleState);
    this.command = command;
    this.iconPath = iconPath;
    this.tooltip = tooltip;
    this.contextValue = contextValue;
  }
}

/**
 * Tree data provider for Agent-S3 Chat view
 */
export class Agent3ChatProvider implements vscode.TreeDataProvider<Agent3TreeItem> {
  private _onDidChangeTreeData: vscode.EventEmitter<Agent3TreeItem | undefined | null | void> = new vscode.EventEmitter();
  readonly onDidChangeTreeData: vscode.Event<Agent3TreeItem | undefined | null | void> = this._onDidChangeTreeData.event;

  constructor(private context: vscode.ExtensionContext) {}

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: Agent3TreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: Agent3TreeItem): Thenable<Agent3TreeItem[]> {
    if (!element) {
      // Root level items
      return Promise.resolve(this.getRootItems());
    }
    
    if (element.contextValue === "chatHistory") {
      return Promise.resolve(this.getChatHistoryItems());
    }

    return Promise.resolve([]);
  }

  private getRootItems(): Agent3TreeItem[] {
    const items: Agent3TreeItem[] = [];

    // Quick action buttons
    items.push(
      new Agent3TreeItem(
        "Start New Chat",
        vscode.TreeItemCollapsibleState.None,
        {
          command: "agent-s3.openChatWindow",
          title: "Open Chat Window",
        },
        new vscode.ThemeIcon("comment"),
        "Open a new chat window with Agent-S3",
        "newChat"
      )
    );

    items.push(
      new Agent3TreeItem(
        "Make Change Request", 
        vscode.TreeItemCollapsibleState.None,
        {
          command: "agent-s3.request",
          title: "Make Change Request",
        },
        new vscode.ThemeIcon("edit"),
        "Create a new change request",
        "changeRequest"
      )
    );

    items.push(
      new Agent3TreeItem(
        "Interactive View",
        vscode.TreeItemCollapsibleState.None,
        {
          command: "agent-s3.openInteractiveView", 
          title: "Open Interactive View",
        },
        new vscode.ThemeIcon("preview"),
        "Open the interactive components view",
        "interactiveView"
      )
    );

    // Chat history section
    items.push(
      new Agent3TreeItem(
        "Chat History",
        vscode.TreeItemCollapsibleState.Collapsed,
        undefined,
        new vscode.ThemeIcon("history"),
        "Recent chat conversations",
        "chatHistory"
      )
    );

    return items;
  }

  private getChatHistoryItems(): Agent3TreeItem[] {
    const items: Agent3TreeItem[] = [];
    
    try {
      const chatHistory = this.context.workspaceState.get<ChatHistoryEntry[]>(CHAT_HISTORY_KEY, []);
      
      if (chatHistory.length === 0) {
        items.push(
          new Agent3TreeItem(
            "No chat history",
            vscode.TreeItemCollapsibleState.None,
            undefined,
            new vscode.ThemeIcon("info"),
            "Start a conversation to see history",
            "noHistory"
          )
        );
      } else {
        // Show recent conversations (limit to 10)
        const recentChats = chatHistory.slice(-10).reverse();
        
        for (const entry of recentChats) {
          const timestamp = new Date(entry.timestamp).toLocaleString();
          const preview = entry.content.length > 50 
            ? entry.content.substring(0, 50) + "..."
            : entry.content;
            
          items.push(
            new Agent3TreeItem(
              preview,
              vscode.TreeItemCollapsibleState.None,
              {
                command: "agent-s3.showChatEntry",
                title: "Show Chat Entry",
                arguments: [entry]
              },
              new vscode.ThemeIcon(entry.type === "user" ? "person" : "robot"),
              `${entry.type}: ${entry.content}\n${timestamp}`,
              "chatEntry"
            )
          );
        }
      }
    } catch (error) {
      console.error("Error loading chat history:", error);
      items.push(
        new Agent3TreeItem(
          "Error loading history",
          vscode.TreeItemCollapsibleState.None,
          undefined,
          new vscode.ThemeIcon("error"),
          "Failed to load chat history",
          "error"
        )
      );
    }

    return items;
  }
}

/**
 * Tree data provider for Agent-S3 History view
 */
export class Agent3HistoryProvider implements vscode.TreeDataProvider<Agent3TreeItem> {
  private _onDidChangeTreeData: vscode.EventEmitter<Agent3TreeItem | undefined | null | void> = new vscode.EventEmitter();
  readonly onDidChangeTreeData: vscode.Event<Agent3TreeItem | undefined | null | void> = this._onDidChangeTreeData.event;

  constructor(private context: vscode.ExtensionContext) {}

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: Agent3TreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: Agent3TreeItem): Thenable<Agent3TreeItem[]> {
    if (!element) {
      return Promise.resolve(this.getRootItems());
    }

    if (element.contextValue === "recentTasks") {
      return Promise.resolve(this.getRecentTaskItems());
    }

    if (element.contextValue === "workspaceInfo") {
      return Promise.resolve(this.getWorkspaceInfoItems());
    }

    return Promise.resolve([]);
  }

  private getRootItems(): Agent3TreeItem[] {
    const items: Agent3TreeItem[] = [];

    // Workspace status
    items.push(
      new Agent3TreeItem(
        "Workspace Info",
        vscode.TreeItemCollapsibleState.Collapsed,
        undefined,
        new vscode.ThemeIcon("folder"),
        "Information about the current workspace",
        "workspaceInfo"
      )
    );

    // Recent tasks
    items.push(
      new Agent3TreeItem(
        "Recent Tasks",
        vscode.TreeItemCollapsibleState.Collapsed,
        undefined,
        new vscode.ThemeIcon("list-ordered"),
        "Recently executed Agent-S3 tasks",
        "recentTasks"
      )
    );

    // Quick actions
    items.push(
      new Agent3TreeItem(
        "Initialize Workspace",
        vscode.TreeItemCollapsibleState.None,
        {
          command: "agent-s3.init",
          title: "Initialize Workspace",
        },
        new vscode.ThemeIcon("gear"),
        "Initialize Agent-S3 for this workspace",
        "initWorkspace"
      )
    );

    items.push(
      new Agent3TreeItem(
        "Show Help",
        vscode.TreeItemCollapsibleState.None,
        {
          command: "agent-s3.help",
          title: "Show Help",
        },
        new vscode.ThemeIcon("question"),
        "Show Agent-S3 help information",
        "showHelp"
      )
    );

    items.push(
      new Agent3TreeItem(
        "Show Guidelines",
        vscode.TreeItemCollapsibleState.None,
        {
          command: "agent-s3.guidelines",
          title: "Show Guidelines",
        },
        new vscode.ThemeIcon("book"),
        "Show coding guidelines",
        "showGuidelines"
      )
    );

    return items;
  }

  private getRecentTaskItems(): Agent3TreeItem[] {
    const items: Agent3TreeItem[] = [];

    // Try to load recent tasks from workspace state
    try {
      const recentTasks = this.context.workspaceState.get<TaskEntry[]>("agent-s3.recentTasks", []);
      
      if (recentTasks.length === 0) {
        items.push(
          new Agent3TreeItem(
            "No recent tasks",
            vscode.TreeItemCollapsibleState.None,
            undefined,
            new vscode.ThemeIcon("info"),
            "Execute some Agent-S3 commands to see history",
            "noTasks"
          )
        );
      } else {
        // Show recent tasks (limit to 10)
        const tasks = recentTasks.slice(-10).reverse();
        
        for (const task of tasks) {
          const timestamp = task.timestamp ? new Date(task.timestamp).toLocaleString() : "Unknown time";
          items.push(
            new Agent3TreeItem(
              task.name || "Unknown task",
              vscode.TreeItemCollapsibleState.None,
              undefined,
              new vscode.ThemeIcon(task.status === "completed" ? "check" : task.status === "failed" ? "error" : "clock"),
              `${task.name}\nStatus: ${task.status}\n${timestamp}`,
              "task"
            )
          );
        }
      }
    } catch (error) {
      console.error("Error loading recent tasks:", error);
      items.push(
        new Agent3TreeItem(
          "Error loading tasks",
          vscode.TreeItemCollapsibleState.None,
          undefined,
          new vscode.ThemeIcon("error"),
          "Failed to load task history",
          "error"
        )
      );
    }

    return items;
  }

  private getWorkspaceInfoItems(): Agent3TreeItem[] {
    const items: Agent3TreeItem[] = [];
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];

    if (!workspaceFolder) {
      items.push(
        new Agent3TreeItem(
          "No workspace open",
          vscode.TreeItemCollapsibleState.None,
          undefined,
          new vscode.ThemeIcon("warning"),
          "Open a workspace to use Agent-S3",
          "noWorkspace"
        )
      );
      return items;
    }

    // Workspace name
    items.push(
      new Agent3TreeItem(
        `Workspace: ${workspaceFolder.name}`,
        vscode.TreeItemCollapsibleState.None,
        undefined,
        new vscode.ThemeIcon("folder"),
        `Current workspace: ${workspaceFolder.uri.fsPath}`,
        "workspaceName"
      )
    );

    // Check if Agent-S3 is initialized
    vscode.workspace.fs.stat(
      vscode.Uri.joinPath(workspaceFolder.uri, ".agent-s3")
    ).then(
      () => true,
      () => false
    );

    items.push(
      new Agent3TreeItem(
        "Initialization Status",
        vscode.TreeItemCollapsibleState.None,
        undefined,
        new vscode.ThemeIcon("gear"),
        "Check if Agent-S3 is initialized",
        "initStatus"
      )
    );

    // Connection status
    items.push(
      new Agent3TreeItem(
        "Connection Status",
        vscode.TreeItemCollapsibleState.None,
        {
          command: "agent-s3.testWebSocket",
          title: "Test WebSocket Connection",
        },
        new vscode.ThemeIcon("plug"),
        "Test connection to Agent-S3 backend",
        "connectionStatus"
      )
    );

    return items;
  }
}
