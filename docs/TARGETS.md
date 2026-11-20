# Making a project testable

fandian tests a project the way a user would: it starts a fresh instance of it, signs in and uses it. The tester knows
what a user knows: the product's address, its own login and mailbox, why it came to the product, and, when the product's
outside services are simulated, the page that controls them. It never sees the project's code, and it is never told how
the instance is set up: which accounts exist, how mail is delivered, what the seed holds.

Everything fandian needs lives in the project's repository, in a `.fandian/` directory at its root:

```
.fandian/
  profile.md             how to start the instance, and why its user is here
  personas/<name>.md     optional: personas of the project's own
  focus/<name>.md        optional: focuses, each narrowing a run to one feature
```

fandian reads only this directory, on the host, and builds the instance from the checkout's own `Dockerfile`. None of
the checkout reaches the tester's container. The profile's header stays with fandian; its body, and the project's
personas and focuses, become part of the tester's instructions, where they can narrow what the tester does but never
widen where it may send data or where its findings go.

## What the project must provide

- **One container.** A `Dockerfile` at the root that builds the app, and a command that prepares and seeds it and then
  serves. Services beside it, such as a separate database, are not started.
- **A seed.** The accounts and data every run starts from, the same on every run, with public development credentials.
- **One HTTP port and a health path**, which answers once the app is ready. The tester reaches the app at
  `http://localhost:<port>`, so the app must accept the host name `localhost`. Nothing is published to the host, so the
  app may listen on every interface.
- **Error pages, not tracebacks.** Run the instance with the framework's debug mode off, so that a server error shows
  the product's own error page and no source code. Whatever the project allows only on a test instance (fakes, a seed
  with well-known passwords) needs a guard of its own that a deployment serving its users cannot pass, such as answering
  only to loopback host names.
- **Sign-in by email and password**, for the accounts the personas use.
- **Mail, if the app sends any**, in plain SMTP to the host and port it is given, with no TLS or login. The profile's
  `[mail]` table puts a Mailpit inbox beside the instance as `mailpit`, SMTP on port 1025; point the app at it in
  `[instance] env`. The tester reads only its own address's mail, in a mailbox fandian serves in front of Mailpit.
- **Nothing real written to.** Every outside service the app writes to (payments, filings, messages) must be a fake or a
  sandbox the tester cannot harm. Services the app only reads may stay real; the tester is told not to hammer the
  product.

Optional, and worth having:

- **A user guide the app serves**, linked from its own pages. The tester finds it as a user would and holds the product
  to it, and tests the guide too.
- **A harness** for the fakes: a page, for a signed-in account, that shows what each fake received from that account, as
  the real service would let its user see their own records, and sets what the fakes answer next and, with a clock the
  app can move, the date. Show each account only its own submissions. The tester is told that the outside services are
  simulated, and uses the harness to reach the situations their answers lead to.

## The profile

`.fandian/profile.md` opens with a TOML header between `+++` lines, for fandian alone. The body below it is the one part
the tester reads.

```toml
+++
repo = "owner/example"  # the GitHub repository findings are filed in

[instance]
command = "sh -c 'migrate && seed && serve on port 8080'"  # split as a shell would split it
port = 8080
health = "/health/"  # polled until it answers, before the tester starts

[instance.env]  # optional; public values only
SECRET_KEY = "not-secret"
ALLOWED_HOSTS = "localhost,127.0.0.1"
SMTP_HOST = "mailpit"
SMTP_PORT = "1025"

[mail]  # optional; present = a Mailpit inbox beside the instance, and the tester's mailbox
allowed_recipients = '@example\.[a-z]+$'  # optional; any other address bounces, and the tester is told so

[accounts]  # from the seed, by the keys personas name
user = { email = "dev@example.com", password = "devpassword" }
empty = { email = "new@example.com", password = "devpassword" }

[harness]  # optional; the page that shows and steers the fakes
path = "/fake/"
+++

You run a small agency and came here to send your clients invoices without keeping a spreadsheet. You rely on the totals
it gives you.
```

**The body** says, in a few sentences addressed to the tester, who the user is and why they came to the product. The
tester judges features against it. Say nothing about how the product is built or set up, which accounts exist, or what
the seed holds: a user would not know.

**Accounts.** fandian's personas name accounts by these keys, so map each one the project can supply:

| Key     | The account                                              |
| ------- | -------------------------------------------------------- |
| `user`  | the main seeded account, with data in it                 |
| `empty` | an account with nothing in it, as a first visit finds it |

Add other accounts under keys of your own for the project's personas. The tester is given only its own persona's login.

## Personas and focuses

A persona file has a header and a body, its section of the instructions:

```toml
+++
enabled = true
account = "empty"  # optional: a key in the profile's [accounts]; without one it starts signed out
+++
```

A project's personas sit beside fandian's; a name both define is refused.

A focus narrows a run to one feature (`fand run <target> <persona> --focus <name>`) and is its whole mission. Its header
names the personas it is written for:

```toml
+++
personas = ["newcomer"]
+++
```

Write a focus from what the product and its guide say about the feature, never from its code.

## Running it

```
fand run ~/projects/example newcomer --check
fand run https://github.com/owner/example newcomer
```

The repository named by `repo` needs a GitHub token in fandian's `.env`, under `FANDIAN_GITHUB_TOKEN_<OWNER>_<REPO>`:
the repository in upper case with every other character `_`.
