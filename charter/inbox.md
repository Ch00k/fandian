## INBOX

Every message the instance sends lands in a Mailpit inbox at `$INBOX_URL` (`echo $INBOX_URL`), whatever the address. No
mail reaches a real person. Read it in the browser or through its API:

```sh
curl -s "$INBOX_URL/api/v1/messages" | jq '.messages[] | {ID, Created, Subject, To: [.To[].Address]}'
curl -s "$INBOX_URL/api/v1/message/<ID>" | jq '{Subject, Text, Attachments}'
curl -s -o "$RUN_DIR/evidence/<file>" "$INBOX_URL/api/v1/message/<ID>/part/<PartID>"  # an attachment
curl -s "$INBOX_URL/api/v1/search?query=to:someone@example.com" | jq '.messages[].Subject'
```

- Use it to complete what mail starts: invitations, address confirmations, password resets. Open the link the message
  carries in the browser, as its recipient would.
- What the instance sends is product, and under test: a message's wording, its links, its attachments and their figures
  against the pages they come from.
- Mailpit itself is the test harness. Its pages and behaviour are never a finding.
- The TARGET section says which addresses Mailpit refuses, so that a send to them fails as a bounce would.
