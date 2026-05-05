import React, { useEffect, useState, useCallback } from 'react';
import { AppShell } from './components/AppShell.jsx';
import { LiveScreen } from './screens/LiveScreen.jsx';
import { WorkflowScreen } from './screens/WorkflowScreen.jsx';
import { AgentsScreen } from './screens/AgentsScreen.jsx';
import { KnowledgeScreen, HistoryScreen, SimScreen } from './screens/MiscScreens.jsx';
import { api, subscribeEvents } from './api.js';

export default function App() {
  const [tab, setTab] = useState('live');
  const [state, setState] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const s = await api.state();
      setState(s);
    } catch (e) {
      console.warn('state fetch failed', e);
    }
  }, []);

  useEffect(() => {
    refresh();
    const stop = subscribeEvents((s) => setState(s));
    return stop;
  }, [refresh]);

  // Auto-select first incident if none picked, or if previous selection is gone.
  useEffect(() => {
    const ids = (state?.incidents || []).map(i => i.id);
    if (!ids.length) {
      if (selectedId) setSelectedId(null);
      return;
    }
    if (!selectedId || !ids.includes(selectedId)) {
      setSelectedId(ids[0]);
    }
  }, [state, selectedId]);

  const selected = state?.incidents?.find(i => i.id === selectedId) || null;

  return (
    <AppShell tab={tab} onTab={setTab} state={state}>
      {tab === 'live' && (
        <LiveScreen state={state} refresh={refresh}
          selectedId={selectedId} onSelect={setSelectedId} />
      )}
      {tab === 'workflow' && (
        <WorkflowScreen state={state} selected={selected}
          selectedId={selectedId} onSelect={setSelectedId} />
      )}
      {tab === 'agents' && (
        <AgentsScreen state={state} refresh={refresh} selected={selected}
          selectedId={selectedId} onSelect={setSelectedId} />
      )}
      {tab === 'knowledge' && <KnowledgeScreen />}
      {tab === 'history' && <HistoryScreen />}
      {tab === 'sim' && <SimScreen state={state} refresh={refresh} />}
    </AppShell>
  );
}
