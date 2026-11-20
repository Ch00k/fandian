FROM node:26-trixie

# A black-box tester's toolbox: HTTP, data wrangling, TOTP, and reading the documents a product
# hands out (PDFs, XML). Deliberately nothing that reaches past the product's own surfaces.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 jq gawk ripgrep file tree less vim-tiny \
      curl wget ca-certificates openssl dnsutils netcat-openbsd \
      unzip zip uuid-runtime oathtool \
      poppler-utils libxml2-utils \
 && rm -rf /var/lib/apt/lists/*

# gh, the agent's way to the target's issues. Pinned, and checked against the release's own
# checksums.
ARG GH_VERSION=2.105.0
RUN ARCH="$(dpkg --print-architecture)" \
 && DEB="gh_${GH_VERSION}_linux_${ARCH}.deb" \
 && BASE="https://github.com/cli/cli/releases/download/v${GH_VERSION}" \
 && curl -fsSL "${BASE}/${DEB}" -o "/tmp/${DEB}" \
 && curl -fsSL "${BASE}/gh_${GH_VERSION}_checksums.txt" | grep " ${DEB}\$" | (cd /tmp && sha256sum -c -) \
 && dpkg -i "/tmp/${DEB}" \
 && rm "/tmp/${DEB}"

# The headless browser the agent drives via MCP, pinned, and Google Chrome (the channel
# Playwright MCP uses by default), installed by the Playwright the MCP server itself depends on.
ARG PLAYWRIGHT_MCP_VERSION=0.0.86
RUN npm install -g "@playwright/mcp@${PLAYWRIGHT_MCP_VERSION}" \
 && apt-get update \
 && "$(npm root -g)/@playwright/mcp/node_modules/.bin/playwright" install --with-deps chrome \
 && rm -rf /var/lib/apt/lists/*

# Run as the base image's 'node' user (uid 1000), which matches the operator's uid, so the mounted
# run directory is writable. A non-root user also keeps the agent, which runs without permission
# prompts, boxed inside the container.
ENV HOME=/home/node
RUN mkdir -p /home/node/.claude && chown -R node:node /home/node/.claude
# Pre-seeded so the first-run onboarding, which cannot be answered non-interactively, is skipped.
COPY --chown=node:node claude-config.json /home/node/.claude.json
WORKDIR /work
RUN mkdir -p /work/findings && chown -R node:node /work
USER node

# Claude Code via the native installer, as the node user. `fand run` resolves the current
# release and passes it in: the install command is otherwise identical from one release to the
# next, so the cache would keep the first version forever.
ENV PATH=/home/node/.local/bin:$PATH
# The account's claude.ai connectors (Google Drive, Slack, ...) would otherwise load into the
# agent, handing a tester running without permission prompts access to them.
ENV ENABLE_CLAUDEAI_MCP_SERVERS=false
ARG CLAUDE_VERSION=latest
RUN curl -fsSL https://claude.ai/install.sh | bash -s "${CLAUDE_VERSION}"

# The files edited most often come last, so editing them rebuilds only these layers.
COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh
COPY progress.jq /opt/progress.jq
COPY src/fandian/mailbox.py /opt/mailbox.py
CMD ["entrypoint.sh"]
