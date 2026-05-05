import React, { useState } from 'react';
import { api } from '../api.js';
import { severityTone } from '../agents.js';
import { Sparkline } from '../components/Sparkline.jsx';

// ---------- Knowledge ----------
const KB_DEMO = [
  { id: 'INC-1827', t: 'orders-db pool exhaustion', sev: 'P1' },
  { id: 'INC-1612', t: 'query plan flip', sev: 'P2' },
  { id: 'INC-1991', t: 'gateway circuit cascade', sev: 'P2' },
  { id: 'INC-2003', t: 'replica lag → reads stalled', sev: 'P2' },
  { id: 'INC-1450', t: 'auth latency p99 spike', sev: 'P3' },
  { id: 'INC-1399', t: 'CDN cache miss', sev: 'P3' },
  { id: 'INC-1287', t: 'memory leak payments-svc', sev: 'P1' },
];

export function KnowledgeScreen() {
  const [sel, setSel] = useState(KB_DEMO[0]);
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr 320px', minHeight: 'calc(100vh - 60px)' }}>
      <div style={{ borderRight: '1px solid var(--line)', padding: 16, background: 'var(--bg)' }}>
        <h2 className="serif" style={{ fontSize: 20, margin: 0 }}>ChromaDB</h2>
        <div className="muted mono-xs" style={{ marginBottom: 10 }}>21 incidents indexed</div>
        <input type="search" placeholder="Search…" style={{ width: '100%', marginBottom: 10 }} />
        <div className="col" style={{ gap: 6 }}>
          {KB_DEMO.map(i => (
            <button
              key={i.id}
              className="card"
              onClick={() => setSel(i)}
              style={{
                textAlign: 'left', padding: 10, cursor: 'pointer',
                borderColor: sel.id === i.id ? 'var(--ink)' : 'var(--line)',
              }}>
              <div className="mono-xs muted">{i.id}</div>
              <div style={{ fontSize: 13 }}>{i.t}</div>
              <span className={`chip ${severityTone(i.sev)}`} style={{ marginTop: 4 }}>{i.sev}</span>
            </button>
          ))}
        </div>
      </div>

      <div style={{ padding: 28, overflow: 'auto' }}>
        <h1>{sel.id} · {sel.t}</h1>
        <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
          <span className={`chip ${severityTone(sel.sev)}`}>{sel.sev}</span>
          <span className="chip">resolved</span>
          <span className="chip">32d ago</span>
          <span className="chip violet">embedding · text-3-small</span>
        </div>
        <div className="grid-2">
          <div className="card">
            <div className="card-title">Symptoms</div>
            <ul style={{ margin: '8px 0 0 18px', fontSize: 13.5, lineHeight: 1.65 }}>
              <li>5xx surge checkout-svc</li>
              <li>p99 latency 8× baseline</li>
              <li>PoolExhaustedException</li>
            </ul>
          </div>
          <div className="card">
            <div className="card-title">Root cause</div>
            <div style={{ fontSize: 13.5, lineHeight: 1.65, marginTop: 8 }}>
              Pool size (20) too small after marketing-driven traffic 3×; long queries held connections.
            </div>
          </div>
          <div className="card" style={{ gridColumn: 'span 2' }}>
            <div className="card-title">Resolution</div>
            <ol style={{ margin: '8px 0 0 18px', fontSize: 13.5, lineHeight: 1.65 }}>
              <li>scaled checkout replicas +3</li>
              <li>restarted pool</li>
              <li>raised maxConn 20 → 50</li>
              <li>added pool-utilization alert at 70%</li>
            </ol>
          </div>
          <div className="card" style={{ gridColumn: 'span 2' }}>
            <div className="card-title">Embedding · vector preview</div>
            <div style={{ display: 'flex', gap: 2, marginTop: 12, alignItems: 'flex-end', height: 60 }}>
              {Array.from({ length: 64 }).map((_, i) => (
                <div key={i} style={{
                  flex: 1,
                  height: `${20 + Math.abs(Math.sin(i * 0.7)) * 80}%`,
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
          docs · 21<br />last reindex · 6h ago<br />avg query · 312ms<br />collection · incidents-v2
        </div>
      </div>
    </div>
  );
}

// ---------- History ----------
const HIST_DEMO = [
  { id: 'INC-2038', t: 'Auth latency p99', d: '2d ago', mttr: '3m 41s', sev: 'P3', cause: 'JWT verifier cache TTL too short' },
  { id: 'INC-2032', t: 'Payments timeout cascade', d: '5d ago', mttr: '8m 12s', sev: 'P1', cause: 'Upstream gateway slow + missing retry budget' },
  { id: 'INC-2027', t: 'CDN purge propagation', d: '9d ago', mttr: '2m 04s', sev: 'P2', cause: 'Stale config in 1/3 edge regions' },
];

export function HistoryScreen() {
  return (
    <div className="page">
      <h1>History · post-mortems</h1>
      <div className="subtitle">Long-term incident patterns and resolution playbooks.</div>

      <div className="grid-4" style={{ marginBottom: 18 }}>
        {[
          ['Incidents', 47],
          ['Auto-resolved', 31],
          ['Avg MTTR', '4m 12s'],
          ['Agent accuracy', '88%'],
        ].map(([k, v]) => (
          <div key={k} className="card kpi">
            <div className="k">{k}</div>
            <div className="v">{v}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-title" style={{ marginBottom: 8 }}>Timeline · last 30d</div>
        <svg viewBox="0 0 800 80" style={{ width: '100%' }}>
          <line x1="0" y1="50" x2="800" y2="50" stroke="var(--line-2)" strokeWidth="1.4" />
          {[0,1,0,0,2,0,1,0,0,3,1,0,0,0,1,2,0,0,1,0,0,0,1,4,1,0,0,1,2,1].map((n, i) =>
            Array.from({ length: n }).map((_, j) => (
              <circle
                key={`${i}-${j}`}
                cx={(i / 29) * 760 + 20}
                cy={50 - j * 8 - 6}
                r="3.5"
                fill={['var(--red)', 'var(--amber)', 'var(--green)'][(i + j) % 3]}
              />
            ))
          )}
          {[0, 7, 14, 21, 28].map(d => (
            <text key={d} x={(d / 29) * 760 + 20} y="72" textAnchor="middle" fontFamily="var(--mono)" fontSize="9" fill="var(--ink-3)">d-{29 - d}</text>
          ))}
        </svg>
      </div>

      <h2 className="serif" style={{ fontSize: 20, marginTop: 28, marginBottom: 12 }}>Post-mortems</h2>
      <div className="col">
        {HIST_DEMO.map(p => (
          <div key={p.id} className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className={`chip ${severityTone(p.sev)}`}>{p.sev}</span>
              <span className="mono-xs muted">{p.id}</span>
              <span style={{ fontSize: 14, fontWeight: 600 }}>{p.t}</span>
              <span className="mono-xs muted" style={{ marginLeft: 'auto' }}>{p.d} · MTTR {p.mttr}</span>
            </div>
            <div style={{ fontSize: 13, color: 'var(--ink-2)', marginTop: 8 }}>↳ {p.cause}</div>
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button className="btn sm">Replay timeline</button>
              <button className="btn sm ghost">Export PDF</button>
              <button className="btn sm ghost">Add to KB</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
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

// ---------- Settings ----------
export function SettingsScreen() {
  const [section, setSection] = useState('policy');
  return (
    <div className="split">
      <div className="side">
        <div className="side-section">Settings</div>
        {[
          ['policy', 'Policy engine'],
          ['llm', 'LLM mode'],
          ['integrations', 'Integrations'],
          ['agents', 'Agents'],
          ['notifications', 'Notifications'],
          ['audit', 'Audit log'],
        ].map(([k, l]) => (
          <div key={k} className={`side-item ${section === k ? 'active' : ''}`} onClick={() => setSection(k)}>
            {l}
          </div>
        ))}
      </div>
      <div className="main">
        {section === 'policy' && <PolicySettings />}
        {section !== 'policy' && (
          <>
            <h1 style={{ textTransform: 'capitalize' }}>{section}</h1>
            <div className="empty">Configuration UI placeholder.</div>
          </>
        )}
      </div>
    </div>
  );
}

function PolicySettings() {
  const classes = [
    { c: 'safe', tone: 'green', d: 'auto-execute', actions: ['scale +N', 'rotate logs', 'clear cache'] },
    { c: 'risky', tone: 'amber', d: 'human approval required', actions: ['restart service', 'pool resize', 'failover'] },
    { c: 'forbidden', tone: 'red', d: 'never auto-attempted', actions: ['drop table', 'rm -rf', 'rotate prod keys'] },
  ];
  return (
    <>
      <h1>Policy engine</h1>
      <div className="subtitle">Classifies actions safe / risky / forbidden — gates remediation autonomy.</div>
      <h2 className="serif" style={{ fontSize: 18, marginTop: 18 }}>Action classes</h2>
      <div className="col">
        {classes.map(p => (
          <div key={p.c} className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className={`chip ${p.tone}`}>{p.c}</span>
              <span className="mono-xs muted">{p.d}</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
              {p.actions.map(a => <span key={a} className="chip">{a}</span>)}
              <span className="chip" style={{ borderStyle: 'dashed' }}>+ add</span>
            </div>
          </div>
        ))}
      </div>
      <h2 className="serif" style={{ fontSize: 18, marginTop: 22 }}>Approval thresholds</h2>
      <div className="card">
        <div className="grid-3">
          {[
            ['auto-execute below', 'P3'],
            ['min RCA confidence', '70%'],
            ['max blast radius', '1 service'],
          ].map(([k, v]) => (
            <div key={k}>
              <div className="label">{k}</div>
              <div className="serif" style={{ fontSize: 22, fontWeight: 600 }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
