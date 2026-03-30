import { useState, useCallback } from 'react';
import { ConnectScreen } from './components/ConnectScreen';
import { LoadingScreen } from './components/LoadingScreen';
import { RevealScreen } from './components/RevealScreen';
import { api } from './api';
import type { ConnectionData, ResearchData } from './types';

type AppState = 'connect' | 'loading' | 'reveal';

function App() {
  const [state, setState] = useState<AppState>('connect');
  const [researchData, setResearchData] = useState<ResearchData | null>(null);
  const [isResearchDone, setIsResearchDone] = useState(false);

  const handleConnected = useCallback(async (data: ConnectionData) => {
    setState('loading');

    // Start research in background
    try {
      const result = await api.research(data.userId);
      if (result.data) {
        setResearchData(result.data);
      } else {
        setResearchData({ first_name: 'there', insights: [] });
      }
    } catch {
      setResearchData({ first_name: 'there', insights: [] });
    }
    setIsResearchDone(true);
  }, []);

  const handleLoadingComplete = useCallback(() => {
    if (researchData) {
      setState('reveal');
    }
  }, [researchData]);

  return (
    <div className="h-full" style={{ background: 'var(--bg)' }}>
      {state === 'connect' && <ConnectScreen onConnected={handleConnected} />}
      {state === 'loading' && (
        <LoadingScreen onComplete={handleLoadingComplete} isResearchDone={isResearchDone} />
      )}
      {state === 'reveal' && researchData && <RevealScreen data={researchData} />}
    </div>
  );
}

export default App;
