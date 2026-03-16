export interface Insight {
  label: string;
  value: string;
}

export interface ResearchData {
  first_name: string;
  full_name?: string;
  insights: Insight[];
}

export interface ConnectionData {
  userId: string;
  connectionId: string;
  redirectUrl?: string;
}
