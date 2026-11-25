# hirsel.ai

The website of the [Hirsel](https://github.com/SamGalanakis/hirsel) programming language, and
the Hirsel program that serves it. It runs on [Fly.io](https://fly.io).

## Layout

| Path | What it is |
| --- | --- |
| `site/` | Hand-written pages and assets: the landing page, gallery, benchmarks board, install script, fonts, `_headers` |
| `tools/` | Python generators that turn a Hirsel checkout's docs into `/docs/`, `/docs/std/`, `/docs/spec/`, `primer.md`, `cookbook.md`, `api-index.md`, `llms.txt`, `llms-full.txt` and `sitemap.xml` |
| `src/main.hirsel` | The server's entry: settings, listener, graceful stop |
| `src/site.hirsel` | Loading the built site, clean-URL resolution, `_headers` rules, the route table |
| `tests/site_laws.hirsel` | The server's laws (`hirsel test`) |
| `hirsel.toml` | The package, with the server's grants in `[program]` |
| `Dockerfile`, `fly.toml`, `.github/workflows/deploy.yml` | The image and its deployment |

## Building the site

The docs come from a checkout of `SamGalanakis/hirsel`, aligned to its newest `v*` tag by default:

```sh
pip install tree-sitter==0.25.2     # and a C compiler and Node.js (for esbuild)
python3 tools/build_site.py --hirsel-repo ../hirsel --out _site
HIRSEL_REPO=../hirsel python3 tools/site_check_links.py --site-dir _site --release-tag v0.2.0-pre
```

`--release-tag TAG` picks another tag, and `--release-tag main` uses the checkout's working
tree. `HIRSEL_REPO` can stand in for `--hirsel-repo`. Two source checks run in the image build
too: `tools/site_benchmarks.py --check` (the benchmarks page against `board-data.json`) and
`tools/site_highlight.py --check` (the landing page's highlighted snippets against the grammar).
Run either without `--check` to regenerate.

## The server

The server uses only Hirsel's standard library: `std.http` and `std.router` for HTTP/1.1, and
`std.dir` and `std.file` for the site. At startup it walks the granted `_site/` directory once and
keeps every regular file in memory. It never follows a link, so nothing outside `_site/` can be
served. It also reads `_site/_headers`, which it uses but never serves.

- `/healthz` answers `200 ok` with `Cache-Control: no-store`.
- A directory is served at its trailing-slash URL (`/docs/` is `docs/index.html`).
- `/docs` and `/docs/index.html` answer `307` to `/docs/`, and keep the query string.
- A file has no trailing-slash form. Anything else is a `404` with a short text body.
- A path segment that decodes to `.`, `..`, or anything containing NUL, `/` or `\` is a `400`.
- Methods other than `GET` and `HEAD` get `405`. A `HEAD` answers with `GET`'s head and no body.
- Every response carries the fields of each `_headers` rule whose pattern matches its URL path.
- `Content-Type` comes from the file extension unless a rule sets one.
- `Cache-Control` defaults to `public, max-age=0, must-revalidate`.

Its authority is declared in `hirsel.toml`:

- `Net=Listen 0.0.0.0/0`
- the `_site` directory
- `Env` for `PORT` (default `8080`), `BUCKET_NAME` and `AWS_ENDPOINT_URL_S3`
- `Clock`, `Tasks`, `Process` (for SIGTERM) and `Stderr`

When Fly attaches a Tigris bucket, `BUCKET_NAME` and `AWS_ENDPOINT_URL_S3` are set and the
server logs them at startup. The static pages never touch the bucket.

```sh
hirsel test                                  # the laws
hirsel build --release -o hirsel-site
PORT=8080 ./hirsel-site                      # serves ./_site
```

## Deploying

A push to `main` runs `.github/workflows/deploy.yml`, which calls `flyctl deploy --remote-only`
with the `FLY_API_TOKEN` secret. The image build:

1. clones `SamGalanakis/hirsel` at `HIRSEL_REF` (default `v0.2.0-pre`);
2. checks the source pages, builds `_site`, and checks its links;
3. downloads the Hirsel release `HIRSEL_VERSION` and verifies its `SHA256SUMS`;
4. runs the laws and builds the server;
5. ships only the executable and `_site/` on `debian:bookworm-slim`.

To build the image with a local toolchain instead of the release download:

```sh
docker build --build-context hirsel-toolchain=$HOME/.hirsel/current -t hirsel-site .
docker run --rm -p 8080:8080 hirsel-site
```

First deploy:

```sh
fly apps create hirsel-site
fly deploy
fly certs add hirsel.ai
fly certs add www.hirsel.ai
```

Then point the DNS records at the app.
