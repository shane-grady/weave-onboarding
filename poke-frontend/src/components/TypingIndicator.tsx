export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-2">
      <div className="w-1.5 h-1.5 rounded-full bg-neutral-500 typing-dot" />
      <div className="w-1.5 h-1.5 rounded-full bg-neutral-500 typing-dot" />
      <div className="w-1.5 h-1.5 rounded-full bg-neutral-500 typing-dot" />
    </div>
  );
}
