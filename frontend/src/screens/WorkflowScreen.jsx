import React, { useEffect, useRef, useState } from 'react';
import { severityTone } from '../agents.js';
import { FlowPath } from '../components/FlowPath.jsx';

const STAGE_KEYS = ['triage', 'diagnostics', 'rca', 'remediation', 'comms'];

/**
 * Replay the agent pipeline on the client. The server returns the whole
 * analysis at once (engine.tick is sync). We animate progress from idle →
 * active → done so the user perceives the walkthrough.
 *
 * Returns { reachedIdx, activeIdx, complete } where indexes are positions
 * within STAGE_KEYS.
 */
function usePipelineReplay(incidentId, stages, retried) {
  const [step, setStep] = useState(0);
  const [phase, setPhase] = useState('idle'); // 'forward' | 'retry' | 'done' | 'idle'
  const lastIdRef = useRef(null);

  useEffect(() => {
    if (!incidentId || !stages || !STAGE_KEYS.every(k => stages[k]?.status === 'complete')) {
      setStep(0);
      setPhase('idle');
      lastIdRef.current = null;
      return;
    }
    // Restart replay only when the incident changes
    if (lastIdRef.current === incidentId) return;
    lastIdRef.current = incidentId;
    setStep(0);
    setPhase('forward');

    // Build the timeline of "events" we'll step through:
    //   forward:  triage → diag → rca
    //   if retried:  rca-loop-back, diag, rca
    //   continue:  remed → comms
    const events = ['triage', 'diagnostics', 'rca'];
    if (retried) events.push('retry-back', 'diagnostics', 'rca');
    events.push('remediation', 'comms', 'done');

    let i = 0;
    const tick = () => {
      i += 1;
      if (i >= events.length) {
        setPhase('done');
        return;
      }
      const ev = events[i];
      if (ev === 'retry-back') {
        setPhase('retry');
      } else if (ev === 'done') {
        setPhase('done');
      } else {
        setPhase(p => (p === 'retry' ? 'forward' : p));
        const idx = STAGE_KEYS.indexOf(ev);
        if (idx >= 0) setStep(idx);
      }
      timer = setTimeout(tick, ev === 'retry-back' ? 900 : 700);
    };
    let timer = setTimeout(tick, 700);
    return () => clearTimeout(timer);
  }, [incidentId, stages, retried]);

  return { step, phase };
}

