import React, { useState, useRef, useEffect } from "react";

export default function FollowUpChat({ runId, findings }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading || !runId) return;

    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);

    try {
      // Use the first finding as context, or a general one
      const findingId = findings?.[0]?.id || "general";
      const response = await fetch("/subchat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          run_id: runId,
          finding_id: findingId,
          message: userMsg,
        }),
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      // Read SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let assistantText = "";

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "" },
      ]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.delta) {
              assistantText += data.delta;
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  role: "assistant",
                  content: assistantText,
                };
                return updated;
              });
            }
          } catch {
            // skip
          }
        }
      }

      // If no streaming content arrived, show a placeholder
      if (!assistantText) {
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            role: "assistant",
            content:
              "I can answer follow-up questions about this research. Try asking about specific findings or request more detail on a topic.",
          };
          return updated;
        });
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev.filter((m) => m.content !== ""),
        {
          role: "assistant",
          content: `Error: ${err.message}. Make sure the backend is running.`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="followup-section">
      <div className="followup-container">
        <div className="followup-label">Follow-up Questions</div>

        {messages.length > 0 && (
          <div className="followup-messages">
            {messages.map((msg, i) => (
              <div key={i} className={`followup-msg ${msg.role}`}>
                {msg.content || (
                  <span className="loading-spinner" />
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}

        <div className="followup-input-row" style={{ marginTop: messages.length > 0 ? 12 : 0 }}>
          <input
            type="text"
            className="followup-input"
            placeholder="Ask a follow-up question..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading || !runId}
          />
          <button
            className="followup-send"
            onClick={handleSend}
            disabled={loading || !input.trim() || !runId}
          >
            {loading ? <span className="loading-spinner" /> : "Ask"}
          </button>
        </div>
      </div>
    </div>
  );
}
