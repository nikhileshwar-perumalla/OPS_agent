# Dashboard V2 Architecture

## Goals
1. Replace ad-hoc component usage with `SimulationEngine`.
2. Implement "Tick" based update loop.
3. Visualize "Game State" (Tick count, Mode, Active Incidents).

## Changes in `dashboard/app.py`
1. **Initialization**:
   - `st.session_state.engine = SimulationEngine()`
   - Remove individual component inits (they are inside engine).

2. **Main Loop**:
   - Controls: [Step Tick] [Start Auto-Run] [Stop]
   - Mode Toggle: [SIMULATION] / [OBSERVE_ONLY]

3. **Visualization Update**:
   - `latest_state = engine.tick()` (if running)
   - Metrics Plot -> `latest_state['metrics']`
   - Logs -> `latest_state['log_features']`
   - Incident List -> `latest_state['incident_states']`

4. **Integration**:
   - Slack Polling still happens, but actions now route to `engine.handle_action()` (Future) or similar.

## Risk
- The `poll_slack_updates` fragment relies on `st.metrics_gen`. We need to fix that dependency.
- Need to expose `engine.metrics_generator` or proxy it.
