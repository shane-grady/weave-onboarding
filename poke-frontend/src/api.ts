const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = {
  async createUser(connectionId: string): Promise<{ user_id: string }> {
    const res = await fetch(`${API_BASE_URL}/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ connection_id: connectionId }),
    });
    if (!res.ok) throw new Error('Failed to create user');
    return res.json();
  },

  async initiateConnection(userId: string, authConfigId?: string): Promise<{
    connection_id: string;
    redirect_url?: string;
  }> {
    const res = await fetch(`${API_BASE_URL}/connections/initiate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, auth_config_id: authConfigId }),
    });
    if (!res.ok) throw new Error('Failed to initiate connection');
    return res.json();
  },

  async checkConnectionStatus(connectionId: string): Promise<{
    status: string;
    connection_id: string;
  }> {
    const res = await fetch(`${API_BASE_URL}/connections/${connectionId}/status`);
    if (!res.ok) throw new Error('Failed to check status');
    return res.json();
  },

  async research(userId: string): Promise<{
    status: string;
    data: { first_name: string; full_name?: string; insights: Array<{ label: string; value: string }> };
  }> {
    const res = await fetch(`${API_BASE_URL}/research/${userId}`, { method: 'POST' });
    if (!res.ok) throw new Error('Research failed');
    return res.json();
  },

  async getResearchStatus(userId: string): Promise<{
    status: string;
    data?: { first_name: string; full_name?: string; insights: Array<{ label: string; value: string }> };
  }> {
    const res = await fetch(`${API_BASE_URL}/research/${userId}/status`);
    if (!res.ok) throw new Error('Failed to get research status');
    return res.json();
  },
};
