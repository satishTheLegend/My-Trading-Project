# GitHub setup (optional)

Claude Code does **not** require GitHub. It's a local CLI that reads files from your filesystem. Everything in `claude-code-routine.md` works without ever pushing anywhere.

GitHub is useful for:

- **Backup** — your laptop dies, you don't lose months of agent tuning
- **Version history** — see how the agency evolved, roll back bad changes
- **Multi-machine sync** — same project on laptop + desktop + VPS
- **24/7 trading** — clone to a VPS and run full-auto from there

If you don't need any of those, skip this file.

---

## 1. CRITICAL: protect your secrets first

Before you even `git init`, do this audit:

```bash
cd ~/Documents/Claude/Projects/My-Trading-Project

# 1. Make sure .env exists in .gitignore
grep -E "^\.env" .gitignore
# → expects: .env

# 2. Confirm .env is NOT in your project (you may have it elsewhere)
ls -la .env 2>/dev/null && echo "WARNING: .env exists locally — gitignore must catch it" || echo "OK: no .env"

# 3. Scan for any accidentally-hardcoded secrets:
grep -rE 'BINANCE_API_KEY\s*=\s*"[a-zA-Z0-9]{10,}"' . 2>/dev/null && echo "FOUND HARDCODED KEY — fix before pushing" || echo "OK: no hardcoded keys"
grep -rE 'TELEGRAM_BOT_TOKEN\s*=\s*"[0-9]{6,}:[a-zA-Z0-9_-]{20,}"' . 2>/dev/null && echo "FOUND HARDCODED TOKEN" || echo "OK: no hardcoded tokens"
grep -rEn '"[a-f0-9]{64}"' --include='*.py' --include='*.md' . 2>/dev/null | grep -v "test_binance_signed_client" && echo "FOUND 64-hex string (might be a leaked HMAC secret)" || echo "OK: no leaked HMAC secrets"

# 4. Verify the .gitignore covers data/runtime files (your trading activity)
git check-ignore data/risk-state.json data/open-positions.json 2>/dev/null \
  || echo "If these print no output above, runtime data/ files are NOT ignored — fix .gitignore."
```

If anything fails the audit, **fix it before initializing git**. Once a secret is in any commit (even later removed), it's effectively public forever.

---

## 2. Initialize the repo

```bash
cd ~/Documents/Claude/Projects/My-Trading-Project

git init
git add .
git status                 # READ THIS CAREFULLY before committing

# Verify .env and any data/*.json are NOT in the staged list.
# If they are, fix .gitignore and `git rm --cached <file>` them.

git commit -m "Initial agency commit"
```

After `git status`, the staged list should look something like:

```
.gitignore
CLAUDE.md
wiki.md
claude-code-routine.md
github-setup.md
.claude/
agency/
agents/
config/env.example
config/*.example.json
memory/
scripts/
tests/
tools/
```

It should **not** include:

- `.env`
- Any `config/*.json` that isn't `.example.json`
- `data/*.json` or `data/*.jsonl` (your trading activity)
- `__pycache__/`

If you see any of those, stop, fix `.gitignore`, then `git rm --cached <file>` them.

---

## 3. Pick public or private

For a trading agency, **default to private**. Here's why:

- A public repo with your agency code lets anyone reverse-engineer your strategy.
- If you ever accidentally commit a secret, public means scanner bots find it in seconds.
- Your `memory/trade-journal.md` (if tracked) leaks your PnL history.

```bash
# Using GitHub CLI:
gh repo create my-trading-agency --private --source=. --push

# Or manually create a private repo on github.com, then:
git remote add origin git@github.com:YOUR_USER/my-trading-agency.git
git push -u origin main
```

If you're absolutely sure you want public, that's your call — just be doubly sure the audit in section 1 passes and you've added pre-commit hooks.

---

## 4. Pre-commit hook (recommended)

