# syntax=docker/dockerfile:1.7
#
# hirsel.ai: the site built from a Hirsel release's docs, served by a Hirsel executable.
#
#   docker build -t hirsel-site .
#
# downloads the Hirsel release HIRSEL_VERSION (Linux x86_64) and checks its SHA-256. To build
# with a toolchain on this machine instead, name its directory as the hirsel-toolchain context:
#
#   docker build --build-context hirsel-toolchain=$HOME/.hirsel/current -t hirsel-site .
#
# The docs come from SamGalanakis/hirsel at HIRSEL_REF, the same release by default.

ARG HIRSEL_VERSION=0.2.0-pre
ARG HIRSEL_REF=v${HIRSEL_VERSION}

# ---- The Hirsel toolchain, from its GitHub release -------------------------------------
FROM debian:bookworm-slim AS toolchain-download
ARG HIRSEL_VERSION
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /download
RUN set -eu; \
    base="https://github.com/SamGalanakis/hirsel/releases/download/v${HIRSEL_VERSION}"; \
    archive="hirsel-v${HIRSEL_VERSION}-x86_64-unknown-linux-gnu.tar.gz"; \
    curl --proto '=https' --tlsv1.2 --retry 3 -fsSLO "$base/SHA256SUMS"; \
    curl --proto '=https' --tlsv1.2 --retry 3 -fsSLO "$base/$archive"; \
    grep " $archive\$" SHA256SUMS | sha256sum -c -; \
    mkdir -p /opt/hirsel; \
    tar -xzf "$archive" -C /opt/hirsel; \
    test -x /opt/hirsel/hirsel

# Replaced wholesale by `--build-context hirsel-toolchain=DIR`.
FROM scratch AS hirsel-toolchain
COPY --from=toolchain-download /opt/hirsel/ /

# ---- The static site, from the Hirsel docs at HIRSEL_REF -------------------------------
FROM node:22-bookworm-slim AS site
ARG HIRSEL_REF
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git gcc libc6-dev python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --break-system-packages --no-cache-dir 'tree-sitter==0.25.2'
RUN git clone --quiet --depth 1 --branch "${HIRSEL_REF}" https://github.com/SamGalanakis/hirsel /src/hirsel
WORKDIR /work
COPY tools/ tools/
COPY site/ site/
ENV HIRSEL_REPO=/src/hirsel
RUN python3 tools/site_benchmarks.py --check \
    && python3 tools/site_highlight.py --check \
    && python3 tools/build_site.py --release-tag "${HIRSEL_REF}" --out /out/_site \
    && python3 tools/site_check_links.py --site-dir /out/_site --release-tag "${HIRSEL_REF}"

# ---- The server: laws, then a release build ---------------------------------------------
FROM debian:bookworm-slim AS server
RUN apt-get update && apt-get install -y --no-install-recommends libc6-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=hirsel-toolchain / /opt/hirsel/
ENV PATH=/opt/hirsel:$PATH
WORKDIR /work
COPY hirsel.toml hirsel.lock ./
COPY src/ src/
COPY tests/ tests/
RUN hirsel test && hirsel build --release -o /out/hirsel-site

# ---- Runtime: the executable and the site, nothing else --------------------------------
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=server /out/hirsel-site ./hirsel-site
COPY --from=site /out/_site ./_site
USER nobody
ENV PORT=8080
EXPOSE 8080
# The executable reads _site/ relative to its working directory (hirsel.toml [program] dirs).
CMD ["/app/hirsel-site"]
