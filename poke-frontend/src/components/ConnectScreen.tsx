import { useState } from 'react';
import { api } from '../api';
import type { ConnectionData } from '../types';

const AUTH_CONFIG_ID = import.meta.env.VITE_AUTH_CONFIG_ID || 'ac_JO3RFglIYYKs';

interface Props {
  onConnected: (data: ConnectionData) => void;
}

export function ConnectScreen({ onConnected }: Props) {
  const [phase, setPhase] = useState<'idle' | 'waiting' | 'error'>('idle');
  const [connectionData, setConnectionData] = useState<ConnectionData | null>(null);
  const [error, setError] = useState('');

  const handleConnect = async () => {
    setPhase('waiting');
    setError('');

    try {
      const userId = `user_${Date.now()}`;
      await api.createUser(userId);
      const conn = await api.initiateConnection(userId, AUTH_CONFIG_ID);

      const data: ConnectionData = {
        userId,
        connectionId: conn.connection_id,
        redirectUrl: conn.redirect_url,
      };
      setConnectionData(data);

      if (conn.redirect_url) {
        window.open(conn.redirect_url, '_blank', 'width=600,height=700');
      } else {
        onConnected(data);
      }
    } catch {
      setError('Connection failed. Please try again.');
      setPhase('error');
    }
  };

  const handleAuthDone = async () => {
    if (!connectionData) return;
    try {
      const status = await api.checkConnectionStatus(connectionData.connectionId);
      if (status.status === 'ACTIVE' || status.status === 'connected') {
        onConnected(connectionData);
      } else {
        setError('Authorization not yet complete. Please finish the Gmail authorization first.');
      }
    } catch {
      setError('Could not verify connection. Please try again.');
    }
  };

  return (
    <div className="h-full flex flex-col items-center justify-center px-6">
      {/* Logo */}
      <div className="mb-12 fade-in">
        <h1 className="text-5xl font-semibold tracking-tight" style={{ color: 'var(--accent)' }}>
          weave
        </h1>
      </div>

      {/* Main card */}
      <div className="w-full max-w-sm text-center fade-in" style={{ animationDelay: '0.2s' }}>
        {phase === 'idle' || phase === 'error' ? (
          <>
            <p className="text-lg text-neutral-400 mb-8 font-light">
              See what the internet already knows about you.
            </p>
            <button
              onClick={handleConnect}
              className="w-full py-3.5 px-6 rounded-xl font-medium text-white btn-glow"
              style={{ background: 'var(--accent)' }}
            >
              Connect Gmail
            </button>
            {error && (
              <p className="mt-4 text-sm text-red-400">{error}</p>
            )}
          </>
        ) : (
          <>
            <p className="text-lg text-neutral-400 mb-8 font-light">
              Complete the authorization in the popup, then come back here.
            </p>
            <button
              onClick={handleAuthDone}
              className="w-full py-3.5 px-6 rounded-xl font-medium text-white btn-glow"
              style={{ background: 'var(--accent)' }}
            >
              I've authorized Gmail
            </button>
            {connectionData?.redirectUrl && (
              <a
                href={connectionData.redirectUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="block mt-3 text-sm text-neutral-500 hover:text-neutral-300 transition-colors"
              >
                Reopen authorization window
              </a>
            )}
            {error && (
              <p className="mt-4 text-sm text-red-400">{error}</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
