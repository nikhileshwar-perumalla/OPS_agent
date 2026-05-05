import React, { useState } from 'react';
import { api } from '../api.js';
import { AGENTS, severityTone } from '../agents.js';
import { MiniPipeline } from '../components/MiniPipeline.jsx';
import { Sparkline } from '../components/Sparkline.jsx';
import { PlaybookModal, extractPlaybookSteps } from '../components/PlaybookModal.jsx';

const INC_TYPES = [
  ['high_cpu', 'High CPU'],
  ['memory_leak', 'Memory leak'],
  ['network_latency', 'Network latency'],
  ['service_down', 'Service down'],
  ['disk_usage_high', 'Disk usage'],
  ['process_crash', 'Process crash'],
  ['database_lock', 'DB lock'],
  ['ssl_expiry', 'SSL expiry'],
];

export function LiveScreen({ state, refresh, selectedId, onSelect }) {
  const incidents = state?.incidents ?? [];
  const selected = incidents.find(i => i.id === selectedId) || incidents[0];
  const [playbook, setPlaybook] = useState(null); // { incident, kind, steps }

  const runAction = async (kind, incident) => {
    const beforeLogs = state?.logs || [];
    const after = kind === 'approve'
      ? await api.approve(incident.id)
      : await api.deny(incident.id);
    const steps = extractPlaybookSteps(beforeLogs, after?.logs, kind);
    setPlaybook({ incident, kind, steps });
    refresh();
  };

  const history = (state?.metrics_history ?? []).filter(Boolean);
  const cpuSeries = history.map(m => m?.cpu_percent ?? 0);
  const memSeries = history.map(m => m?.memory_percent ?? 0);
  const latSeries = history.map(m => (m?.latency_seconds ?? 0) * 100);

  return (
    <>
    <div className="page" style={{ display: 'grid', gridTemplateColumns: '300px 1fr 320px', gap: 18, maxWidth: 1600 }}>
      {/* Queue */}
      <div className="col">
        <div className="card">
          <div className="card-head">
            <div className="card-title">Open · {incidents.length}</div>
            <div className="card-sub mono-xs">SORT · sev</div>
          </div>
          {incidents.length === 0 && (
            <div className="muted" style={{ fontSize: 13, padding: '12px 0' }}>No active incidents.</div>
          )}
          <div className="col" style={{ gap: 8 }}>
            {incidents.map(inc => {
              const sev = inc.analysis?.severity || 'P2';
              const active = inc.id === selected?.id;
              return (
                <button
                  key={inc.id}
                  onClick={() => onSelect(inc.id)}
                  className="card"
                  style={{
                    textAlign: 'left',
                    cursor: 'pointer',
                    padding: 12,
                    borderColor: active ? 'var(--ink)' : 'var(--line)',
                    boxShadow: active ? 'var(--shadow-2)' : 'var(--shadow-1)',
                    background: active ? 'var(--surface)' : 'var(--surface)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span className="mono-xs muted">{inc.id}</span>
                    <span className={`chip ${severityTone(sev)}`}>{sev}</span>
                  </div>
                  <div style={{ fontSize: 13.5, fontWeight: 600, marginTop: 4 }}>
                    {inc.type.replaceAll('_', ' ')}
                  </div>
                  <div className="mono-xs muted" style={{ marginTop: 2 }}>
                    started tick {inc.start_tick} · {inc.state.toLowerCase()}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="card">
          <div className="card-title" style={{ marginBottom: 8 }}>Inject incident</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {INC_TYPES.map(([t, label]) => (
              <button
                key={t}
                className="btn sm"
                onClick={async () => { await api.inject(t); refresh(); }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Focus */}
      <div className="col">
        {selected ? (
          <FocusPanel incident={selected} runAction={runAction} />
        ) : (
          <div className="empty">Select or inject an incident to view details.</div>
        )}

        <div className="card">
          <div className="card-head">
            <div className="card-title">Live signals</div>
            <div className="toggle">
              <button className="on">5m</button>
              <button>15m</button>
              <button>1h</button>
            </div>
          </div>
          <div className="grid-3">
            <SignalCell label="CPU %" series={cpuSeries} value={state?.metrics?.cpu_percent} />
            <SignalCell label="Memory %" series={memSeries} value={state?.metrics?.memory_percent} />
            <SignalCell label="Latency (s)" series={latSeries} value={state?.metrics?.latency_seconds} suffix="" />
          </div>
        </div>
      </div>

      {/* Activity */}
      <div className="col">
        <div className="card">
          <div className="card-title" style={{ marginBottom: 8 }}>Agent chatter</div>
          <ConversationList conversation={selected?.analysis?.agent_conversation} />
        </div>

        <div className="card">
          <div className="card-title" style={{ marginBottom: 8 }}>System log</div>
          <div style={{ maxHeight: 220, overflow: 'auto' }}>
            {(state?.logs ?? []).slice(-25).map((l, i) => (
              <div key={i} className="logline"><span>{l}</span></div>
            ))}
          </div>
        </div>
      </div>
    </div>
    {playbook && (
      <PlaybookModal
        incident={playbook.incident}
        kind={playbook.kind}
        steps={playbook.steps}
        onClose={() => setPlaybook(null)}
      />
    )}
    </>
  );
}

function FocusPanel({ incident, runAction }) {
  const a = incident.analysis;
  const sev = a?.severity || 'P2';
  const stages = a?.workflow_stages || {};
  const totalMs = a?.pipeline_duration_ms || 0;
  const top = a?.top_recommendation;
  const needsApproval = a?.needs_approval;

  return (
    <div className="card elevated">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <span className="mono-xs muted">{incident.id}</span>
        <span className={`chip ${severityTone(sev)}`}>{sev}</span>
        {a && <span className="chip"><span className="dot amber pulse"></span>agents working</span>}
        {incident.jira_ticket_key && <span className="chip blue">{incident.jira_ticket_key}</span>}
      </div>
      <h2 className="serif" style={{ margin: '4px 0 14px', fontSize: 24, fontWeight: 600, letterSpacing: '-0.01em' }}>
        {incident.type.replaceAll('_', ' ')}
      </h2>

      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div className="label">Agent pipeline</div>
          <span className="mono-xs muted">{totalMs ? `${totalMs.toFixed(0)}ms total` : 'pending'}</span>
        </div>
        <MiniPipeline stages={stages} />
      </div>

      <div className="grid-2">
        <div>
          <div className="label" style={{ marginBottom: 6 }}>Summary</div>
          <div style={{ fontSize: 13.5, lineHeight: 1.55 }}>{a?.summary || 'Awaiting diagnostics…'}</div>
        </div>
        <div>
          <div className="label" style={{ marginBottom: 6 }}>Top hypothesis</div>
          {a?.hypotheses?.[0] ? (
            <>
              <div style={{ fontSize: 13.5, fontWeight: 600 }}>{a.hypotheses[0].root_cause}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                <div className="bar accent" style={{ flex: 1 }}>
                  <span style={{ width: `${Math.round((a.hypotheses[0].confidence || 0) * 100)}%` }}></span>
                </div>
                <span className="mono-xs">{Math.round((a.hypotheses[0].confidence || 0) * 100)}%</span>
              </div>
            </>
          ) : <div className="muted">No hypothesis yet.</div>}
        </div>
      </div>

      {top && (
        <div style={{ marginTop: 16, padding: 12, background: 'var(--surface-2)', borderRadius: 'var(--radius-sm)' }}>
          <div className="label" style={{ marginBottom: 4 }}>Recommended action</div>
          <code className="mono" style={{ fontSize: 13 }}>{top}</code>
        </div>
      )}

      {needsApproval && (
        <div style={{ marginTop: 14, display: 'flex', gap: 8 }}>
          <button className="btn accent" onClick={() => runAction('approve', incident)}>Approve</button>
          <button className="btn danger" onClick={() => runAction('deny', incident)}>Deny</button>
        </div>
      )}
    </div>
  );
}

function SignalCell({ label, series, value, suffix = '%' }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div className="label">{label}</div>
        <div className="serif" style={{ fontSize: 18, fontWeight: 600 }}>
          {value != null ? `${Number(value).toFixed(1)}${suffix}` : '—'}
        </div>
      </div>
      <Sparkline values={series} height={48} />
    </div>
  );
}

function ConversationList({ conversation }) {
  if (!conversation?.length) {
    return <div className="muted" style={{ fontSize: 13 }}>No messages yet.</div>;
  }
  const icons = {
    orchestrator: '🎯', triage: '🔍', diagnostics: '🔬',
    rca: '🧠', remediation: '🛠️', comms: '📡',
  };
  return (
    <div style={{ maxHeight: 360, overflow: 'auto' }}>
      {conversation.map((m, i) => (
        <div key={i} style={{ paddingLeft: 10, borderLeft: '2px solid var(--line)', marginBottom: 10 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600 }}>
            {icons[m.sender] || '•'} {m.sender} → {m.recipient}
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--ink-2)' }}>{m.payload_summary || m.type}</div>
          <div className="mono-xs muted">{m.duration_ms?.toFixed(0)}ms</div>
        </div>
      ))}
    </div>
  );
}
