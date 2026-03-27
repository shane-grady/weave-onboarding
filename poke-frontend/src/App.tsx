import { useState, useCallback } from 'react';
import { ConnectScreen } from './components/ConnectScreen';
import { LoadingScreen } from './components/LoadingScreen';
import { ChatScreen } from './components/ChatScreen';
import { api } from './api';
import type { ConnectionData, ResearchData } from './types';

type AppState = 'connect' | 'loading' | 'chat';

function App() {
  const [state, setState] = useState<AppState>('connect');
  const [researchData, setResearchData] = useState<ResearchData | null>(null);
  const [openingMessage, setOpeningMessage] = useState('');
  const [userId, setUserId] = useState('');
  const [isResearchDone, setIsResearchDone] = useState(false);

  const handleConnected = useCallback(async (data: ConnectionData) => {
    setState('loading');
    setUserId(data.userId);

    // Fire research (returns immediately)
    try {
      await api.research(data.userId);
    } catch {
      setResearchData({ first_name: 'there', insights: [] });
      setIsResearchDone(true);
      return;
    }

    // Poll for completion
    const poll = setInterval(async () => {
      try {
        const result = await api.getResearchStatus(data.userId);
        if (result.status === 'completed') {
          clearInterval(poll);
          setResearchData(result.data || { first_name: 'there', insights: [] });
          setOpeningMessage(result.opening_message || '');
          setIsResearchDone(true);
        } else if (result.status === 'error') {
          clearInterval(poll);
          setResearchData({ first_name: 'there', insights: [] });
          setIsResearchDone(true);
        }
      } catch {
        // keep polling on network errors
      }
    }, 2000);
  }, []);

  const handleLoadingComplete = useCallback(() => {
    if (researchData) {
      setState('chat');
    }
  }, [researchData]);

  return (
    <div className="h-full" style={{ background: 'var(--bg)' }}>
      {state === 'connect' && <ConnectScreen onConnected={handleConnected} />}
      {state === 'loading' && (
        <LoadingScreen onComplete={handleLoadingComplete} isResearchDone={isResearchDone} />
      )}
      {state === 'chat' && researchData && (
        <ChatScreen data={researchData} openingMessage={openingMessage} userId={userId} />
      )}
    </div>
  );
}

export default App;
