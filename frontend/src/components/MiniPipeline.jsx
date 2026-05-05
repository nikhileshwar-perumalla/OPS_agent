import React from 'react';
import { AGENTS } from '../agents.js';
import { AgentNode } from './AgentNode.jsx';
import { FlowPath } from './FlowPath.jsx';

export function MiniPipeline({ stages = {}, size = 44 }) {
  // workflow_stages keys: triage, diagnostics, rca, remediation, comms
  return (
    <div className="pipeline">
      {AGENTS.map((a, i) => {
        const st = stages[a.id]?.status || 'pending';
        const state = st === 'complete' ? 'done' : st === 'active' || st === 'running' ? 'active' : 'idle';
        return (
          <React.Fragment key={a.id}>
            <AgentNode agent={a} state={state} size={size} showMeta={false} />
            {i < AGENTS.length - 1 && (
              <svg width="48" height="36" viewBox="0 0 48 36" style={{ flexShrink: 0 }}>
                <FlowPath
                  d="M 4 18 Q 24 10, 44 18"
                  packets={state === 'done' || state === 'active' ? 2 : 0}
                  dur={1.6}
                  color={state === 'done' ? 'var(--green)' : 'var(--amber)'}
                />
                <path d="M 38 14 L 44 18 L 38 22" stroke="var(--line-2)" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
