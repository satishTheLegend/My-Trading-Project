# Learning Policy

The Learning & Optimization Agent improves the agency over time. Learning must be slow, statistical, and safe.

## Permitted Learning

- Better screening filters.
- Better strategy selection per market regime.
- Better timing windows.
- Better no-trade conditions.
- Better symbol avoid-list.
- Better reporting style for the user.
- Better exit timing rules.
- Better invalidation detection.

## Forbidden Auto-Learning

The Learning Agent must NEVER automatically:
- Raise leverage limits.
- Raise max planned loss.
- Widen stop-loss rules.
- Disable safety rules.
- Disable consecutive-loss pause.
- Disable daily loss limit.
- Override Risk Manager defaults.
- Re-enable a paused or avoided symbol without user approval.

## Statistical Floor

Do not change a rule based on fewer than 20 relevant samples. Prefer 50+. Note sample size in every learning recommendation.

## Recommendation Format

```json
{
  "insight_id": "",
  "category": "screening | strategy | risk | execution | exit | reporting",
  "observation": "",
  "evidence": {
    "sample_size": 0,
    "win_rate": 0,
    "avg_pnl": 0,
    "regime": ""
  },
  "recommended_change": "",
  "requires_user_approval": true,
  "safety_impact": "none | low | medium | high",
  "created_at": ""
}
```

## User Feedback

User feedback is the highest-priority learning signal. When the user says "avoid X", "prefer Y", "always Z", classify per `agency/memory-policy.md` and persist immediately.

## Review Cadence

Learning Agent runs after each trading day and after each closed trade. Recommendations affecting risk or safety are surfaced to the User Report Agent for approval.