Install [`gitleaks`](https://github.com/gitleaks/gitleaks) and a hook that blocks commits with secrets:

```bash
# Install gitleaks (macOS):
brew install gitleaks

# Add a pre-commit hook:
cat > .git/hooks/pre-commit <<'EOF'
#!/usr/bin/env bash
gitleaks protect --staged --redact -v
EOF
chmod +x .git/hooks/pre-commit
```

Now any commit that contains an API-key-shaped string or token gets blocked locally before it reaches GitHub.

---

## 5. Multi-machine workflow

Once the repo is on GitHub:

```bash
# On the second machine (laptop, VPS, etc.):
git clone git@github.com:YOUR_USER/my-trading-agency.git
cd my-trading-agency

# Set up env vars LOCALLY on this machine — they're not in the repo:
cp config/env.example .env
$EDITOR .env

# Verify and run as usual:
python tools/run_offline_tests.py
claude
```

Each machine has its own `.env`, its own `data/*.json` (since runtime state is gitignored), and its own `.claude/settings.local.json`. Code + agency definitions are shared via git.

---

## 6. Running 24/7 on a VPS for full-auto

For full-auto live trading you generally want a VPS so the cycles run when you're sleeping.

```bash
# Provision a tiny VPS (1 vCPU / 1GB is plenty — Python stdlib only).
# Standard ssh key setup, then:

ssh user@your-vps
git clone git@github.com:YOUR_USER/my-trading-agency.git
cd my-trading-agency

# Set env vars:
cp config/env.example .env
$EDITOR .env
# Set MODE=live, ALLOW_LIVE_EXECUTION=true, BINANCE_API_KEY, etc.

# Run a smoke test:
set -a; source .env; set +a
python tools/run_offline_tests.py
python -m scripts.run_safety_reset --status

# Run the full-auto cycle every 15 min via cron:
crontab -e
```

Add to crontab:

```cron
# Full-auto cycle every 15 min (logs to ~/auto.log)
*/15 * * * * cd ~/my-trading-agency && set -a; source .env; set +a && \
    python -m scripts.run_full_auto_cycle \
        --i-understand-this-fires-trades-without-asking --top 3 \
    >> ~/auto.log 2>&1

# Watcher loop (continuous in tmux is more reliable than cron for this)
# In tmux: tmux new -s watcher; cd ~/my-trading-agency; set -a; source .env; set +a; \
#          python -m scripts.run_watch_positions --loop --interval 60

# Daily reconcile + safety state every minute (cheap)
* * * * * cd ~/my-trading-agency && set -a; source .env; set +a && \
    python -m scripts.run_reconcile --pause-on-mismatch >> ~/reconcile.log 2>&1
```

Claude Code can connect to a VPS too (`claude` over `mosh`/`ssh`), so you can audit the VPS state from anywhere.

---

## 7. What to commit, what not to commit

| Path | Commit? | Why |
|---|---|---|
| `CLAUDE.md`, `wiki.md`, `claude-code-routine.md`, `github-setup.md` | ✅ Yes | Reference docs |
| `.claude/agents/*.md`, `.claude/commands/*.md` | ✅ | Agent definitions |
| `agency/*.md` | ✅ | Policy files |
| `agents/*/*.md` | ✅ | Agent details |
| `scripts/*.py`, `tests/*.py`, `tools/*.py` | ✅ | Code |
| `config/*.example.*` | ✅ | Templates |
| `.gitignore`, `requirements.txt` | ✅ | |
| `.env` | ❌ Never | Secrets |
| `config/runtime-config.json` (non-example) | ❌ | Local override, may have wallet sizes |
| `data/*.json`, `data/*.jsonl` | ❌ | Live trading state — leaks PnL, positions |
| `memory/*.md` | ⚠️ Your call | History; useful for backup but reveals strategy |
| `.claude/settings.local.json` | ❌ | Per-user permissions / hooks |
| `__pycache__/`, `.pytest_cache/` | ❌ | Build artifacts |

The `.gitignore` shipped with this project handles all of this automatically.

---

## 8. If you accidentally pushed a secret

1. **Rotate the secret immediately** — Binance: revoke the API key, create a new one. Telegram: revoke the bot, create a new one with `@BotFather`.
2. Don't bother trying to scrub git history on a public repo — assume it's been scraped.
3. For private repos, you can do `git filter-repo` or use BFG to remove from history, but rotation is still mandatory.

---

## 9. GitHub-specific Claude Code features (optional)

Claude Code can do useful things if you set up the GitHub CLI:

```bash
brew install gh        # or: https://cli.github.com
gh auth login
```

Then in Claude Code chat:

> "Open a PR on the main branch with the changes I just made, titled 'Tighten the approval threshold to $25', and add a description explaining why."

Claude will use `gh pr create`. Useful for:
- Reviewing diffs before merging
- Keeping a paper trail when you change risk caps
- Collaborating if multiple people manage the agency

For the trading agency itself, the most valuable GitHub feature is **branch protection on main**: require PR review before any change to `agency/safety-rules.md` or `scripts/risk_engine.py` lands. Even if you're solo, the friction prevents 2-AM "I'll just bump the leverage cap a bit" mistakes.

---

## TL;DR

1. **Claude Code does not need GitHub** — it works on local files.
2. If you want backup / sync / VPS deployment, push to a **private** repo.
3. Audit for secrets first (`.gitignore` already handles `.env`, runtime state, and common typo filenames).
4. On any second machine, set up `.env` locally; the code + agency definitions come from git.
5. For 24/7 full-auto: VPS + cron + watcher in tmux.
