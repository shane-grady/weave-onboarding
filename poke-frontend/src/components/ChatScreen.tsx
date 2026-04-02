import { useState, useEffect, useRef, type ReactNode, type FormEvent } from 'react';
import { TypingIndicator } from './TypingIndicator';
import { useTypewriter } from '../hooks/useTypewriter';
import { api } from '../api';
import type { ResearchData } from '../types';

interface Props {
  data: ResearchData;
  openingMessage: string;
  userId: string;
  onDisconnect?: () => void;
}

type Phase = 'typing-greeting' | 'showing-insights' | 'typing-opening' | 'chat';

interface ChatEntry {
  id: string;
  content: string;
  response?: string;
  status: string;
}

const ICON_MAP: Record<string, string> = {
  Email: 'mail',
  Company: 'building',
  Role: 'briefcase',
  Location: 'map-pin',
  Industry: 'globe',
  Education: 'graduation-cap',
  LinkedIn: 'link',
  About: 'user',
  'Shops At': 'shopping',
  'Subscribes To': 'bell',
  'Travels To': 'plane',
  Uses: 'smartphone',
  Interests: 'heart',
  Contacts: 'users',
  Address: 'home',
  Phone: 'phone',
  Website: 'globe',
  'Known For': 'briefcase',
  'Side Projects': 'heart',
  Network: 'users',
};

function InsightIcon({ label }: { label: string }) {
  const icons: Record<string, ReactNode> = {
    mail: (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
    ),
    building: (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M12 14h.01"/><path d="M16 10h.01"/><path d="M16 14h.01"/><path d="M8 10h.01"/><path d="M8 14h.01"/></svg>
    ),
    briefcase: (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><rect width="20" height="14" x="2" y="6" rx="2"/></svg>
    ),
    'map-pin': (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
    ),
    globe: (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>
    ),
    'graduation-cap': (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/></svg>
    ),
    link: (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
    ),
    user: (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
    ),
    shopping: (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/></svg>
    ),
    bell: (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
    ),
    plane: (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/></svg>
    ),
    smartphone: (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/></svg>
    ),
    heart: (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/></svg>
    ),
    users: (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
    ),
    home: (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
    ),
    phone: (
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
    ),
  };

  const iconKey = ICON_MAP[label] || 'user';
  return <span className="text-neutral-500">{icons[iconKey] || icons.user}</span>;
}

