import React from "react";

const STAGE_LABELS = {
  planning: "Planning",
  discovery: "Discovery",
  collection: "Collection",
  verification: "Verification",
  knowledge_graph: "Knowledge Graph",
  synthesis: "Synthesis",
};

export default function PipelineProgress({ stages, activeStage, completedStages, events }) {
  return (
    <div className="pipeline-progress">
      <div className="pipeline-stages">
        {stages.map((stage, i) => {
          const isActive = activeStage === stage;
          const isCompleted = completedStages.includes(stage);
          const cls = isActive
            ? "active"
            : isCompleted
              ? "completed"
              : "";

          return (
            <React.Fragment key={stage}>
              {i > 0 && <div className="pipeline-connector" />}
              <div className={`pipeline-stage ${cls}`}>
                <div className="pipeline-stage-dot" />
                {STAGE_LABELS[stage] || stage}
              </div>
            </React.Fragment>
          );
        })}
      </div>

      {events.length > 0 && (
        <div
          style={{
            marginTop: 8,
            fontSize: "0.75rem",
            color: "var(--text-secondary)",
            fontFamily: "var(--font-mono)",
          }}
        >
          {events[events.length - 1]?.message}
        </div>
      )}
    </div>
  );
}
