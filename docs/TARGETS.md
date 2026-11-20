# Making a project testable

fandian tests a project the way a user would: it starts a fresh instance of it, signs in and uses it, and never sees its
code. Everything it needs to know about a project lives in that project's repository, in a `.fandian/` directory at its
root:

```
.fandian/
  profile.md             how to start the instance, and what the tester should know about it
  personas/<name>.md     optional: personas of the project's own
  focus/<name>.md        optional: focuses, each narrowing a run to one feature
```

fandian reads only this directory, on the host, and builds the instance from the checkout's own `Dockerfile`. None of
the checkout reaches the tester's container. The text of these files becomes part of the tester's instructions: it can
narrow what the tester does, but never widen where it may send data or where its findings go.

## What the project must provide

- **One container.** A `Dockerfile` at the root that builds the app, and a command that prepares and seeds it and then
  serves. Services beside it, such as a separate database, are not started.
- **A seed.** The accounts and data every run starts from, the same on every run. Its credentials are public development
  ones, written in the profile.
- **One HTTP port and a health path**, which answers once the app is ready. The tester reaches the app at
  `http://localhost:<port>`, so the app must accept the host name `localhost`. Nothing is published to the host, so the
  app may listen on every interface.
- **Sign-in by email and password**, for the accounts the personas use.
- **Mail, if the app sends any**, in plain SMTP to the host and port it is given, with no TLS or login. The profile's
  `[mail]` table puts a Mailpit inbox beside the instance as `mailpit`, SMTP on port 1025; point the app at it in
  `[instance] env`.
- **Nothing real written to.** Every outside service the app writes to (payments, filings, messages) must be a fake or a
  sandbox the tester cannot harm. Outside sources the app only reads may stay real; name them under Hazards.

Optional, and worth having:

- **A user guide the app serves.** With one, the tester runs in oracle mode: the guide is what it checks the product
  against, and the guide is tested too.
- **Harness pages** that show what the fakes received and set what they answer next, and a clock a run can move. Name
  them under Off-limits, with what the tester may use them for.

## The profile

`.fandian/profile.md` opens with a TOML header between `+++` lines. The body below it is the tester's section about the
project.

```toml
+++
repo = "owner/example"  # the GitHub repository findings are filed in

[instance]
command = "sh -c 'migrate && seed && serve on port 8080'"  # split as a shell would split it
port = 8080
health = "/health/"  # polled until it answers, before the tester starts

[instance.env]  # optional; public values only
DEBUG = "1"
SMTP_HOST = "mailpit"
SMTP_PORT = "1025"

[mail]  # optional; present = a Mailpit inbox beside the instance
allowed_recipients = '@example\.[a-z]+$'  # optional; Mailpit refuses any other address, as a bounce

[accounts]  # from the seed, by the keys personas name
user = { email = "dev@example.com", password = "devpassword" }
empty = { email = "new@example.com", password = "devpassword" }

[guide]  # optional; present = oracle mode
urls = ["/help/"]  # the guide's pages, as paths on the instance
+++
```

**Accounts.** fandian's own personas name accounts by role, so map each role the project can supply:

| Role    | The account                                                                |
| ------- | -------------------------------------------------------------------------- |
| `user`  | the main seeded account, with data in it; the one most personas sign in as |
| `empty` | an account with nothing in it, as a first visit finds it                   |

Add any other accounts under keys of your own for the project's personas, and describe every seeded account in the body.

**The body** holds these sections, as Markdown under a `## TARGET: <name>` heading:

- **Purpose**: a paragraph on what the product is for and who uses it. The tester judges features against it.
- **The seed**: every account, what it holds and what it is for, and any other seeded state worth testing (an
  invitation, a document in flight).
- **Surfaces**: what besides the web pages is in scope, such as an API, and how to reach it.
- **Hazards**: what the instance still reaches outside itself, and how gently to treat it; anything that costs money.
- **Off-limits**: pages and actions the tester must not touch, and harness pages with what it may use them for.

Where the body names the instance's address, write `$BASE_URL`.

## Personas and focuses

A persona file has a header and a body, its section of the instructions:

```toml
+++
enabled = true
account = "user"  # optional: a key in the profile's [accounts]; without one it starts signed out
+++
```

A project's personas sit beside fandian's; a name both define is refused.

A focus narrows a run to one feature (`fand run <target> <persona> --focus <name>`) and is its whole mission. Its header
names the personas it is written for:

```toml
+++
personas = ["explorer"]
+++
```

Write a focus from what the guide says about the feature, never from its code.

## Running it

```
fand run ~/projects/example explorer --check
fand run https://github.com/owner/example explorer
```

The repository named by `repo` needs a GitHub token in fandian's `.env`, under `FANDIAN_GITHUB_TOKEN_<OWNER>_<REPO>`:
the repository in upper case with every other character `_`.
