import React from 'react';

const TABS = [
  { id: 'live', label: 'Live' },
  { id: 'workflow', label: 'Workflow' },
  { id: 'agents', label: 'Agents' },
  { id: 'knowledge', label: 'Knowledge' },
  { id: 'history', label: 'History' },
  { id: 'sim', label: 'Sim' },
];

export function AppShell({ tab, onTab, state, children }) {
  const llmActive = state?.llm_active;
  const auto = state?.auto_run;
  const tick = state?.tick ?? 0;
  const incidents = state?.incidents?.length ?? 0;

  return (
    <div className="app">
      <div className="topbar">
        <div className="brand">
          <div className="brand-mark">⌖</div>
          <div className="brand-name">OPS Agent</div>
          <div className="brand-version">v0.2</div>
        </div>
        <div className="tabs">
          {TABS.map(t => (
            <button
              key={t.id}
              className={`tab ${tab === t.id ? 'active' : ''}`}
              onClick={() => onTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="topbar-right">
          <div className="status-pill">
            <span className={`ind ${auto ? 'green' : 'amber'}`}></span>
            {auto ? 'live' : 'paused'}
          </div>
          <div className="status-pill">
            <span className={`ind ${llmActive ? 'green' : 'amber'}`}></span>
            {llmActive ? 'LLM' : 'mock'}
          </div>
          <div className="status-pill mono-xs">tick {tick}</div>
          <div className="status-pill">
            <span className={`ind ${incidents ? 'red' : 'green'}`}></span>
            {incidents} active
          </div>
        </div>
      </div>
      {children}
    </div>
  );
}
