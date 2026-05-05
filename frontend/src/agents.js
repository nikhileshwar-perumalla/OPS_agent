// Shared agent metadata
export const AGENTS = [
  { id: 'triage',     emoji: '🔍', name: 'Triage',       tag: 'P1/P2/P3',   color: 'amber' },
  { id: 'diagnostics',emoji: '🔬', name: 'Diagnostics',  tag: 'log corr.',  color: 'blue' },
  { id: 'rca',        emoji: '🧠', name: 'RCA',          tag: 'RAG search', color: 'violet' },
  { id: 'remediation',emoji: '🛠️', name: 'Remediation',  tag: 'policy chk', color: 'green' },
  { id: 'comms',      emoji: '📡', name: 'Comms',        tag: 'slack/jira', color: 'red' },
];

export const ORCH = { id: 'orchestrator', emoji: '🎯', name: 'Orchestrator', tag: 'coord.' };

export const AGENT_BY_ID = Object.fromEntries(AGENTS.map(a => [a.id, a]));

export function severityTone(sev) {
  if (!sev) return '';
  const s = String(sev).toUpperCase();
  if (s.includes('P1') || s === 'CRITICAL') return 'red';
  if (s.includes('P2')) return 'amber';
  if (s.includes('P3')) return 'green';
  return '';
}
