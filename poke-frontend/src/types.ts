export interface Insight {
  label: string;
  value: string;
}

export interface ResearchData {
  first_name: string;
  full_name?: string;
  insights: Insight[];
}

export interface ResearchStatus {
  status: string;
  data?: ResearchData;
  opening_message?: string;
}

export interface ChatMessage {
  id: string;
  content: string;
  response?: string;
  status: string;
  isUser: boolean;
}

export interface ConnectionData {
  userId: string;
  connectionId: string;
  redirectUrl?: string;
}
