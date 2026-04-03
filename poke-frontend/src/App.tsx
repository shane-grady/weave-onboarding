import { useState, useCallback, useEffect, useRef } from 'react';
import { ConnectScreen } from './components/ConnectScreen';
import { LoadingScreen } from './components/LoadingScreen';
import { RevealScreen } from './components/RevealScreen';
import { api } from './api';
import type { ConnectionData, ResearchData } from './types';

type AppState = 'connect' | 'loading' | 'reveal';

const STORAGE_KEYS = {
  userId: 'weave_user_id',
  researchData: 'weave_research_data',
};

function loadFromStorage(): {
  userId: string;
  researchData: ResearchData | null;
} {
  try {
    const userId = localStorage.getItem(STORAGE_KEYS.userId) || '';
    const raw = localStorage.getItem(STORAGE_KEYS.researchData);
    const researchData = raw ? JSON.parse(raw) : null;
    return { userId, researchData };
  } catch {
    return { userId: '', researchData: null };
  }
}

function saveToStorage(userId: string, researchData: ResearchData) {
  localStorage.setItem(STORAGE_KEYS.userId, userId);
  localStorage.setItem(STORAGE_KEYS.researchData, JSON.stringify(researchData));
}

function clearStorage() {
  localStorage.removeItem(STORAGE_KEYS.userId);
  localStorage.removeItem(STORAGE_KEYS.researchData);
}

/**
 * The LLM sometimes returns a non-standard shape (user_profile, company_context,
 * gmail_contacts_search, first_impression_data) instead of { first_name, insights }.
 * Normalize either shape into what RevealScreen expects.
 */
function normalizeResearchData(raw: Record<string, unknown>): ResearchData {
  // Already in the expected shape
  if (raw.first_name && Array.isArray(raw.insights) && raw.insights.length > 0) {
    return raw as unknown as ResearchData;
  }

  const insights: Array<{ label: string; value: string }> = [];
  let firstName = (raw.first_name as string) || '';

  // Extract from user_profile
  const profile = raw.user_profile as Record<string, unknown> | undefined;
  if (profile) {
    if (!firstName && profile.name) {
      firstName = (profile.name as string).split(' ')[0];
    }
    if (!firstName && profile.first_name) {
      firstName = profile.first_name as string;
    }
    if (profile.email) insights.push({ label: 'Email', value: profile.email as string });
    if (profile.name) insights.push({ label: 'About', value: profile.name as string });
    if (profile.location) insights.push({ label: 'Location', value: profile.location as string });
    if (profile.role || profile.title) insights.push({ label: 'Role', value: (profile.role || profile.title) as string });
    if (profile.linkedin_url || profile.linkedin) insights.push({ label: 'LinkedIn', value: (profile.linkedin_url || profile.linkedin) as string });
  }

  // Extract from company_context
  const company = raw.company_context as Record<string, unknown> | undefined;
  if (company) {
    const companyName = (company.name || company.company_name || company.company) as string | undefined;
    if (companyName) insights.push({ label: 'Company', value: companyName });
    if (company.industry) insights.push({ label: 'Industry', value: company.industry as string });
    if (company.website || company.domain) insights.push({ label: 'Website', value: (company.website || company.domain) as string });
    if (company.description) insights.push({ label: 'Company', value: `${companyName || ''} — ${company.description}`.replace(/^ — /, '') });
  }

  // Extract from gmail_contacts_search
  const contacts = raw.gmail_contacts_search as Record<string, unknown> | undefined;
  if (contacts) {
    if (!firstName && contacts.name) firstName = (contacts.name as string).split(' ')[0];
    if (contacts.email && !insights.some((i) => i.label === 'Email')) {
      insights.push({ label: 'Email', value: contacts.email as string });
    }
  }

  // Extract from first_impression_data
  const impression = raw.first_impression_data as Record<string, unknown> | undefined;
  if (impression) {
    if (impression.known_for) insights.push({ label: 'Known For', value: impression.known_for as string });
    if (impression.interests) insights.push({ label: 'Interests', value: impression.interests as string });
    if (impression.about) insights.push({ label: 'About', value: impression.about as string });
    if (impression.summary) insights.push({ label: 'About', value: impression.summary as string });
  }

  // Walk any remaining top-level string fields we haven't captured
  const handled = new Set(['first_name', 'full_name', 'insights', 'linkedin_url', 'user_profile', 'company_context', 'gmail_contacts_search', 'first_impression_data']);
  for (const [key, val] of Object.entries(raw)) {
    if (handled.has(key) || typeof val !== 'string') continue;
    const label = key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    insights.push({ label, value: val });
  }

  // Deduplicate by label (keep first)
  const seen = new Set<string>();
  const deduped = insights.filter((i) => {
    if (seen.has(i.label)) return false;
    seen.add(i.label);
    return true;
  });

  return {
    first_name: firstName || 'there',
    full_name: (raw.full_name as string) || undefined,
    insights: deduped,
  };
}

