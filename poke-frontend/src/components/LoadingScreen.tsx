import { useState, useEffect } from 'react';

interface Props {
  onComplete: () => void;
  isResearchDone: boolean;
}

const stages = [
  { target: 15, label: 'Connecting to Gmail...', duration: 2000 },
  { target: 30, label: 'Reading your emails...', duration: 6000 },
  { target: 45, label: 'Scanning receipts & subscriptions...', duration: 8000 },
  { target: 60, label: 'Mapping your contacts...', duration: 10000 },
  { target: 75, label: 'Searching the web for you...', duration: 12000 },
  { target: 88, label: 'Building your digital profile...', duration: 15000 },
];

export function LoadingScreen({ onComplete, isResearchDone }: Props) {
  const [progress, setProgress] = useState(0);
  const [stageIndex, setStageIndex] = useState(0);

  // Animate through stages
  useEffect(() => {
    if (isResearchDone) {
      setProgress(100);
      const timer = setTimeout(onComplete, 600);
      return () => clearTimeout(timer);
    }

    if (stageIndex >= stages.length) return;

    const stage = stages[stageIndex];
    const timer = setTimeout(() => {
      setProgress(stage.target);
      setStageIndex((i) => i + 1);
    }, stageIndex === 0 ? 300 : stages[stageIndex - 1].duration);

    return () => clearTimeout(timer);
  }, [stageIndex, isResearchDone, onComplete]);

  const currentLabel = isResearchDone
    ? 'Done'
    : stageIndex < stages.length
      ? stages[stageIndex].label
      : stages[stages.length - 1].label;

  return (
    <div className="h-full flex flex-col items-center justify-center px-6">
      <div className="w-full max-w-lg">
        {/* Progress bar */}
        <div className="progress-track rounded-full">
          <div
            className="progress-fill rounded-full"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Label */}
        <div className="mt-6 text-center">
          <p className="text-sm text-neutral-500 font-light tracking-wide">
            {currentLabel}
          </p>
          <p className="mt-2 text-xs text-neutral-600 tabular-nums">
            {progress}%
          </p>
        </div>
      </div>
    </div>
  );
}
