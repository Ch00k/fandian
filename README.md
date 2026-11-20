# fandian

An autonomous black-box exploratory tester for web apps. Each run starts a fresh instance of a project from its own
Docker image and seed, lets Claude Code use it in a headless browser from a container of its own, files what it finds as
GitHub issues in the project's repository, and destroys the instance. It never sees the project's code.

The name is Old English _fandian_, "to try, test, explore". The command is `fand`.

A project makes itself testable with a `.fandian/` directory: [docs/TARGETS.md](docs/TARGETS.md).

## Setup

You need `uv`, Docker and git.

```
make install
cp .env.example .env
```

Then fill in `.env`:

- `FANDIAN_CLAUDE_TOKEN`: the output of `claude setup-token`. The tester runs on the plan behind it, and a run is
  refused unless paid overage is switched off on that plan.
- `FANDIAN_GITHUB_TOKEN_<OWNER>_<REPO>`, one per project: a fine-grained personal access token
  (https://github.com/settings/personal-access-tokens/new) whose repository access is only the project's repository and
  whose only permission is Issues: Read and write. A run refuses any other kind of token, and creates the labels it
  uses.

## Run

```
fand run ~/projects/example newcomer                  # a session of the newcomer persona
fand run https://github.com/owner/example newcomer    # the same, cloned from the repository
fand run ~/projects/example newcomer --check          # start the instance, print the wiring, stop
fand run ~/projects/example newcomer --focus search    # one feature only
```

A repository is cloned into `~/.cache/fandian/` with your own git credentials, and brought up to date on each run.

A run checks the GitHub token and the Claude plan, builds the tester's image (`fandian-agent`) and the project's
(`fandian-target-<name>`), starts the instance on a Docker network of its own (with a Mailpit inbox when the project
sends mail), waits for its health path and starts the tester. The terminal shows a short live log. When the tester ends,
or the run is interrupted, the instance, its inbox and its network are removed with their data.

Each run leaves `findings/run-<stamp>-<name>-<persona>[-<focus>]/`: `charter.md` (the instructions the tester was
given), its `JOURNAL.md`, `SUMMARY.md`, `evidence/` and `issues/`, the browser's snapshots, Claude Code's `transcript/`,
and `instance.log`, the instance's own output. Screenshots stay there: an issue names them, since GitHub takes no
attachments through its API.

## Findings

Findings are issues labelled `fandian`, with `persona:*`, `severity:*`, `oracle:*` (the layer of the oracle stack the
finding breaks) and `focus:*` on a focused run. Each run starts by reading the open ones and the last run records, and
ends by filing its own record as a closed `fandian-run` issue. The tester never closes a finding: it labels one it no
longer reproduces `fandian:appears-fixed`, and reopens one that breaks again. Close a finding yourself once you have
checked the fix, or let the fix's pull request close it.

## What is here

- `charter/`: the tester's instructions, composed on the host with the project's profile, persona and focus, and
  mounted read-only into its container.
- `personas/`: the generic personas. A project can add its own.
- `Dockerfile`, `entrypoint.sh`, `progress.jq`: the tester's container and its live log.
- `src/fandian/`: the `fand` command. `make check` lints, type-checks and tests it.
