const BASE = '/api';

async function req(path, opts = {}) {
  const r = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

export const api = {
  state: () => req('/state'),
  tick: () => req('/tick', { method: 'POST' }),
  setAuto: (on) => req(`/auto?on=${on}`, { method: 'POST' }),
  inject: (incident_type, severity = 'P2') =>
    req('/inject', { method: 'POST', body: JSON.stringify({ incident_type, severity }) }),
  approve: (id) => req(`/incidents/${id}/approve`, { method: 'POST' }),
  deny: (id) => req(`/incidents/${id}/deny`, { method: 'POST' }),
  reanalyze: () => req('/reanalyze', { method: 'POST' }),
  injectLogs: (text) =>
    req('/logs/inject', { method: 'POST', body: JSON.stringify({ text }) }),
  history: () => req('/history'),
  kb: () => req('/kb'),
  kbIngest: (incident_id) =>
    req('/kb/ingest', { method: 'POST', body: JSON.stringify({ incident_id }) }),
};

export function subscribeEvents(onState) {
  const es = new EventSource(BASE + '/events');
  es.onmessage = (e) => {
    try { onState(JSON.parse(e.data)); } catch {}
  };
  return () => es.close();
}
