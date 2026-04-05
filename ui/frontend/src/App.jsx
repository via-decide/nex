import React, { useState } from "react";
import ResearchUI from "./pages/ResearchUI";
import SystemStatus from "./pages/SystemStatus";

export default function App() {
  const [page, setPage] = useState("research");
  const [researchMode, setResearchMode] = useState(true);
  const [devMode, setDevMode] = useState(false);

  return (
    <div className="app-layout">
      <header className="header">
        <div className="header-brand">
          <div>
            <div className="header-logo">
              <span>Nex</span> Research Engine
            </div>
            <div className="header-subtitle">Deep autonomous research</div>
          </div>
        </div>

        <div className="header-controls">
          <div className="nav-tabs">
            <button
              className={`nav-tab ${page === "research" ? "active" : ""}`}
              onClick={() => setPage("research")}
            >
              Research
            </button>
            <button
              className={`nav-tab ${page === "status" ? "active" : ""}`}
              onClick={() => setPage("status")}
            >
              System
            </button>
          </div>

          <Toggle
            label="Research Mode"
            active={researchMode}
            onToggle={() => setResearchMode((v) => !v)}
          />
          <Toggle
            label="Developer"
            active={devMode}
            onToggle={() => setDevMode((v) => !v)}
          />
        </div>
      </header>

      <div className="main-content">
        {page === "research" ? (
          <ResearchUI
            researchMode={researchMode}
            devMode={devMode}
          />
        ) : (
          <SystemStatus />
        )}
      </div>
    </div>
  );
}

function Toggle({ label, active, onToggle }) {
  return (
    <label className="toggle" onClick={onToggle}>
      <div className={`toggle-track ${active ? "active" : ""}`}>
        <div className="toggle-thumb" />
      </div>
      {label}
    </label>
  );
}
