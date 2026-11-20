## MAILBOX

Your mailbox is at `$MAILBOX_URL` (`echo $MAILBOX_URL`): the mail sent to `$ACCOUNT_EMAIL`, the latest first. Read it
in the browser, or as JSON:

```sh
curl -s "$MAILBOX_URL/api/messages" | jq            # every message: id, from, subject, date
curl -s "$MAILBOX_URL/api/messages/<id>" | jq       # one message: its text, HTML and attachments
curl -s -o "$RUN_DIR/evidence/<file>" "$MAILBOX_URL<attachment url>"
```

- Mail the product sends you is part of the product, and under test: its wording, its links, and its attachments and
  their figures against the pages they come from. Open its links in the browser, as you would from any mailbox.
- The mailbox itself is not part of the product. How it looks and works is never a finding.