export function ChatScreen({ data, openingMessage, userId, onDisconnect }: Props) {
  const firstName = data?.first_name || 'there';
  const insights = data?.insights ?? [];
  const hasInsights = insights.length > 0;

  const [phase, setPhase] = useState<Phase>('typing-greeting');
  const [showTypingIndicator, setShowTypingIndicator] = useState(true);
  const [visibleInsights, setVisibleInsights] = useState(0);
  const [showOpeningIndicator, setShowOpeningIndicator] = useState(false);
  const [chatEntries, setChatEntries] = useState<ChatEntry[]>([]);
  const [input, setInput] = useState('');
  const [isWaiting, setIsWaiting] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const greeting = hasInsights
    ? `Welcome, ${firstName}. Here's what we already know about you.`
    : `Welcome, ${firstName}.`;

  const {
    displayed: greetingText,
    isDone: greetingDone,
  } = useTypewriter(greeting, 35, !showTypingIndicator);

  const {
    displayed: openingText,
    isDone: openingDone,
  } = useTypewriter(openingMessage, 35, phase === 'typing-opening');

  // Phase: initial typing indicator -> greeting
  useEffect(() => {
    const timer = setTimeout(() => setShowTypingIndicator(false), 1500);
    return () => clearTimeout(timer);
  }, []);

  // Phase: greeting done -> show insights
  useEffect(() => {
    if (!greetingDone) return;
    setPhase('showing-insights');
  }, [greetingDone]);

  // Reveal insights one by one
  useEffect(() => {
    if (phase !== 'showing-insights') return;
    if (visibleInsights >= insights.length) {
      const timer = setTimeout(() => {
        setShowOpeningIndicator(true);
        setTimeout(() => {
          setShowOpeningIndicator(false);
          setPhase('typing-opening');
        }, 1500);
      }, 600);
      return () => clearTimeout(timer);
    }

    const timer = setTimeout(() => {
      setVisibleInsights((n) => n + 1);
    }, 400);
    return () => clearTimeout(timer);
  }, [phase, visibleInsights, insights.length]);

  // Opening message done -> enter chat
  useEffect(() => {
    if (phase !== 'typing-opening') return;
    if (openingDone || !openingMessage) {
      setPhase('chat');
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [phase, openingDone, openingMessage]);

  // Auto-scroll
  useEffect(() => {
    containerRef.current?.scrollTo({
      top: containerRef.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [greetingText, visibleInsights, openingText, showTypingIndicator, showOpeningIndicator, chatEntries, isWaiting]);

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    const content = input.trim();
    if (!content || isWaiting) return;

    setInput('');
    setIsWaiting(true);

    try {
      const { message_id } = await api.sendMessage(userId, content);
      setChatEntries((prev) => [...prev, { id: message_id, content, status: 'queued' }]);

      const poll = setInterval(async () => {
        try {
          const result = await api.getMessageStatus(message_id);
          if (result.status === 'completed') {
            clearInterval(poll);
            setChatEntries((prev) =>
              prev.map((e) => e.id === message_id ? { ...e, response: result.response || '', status: 'completed' } : e)
            );
            setIsWaiting(false);
          } else if (result.status === 'error') {
            clearInterval(poll);
            setChatEntries((prev) =>
              prev.map((e) => e.id === message_id ? { ...e, response: 'Something went wrong. Try again.', status: 'error' } : e)
            );
            setIsWaiting(false);
          }
        } catch {
          // keep polling
        }
      }, 1500);
    } catch {
      setIsWaiting(false);
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="shrink-0 px-6 pt-8 pb-4 flex items-center justify-between">
        <span className="text-sm font-medium tracking-wide" style={{ color: 'var(--accent)' }}>
          weave fabric
        </span>
        {onDisconnect && (
          <button
            onClick={onDisconnect}
            className="text-xs text-neutral-600 hover:text-neutral-400 transition-colors"
          >
            Disconnect
          </button>
        )}
      </div>

      {/* Messages area */}
      <div ref={containerRef} className="flex-1 overflow-y-auto px-6 pb-4 scrollbar-hide">
        <div className="max-w-lg">
          {/* Typing indicator before greeting */}
          {showTypingIndicator && <TypingIndicator />}

          {/* Greeting */}
          {!showTypingIndicator && (
            <p className="text-xl font-light leading-relaxed text-neutral-200">
              {greetingText}
              {!greetingDone && <span className="cursor" />}
            </p>
          )}

          {/* Insights */}
          {visibleInsights > 0 && hasInsights && (
            <div className="mt-8 space-y-3">
              {insights.slice(0, visibleInsights).map((insight, i) => (
                <div
                  key={i}
                  className="slide-up flex items-start gap-3 py-2.5 px-4 rounded-lg"
                  style={{
                    background: 'rgba(255, 255, 255, 0.03)',
                    border: '1px solid rgba(255, 255, 255, 0.06)',
                    animationDelay: '0s',
                  }}
                >
                  <div className="mt-0.5 shrink-0">
                    <InsightIcon label={insight.label} />
                  </div>
                  <div className="min-w-0">
                    <span className="text-xs uppercase tracking-wider text-neutral-600">
                      {insight.label}
                    </span>
                    <p className="text-sm text-neutral-300 mt-0.5 break-words">
                      {insight.value}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Opening message typing indicator */}
          {showOpeningIndicator && (
            <div className="mt-8">
              <TypingIndicator />
            </div>
          )}

          {/* Opening message (AI-generated, replaces static closing) */}
          {(phase === 'typing-opening' || phase === 'chat') && openingMessage && (
            <p className="mt-8 text-xl font-light leading-relaxed text-neutral-200">
              {openingText}
              {!openingDone && <span className="cursor" />}
            </p>
          )}

          {/* Chat messages */}
          {chatEntries.map((entry) => (
            <div key={entry.id} className="mt-6">
              {/* User message */}
              <div className="flex justify-end">
                <div
                  className="max-w-xs px-4 py-2.5 rounded-2xl text-sm text-neutral-200"
                  style={{ background: 'rgba(139, 92, 246, 0.15)' }}
                >
                  {entry.content}
                </div>
              </div>
              {/* AI response */}
              {entry.response && (
                <p className="mt-3 text-base font-light leading-relaxed text-neutral-200 fade-in">
                  {entry.response}
                </p>
              )}
            </div>
          ))}

          {/* Waiting for response */}
          {isWaiting && chatEntries.length > 0 && !chatEntries[chatEntries.length - 1].response && (
            <div className="mt-3">
              <TypingIndicator />
            </div>
          )}
        </div>
      </div>

      {/* Input area — visible only after opening message completes */}
      {phase === 'chat' && (
        <div className="shrink-0 px-6 pb-6 pt-2 fade-in">
          <form onSubmit={handleSend} className="max-w-lg flex gap-3">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Say something..."
              disabled={isWaiting}
              className="flex-1 px-4 py-3 rounded-xl text-sm text-neutral-200 placeholder-neutral-600 outline-none transition-colors"
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
              }}
            />
            <button
              type="submit"
              disabled={isWaiting || !input.trim()}
              className="px-5 py-3 rounded-xl text-sm font-medium text-white transition-opacity disabled:opacity-30"
              style={{ background: 'var(--accent)' }}
            >
              Send
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
