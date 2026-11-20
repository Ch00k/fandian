#!/usr/bin/env bash
set -euo pipefail

# `fand run` composes the charter on the host and mounts it, read-only, as /work/CLAUDE.md. It
# passes in: the target and the persona (TARGET, PERSONA) and the focus that narrows it, if any
# (FOCUS); what a user would have: the product's address (BASE_URL), the persona's login
# (ACCOUNT_EMAIL, ACCOUNT_PASSWORD) and mailbox (MAILBOX_URL), and the harness (HARNESS_URL), when
# there are; the repository and its token (GH_REPO, GH_TOKEN, REPO_VISIBILITY); this run's
# directory (RUN_DIR, the only part of findings/ mounted); the model (FANDIAN_MODEL,
# FANDIAN_EFFORT, when set), the Claude token (CLAUDE_CODE_OAUTH_TOKEN) and whether its output goes
# to a terminal (FANDIAN_COLOR).

# The browser keeps its page snapshots and unnamed screenshots in the run directory. It may write
# only there and under /work, which holds the run directory, so a named screenshot goes straight
# into the run's evidence.
mkdir -p "$RUN_DIR/evidence"
jq -n --arg out "$RUN_DIR/browser" '{mcpServers: {playwright: {
  command: "playwright-mcp", args: ["--headless", "--no-sandbox", "--isolated", "--output-dir", $out]
}}}' > /work/.mcp.json

# --- Pre-flight: the instance and the mailbox answer from inside the container, which shares the
# instance's network namespace ---
for url in "$BASE_URL" ${MAILBOX_URL:+"$MAILBOX_URL"}; do
  if ! curl -s -o /dev/null --max-time 10 "$url"; then
    echo "FATAL: the container cannot reach $url." >&2
    exit 1
  fi
done

# FANDIAN_CHECK=1 shows the wiring without launching the agent.
if [ "${FANDIAN_CHECK:-}" = "1" ]; then
  echo "target        : $TARGET, $BASE_URL"
  echo "persona       : $PERSONA"
  echo "focus         : ${FOCUS:-none}"
  echo "account       : ${ACCOUNT_EMAIL:-none}"
  echo "mailbox       : ${MAILBOX_URL:-none}"
  echo "harness       : ${HARNESS_URL:-none}"
  echo "repository    : $GH_REPO ($REPO_VISIBILITY), $(gh api "repos/$GH_REPO" --silent 2>/dev/null && echo "gh reaches it" || echo "gh CANNOT reach it")"
  echo "model         : ${FANDIAN_MODEL:-CLI default} (effort ${FANDIAN_EFFORT:-CLI default})"
  echo "run dir       : $RUN_DIR"
  echo "tools         : $(claude --version), playwright-mcp $(playwright-mcp --version 2>/dev/null || echo '?'), $(gh --version | head -1)"
  echo "charter       : $(grep -c '' /work/CLAUDE.md) lines; \`fand run --charter\` shows it"
  exit 0
fi

# --- Pre-flight: Claude runs on the operator's plan ---
# Anything Claude Code would pick over the plan's token (an ANTHROPIC_API_KEY, say) bills at API
# rates instead.
method="$(claude auth status | jq -r .authMethod)" || true
if [ "$method" != oauth_token ]; then
  echo "FATAL: claude would authenticate with ${method:-nothing}, not the plan's OAuth token - refusing to run at API rates." >&2
  exit 1
fi

if [ -n "${ACCOUNT_EMAIL:-}" ]; then
  start="sign in at $BASE_URL as your account ($ACCOUNT_EMAIL)"
else
  start="open $BASE_URL"
fi
prompt="Read your CLAUDE.md charter in full - you are the '$PERSONA' tester persona. Your run directory is $RUN_DIR (keep your journal and evidence there) and your findings go to GitHub issues in $GH_REPO - both per the charter's Reporting section. Then begin the exploratory test session: $start and work through your mission."
if [ -n "${FOCUS:-}" ]; then
  prompt+=" This run is focused on '$FOCUS': your FOCUS section is your whole mission."
fi
claude_flags=(--dangerously-skip-permissions)
if [ -n "${FANDIAN_MODEL:-}" ]; then
  claude_flags+=(--model "$FANDIAN_MODEL")
fi
if [ -n "${FANDIAN_EFFORT:-}" ]; then
  claude_flags+=(--effort "$FANDIAN_EFFORT")
fi

# Headless (-p), so Claude exits when the agent ends its session. progress.jq cuts its stream-json
# events down to a readable log, in colour on a terminal. Claude Code still keeps the full session
# transcript. stdin is closed so -p never waits on it.
color=false
if [ "${FANDIAN_COLOR:-}" = "1" ]; then
  color=true
fi
claude -p "${claude_flags[@]}" --output-format stream-json --verbose "$prompt" </dev/null \
  | jq -R --unbuffered -r --argjson color "$color" --argjson start "$(date +%s)" -f /opt/progress.jq
