import React, { useRef, useEffect } from "react";

const EXAMPLES = [
  "Explain transformer attention mechanisms",
  "How do Kalman filters work?",
  "Distributed consensus algorithms",
  "Neural network optimization techniques",
];

export default function SearchBar({ value, onChange, onSubmit, loading, compact }) {
  const inputRef = useRef(null);

  useEffect(() => {
    if (!compact && inputRef.current) {
      inputRef.current.focus();
    }
  }, [compact]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit(value);
    }
  };

  return (
    <div className="search-container">
      <input
        ref={inputRef}
        type="text"
        className="search-input"
        placeholder="Ask Nex anything..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={loading}
      />
      <button
        className="search-submit"
        onClick={() => onSubmit(value)}
        disabled={loading || !value.trim()}
      >
        {loading ? (
          <span className="loading-spinner" />
        ) : (
          "Research"
        )}
      </button>

      {!compact && (
        <div className="search-examples">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              className="search-example"
              onClick={() => {
                onChange(ex);
                onSubmit(ex);
              }}
            >
              {ex}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
