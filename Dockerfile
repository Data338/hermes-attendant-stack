FROM hermes-base:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/hermes-agent/.venv/bin:/root/.local/bin:/usr/local/bin:${PATH}"

# Node.js for the WhatsApp bridge, sqlite3 for state inspection,
# poppler-utils (pdftotext) for the PDF auto-extract patch.
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm sqlite3 poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Patches to the Hermes gateway code (see patches.py for what/why).
COPY patches.py /tmp/patches.py
RUN python3 /tmp/patches.py && rm -f /tmp/patches.py

ENV HERMES_HOME=/opt/hermes-agent

CMD ["hermes"]