export function WorkflowScreen({ state, selected, selectedId, onSelect }) {
  const incidents = state?.incidents ?? [];
  const incident = selected || incidents[0];
  const a = incident?.analysis;
  const stages = a?.workflow_stages || {};
  const retried = !!stages?.rca?.retried;
  const conversation = a?.agent_conversation || [];
  const waiting = incident && !a;

  const { step, phase } = usePipelineReplay(incident?.id, stages, retried);

  return (
    <div className="page" style={{ maxWidth: 1480 }}>
      <h1>Agent workflow</h1>
      <div className="subtitle">
        {incident
          ? <>Live pipeline for <span className="mono">{incident.id}</span> · {incident.type.replaceAll('_', ' ')}</>
          : 'No active incident — pipeline idle'}
      </div>

      {incidents.length > 0 && (
        <div className="card" style={{ marginBottom: 16, padding: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <span className="label">Showing</span>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {incidents.map(inc => {
                const sev = inc.analysis?.severity || 'P2';
                const active = inc.id === incident?.id;
                const ready = !!inc.analysis;
                return (
                  <button
                    key={inc.id}
                    onClick={() => onSelect?.(inc.id)}
                    className="chip"
                    style={{
                      cursor: 'pointer',
                      borderColor: active ? 'var(--ink)' : 'var(--line)',
                      background: active ? 'var(--ink)' : 'var(--surface)',
                      color: active ? 'var(--bg)' : 'var(--ink-2)',
                      padding: '5px 12px',
                    }}
                  >
                    <span className={`dot ${ready ? '' : 'pulse'}`}
                      style={{ background: ready ? 'var(--green)' : 'var(--amber)' }}></span>
                    <span className="mono-xs">{inc.id}</span>
                    <span style={{ opacity: 0.85 }}>· {inc.type.replaceAll('_', ' ')}</span>
                    <span className={`chip ${severityTone(sev)}`} style={{ padding: '0 6px', fontSize: 10 }}>{sev}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <div className="card elevated" style={{ padding: 28, position: 'relative' }}>
        <PipelineDiagram
          stages={stages}
          waiting={waiting}
          replayStep={step}
          replayPhase={phase}
          retried={retried}
        />
        <div style={{
          position: 'absolute', top: 14, right: 18,
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 12, color: 'var(--ink-3)',
        }}>
          {waiting && (<><span className="dot amber pulse"></span> Waiting for first analysis…</>)}
          {!waiting && phase === 'forward' && (<><span className="dot amber pulse"></span> Running stage {step + 1} / 5</>)}
          {!waiting && phase === 'retry' && (<><span className="dot" style={{ background: 'var(--red)' }}></span> Low confidence · re-diagnosing</>)}
          {!waiting && phase === 'done' && a && (<><span className="dot" style={{ background: 'var(--green)' }}></span> Pipeline complete · {a.pipeline_duration_ms?.toFixed?.(0)}ms</>)}
        </div>
      </div>

      <div className="grid-3" style={{ marginTop: 18 }}>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 8 }}>Latest payload</div>
          <div className="card-sub mono-xs" style={{ marginBottom: 8 }}>diagnostics → rca</div>
          <pre className="mono" style={{ fontSize: 11.5, margin: 0, whiteSpace: 'pre-wrap', lineHeight: 1.5, color: 'var(--ink-2)', maxHeight: 180, overflow: 'auto' }}>
{a ? JSON.stringify({
  service: a.diagnostic_report?.affected_services?.[0] || 'n/a',
  symptoms: a.triage_report?.symptoms?.slice(0, 4) || [],
  candidates: a.hypotheses?.slice(0, 3).map(h => h.root_cause) || [],
  retried,
}, null, 2) : (waiting ? '— pipeline running, no payload yet —' : '— pipeline idle —')}
          </pre>
        </div>

        <div className="card">
          <div className="card-title" style={{ marginBottom: 8 }}>Bus messages</div>
          <div style={{ maxHeight: 200, overflow: 'auto' }}>
            {conversation.length === 0 && (
              <div className="muted" style={{ fontSize: 13 }}>
                {waiting ? 'Pipeline starting…' : 'No traffic.'}
              </div>
            )}
            {conversation.map((m, i) => (
              <div key={i} className="logline">
                <span className="mono-xs muted" style={{ minWidth: 48 }}>
                  {m.duration_ms != null ? `${Number(m.duration_ms).toFixed(0)}ms` : '—'}
                </span>
                <span style={{ minWidth: 80 }}>{m.sender}</span>
                <span className="muted">{m.type}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-title" style={{ marginBottom: 8 }}>Legend</div>
          <div className="col" style={{ gap: 8, fontSize: 13 }}>
            <div><span className="dot" style={{ background: 'var(--green)' }}></span> &nbsp;completed step</div>
            <div><span className="dot pulse" style={{ background: 'var(--amber)' }}></span> &nbsp;active step</div>
            <div><span className="dot"></span> &nbsp;queued</div>
            <div><span className="dot" style={{ background: 'var(--red)' }}></span> &nbsp;feedback loop (only when retry fired)</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PipelineDiagram({ stages, waiting, replayStep, replayPhase, retried }) {
  const positions = [
    { key: null,            x: 60,   label: 'Incident',    emoji: '⚡', color: 'var(--red-soft)' },
    { key: 'triage',        x: 260,  label: 'Triage',      emoji: '🔍' },
    { key: 'diagnostics',   x: 460,  label: 'Diagnostics', emoji: '🔬' },
    { key: 'rca',           x: 660,  label: 'RCA',         emoji: '🧠' },
    { key: 'remediation',   x: 860,  label: 'Remediation', emoji: '🛠️' },
    { key: 'comms',         x: 1060, label: 'Comms',       emoji: '📡' },
  ];

  // Determine each stage's visual status from replay progress.
  // replayStep is the index into STAGE_KEYS = [triage, diag, rca, remed, comms].
  const stageStatus = (k) => {
    if (!k) return 'done';
    const allComplete = stages?.[k]?.status === 'complete';
    if (waiting) return k === 'triage' ? 'active' : 'idle';
    if (!allComplete) return 'idle';
    if (replayPhase === 'idle') return 'idle';
    if (replayPhase === 'done') return 'done';
    const idx = STAGE_KEYS.indexOf(k);
    if (idx < replayStep) return 'done';
    if (idx === replayStep) return 'active';
    return 'idle';
  };

  const colorFor = (a, b) => {
    const sa = stageStatus(a);
    const sb = stageStatus(b);
    if (sa === 'done' && (sb === 'done' || sb === 'active')) return 'var(--green)';
    if (sb === 'active') return 'var(--amber)';
    return 'var(--line-2)';
  };

  const packetsFor = (a, b) => {
    const sa = stageStatus(a);
    const sb = stageStatus(b);
    if (sa === 'done' && sb === 'done') return 2;
    if (sb === 'active') return 2;
    return 0;
  };

  const fillFor = (s) => {
    if (s === 'done') return 'var(--green-soft)';
    if (s === 'active') return '#FFF6E5';
    return 'var(--surface)';
  };
  const strokeFor = (s) => {
    if (s === 'active') return 'var(--amber)';
    if (s === 'done') return 'transparent';
    return 'var(--line)';
  };

  // Show feedback loop only when a retry actually happened, and only
  // animate it when we're currently in the 'retry' replay phase.
  const showLoop = retried;
  const loopActive = replayPhase === 'retry';

  return (
    <svg viewBox="0 0 1120 280" style={{ width: '100%', height: 320 }}>
      {positions.slice(0, -1).map((p, i) => {
        const next = positions[i + 1];
        return (
          <FlowPath
            key={i}
            d={`M ${p.x + 38} 140 Q ${(p.x + next.x) / 2} 110, ${next.x - 38} 140`}
            packets={packetsFor(p.key, next.key)}
            color={colorFor(p.key, next.key)}
            dur={1.6}
            stroke="var(--line-2)"
          />
        );
      })}

      {positions.slice(1).map(p => (
        <path
          key={`arr-${p.x}`}
          d={`M ${p.x - 44} 136 L ${p.x - 38} 140 L ${p.x - 44} 144`}
          stroke="var(--line-2)"
          strokeWidth="1.4"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}

      {showLoop && (
        <g style={{ opacity: loopActive ? 1 : 0.35, transition: 'opacity 200ms' }}>
          <FlowPath
            d="M 660 175 Q 660 245, 540 245 Q 420 245, 460 175"
            packets={loopActive ? 2 : 0}
            dur={1.6}
            color="var(--red)"
            dash
            stroke={loopActive ? 'var(--red)' : 'var(--line-2)'}
          />
          <text x="500" y="265" fontFamily="var(--sans)" fontSize="11" fill="var(--red)" fontWeight="500">
            ↻ low-confidence retry
          </text>
        </g>
      )}

      {positions.map((p) => {
        const status = stageStatus(p.key);
        const meta = p.key ? stages[p.key] : null;
        return (
          <g key={p.x}>
            <circle
              cx={p.x}
              cy={140}
              r="34"
              fill={p.color || fillFor(status)}
              stroke={strokeFor(status)}
              strokeWidth="1.5"
              style={{ transition: 'fill 200ms, stroke 200ms' }}
            />
            <text x={p.x} y={148} textAnchor="middle" fontSize="22">{p.emoji}</text>
            <text x={p.x} y={195} textAnchor="middle" fontFamily="var(--sans)" fontSize="13" fontWeight="600" fill="var(--ink)">
              {p.label}
            </text>
            {meta && (
              <text x={p.x} y={212} textAnchor="middle" fontFamily="var(--mono)" fontSize="10" fill="var(--ink-3)">
                {meta.duration_ms != null ? `${Number(meta.duration_ms).toFixed(0)}ms` : (meta.status || '—')}
              </text>
            )}
            {status === 'active' && (
              <circle cx={p.x + 26} cy={114} r="6" fill="var(--amber)" stroke="var(--ink)" strokeWidth="0.8">
                <animate attributeName="r" values="5;8;5" dur="1.4s" repeatCount="indefinite" />
              </circle>
            )}
          </g>
        );
      })}
    </svg>
  );
}
