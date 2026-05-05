import React, { useEffect, useState } from 'react';

/**
 * Modal that reveals the agent's recovery playbook step-by-step
 * after approve/deny. Steps are pulled from the system log.
 */
export function PlaybookModal({ incident, kind, steps, onClose }) {
  const [revealed, setRevealed] = useState(0);

  useEffect(() => {
    setRevealed(0);
    if (!steps?.length) return;
    const id = setInterval(() => {
      setRevealed(r => {
        if (r >= steps.length) { clearInterval(id); return r; }
        return r + 1;
      });
    }, 550);
    return () => clearInterval(id);
  }, [steps]);

  if (!incident) return null;

  const isApprove = kind === 'approve';
  const accent = isApprove ? 'var(--green)' : 'var(--red)';
  const accentSoft = isApprove ? 'var(--green-soft)' : 'var(--red-soft)';
  const verb = isApprove ? 'Executing recovery' : 'Escalating to L3';
  const done = revealed >= (steps?.length || 0);

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        background: 'rgba(31, 30, 29, 0.45)',
        backdropFilter: 'blur(2px)',
        display: 'grid', placeItems: 'center',
        animation: 'fade-in 180ms ease',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        className="card elevated"
        style={{
          width: 580, maxWidth: '90vw', maxHeight: '80vh',
          display: 'flex', flexDirection: 'column',
          padding: 0, overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{
          padding: '18px 22px',
          borderBottom: '1px solid var(--line)',
          background: accentSoft,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{
              width: 28, height: 28, borderRadius: '50%',
              background: accent, color: 'white',
              display: 'grid', placeItems: 'center',
              fontSize: 14, fontWeight: 600,
            }}>
              {isApprove ? '✓' : '↑'}
            </span>
            <div>
              <div style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 500 }}>
                {isApprove ? 'Action approved' : 'Action denied'}
              </div>
              <div className="serif" style={{ fontSize: 18, fontWeight: 600 }}>
                {verb} · <span className="mono" style={{ fontSize: 14 }}>{incident.id}</span>
              </div>
            </div>
            <div style={{ marginLeft: 'auto' }}>
              <button className="btn sm ghost" onClick={onClose}>Close</button>
            </div>
          </div>
        </div>

        {/* Steps */}
        <div style={{ padding: 22, overflow: 'auto', flex: 1 }}>
          {(steps || []).length === 0 ? (
            <div className="muted" style={{ fontSize: 13 }}>No playbook steps captured.</div>
          ) : (
            <div style={{ position: 'relative' }}>
              {/* connector line */}
              <div style={{
                position: 'absolute', left: 11, top: 4, bottom: 4,
                width: 2, background: 'var(--line)',
              }} />
              {steps.map((step, i) => {
                const shown = i < revealed;
                const active = i === revealed - 1 && !done;
                return (
                  <div
                    key={i}
                    style={{
                      display: 'flex', gap: 14,
                      paddingBottom: i === steps.length - 1 ? 0 : 14,
                      opacity: shown ? 1 : 0.25,
                      transform: shown ? 'translateX(0)' : 'translateX(-6px)',
                      transition: 'opacity 280ms ease, transform 280ms ease',
                      position: 'relative',
                    }}
                  >
                    <div style={{
                      width: 24, height: 24, borderRadius: '50%',
                      background: shown ? accent : 'var(--bg-2)',
                      border: `2px solid ${shown ? accent : 'var(--line-2)'}`,
                      display: 'grid', placeItems: 'center',
                      flexShrink: 0,
                      color: 'white', fontSize: 11, fontWeight: 600,
                      zIndex: 1,
                    }}>
                      {shown && !active ? '✓' : ''}
                    </div>
                    <div style={{
                      flex: 1,
                      padding: '4px 0 0',
                    }}>
                      <code className="mono" style={{
                        fontSize: 12.5,
                        color: shown ? 'var(--ink)' : 'var(--ink-3)',
                        lineHeight: 1.5,
                      }}>{step}</code>
                      {active && (
                        <div className="mono-xs muted" style={{ marginTop: 4 }}>
                          <span className="dot pulse" style={{ background: accent }}></span>
                          &nbsp;running…
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '14px 22px',
          borderTop: '1px solid var(--line)',
          background: 'var(--surface-2)',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          {done ? (
            <>
              <span className="dot" style={{ background: accent }}></span>
              <span style={{ fontSize: 13, fontWeight: 500 }}>
                {isApprove ? 'Incident resolved.' : 'Incident escalated to L3.'}
              </span>
              <button className="btn primary sm" style={{ marginLeft: 'auto' }} onClick={onClose}>Done</button>
            </>
          ) : (
            <>
              <span className="dot pulse" style={{ background: accent }}></span>
              <span style={{ fontSize: 13, color: 'var(--ink-2)' }}>
                Step {revealed} of {steps?.length || 0}
              </span>
            </>
          )}
        </div>
      </div>
      <style>{`
        @keyframes fade-in { from { opacity: 0 } to { opacity: 1 } }
      `}</style>
    </div>
  );
}

/**
 * Capture playbook steps from the system log delta after approve/deny.
 * Returns lines that look like recovery actions or escalation events.
 */
export function extractPlaybookSteps(beforeLogs, afterLogs, kind) {
  const before = new Set(beforeLogs || []);
  const newLines = (afterLogs || []).filter(l => !before.has(l));
  const steps = [];
  for (const line of newLines) {
    // strip leading "[HH:MM:SS] "
    const m = line.match(/^\[\d{2}:\d{2}:\d{2}\]\s*(.*)$/);
    const body = m ? m[1] : line;
    if (
      body.startsWith('[Action]') ||
      body.startsWith('[Jira]') ||
      (kind === 'deny' && body.includes('Escalat')) ||
      body.includes('RESOLVED') ||
      body.includes('Cooldown')
    ) {
      // tidy "[Action] > foo" → "foo"
      let pretty = body
        .replace(/^\[Action\]\s*>\s*/, '')
        .replace(/^\[Action\]\s*/, '')
        .replace(/^\[Engine\]\s*/, '')
        .replace(/^\[Jira\]\s*/, 'jira · ');
      steps.push(pretty);
    }
  }
  return steps;
}
