import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function AnswerPanel({ answer, title }) {
  if (!answer) return null;

  return (
    <div className="answer-section">
      <div className="answer-label">
        {title ? `Research Report — ${title}` : "Synthesized Answer"}
      </div>
      <div className="answer-text">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
      </div>
    </div>
  );
}
