import { useState, useEffect, useCallback } from 'react';

export function useTypewriter(text: string, speed = 30, startImmediately = true) {
  const [displayed, setDisplayed] = useState('');
  const [isDone, setIsDone] = useState(false);
  const [isStarted, setIsStarted] = useState(startImmediately);

  const start = useCallback(() => setIsStarted(true), []);

  // React to external trigger changes
  useEffect(() => {
    if (startImmediately) setIsStarted(true);
  }, [startImmediately]);

  useEffect(() => {
    if (!isStarted || !text) return;

    setDisplayed('');
    setIsDone(false);
    let i = 0;

    const interval = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(interval);
        setIsDone(true);
      }
    }, speed);

    return () => clearInterval(interval);
  }, [text, speed, isStarted]);

  return { displayed, isDone, start };
}
