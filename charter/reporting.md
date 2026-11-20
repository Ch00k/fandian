## Reporting: GitHub issues and your run directory

Your output goes to two places:

- **Findings go to GitHub issues** in **`$GH_REPO`**, through `gh`, which is already authenticated and pointed at that
  repository. It is the **one place outside the instance** you may send anything to, and only findings and your run
  record. Its token reaches that repository's issues and nothing else.
- **Working files go to your run directory, `$RUN_DIR`** (already created): `JOURNAL.md` (your running log, with the
  coverage map), `evidence/` (screenshots, saved responses and documents; give a screenshot the full path
  `$RUN_DIR/evidence/<name>.png` as its file name, with `$RUN_DIR` written out), `issues/` (the bodies you file, drafted
  first as files) and `SUMMARY.md` (your run record). `browser/` holds the browser's page snapshots, and `transcript/`
  Claude Code's own session log: leave both alone. Earlier runs' directories are not available to you; the issues are
  the record of what they found.

The issues are read by the project's owner, who acts on them. Keep them accurate: no duplicates, no speculation, nothing
filed that you have not reproduced.

### Before you test: read the record

List issues with every page read, and only their number, title and labels kept (`gh issue list` reads one page only):

```sh
gh api --paginate "repos/$GH_REPO/issues?per_page=100&<filter>" \
  | jq -s 'add | map(select(.pull_request | not) | {number, title, labels: [.labels[].name]})'
```

- **Open findings** (`<filter>` = `state=open&labels=fandian`): read each one in your area with
  `gh issue view <number> --comments`. This is your dedup list and your re-verify worklist.
- **Your persona's closed findings** (`state=closed&labels=fandian,persona:$PERSONA`): your regression list.
- **The last few run records** (`state=closed&labels=fandian-run&sort=created&direction=desc`, then
  `gh issue view <number>`): their coverage maps say which areas earlier runs covered thinly. Lean towards those.
- **On a focused run**, re-verify only the open findings in the FOCUS's feature, and take its closed findings
  (`state=closed&labels=fandian,focus:$FOCUS`) as your regression list in place of your persona's.

### Re-verify what is on record

- **Still reproduces:** do not file it again, and do not comment just to say so. Comment only when the behaviour has
  **changed** (worse, different or narrower), with the new evidence.
- **Appears fixed:** add the label `fandian:appears-fixed`
  (`gh issue edit <number> --add-label fandian:appears-fixed`) and comment with what you did and saw. **Never close a
  finding**: closing is the owner's call, or the fix's own pull request.
- **Labelled `fandian:appears-fixed` but reproduces again:** remove the label (`--remove-label`) and comment with the
  evidence.
- **A closed finding has broken again:** reopen it (`gh issue reopen <number>`) and comment with the evidence: one
  history per defect, not a fresh issue.

### Filing a new finding

- **One issue per defect.** The title states the defect in one line, as a fact ("Saving a contract with no end date
  drops its day cap").
- **Labels:** `fandian`, `persona:$PERSONA`, `severity:<blocker|major|minor|cosmetic>`, `oracle:<layer>`, and on a
  focused run `focus:$FOCUS` on a finding in the focus's feature. They exist already; add no others.
- **The body** leads with a header list: **Severity**, **Oracle** (the layer, and the claim, invariant or rule it
  breaks: for `guide`, the page's URL with its `#anchor` and the sentence quoted), **Persona**, **Account**, **Area**
  (the page's path), **Preconditions** (seeded accounts and data, and anything you changed first, such as the date on a
  test clock) and **Run** (your run directory's name). Then exact steps to reproduce, expected, actual, and evidence.
- **Evidence:** GitHub cannot take attachments through `gh`, so put text evidence (a response, console errors, a trimmed
  traceback) in the body, and name screenshots and documents by their file name in `evidence/`; the owner reads them
  from the run directory.
- **Quote what you test only inside fenced code blocks.** Text from the product can hold an `@name`, which would notify
  that GitHub user, or a `#123`, which would link an unrelated issue. Inside a code block both are inert. Write neither
  in your own prose.
- **How:** write the body to `$RUN_DIR/issues/<slug>.md`, then
  `gh issue create --title "<title>" --label "<label>,<label>" --body-file "$RUN_DIR/issues/<slug>.md"`. Note the issue
  number it returns in your journal.

**On a public repository** (`$REPO_VISIBILITY` is `public`), anything filed is readable by anyone. A finding that would
show credentials other than the seed's, secrets, or a security weakness (one user reaching another's data, a way past a
check) stays in `$RUN_DIR/issues/` and is not filed; the run record counts it as "held locally" without describing it.
On a private repository, everything is filed.

### The run record

At the end of the run, write `$RUN_DIR/SUMMARY.md`: the coverage map (each area, how deep you went, and what held as
well as what failed), the findings you filed (by severity, with their numbers), the re-verify results (still open,
appears fixed, reopened), findings held locally (a count), and testing limitations. File it as **one issue** titled
`Run <your run directory's name>`, labelled `fandian-run` and `persona:$PERSONA` (and `focus:$FOCUS` on a focused run).
Then close that issue (`gh issue close <number> --reason completed`): it is a record, not a work item.
