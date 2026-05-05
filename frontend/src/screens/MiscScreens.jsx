import React, { useState, useEffect } from 'react';
import { api } from '../api.js';
import { severityTone } from '../agents.js';
import { Sparkline } from '../components/Sparkline.jsx';
import { PlaybookModal } from '../components/PlaybookModal.jsx';

// ---------- Knowledge ----------
export function KnowledgeScreen() {
  const [items, setItems] = useState([]);
  const [sel, setSel] = useState(null);
  const [query, setQuery] = useState('');

  useEffect(() => {
    api.kb()
      .then(d => {
        setItems(d.items || []);
        if (d.items?.length) setSel(d.items[0]);
      })
      .catch(() => setItems([]));
  }, []);

  const filtered = items.filter(i => {
    if (!query) return true;
    const q = query.toLowerCase();
    return (
      i.id?.toLowerCase().includes(q) ||
      i.summary?.toLowerCase().includes(q) ||
      i.root_cause?.toLowerCase().includes(q)
    );
  });

  if (!sel) {
    return (
      <div style={{ padding: 28 }}>
        <h2 className="serif">ChromaDB</h2>
        <div className="muted">{items.length === 0 ? 'Loading knowledge base…' : 'No incidents found.'}</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr 320px', minHeight: 'calc(100vh - 60px)' }}>
      <div style={{ borderRight: '1px solid var(--line)', padding: 16, background: 'var(--bg)', overflow: 'auto', maxHeight: 'calc(100vh - 60px)' }}>
        <h2 className="serif" style={{ fontSize: 20, margin: 0 }}>ChromaDB</h2>
        <div className="muted mono-xs" style={{ marginBottom: 10 }}>{items.length} incidents indexed</div>
        <input
          type="search"
          placeholder="Search…"
          value={query}
          onChange={e => setQuery(e.target.value)}
          style={{ width: '100%', marginBottom: 10 }}
        />
        <div className="col" style={{ gap: 6 }}>
          {filtered.map(i => (
            <button
              key={i.id}
              className="card"
              onClick={() => setSel(i)}
              style={{
                textAlign: 'left', padding: 10, cursor: 'pointer',
                borderColor: sel.id === i.id ? 'var(--ink)' : 'var(--line)',
              }}>
              <div className="mono-xs muted">{i.id}</div>
              <div style={{ fontSize: 13 }}>{i.summary}</div>
              <span className={`chip ${severityTone(i.severity)}`} style={{ marginTop: 4 }}>{i.severity}</span>
            </button>
          ))}
        </div>
      </div>

      <div style={{ padding: 28, overflow: 'auto' }}>
        <h1>{sel.id} · {sel.summary}</h1>
        <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
          <span className={`chip ${severityTone(sel.severity)}`}>{sel.severity}</span>
          <span className="chip">resolved</span>
          <span className="chip violet">embedding · text-3-small</span>
        </div>
        <div className="grid-2">
          <div className="card">
            <div className="card-title">Logs signature</div>
            <div style={{ fontSize: 13.5, lineHeight: 1.65, marginTop: 8, fontFamily: 'monospace' }}>
              {sel.logs_signature || '—'}
            </div>
          </div>
          <div className="card">
            <div className="card-title">Recommended action</div>
            <div style={{ fontSize: 13.5, lineHeight: 1.65, marginTop: 8 }}>
              {sel.recommended_action || '—'}
            </div>
          </div>
          <div className="card" style={{ gridColumn: 'span 2' }}>
            <div className="card-title">Root cause</div>
            <div style={{ fontSize: 13.5, lineHeight: 1.65, marginTop: 8 }}>
              {sel.root_cause}
            </div>
          </div>
          <div className="card" style={{ gridColumn: 'span 2' }}>
            <div className="card-title">Resolution</div>
            <div style={{ fontSize: 13.5, lineHeight: 1.65, marginTop: 8 }}>
              {sel.resolution}
            </div>
          </div>
          <div className="card" style={{ gridColumn: 'span 2' }}>
            <div className="card-title">Embedding · vector preview</div>
            <div style={{ display: 'flex', gap: 2, marginTop: 12, alignItems: 'flex-end', height: 60 }}>
              {Array.from({ length: 64 }).map((_, i) => (
                <div key={i} style={{
                  flex: 1,
                  height: `${20 + Math.abs(Math.sin(i * 0.7 + (sel.id?.length || 0))) * 80}%`,
                  background: 'var(--ink-2)', borderRadius: 1,
                }} />
              ))}
            </div>
            <div className="mono-xs muted" style={{ marginTop: 6 }}>1536 dims · showing 64</div>
          </div>
        </div>
      </div>

      <div style={{ borderLeft: '1px solid var(--line)', padding: 16, background: 'var(--bg)' }}>
        <div className="card-title">Currently retrieved by</div>
        <div className="card" style={{ marginTop: 8 }}>
          <div className="mono-xs muted">live · in-flight</div>
          <div style={{ fontSize: 13 }}>RCA agent · 0.91 sim</div>
        </div>
        <div className="card-title" style={{ marginTop: 18 }}>Index health</div>
        <div style={{ fontSize: 13.5, lineHeight: 1.7, marginTop: 6, color: 'var(--ink-2)' }}>
          docs · {items.length}<br />avg query · 312ms<br />collection · incidents-v2
        </div>
      </div>
    </div>
  );
}

// ---------- History (real data from /api/history) ----------
export function HistoryScreen() {
  const [data, setData] = useState(null);
  const [replay, setReplay] = useState(null); // { incident, kind, steps }
  const [kbStatus, setKbStatus] = useState({}); // { [id]: 'pending' | 'ok' | 'err' }

  const refresh = async () => {
    try { setData(await api.history()); } catch (e) { console.warn(e); }
  };
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, []);

  const items = data?.items ?? [];
  const kpis = data?.kpis ?? {};

  const onReplay = (inc) => {
    const steps = buildResolutionSteps(inc);
    const kind = inc.state === 'ESCALATED' ? 'deny' : 'approve';
    setReplay({ incident: inc, kind, steps });
  };

  const onAddToKB = async (inc) => {
    setKbStatus(s => ({ ...s, [inc.id]: 'pending' }));
    try {
      await api.kbIngest(inc.id);
      setKbStatus(s => ({ ...s, [inc.id]: 'ok' }));
    } catch (e) {
      setKbStatus(s => ({ ...s, [inc.id]: 'err' }));
    }
  };

  return (
    <div className="page">
      <h1>History · post-mortems</h1>
      <div className="subtitle">
        {items.length > 0
          ? `Real resolved incidents from this session (${items.length} so far).`
          : 'No resolved incidents yet — approve or deny one in Live to populate this view.'}
      </div>

      <div className="grid-4" style={{ marginBottom: 18 }}>
        <Kpi k="Incidents (total)" v={kpis.incidents ?? 0} />
        <Kpi k="Resolved" v={kpis.resolved ?? 0} />
        <Kpi k="Auto-resolved" v={kpis.auto_resolved ?? 0} />
        <Kpi k="Avg ticks to resolve" v={kpis.avg_ticks ?? '—'} />
      </div>

      {items.length > 0 && (
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="card-title" style={{ marginBottom: 8 }}>Resolution timeline</div>
          <ResolutionDots items={items} />
        </div>
      )}

      <h2 className="serif" style={{ fontSize: 20, marginTop: 18, marginBottom: 12 }}>Post-mortems</h2>
      {items.length === 0 && (
        <div className="empty">No post-mortems yet.</div>
      )}
      <div className="col">
        {items.map(p => {
          const sev = p.analysis?.severity || 'P2';
          const summary = p.analysis?.summary || '—';
          const root = p.analysis?.hypotheses?.[0]?.root_cause || '—';
          const ticks = p.history?.length ? (p.history[p.history.length - 1][0] - p.start_tick) : null;
          const escalated = p.state === 'ESCALATED';
          const kbS = kbStatus[p.id];
          return (
            <div key={p.id} className="card">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <span className={`chip ${severityTone(sev)}`}>{sev}</span>
                <span className="mono-xs muted">{p.id}</span>
                <span style={{ fontSize: 14, fontWeight: 600 }}>{p.type.replaceAll('_', ' ')}</span>
                {escalated && <span className="chip red">escalated</span>}
                {p.jira_ticket_key && <span className="chip blue">{p.jira_ticket_key}</span>}
                <span className="mono-xs muted" style={{ marginLeft: 'auto' }}>
                  resolved at tick {p.history?.[p.history.length - 1]?.[0] ?? '?'} · {ticks != null ? `${ticks} ticks` : '—'}
                </span>
              </div>
              <div style={{ fontSize: 13, color: 'var(--ink-2)', marginTop: 8 }}>↳ {root}</div>
              <div style={{ fontSize: 12.5, color: 'var(--ink-3)', marginTop: 4 }}>{summary}</div>
              <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                <button className="btn sm" onClick={() => onReplay(p)}>Replay timeline</button>
                <button className="btn sm ghost" disabled title="Not implemented">Export PDF</button>
                <button
                  className={`btn sm ${kbS === 'ok' ? 'accent' : 'ghost'}`}
                  onClick={() => onAddToKB(p)}
                  disabled={kbS === 'pending' || kbS === 'ok'}
                >
                  {kbS === 'pending' ? 'Adding…' : kbS === 'ok' ? '✓ Added to KB' : kbS === 'err' ? 'Retry' : 'Add to KB'}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {replay && (
        <PlaybookModal
          incident={replay.incident}
          kind={replay.kind}
          steps={replay.steps}
          onClose={() => setReplay(null)}
        />
      )}
    </div>
  );
}

function Kpi({ k, v }) {
  return (
    <div className="card kpi">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
    </div>
  );
}

function ResolutionDots({ items }) {
  if (!items.length) return null;
  const ticks = items.map(i => i.history?.[i.history.length - 1]?.[0] || i.start_tick);
  const minT = Math.min(...ticks);
  const maxT = Math.max(...ticks);
  const span = Math.max(maxT - minT, 1);
  return (
    <svg viewBox="0 0 800 80" style={{ width: '100%' }}>
      <line x1="0" y1="50" x2="800" y2="50" stroke="var(--line-2)" strokeWidth="1.4" />
      {items.map((inc, i) => {
        const t = inc.history?.[inc.history.length - 1]?.[0] || inc.start_tick;
        const x = ((t - minT) / span) * 760 + 20;
        const tone = severityTone(inc.analysis?.severity || 'P2');
        const fill = tone === 'red' ? 'var(--red)' : tone === 'amber' ? 'var(--amber)' : 'var(--green)';
        return (
          <g key={inc.id}>
            <circle cx={x} cy="50" r="4" fill={fill} stroke="var(--ink)" strokeWidth="0.6">
              <title>{`${inc.id} · ${inc.type} · tick ${t}`}</title>
            </circle>
          </g>
        );
      })}
      <text x="20" y="72" fontFamily="var(--mono)" fontSize="9" fill="var(--ink-3)">tick {minT}</text>
      <text x="780" y="72" textAnchor="end" fontFamily="var(--mono)" fontSize="9" fill="var(--ink-3)">tick {maxT}</text>
    </svg>
  );
}

function buildResolutionSteps(inc) {
  const a = inc.analysis || {};
  const out = [];
  out.push(`Detected ${inc.type.replaceAll('_', ' ')} at tick ${inc.start_tick}`);
  if (a.severity) out.push(`Triage classified as ${a.severity}`);
  const symptoms = a.triage_report?.symptoms?.slice(0, 3) || [];
  if (symptoms.length) out.push(`Symptoms: ${symptoms.join(', ')}`);
  const cause = a.hypotheses?.[0]?.root_cause;
  if (cause) {
    const conf = Math.round((a.hypotheses[0].confidence || 0) * 100);
    out.push(`RCA top hypothesis (${conf}%): ${cause}`);
  }
  if (a.top_recommendation) out.push(`Recommended action: ${a.top_recommendation}`);
  if (inc.jira_ticket_key) out.push(`Jira ticket ${inc.jira_ticket_key} created`);
  out.push(inc.state === 'ESCALATED' ? 'User denied → escalated to L3' : 'User approved → executed playbook');
  out.push(`Final state: ${inc.state}`);
  return out;
}

// ---------- Sim ----------
const SIM_TYPES = [
  ['high_cpu', 'CPU spike'],
  ['memory_leak', 'Memory leak'],
  ['network_latency', 'Network latency'],
  ['service_down', 'Service down'],
  ['disk_usage_high', 'Disk high'],
  ['process_crash', 'Process crash'],
  ['database_lock', 'DB lock'],
  ['ssl_expiry', 'SSL expiry'],
];

export function SimScreen({ state, refresh }) {
  const [scenario, setScenario] = useState('high_cpu');
  const [severity, setSeverity] = useState('P2');
  const history = (state?.metrics_history ?? []).filter(Boolean);

  return (
    <div className="page">
      <h1>Simulation control</h1>
      <div className="subtitle">Drive the synthetic engine and inject incidents.</div>
      <div className="grid-2">
        <div className="card">
          <div className="card-title">Engine</div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn accent" onClick={async () => { await api.setAuto(true); refresh(); }}>▶ Run</button>
            <button className="btn" onClick={async () => { await api.setAuto(false); refresh(); }}>⏸ Pause</button>
            <button className="btn ghost" onClick={async () => { await api.tick(); refresh(); }}>⏭ Step</button>
          </div>
          <div className="grid-2" style={{ marginTop: 18 }}>
            <Stat k="tick" v={state?.tick ?? 0} />
            <Stat k="mode" v={state?.mode ?? '—'} />
            <Stat k="active incidents" v={state?.incidents?.length ?? 0} />
            <Stat k="LLM" v={state?.llm_active ? 'active' : 'mock'} />
          </div>
        </div>

        <div className="card">
          <div className="card-title">Inject incident</div>
          <div className="muted mono-xs">fire a synthetic incident into the engine</div>
          <div style={{ marginTop: 14 }}>
            <div className="label" style={{ marginBottom: 6 }}>Scenario</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {SIM_TYPES.map(([k, l]) => (
                <button
                  key={k}
                  className={`chip ${scenario === k ? 'solid' : ''}`}
                  onClick={() => setScenario(k)}
                  style={{ border: 0, cursor: 'pointer' }}
                >{l}</button>
              ))}
            </div>
          </div>
          <div style={{ marginTop: 14 }}>
            <div className="label" style={{ marginBottom: 6 }}>Severity hint</div>
            <div className="toggle">
              {['P1', 'P2', 'P3'].map(s => (
                <button key={s} className={severity === s ? 'on' : ''} onClick={() => setSeverity(s)}>{s}</button>
              ))}
            </div>
          </div>
          <button
            className="btn accent"
            style={{ marginTop: 18, width: '100%', justifyContent: 'center' }}
            onClick={async () => { await api.inject(scenario, severity); refresh(); }}
          >⚡ Inject now</button>
        </div>

        <div className="card" style={{ gridColumn: 'span 2' }}>
          <div className="card-title">Live metrics — synthetic stream</div>
          <div className="grid-4" style={{ marginTop: 12 }}>
            <SignalCell label="CPU %" series={history.map(m => m?.cpu_percent ?? 0)} value={state?.metrics?.cpu_percent} />
            <SignalCell label="Memory %" series={history.map(m => m?.memory_percent ?? 0)} value={state?.metrics?.memory_percent} />
            <SignalCell label="Latency (s)" series={history.map(m => m?.latency_seconds ?? 0)} value={state?.metrics?.latency_seconds} suffix="" />
            <SignalCell label="Disk %" series={history.map(m => m?.disk_percent ?? 0)} value={state?.metrics?.disk_percent} />
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ k, v }) {
  return (
    <div style={{ padding: 12, background: 'var(--surface-2)', borderRadius: 8 }}>
      <div className="label">{k}</div>
      <div className="serif" style={{ fontSize: 22, fontWeight: 600 }}>{v}</div>
    </div>
  );
}

function SignalCell({ label, series, value, suffix = '%' }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div className="label">{label}</div>
        <div className="serif" style={{ fontSize: 16, fontWeight: 600 }}>
          {value != null ? `${Number(value).toFixed(1)}${suffix}` : '—'}
        </div>
      </div>
      <Sparkline values={series} height={48} />
    </div>
  );
}

