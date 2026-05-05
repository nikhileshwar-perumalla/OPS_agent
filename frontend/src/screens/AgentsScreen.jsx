import React, { useState } from 'react';
import { AGENTS, severityTone } from '../agents.js';
import { api } from '../api.js';
import { PlaybookModal, extractPlaybookSteps } from '../components/PlaybookModal.jsx';

export function AgentsScreen({ state, refresh, selected, selectedId, onSelect }) {
  const [activeId, setActiveId] = useState('triage');
  const [playbook, setPlaybook] = useState(null);
  const incidents = state?.incidents ?? [];
  const incident = selected || incidents[0];
  const a = incident?.analysis;

  const runAction = async (kind, inc) => {
    const beforeLogs = state?.logs || [];
    const after = kind === 'approve' ? await api.approve(inc.id) : await api.deny(inc.id);
    setPlaybook({ incident: inc, kind, steps: extractPlaybookSteps(beforeLogs, after?.logs, kind) });
    refresh();
  };

  return (
    <div className="split">
      <div className="side">
        <div className="side-section">Agents</div>
        {AGENTS.map(ag => (
          <div
            key={ag.id}
            className={`side-item ${activeId === ag.id ? 'active' : ''}`}
            onClick={() => setActiveId(ag.id)}
          >
            <span>{ag.emoji}</span>{ag.name}
          </div>
        ))}
        <div className="side-section">Incident · {incidents.length}</div>
        {incidents.length === 0 && (
          <div className="muted mono-xs" style={{ padding: '4px 10px' }}>none active</div>
        )}
        {incidents.map(inc => {
          const sev = inc.analysis?.severity || 'P2';
          const active = inc.id === incident?.id;
          const pState = inc.pipeline_state || (inc.analysis ? 'done' : 'queued');
          const dotColor = pState === 'done' ? 'var(--green)'
            : pState === 'running' ? 'var(--amber)' : 'var(--ink-3)';
          const isPulse = pState === 'running';
          return (
            <div
              key={inc.id}
              className={`side-item ${active ? 'active' : ''}`}
              onClick={() => onSelect?.(inc.id)}
              style={{ alignItems: 'flex-start', flexDirection: 'column', gap: 2 }}
              title={pState}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}>
                <span className={`dot ${isPulse ? 'pulse' : ''}`} style={{ background: dotColor }}></span>
                <span className="mono-xs">{inc.id}</span>
                <span className={`chip ${severityTone(sev)}`} style={{ marginLeft: 'auto', padding: '0 6px', fontSize: 10 }}>{sev}</span>
              </div>
              <div style={{ fontSize: 11.5, color: active ? 'var(--bg)' : 'var(--ink-3)', paddingLeft: 13, display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                <span>{inc.type.replaceAll('_', ' ')}</span>
                {pState !== 'done' && (
                  <span className="mono-xs" style={{ fontSize: 10, opacity: 0.8 }}>{pState}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <div className="main">
        <AgentHeader agent={AGENTS.find(x => x.id === activeId)} state={state} incident={incident} />
        {!incident && (
          <div className="empty">No incidents yet. Inject one from the <strong>Sim</strong> tab to see agent reports.</div>
        )}
        {incident && activeId === 'triage' && <TriagePanel a={a} incident={incident} />}
        {incident && activeId === 'diagnostics' && <DiagnosticsPanel a={a} incident={incident} />}
        {incident && activeId === 'rca' && <RCAPanel a={a} incident={incident} />}
        {incident && activeId === 'remediation' && <RemediationPanel a={a} incident={incident} runAction={runAction} />}
        {incident && activeId === 'comms' && <CommsPanel a={a} incident={incident} />}
      </div>
      {playbook && (
        <PlaybookModal
          incident={playbook.incident}
          kind={playbook.kind}
          steps={playbook.steps}
          onClose={() => setPlaybook(null)}
        />
      )}
    </div>
  );
}

function AgentHeader({ agent, state, incident }) {
  if (!agent) return null;
  const llmStats = state?.agent_stats?.llm;
  const llmActive = state?.llm_active;
  const llmLabel = llmActive
    ? `${llmStats?.provider || 'llm'} · ${llmStats?.model || ''}`.trim()
    : 'rule-based';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 22 }}>
      <div style={{
        width: 56, height: 56, borderRadius: '50%',
        background: 'var(--surface)', border: '1px solid var(--line)',
        display: 'grid', placeItems: 'center', fontSize: 28,
        boxShadow: 'var(--shadow-1)',
      }}>{agent.emoji}</div>
      <div>
        <h1 style={{ margin: 0 }}>{agent.name} agent</h1>
        <div className="card-sub mono-xs">{agent.tag}</div>
      </div>
      <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
        {incident && <span className="chip"><span className="dot amber pulse"></span>active on {incident.id}</span>}
        <span className="chip">{llmLabel}</span>
      </div>
    </div>
  );
}

function Empty({ msg = 'No data — pipeline idle.', incident }) {
  // Differentiate "no incident at all" vs "incident exists but analysis pending"
  const realMsg = incident && !incident.analysis
    ? 'Pipeline running for this incident — analysis will appear in a few seconds.'
    : msg;
  return (
    <div className="empty">
      {incident && !incident.analysis && (
        <div style={{ marginBottom: 8 }}>
          <span className="dot amber pulse"></span>
          <span style={{ marginLeft: 8 }}>Waiting for first analysis…</span>
        </div>
      )}
      <div style={{ fontSize: 13 }}>{realMsg}</div>
    </div>
  );
}

function TriagePanel({ a, incident }) {
  const t = a?.triage_report;
  if (!t) return <Empty incident={incident} />;
  const allSymptoms = t.symptoms || [];
  const symChips = allSymptoms.filter(s => typeof s === 'string' && s.length <= 60);
  const symLong = allSymptoms.filter(s => typeof s === 'string' && s.length > 60);
  return (
    <div className="grid-2">
      <div className="card">
        <div className="card-title">Severity</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8 }}>
          <span className={`chip ${severityTone(t.severity)}`}>{t.severity}</span>
          <span className="mono-xs muted">urgency · {t.urgency_score?.toFixed?.(2) ?? '—'}</span>
        </div>
      </div>
      <div className="card" style={{ minWidth: 0 }}>
        <div className="card-title">Symptoms</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
          {symChips.map((s, i) => <span key={i} className="chip amber">{s}</span>)}
          {symChips.length === 0 && symLong.length === 0 && (
            <span className="muted" style={{ fontSize: 13 }}>—</span>
          )}
        </div>
      </div>
      {symLong.length > 0 && (
        <div className="card" style={{ gridColumn: 'span 2' }}>
          <div className="card-title">AI insight</div>
          {symLong.map((s, i) => (
            <blockquote key={i} style={{
              margin: '8px 0 0', padding: '10px 14px',
              borderLeft: '3px solid var(--accent)',
              background: 'var(--accent-soft)',
              borderRadius: 4,
              fontSize: 13.5, lineHeight: 1.6,
              color: 'var(--ink-2)',
              fontStyle: 'italic',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}>
              {s.replace(/^\[AI Insight\]\s*/, '')}
            </blockquote>
          ))}
        </div>
      )}
      <div className="card" style={{ gridColumn: 'span 2', minWidth: 0 }}>
        <div className="card-title">Reasoning</div>
        <div style={{ fontSize: 13.5, lineHeight: 1.6, marginTop: 8, color: 'var(--ink-2)', wordBreak: 'break-word' }}>
          {t.reasoning || a?.summary || '—'}
        </div>
      </div>
    </div>
  );
}

function DiagnosticsPanel({ a, incident }) {
  const d = a?.diagnostic_report;
  if (!d) return <Empty incident={incident} />;
  return (
    <div className="grid-2">
      <div className="card" style={{ gridColumn: 'span 2' }}>
        <div className="card-head">
          <div className="card-title">LLM summary</div>
          <span className="chip">{d.llm_enhanced ? 'LLM-enhanced' : 'rule-based'}</span>
        </div>
        <div style={{ fontSize: 14, lineHeight: 1.65, color: 'var(--ink-2)', fontStyle: 'italic' }}>
          “{d.readable_summary || '—'}”
        </div>
      </div>
      <div className="card">
        <div className="card-title">Error patterns</div>
        <div className="col" style={{ gap: 4, marginTop: 8 }}>
          {(d.error_patterns || []).map((p, i) => (
            <code key={i} className="mono" style={{ fontSize: 12, padding: '4px 8px', background: 'var(--surface-2)', borderRadius: 4 }}>{p}</code>
          ))}
        </div>
      </div>
      <div className="card">
        <div className="card-title">Affected services</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
          {(d.affected_services || []).map((s, i) => <span key={i} className="chip red">{s}</span>)}
        </div>
      </div>
      <div className="card" style={{ gridColumn: 'span 2' }}>
        <div className="card-title">Correlated symptoms</div>
        <ul style={{ margin: '8px 0 0 18px', fontSize: 13.5, lineHeight: 1.6 }}>
          {(d.correlated_symptoms || []).map((c, i) => <li key={i}>{c}</li>)}
        </ul>
      </div>
    </div>
  );
}

function RCAPanel({ a, incident }) {
  const r = a?.rca_report;
  if (!r) return <Empty incident={incident} />;
  const top = r.top_root_cause;
  return (
    <div className="grid-2">
      <div className="card">
        <div className="card-title">RAG matches</div>
        <div className="serif" style={{ fontSize: 32, fontWeight: 600, marginTop: 6 }}>
          {r.rag_match_count ?? 0}
        </div>
        <div className="muted mono-xs">historical incidents searched</div>
      </div>
      <div className="card">
        <div className="card-title">Top root cause</div>
        {top ? (
          <>
            <div style={{ fontSize: 14, fontWeight: 600, marginTop: 6 }}>{top.root_cause}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
              <div className="bar accent" style={{ flex: 1 }}>
                <span style={{ width: `${Math.round((top.confidence || 0) * 100)}%` }}></span>
              </div>
              <span className="mono-xs">{Math.round((top.confidence || 0) * 100)}%</span>
            </div>
            <div className="mono-xs muted" style={{ marginTop: 4 }}>match · {top.historical_id || '—'}</div>
          </>
        ) : <div className="muted">No match.</div>}
      </div>

      {r.llm_reasoning && (
        <div className="card" style={{ gridColumn: 'span 2' }}>
          <div className="card-title">Reasoning chain · LLM</div>
          <div style={{ fontSize: 13.5, lineHeight: 1.65, marginTop: 8, color: 'var(--ink-2)', whiteSpace: 'pre-wrap' }}>
            {r.llm_reasoning}
          </div>
        </div>
      )}

      <div className="card" style={{ gridColumn: 'span 2' }}>
        <div className="card-title" style={{ marginBottom: 10 }}>Ranked hypotheses</div>
        {(a.hypotheses || []).map((h, i) => (
          <div key={i} style={{
            padding: 12, borderBottom: i < (a.hypotheses.length - 1) ? '1px solid var(--line)' : 'none',
            background: i === 0 ? 'var(--surface-2)' : 'transparent',
            borderRadius: i === 0 ? 'var(--radius-sm)' : 0,
            marginBottom: i === 0 ? 8 : 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="chip">{`#${i + 1}`}</span>
              <span style={{ fontSize: 13.5, fontWeight: 600 }}>{h.root_cause}</span>
              <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, minWidth: 180 }}>
                <div className="bar accent" style={{ flex: 1 }}>
                  <span style={{ width: `${Math.round((h.confidence || 0) * 100)}%` }}></span>
                </div>
                <span className="mono-xs">{Math.round((h.confidence || 0) * 100)}%</span>
              </div>
            </div>
            {h.reasoning && <div style={{ fontSize: 12.5, color: 'var(--ink-3)', marginTop: 6 }}>{h.reasoning}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

function RemediationPanel({ a, incident, runAction }) {
  const r = a?.remediation_plan;
  if (!r) return <Empty incident={incident} />;
  const safety = r.safety_status;
  return (
    <>
      {r.needs_approval && (
        <div className="card" style={{ background: 'var(--amber-soft)', borderColor: 'transparent', marginBottom: 14 }}>
          <strong>Human approval required.</strong>{' '}
          <span style={{ color: 'var(--ink-2)' }}>{r.safety_message || 'policy gate engaged.'}</span>
        </div>
      )}
      <div className="grid-2">
        <div className="card">
          <div className="card-title">Recommended action</div>
          <code className="mono" style={{ display: 'block', fontSize: 13, marginTop: 8, padding: 10, background: 'var(--surface-2)', borderRadius: 6 }}>
            $ {r.recommended_action}
          </code>
          <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
            <span className={`chip ${safety === 'ALLOWED' ? 'green' : safety === 'BLOCKED' ? 'red' : 'amber'}`}>{safety}</span>
            <span className="chip">{r.playbook_id}</span>
            <span className="chip">{Math.round((r.confidence || 0) * 100)}%</span>
          </div>
        </div>
        <div className="card">
          <div className="card-title">Decision</div>
          {incident && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
              <button className="btn accent" onClick={() => runAction('approve', incident)}>Approve & execute</button>
              <button className="btn danger" onClick={() => runAction('deny', incident)}>Deny & escalate</button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function CommsPanel({ a, incident }) {
  if (!a) return <Empty incident={incident} />;
  const slackSent = a.slack_sent || incident?.slack_sent;
  const jira = incident?.jira_ticket_key;
  return (
    <div className="grid-2">
      <div className="card">
        <div className="card-head">
          <div className="card-title">Slack · #incidents</div>
          <span className={`chip ${slackSent ? 'green' : ''}`}>{slackSent ? 'posted' : 'pending'}</span>
        </div>
        <div className="card" style={{ background: 'var(--surface-2)', borderColor: 'transparent', marginTop: 10 }}>
          <div className="mono-xs muted" style={{ marginBottom: 4 }}>OPS Agent · APP</div>
          <div style={{ fontSize: 13, lineHeight: 1.55 }}>
            <strong>🚨 {a.severity} · {incident?.id}</strong> {incident?.type?.replaceAll('_', ' ')}<br />
            <span className="muted">↳ {a.hypotheses?.[0]?.root_cause}</span><br />
            <span className="muted">↳ {a.top_recommendation}</span>
          </div>
        </div>
      </div>
      <div className="card">
        <div className="card-head">
          <div className="card-title">Jira ticket</div>
          <span className={`chip ${jira ? 'green' : ''}`}>{jira ? 'created' : 'pending'}</span>
        </div>
        {jira ? (
          <>
            <div className="mono-xs muted">{jira}</div>
            <div style={{ fontSize: 13.5, fontWeight: 600, margin: '4px 0' }}>[{a.severity}] {incident?.type?.replaceAll('_', ' ')}</div>
            <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.6 }}>
              {a.summary}
            </div>
          </>
        ) : <div className="muted" style={{ fontSize: 13 }}>No ticket yet.</div>}
      </div>
    </div>
  );
}
