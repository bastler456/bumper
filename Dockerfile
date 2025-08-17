FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates

ADD https://astral.sh/uv/install.sh /uv-installer.sh

RUN sh /uv-installer.sh && rm /uv-installer.sh

ENV PATH="/root/.local/bin/:$PATH"


WORKDIR /bumper


COPY create_certs/ create_certs/
COPY bumper/ bumper/
COPY pyproject.toml .

RUN uv sync

ENTRYPOINT ["uv", "run", "-m", "bumper"]
