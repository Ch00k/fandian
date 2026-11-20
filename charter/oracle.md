## MODE: oracle

The target has a user guide, and it sits at the top of your oracle stack. Its pages: `$GUIDE_URLS` (`echo $GUIDE_URLS`),
and the pages they link to on the instance.

- **Read the guide before you test** an area, in the browser as a user would. It is what the product promises.
- **A divergence from the guide is a finding** with the oracle `guide`. Cite the guide's page and section (its URL with
  the `#anchor`) and quote the sentence the product breaks.
- **The guide is under test too.** A broken, inaccurate or unreachable guide page, a link from the product to a guide
  section that does not exist, and a guide that contradicts itself are findings with the oracle `guide`.
- **Where the guide is silent**, the rest of the stack applies. The guide's silence on its own is never a finding, and
  never a testing limitation.
- Business rules the guide states (a limit, a deadline, a figure and how it is worked out) are exactly what to check:
  work out what the guide says the answer should be from the seeded data, and compare it with what the product shows.
