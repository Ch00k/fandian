# fandian

A generic, autonomous black-box exploratory tester for web apps: Claude Code in Docker uses a fresh, seeded local
instance of a project and files findings as GitHub issues in the project's repository. The command is `fand`. Usage:
README.md. Design and decisions: docs/PLAN.md (kept local, not committed). The convention a project follows: docs/TARGETS.md.

## Project lifecycle

**Alpha (0.0.x), single user (only me).** Breaking changes are fine; no backward compatibility, no migrations.

## Rules

- The repository is public, and names no project it tests and nothing of my employers'. Everything about one project
  lives in that project's `.fandian/`.
- The tester never sees a project's code: only `.fandian/` is read, on the host, and the checkout is never mounted.

## Layout

- `src/fandian/` - the `fand` command, run on the host. Python, standard library only; `make check` lints, type-checks
  and tests it (`tests/`). It composes the charter (`charter.py`) and mounts it into the container.
- `Dockerfile`, `entrypoint.sh`, `progress.jq` - the tester's container: the entrypoint launches Claude, whose output
  `progress.jq` cuts down to the live log.
- `charter/`, `personas/` - the generic charter sections and personas. A file's TOML header wires it and is left out of
  the charter.
