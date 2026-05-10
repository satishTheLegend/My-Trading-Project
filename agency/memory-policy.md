# Memory Policy

## Memory Types

1. User rules.
2. Token memory.
3. Strategy memory.
4. Market regime memory.
5. Risk memory.
6. Execution memory.
7. Journal memory.
8. Safety memory.
9. Learning insights.

## User Instruction Learning

When the user gives instructions, classify as:
- Permanent rule.
- Temporary rule.
- Strategy preference.
- Risk preference.
- Execution preference.
- Symbol note.
- Reporting preference.
- Safety rule.

Examples:
- "Avoid this token" → token memory.
- "Use isolated margin" → execution/risk rule.
- "Stop after two losses" → safety rule.
- "Prefer shorts after pumps" → strategy preference.
- "Send short reports" → reporting preference.

## Memory Safety

Never store:
- API keys.
- Secret keys.
- Passwords.
- Private credentials.
- Withdrawal permissions.
- Sensitive account secrets.

## Learning Limits

The agency may learn:
- Better filters.
- Better timing.
- Better no-trade conditions.
- Better reporting.
- Better symbol avoidance.
- Better exit timing.

The agency may not automatically learn:
- Higher leverage.
- Bigger max loss.
- Wider stop-loss.
- Disabled safety rules.
- Ignoring stop-loss.
