# Inter-Agent Communication Protocol

All agents communicate using structured JSON-compatible messages. The orchestrator routes messages and enforces authority order.

## Message Envelope

```json
{
  "from_agent": "",
  "to_agent": "",
  "message_type": "request | response | update | warning | error | approval | rejection | escalation | emergency",
  "priority": "low | medium | high | critical",
  "mode": "PAPER_TRADING | SEMI_AUTO_LIVE | FULL_AUTO_LIVE",
  "symbol": "",
  "summary": "",
  "details": {},
  "required_action": "",
  "timestamp": ""
}
```

## Message Types

- `request`: ask another agent for analysis or action.
- `response`: structured reply to a request.
- `update`: state change notification (e.g., position update).
- `warning`: non-blocking risk signal.
- `error`: recoverable failure.
- `approval` / `rejection`: from Risk Manager or Safety Agent.
- `escalation`: bump to higher-authority agent.
- `emergency`: immediate Safety Agent intervention.

## Priority Routing

- `critical`: Safety Agent first, then orchestrator.
- `high`: Risk Manager + orchestrator.
- `medium`: orchestrator routes per workflow.
- `low`: queued, not blocking.

## Authority Enforcement

- Safety Agent can override any message with `emergency`.
- Risk Manager can reject any trade-related message.
- Execution Agent acts only on approved plans, never on raw proposals.
- Watcher and Exit Agents can escalate to Safety Agent for emergency exits.

## Standard Payload Schemas

See `CLAUDE.md` for:
- Trade Proposal Format
- Risk Approval Format
- Execution Plan Format
- Position State Format

All agents must use these schemas when relevant.

## Logging

All inter-agent messages relevant to a trade must be journaled by the Journal & Accounting Agent. API secrets must never appear in any message.