function App() {
  const [state, setState] = useState<AppState>('connect');
  const [researchData, setResearchData] = useState<ResearchData | null>(null);
  const [_userId, setUserId] = useState('');
  const [isResearchDone, setIsResearchDone] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const researchDataRef = useRef<ResearchData | null>(null);

  // Keep ref in sync with state
  useEffect(() => {
    researchDataRef.current = researchData;
  }, [researchData]);

  // Restore from localStorage on mount
  useEffect(() => {
    const stored = loadFromStorage();
    if (stored.userId && stored.researchData) {
      const normalized = normalizeResearchData(stored.researchData as unknown as Record<string, unknown>);
      if (
        normalized.first_name &&
        normalized.first_name !== 'there' &&
        normalized.insights.length > 0
      ) {
        setUserId(stored.userId);
        setResearchData(normalized);
        setIsResearchDone(true);
        setState('reveal');
      }
    }
  }, []);

  const handleConnected = useCallback(async (data: ConnectionData) => {
    setState('loading');
    setUserId(data.userId);

    localStorage.setItem(STORAGE_KEYS.userId, data.userId);

    // Fire research (fire-and-forget — don't let a failed POST kill the flow,
    // because the backend may have received the request and started the task)
    api.research(data.userId).catch(() => {});

    // Poll for completion
    let attempts = 0;
    if (pollRef.current) clearInterval(pollRef.current);
    const poll = setInterval(async () => {
      attempts++;
      if (attempts > 30) {
        clearInterval(poll);
        pollRef.current = null;
        setResearchData({ first_name: 'there', insights: [] });
        setIsResearchDone(true);
        return;
      }
      try {
        const result = await api.getResearchStatus(data.userId);
        if (result.status === 'completed') {
          clearInterval(poll);
          pollRef.current = null;
          const raw = result.data || { first_name: 'there', insights: [] };
          const normalized = normalizeResearchData(raw as Record<string, unknown>);
          setResearchData(normalized);
          setIsResearchDone(true);
          saveToStorage(data.userId, normalized);
        } else if (result.status === 'error') {
          clearInterval(poll);
          pollRef.current = null;
          setResearchData({ first_name: 'there', insights: [] });
          setIsResearchDone(true);
        }
      } catch {
        // keep polling on network errors
      }
    }, 2000);
    pollRef.current = poll;
  }, []);

  const handleLoadingComplete = useCallback(() => {
    if (researchDataRef.current) {
      setState('reveal');
    }
  }, []);

  const handleDisconnect = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    clearStorage();
    setUserId('');
    setResearchData(null);
    setIsResearchDone(false);
    setState('connect');
  }, []);

  return (
    <div className="h-full" style={{ background: 'var(--bg)' }}>
      {state === 'connect' && <ConnectScreen onConnected={handleConnected} />}
      {state === 'loading' && (
        <LoadingScreen onComplete={handleLoadingComplete} isResearchDone={isResearchDone} />
      )}
      {state === 'reveal' && researchData && (
        <RevealScreen data={researchData} onDisconnect={handleDisconnect} />
      )}
    </div>
  );
}

export default App;
