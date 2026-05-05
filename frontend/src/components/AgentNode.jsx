import React from 'react';

export function AgentNode({ agent, state = 'idle', size = 56, showMeta = true }) {
  const cls = state === 'active' ? 'active' : state === 'done' ? 'done' : '';
  return (
    <div className="agent-node">
      <div
        className={`agent-circle ${cls}`}
        style={{ width: size, height: size, fontSize: size * 0.4 }}
      >
        <span>{agent.emoji}</span>
        {state === 'active' && <span className="pulse-ring" />}
      </div>
      <div className="agent-name">{agent.name}</div>
      {showMeta && <div className="agent-meta">{agent.tag}</div>}
    </div>
  );
}
