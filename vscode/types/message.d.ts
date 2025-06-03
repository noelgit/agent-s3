export interface ChatHistoryEntry {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

export interface Message {
  type: string;
  data?: any;
  timestamp?: string;
}

export interface CommandMessage extends Message {
  type: 'command';
  data: {
    command: string;
    args?: string[];
  };
}

export interface ResponseMessage extends Message {
  type: 'response';
  data: {
    result: string;
    success: boolean;
  };
}