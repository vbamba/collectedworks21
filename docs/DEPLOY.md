# Deployment — collectedworks21 to EC2

Target: `ask.collectedworksofsriaurobindo.com`
EC2 layout:
- Flask app: `/home/ec2-user/collectedworks21` (proxied at `127.0.0.1:5000`)
- React build: `/usr/share/nginx/html` (served by nginx; `/api/*` proxies to Flask, everything else falls back to `index.html`)
- nginx config: `/etc/nginx/conf.d/ask.collectedworks.conf`
- Flask process: **gunicorn**, launched by systemd unit **`collectedworks.service`**
  (1 master + 3 workers × 2 threads, `ExecStart=.../backend/venv/bin/gunicorn
  --workers 3 --threads 2 --bind 127.0.0.1:5000 wsgi:app`). There is no
  `gunicorn.service` on this host — always use `systemctl <cmd> collectedworks`.
- Python venv: `/home/ec2-user/collectedworks21/backend/venv` (server-only; not
  in the local repo, so it must be excluded from `rsync --delete`, see § 1).

> **Why rsync, not `git pull`:** historical commits in this repo contain
> >100 MB binary artifacts (`backend/indexes/faiss_index*.bin`,
> `backend/indexes/metadata.json`, `backend/scripts/extracted_texts.json`)
> that GitHub rejects on push. Until history is rewritten with
> `git filter-repo` (see § 6), the remote is frozen at the last clean
> state and deploys must bypass `git pull`.

## Connection

Every command below assumes these env vars are set in your shell.
Defined once so the IP and key path aren't hard-coded in every example.

```bash
export EC2=ec2-user@44.245.34.75
export PEM=/Users/vbamba/Projects/aws-ssh-keys/ewcc.pem

# Convenience — keeps subsequent ssh/rsync calls readable
alias ssh-ec2='ssh -i "$PEM" "$EC2"'
RSYNC_SSH=(-e "ssh -i $PEM")   # expand with "${RSYNC_SSH[@]}" inside rsync
```

Sanity-check the connection before starting a deploy:
```bash
ssh -i "$PEM" "$EC2" 'hostname && uptime'
```

## 0. Pre-flight (local)

1. Confirm `HEAD` is the release you want to ship:
   ```bash
   git log --oneline -1
   git tag --points-at HEAD
   ```
2. Bump the React build version so clients bust their cache. Edit [frontend/.env.production](../frontend/.env.production):
   ```
   REACT_APP_BUILD_VERSION=YYYYMMDD
   ```
   Same-day re-deploys can append a suffix (`20260419a`, `20260419b`). The version flows into `?v=…` on every asset URL.
3. Build the frontend bundle:
   ```bash
   cd frontend
   npm ci              # only if package-lock.json changed
   npm run build       # output: frontend/build/
   ```

## 0.5. Snapshot current EC2 state (backup before deploy)

**Run this before every deploy.** Without a snapshot, the § 5 rollback
has nothing to restore from — a bad deploy becomes unrecoverable except
by re-rsyncing from whatever local copy you still have.

Two tarballs into `/home/ec2-user/backups/`:
1. The Flask prod folder (code + `backend/db/chapters.db` +
   `backend/data/out_chapters/` + indexes).
2. The nginx html root (~7 MB, the built React bundle). Small enough
   that there's no reason not to snapshot it — avoids needing to
   rebuild from local during a rollback.

```bash
TAG=release-2026-04-20   # or same-day suffix: release-2026-04-19-1530

ssh -i "$PEM" "$EC2" "
  set -e
  mkdir -p /home/ec2-user/backups

  APP_OUT=/home/ec2-user/backups/collectedworks21-pre-$TAG.tar.gz
  echo '[backup] flask app → '\$APP_OUT
  # CHANGED (2026-04-20): exclude the legacy in-tree backups/ (root-owned,
  # see § 1 note) so snapshots don't recursively swallow earlier tarballs
  # and grow unbounded over successive deploys.
  tar --exclude='collectedworks21/backups' \
      -czf \$APP_OUT -C /home/ec2-user collectedworks21

  WEB_OUT=/home/ec2-user/backups/nginx-html-pre-$TAG.tar.gz
  echo '[backup] nginx html → '\$WEB_OUT
  sudo tar -czf \$WEB_OUT -C /usr/share/nginx html
  sudo chown ec2-user:ec2-user \$WEB_OUT

  # CHANGED (2026-07-17): auto-prune — keep only the newest 2 tarballs of each
  # kind (the snapshot just taken + the previous release). The app tarballs are
  # ~1.6 GB each, so letting them accumulate eats the 60 GB root disk fast.
  # Runs as part of every snapshot so it can't be forgotten. Roll-back depth is
  # therefore ONE release; anything older must be re-deployed from local.
  echo '[backup] pruning to newest 2 of each kind:'
  ls -1t /home/ec2-user/backups/collectedworks21-pre-*.tar.gz | tail -n +3 | xargs -r rm -v
  ls -1t /home/ec2-user/backups/nginx-html-pre-*.tar.gz     | tail -n +3 | xargs -r rm -v

  echo '[backup] done.'
  ls -lh \$APP_OUT \$WEB_OUT
  echo '[backup] all snapshots:'
  ls -lh /home/ec2-user/backups/
"
```

## 1. Backend — rsync code + restart Flask

Rsync the working tree to EC2, excluding local-only paths and the data
directories that ship out-of-band (§ 3). The `--exclude` list mirrors what
wouldn't be tracked in git anyway, so the EC2 checkout stays clean.

```bash
# from local — at repo root
rsync -av --delete -e "ssh -i $PEM" \
      --exclude '.git/' --exclude '.claude/' --exclude '.restore/' \
      --exclude 'node_modules/' --exclude 'frontend/build/' \
      --exclude 'backend/db/' --exclude 'backend/data/' \
      --exclude 'backend/indexes/' --exclude 'backend/pdf/' \
      --exclude 'backend/venv/' --exclude 'backend/.env' \
      --exclude '__pycache__/' --exclude '*.pyc' \
      --exclude 'backend/backup/' --exclude 'frontend/src/backup/' \
      --exclude '.DS_Store' --exclude '*.zip' \
      --exclude 'backups/' \
      /Users/vbamba/Projects/collectedworks21/ "$EC2":/home/ec2-user/collectedworks21/

# EC2 — restart gunicorn workers (systemd unit name is `collectedworks`)
ssh -i "$PEM" "$EC2" 'sudo systemctl restart collectedworks'
```

**Also ship `book_mapping.json` (lives inside the excluded `backend/indexes/`).**
The rsync above excludes all of `backend/indexes/` to avoid pushing the
122 MB `faiss_index.bin` + 88 MB `metadata.json`. But `book_mapping.json`
(~50 KB) lives in that same dir and IS a code-side config: `routes.py` reads
it at startup to build `_PDF_FOLDER_BY_FILE` (PDF subfolder paths) and
`get_filters` reads it for the collection/book dropdowns. If you added or
re-grouped any book, ship it explicitly or the new books get wrong PDF URLs
and don't appear in the filters:
```bash
rsync -av -e "ssh -i $PEM" \
      backend/indexes/book_mapping.json \
      "$EC2":/home/ec2-user/collectedworks21/backend/indexes/book_mapping.json
ssh -i "$PEM" "$EC2" 'sudo systemctl restart collectedworks'   # reload the map
```

The `--delete` is safe: excluded paths (`backend/db/`, `backend/indexes/`,
etc.) are not walked at all, so rsync will not remove files inside them.

Note on `backups/` exclude: EC2 has a legacy root-owned
`/home/ec2-user/collectedworks21/backups/` from an Apr 2026 route-hardening
rollback. rsync-as-ec2-user can't modify it, so `--delete` fails with
exit 23 unless excluded. The new § 0.5 snapshots live in
`/home/ec2-user/backups/` (outside the repo dir), so this legacy
directory is no longer written to and can eventually be removed.

Note on the absolute source path (`/Users/vbamba/Projects/collectedworks21/`
rather than `./`): use an absolute path. Combined with `--delete`, a
plain `./` will silently delete the entire serving tree on EC2 if you
happen to run the command from any subdirectory of the repo (the cwd
becomes the rsync source). The absolute path makes the cwd irrelevant.

Note on `backend/.env` exclude: the prod `.env` carries server-only
settings (FLASK_ENV=production, ADMIN_TOKEN, etc.) that must NOT be
clobbered by the dev `.env`. If you ever need to push env changes,
edit `/home/ec2-user/collectedworks21/backend/.env` on EC2 directly,
then `sudo systemctl restart collectedworks`.

Note on `backend/venv/` exclude: the Python virtualenv lives only on EC2
(`/home/ec2-user/collectedworks21/backend/venv`) and is not in the local
tree. Without this exclude, `--delete` wipes it and gunicorn fails to
start with `status=203/EXEC` (no such file or directory). If this happens,
restore just the venv from the § 0.5 app tarball:
```bash
ssh -i "$PEM" "$EC2" '
  cd /tmp && tar -xzf /home/ec2-user/backups/collectedworks21-pre-<TAG>.tar.gz \
                collectedworks21/backend/venv
  mv /home/ec2-user/collectedworks21/backend/venv \
     /home/ec2-user/collectedworks21/backend/venv.broken-$(date +%s) 2>/dev/null || true
  mv /tmp/collectedworks21/backend/venv /home/ec2-user/collectedworks21/backend/venv
  rmdir /tmp/collectedworks21/backend /tmp/collectedworks21
  sudo systemctl reset-failed collectedworks && sudo systemctl restart collectedworks
'
```

Verify Flask is healthy before touching nginx:
```bash
ssh -i "$PEM" "$EC2" 'curl -s 127.0.0.1:5000/api/chapter_meta?... | head'
```

**Local tag marker for audit (optional):** since remote pushes are frozen,
tag the HEAD locally after each successful deploy so you can correlate an
EC2 state with a specific local commit:
```bash
git tag -a deployed-$(date +%Y-%m-%d) -m "deployed to ask.cw via rsync"
```

## 2. Frontend — rsync build to nginx root

```bash
# from local
rsync -av --delete -e "ssh -i $PEM" frontend/build/ "$EC2":/tmp/cw-build/
ssh -i "$PEM" "$EC2" '
  sudo rsync -av --delete /tmp/cw-build/ /usr/share/nginx/html/ &&
  sudo nginx -t &&
  sudo systemctl reload nginx
'
```

Staging through `/tmp/cw-build/` keeps the user-owned rsync separate from the
`sudo` copy into the nginx root — avoids chown pitfalls.

## 2.5. nginx — route `/` to Flask for bots (SEO)

**One-time nginx change** to pair with the bot-rendered homepage added in
`backend/app/routes.py` (`home_page` at `/`). Without this, Googlebot still
hits the React shell at `/`, sees zero crawlable links, and falls back to
sitemap-only discovery — which is exactly the "Discovered – currently not
indexed" pattern we saw in Search Console.

The `$is_bot` map already exists on EC2 from the May 23 chapter SSR work.
Extend the same logic to the root location in
`/etc/nginx/conf.d/ask.collectedworks.conf`:

```nginx
# inside server { } — alongside the existing /read/ split
location = / {
    if ($is_bot) {
        proxy_pass http://127.0.0.1:5000;
        break;
    }
    try_files /index.html =404;   # humans → React SPA
}
```

Verify before reload:
```bash
ssh -i "$PEM" "$EC2" 'sudo nginx -t'
```

Smoke test from local (simulate Googlebot vs a browser):
```bash
# Should return Flask HTML with <h2>Agenda</h2>, <h2>CWSA</h2>, etc.
curl -s -A "Googlebot" https://ask.collectedworksofsriaurobindo.com/ \
  | grep -oE '<h2>[^<]+</h2>' | head

# Should return the React shell (look for "main.<hash>.css")
curl -s -A "Mozilla/5.0" https://ask.collectedworksofsriaurobindo.com/ \
  | grep -oE 'main\.[a-f0-9]+\.css' | head -1
```

## 2.5b. nginx — add `Google-InspectionTool` to `$is_bot` map

The `$is_bot` regex map lives in `/etc/nginx/conf.d/00-bot-ua.conf` (not the
site server-block file). It originally keyed on `googlebot|bingbot|...` so
the real crawlers got SSR but Search Console's **Test Live URL** feature
(which uses UA `Google-InspectionTool/1.0`) fell through to the SPA. That
made it impossible to verify SSR from the URL Inspection UI — every live
test showed the React shell, even though the regular Googlebot fetch was
getting Flask HTML correctly.

Add `google-inspectiontool` to the first alternation group:

```nginx
map $http_user_agent $is_bot {
    default 0;
    ~*(googlebot|google-inspectiontool|bingbot|slurp|duckduckbot|...)   1;
    ~*(facebookbot|facebookexternalhit|twitterbot|...)                  1;
}
```

Note: must be its own alternation token (the `-` breaks word boundaries, so
the existing `googlebot` pattern does **not** match `google-inspectiontool`).

Verify:
```bash
curl -s -A "Mozilla/5.0 (Linux) Google-InspectionTool/1.0" \
  https://ask.collectedworksofsriaurobindo.com/ \
  | grep -oE '<h2>[^<]+</h2>' | head
```

Should print the four book group headings, same as the Googlebot smoke test
in §2.5.

## 3. Data assets — `chapters.db` and `out_chapters/`

Both are `.gitignore`d and ship out-of-band. Any schema change to
`chapters.db` (e.g. the b.5 `parent_toc_title` column) means the EC2 copy
must be refreshed alongside the code; otherwise API SELECTs 500.

**Post-rebuild checklist** — after any chapters.db rebuild OR re-split into
`out_chapters/`, run these helpers in order before shipping. The pipeline
keeps reintroducing the same artifacts, so this is the standing fixup pass:

```bash
# a) drop oversized Page_X sections (FTS5 bloat from the splitter)
sqlite3 backend/db/chapters.db < backend/scripts/helpers/strip_oversized_sections.sql

# b) recover verse line breaks inside Letters-on-Savitri italic quotes
python3 backend/scripts/helpers/recover_letters_verse_breaks.py --db

# c) strip PDF ligatures (ﬁ → fi etc.) so FTS5 queries with plain f+i match.
#    `--txt` also rewrites out_chapters/*.txt so the rendered chapter page is clean.
python3 backend/scripts/helpers/normalize_ligatures.py --txt
```

```bash
# chapters.db — atomic swap so in-flight Flask requests don't see a half-copy
rsync -av -e "ssh -i $PEM" backend/db/chapters.db \
      "$EC2":/home/ec2-user/collectedworks21/backend/db/chapters.db.tmp
ssh -i "$PEM" "$EC2" '
  mv /home/ec2-user/collectedworks21/backend/db/chapters.db.tmp \
     /home/ec2-user/collectedworks21/backend/db/chapters.db
'

# out_chapters/ — same excludes as sync_from_splitter.sh
# `*.bak` covers the backups recover_letters_verse_breaks.py leaves behind;
# they are never indexed or served, so they must not ship to prod.
rsync -av --delete -e "ssh -i $PEM" \
      --exclude "raw_section_*.txt" --exclude "diagnostic.*" \
      --exclude "toc.json" --exclude "toc.txt" --exclude "*.bak" \
      backend/data/out_chapters/ \
      "$EC2":/home/ec2-user/collectedworks21/backend/data/out_chapters/
```

Restart gunicorn again after a DB swap — existing workers hold the old
file handle until they recycle:
```bash
ssh -i "$PEM" "$EC2" 'sudo systemctl restart collectedworks'
```

## 3.5. Source PDFs — `backend/pdf/` (only when books were added/changed)

**Skip this unless you added new books or modified existing PDFs** (e.g. the
`add_pdf_bookmarks.py` outline injection). Like `chapters.db`, `backend/pdf/`
ships out-of-band: it's excluded from the § 1 code rsync, and new files under
it are `.gitignore`d (only the ~83 pre-ignore PDFs are tracked). So nothing in
§ 1 or § 3 ships a newly added PDF — the book's chapters render fine (served
from `chapters.db`/`out_chapters`), but its **"PDF" link 404s** because the
source file never reached EC2.

Ship with `rsync` but **without `--delete`** — additive only, so it can never
remove a prod PDF (some tracked-but-old books may exist only on EC2):
```bash
rsync -av -e "ssh -i $PEM" \
      --exclude 'metadata.json' --exclude '.DS_Store' \
      backend/pdf/ \
      "$EC2":/home/ec2-user/collectedworks21/backend/pdf/
```
- **`--exclude 'metadata.json'`**: an 88 MB FAISS artifact has historically
  been misfiled under `backend/pdf/disciples/`; this keeps it from riding along.
- rsync is incremental, so unchanged PDFs are skipped by size/mtime — only the
  new + modified files transfer (a full new-book batch is ~20 MB).
- No gunicorn restart needed — PDFs are served straight off disk by
  `send_from_directory`, not cached in the Flask process.

Verify a new book's PDF is reachable:
```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  https://ask.collectedworksofsriaurobindo.com/api/pdfs/compilations/India-the-Mother.pdf
```

## 4. Post-deploy smoke tests

```bash
# a) API up, b.5 breadcrumb field flowing
curl -s 'https://ask.collectedworksofsriaurobindo.com/api/text_search?query=aspiration+surrender+rejection&mode=all&limit=5' \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); \
      print("results:", len(d.get("results",[]))); \
      print("has parent_toc_title:", any("parent_toc_title" in r for r in d.get("results",[])))'

# b) Chapter endpoint returns first/last + breadcrumb
curl -s 'https://ask.collectedworksofsriaurobindo.com/api/chapter?collection_folder=sriaurobindo&book_folder=28LettersOnYoga-I&section_filename=section_21_Chapter_Three_-_The_Psychic_Being.txt' \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); \
      print({k:d.get(k) for k in ["first_section","last_section","prev_section","next_section","parent_toc_title"]})'

# c) Browser — visit a journal page:
#    /read/sriaurobindo/the-mother-agenda-vol-4/january-9-1963
#    Expect: centered italic "from January 9, 1963" under the nav row,
#    and prose reflowed naturally (no ragged ~90-char line breaks).

# d) nginx access log sanity — confirm 2xx on /api/text_search after deploy
ssh -i "$PEM" "$EC2" 'sudo tail -50 /var/log/nginx/access.log | grep text_search'

# e) If books were added (validates § 1 book_mapping.json + § 3.5 PDF steps):
#    new group present in filters, new book indexed, its PDF reachable.
BASE=https://ask.collectedworksofsriaurobindo.com
curl -s "$BASE/api/filters" | python3 -c 'import sys,json; print("groups:", json.load(sys.stdin)["groups"])'
curl -s "$BASE/api/books" | python3 -c 'import sys,json; b=json.load(sys.stdin); print("books:", len(b))'
curl -s -o /dev/null -w 'new PDF: %{http_code}\n' \
  "$BASE/api/pdfs/compilations/India-the-Mother.pdf"   # swap for your new book
```

## 5. Rollback

Since deploys are rsync-based (§ 1) rather than git-based, `git checkout` on
EC2 does not roll back the code. Roll back by extracting the tarball
captured in § 0.5 over the live prod folder.

If you skipped § 0.5, there's no snapshot to restore from — your only
option is to re-deploy a known-good release from local.

```bash
TAG=release-2026-04-20   # same suffix used in § 0.5 snapshot

ssh -i "$PEM" "$EC2" "
  set -e
  STAMP=\$(date +%Y%m%d-%H%M%S)
  APP_ARCHIVE=/home/ec2-user/backups/collectedworks21-pre-$TAG.tar.gz
  WEB_ARCHIVE=/home/ec2-user/backups/nginx-html-pre-$TAG.tar.gz
  test -f \$APP_ARCHIVE || { echo 'no app snapshot at '\$APP_ARCHIVE; exit 1; }
  test -f \$WEB_ARCHIVE || { echo 'no web snapshot at '\$WEB_ARCHIVE; exit 1; }

  # Flask app — move the bad dir aside (don't delete; lets us inspect
  # what went wrong after the fact), then extract snapshot.
  sudo mv /home/ec2-user/collectedworks21 \
          /home/ec2-user/collectedworks21.failed-\$STAMP
  sudo tar -xzf \$APP_ARCHIVE -C /home/ec2-user
  sudo chown -R ec2-user:ec2-user /home/ec2-user/collectedworks21

  # nginx html — same pattern
  sudo mv /usr/share/nginx/html /usr/share/nginx/html.failed-\$STAMP
  sudo tar -xzf \$WEB_ARCHIVE -C /usr/share/nginx

  sudo systemctl restart collectedworks
  sudo nginx -t && sudo systemctl reload nginx
"
```

If you only need to roll back one side (code but not frontend, or vice
versa), comment out the block you want to keep — both guards and both
`mv`/`tar` pairs are independent.

The old `chapters.db` schema matters: reverting past commit `048dfc2`
(Phase b.5) must be paired with the pre-b.5 DB snapshot, because post-b.5
code expects the `parent_toc_title` column and pre-b.5 code does not emit
it — mixing the two will 500 on `/api/text_search`.

## 6. Cleanup — unblock `git push` (defer; schedule when quiet)

The GitHub remote will keep rejecting pushes until history is rewritten to
drop the oversized blobs. One-time cleanup:

```bash
# safety tag in case something goes sideways
git tag rescue-before-filter-repo

# one-time install
brew install git-filter-repo

# strip the offending paths from every commit on every branch
git filter-repo \
  --path 'backend/indexes/faiss_index.bin' \
  --path 'backend/indexes/faiss_index copy.bin' \
  --path 'backend/indexes/metadata.json' \
  --path 'backend/scripts/extracted_texts.json' \
  --invert-paths

# filter-repo removes the remote as a safety measure; re-add it
git remote add origin https://github.com/vbamba/collectedworks21.git

# force-push rewritten history + tags
git push --force origin main
git push --tags --force
```

**Caveats:**
- All commit SHAs change. Existing tags (`baseline-2026-04-18`,
  `release-2026-04-19`) keep their names but point at new commit objects.
- Any other local clone of this repo must `git fetch && git reset --hard
  origin/main` after the force-push.
- Once history is clean, the rsync-based deploy in § 1 can be replaced
  with the simpler `git fetch && git checkout <tag>` flow on EC2.

## 7. Analytics — search query log

Every request to `/api/text_search` and `/api/search` (semantic) appends one
row to `backend/db/query_log.db` — a separate SQLite file that lives next
to `chapters.db` but never touches it (different file, regular table, not
FTS5). The file is created on first request, lives under `backend/db/`
which is `.gitignore`d, and survives across deploys (it isn't rsynced).

**Schema** (one row per search):

| col | what |
| --- | --- |
| `ts` | unix timestamp (UTC) |
| `endpoint` | `text_search` or `semantic_search` |
| `query` | the user's raw query string |
| `result_count` | how many rows the response actually returned |
| `mode` | text: `exact` / `all_words` / `all`; semantic: `all` / `exact` / `semantic` |
| `filters` | JSON of any `author` / `group` / `book_title` filters applied |

**Viewing the log — CLI** (preferred):

```bash
# default: last 7 days, top 20 queries + zero-result list
python3 backend/scripts/helpers/query_stats.py

# narrow window
python3 backend/scripts/helpers/query_stats.py --days 1 --top 50

# against prod log over SSH
ssh -i "$PEM" "$EC2" \
  'cd /home/ec2-user/collectedworks21 && python3 backend/scripts/helpers/query_stats.py --days 30'

# or copy down and inspect locally
scp -i "$PEM" "$EC2:/home/ec2-user/collectedworks21/backend/db/query_log.db" /tmp/prod_query_log.db
python3 backend/scripts/helpers/query_stats.py --db /tmp/prod_query_log.db --days 30
```

**Viewing the log — browser** (quickest for a glance):

```
https://ask.collectedworksofsriaurobindo.com/api/admin/query_stats?token=<ADMIN_TOKEN>&days=7
```

Backed by `/api/admin/query_stats` in [backend/app/routes.py](../backend/app/routes.py).
Gated by the `ADMIN_TOKEN` env var in EC2's `backend/.env` — endpoint
returns 503 if unset, 403 on mismatch. Accepts `?token=…` (logged in
nginx access log) or an `X-Admin-Token` header (preferred for secrets).
Params: `days=N` (1–365), `top=N` (1–100), `format=json` for raw.
Rotate by editing the `.env` line and `sudo systemctl restart collectedworks`.

**Viewing the log — raw SQL** (when you need a custom slice):

```bash
sqlite3 backend/db/query_log.db \
  "SELECT datetime(ts,'unixepoch','localtime'), endpoint, query, result_count
     FROM query_log ORDER BY id DESC LIMIT 20;"
```

**Reset** (e.g. before testing): `rm backend/db/query_log.db` — table
auto-recreates on the next search request.

**Failure mode:** logging is best-effort; any write failure is warned to
`app_logger` and the search response still returns 200. If you see
`query_log write failed:` in app logs, check the file's permissions — it
needs to be writable by the gunicorn user.

## 8. Savitri Study — separate static site on the same EC2

A second, fully static site lives at [savitri-wiki/](../savitri-wiki/) (36
hand-authored HTML files, no build step). It is deployed on the **same
EC2 instance** as ask.collectedworks but served from its own nginx server
block at a different hostname so the two sites stay independent.

**Hostnames (decided 2026-05-25):**

| Hostname | DNS | Behavior |
| --- | --- | --- |
| `savitri.thesunlitpath.in` | A → 44.245.34.75 | Canonical. Serves `savitri-wiki/` statically. |
| `savitri.collectedworksofsriaurobindo.com` | A → 44.245.34.75 | 301 → `https://savitri.thesunlitpath.in$request_uri` |
| `ask.collectedworksofsriaurobindo.com` | unchanged | Existing app. **No** "Savitri Study" link in nav (env var unset in `.env.production`). |

Why redirect instead of dual-serving: one canonical URL avoids duplicate-
content SEO penalties, and there's only one tree of HTML to keep in sync.
TLS for the redirect host still needs its own cert (so users hitting
`https://savitri.collectedworks...` get a clean 301 instead of a cert
error), which is why it gets an A record rather than a bare CNAME.

### 8.1. DNS (do this first, at the registrar)

Both records point to the EC2 elastic IP:

```
savitri.thesunlitpath.in.                  A   44.245.34.75
savitri.collectedworksofsriaurobindo.com.  A   44.245.34.75
```

Wait until both resolve before requesting certs:

```bash
dig +short savitri.thesunlitpath.in
dig +short savitri.collectedworksofsriaurobindo.com
# both should return 44.245.34.75
```

### 8.2. Push the static content

```bash
# from repo root, local machine
rsync -avz --delete "${RSYNC_SSH[@]}" \
  /Users/vbamba/Projects/collectedworks21/savitri-wiki/ \
  "$EC2:/home/ec2-user/savitri-wiki/"

# move into nginx-owned location
ssh -i "$PEM" "$EC2" '
  sudo mkdir -p /usr/share/nginx/savitri-wiki
  sudo rsync -a --delete /home/ec2-user/savitri-wiki/ /usr/share/nginx/savitri-wiki/
  sudo chown -R nginx:nginx /usr/share/nginx/savitri-wiki
  sudo find /usr/share/nginx/savitri-wiki -type d -exec chmod 755 {} \;
  sudo find /usr/share/nginx/savitri-wiki -type f -exec chmod 644 {} \;
'
```

> Absolute source path — see [[feedback_rsync_absolute_path]]; never use
> `./` from a subdirectory with `--delete`.

### 8.3. nginx server blocks

Create `/etc/nginx/conf.d/savitri.conf` on EC2:

```nginx
# Canonical: savitri.thesunlitpath.in — static site
server {
    listen 80;
    listen [::]:80;
    server_name savitri.thesunlitpath.in;
    # certbot will rewrite this block to add 443 + redirect 80→443.
    root /usr/share/nginx/savitri-wiki;
    index index.html;

    location / {
        try_files $uri $uri/ $uri.html =404;
    }

    # long cache for assets; HTML stays uncached so edits propagate fast
    location ~* \.(css|js|png|jpg|jpeg|svg|woff2?)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}

# Legacy hostname: 301 to canonical
server {
    listen 80;
    listen [::]:80;
    server_name savitri.collectedworksofsriaurobindo.com;
    return 301 https://savitri.thesunlitpath.in$request_uri;
}
```

Validate and reload:

```bash
ssh -i "$PEM" "$EC2" 'sudo nginx -t && sudo systemctl reload nginx'
```

### 8.4. TLS certs (Let's Encrypt)

certbot requires every `-d` name to resolve to this EC2 instance at
issue-time (HTTP-01 challenge). If both A records are live, one run
covers them both:

```bash
ssh -i "$PEM" "$EC2" '
  sudo certbot --nginx \
    -d savitri.thesunlitpath.in \
    -d savitri.collectedworksofsriaurobindo.com \
    --redirect --non-interactive --agree-tos -m vishalbamba@gmail.com
'
```

**Staged variant (used 2026-05-25):** thesunlitpath DNS was live but the
collectedworks DNS hadn't propagated yet. We issued the canonical name
alone:

```bash
ssh -i "$PEM" "$EC2" '
  sudo certbot --nginx -d savitri.thesunlitpath.in \
    --redirect --non-interactive --agree-tos -m vishalbamba@gmail.com
'
```

Then once `dig +short savitri.collectedworksofsriaurobindo.com` returns
`44.245.34.75`, expand the existing cert to cover the redirect host:

```bash
ssh -i "$PEM" "$EC2" '
  sudo certbot --nginx --expand \
    -d savitri.thesunlitpath.in \
    -d savitri.collectedworksofsriaurobindo.com \
    --redirect --non-interactive --agree-tos -m vishalbamba@gmail.com
'
```

`--expand` keeps the same cert lineage (so the existing renewal hook
keeps working) and just adds the new SAN. certbot edits `savitri.conf`
in place to add the `listen 443 ssl` blocks and the 80→443 redirect.
Re-run `nginx -t && systemctl reload nginx` if certbot didn't reload
automatically.

Auto-renew is already wired via the system `certbot.timer` (shared with
the ask. cert). Verify:

```bash
ssh -i "$PEM" "$EC2" 'sudo systemctl list-timers | grep certbot'
```

### 8.5. Smoke tests

```bash
# canonical: 200 + HTML
curl -sI https://savitri.thesunlitpath.in/ | head -1
curl -s  https://savitri.thesunlitpath.in/ | grep -i '<title>'

# redirect: 301 to canonical
curl -sI https://savitri.collectedworksofsriaurobindo.com/the-symbol-dawn.html \
  | grep -iE '^(HTTP|location)'
# expect: HTTP/2 301  +  location: https://savitri.thesunlitpath.in/the-symbol-dawn.html

# ask. host: confirm "Savitri Study" link is GONE
curl -s https://ask.collectedworksofsriaurobindo.com/ | grep -i 'savitri study' || echo 'OK: no link'
```

### 8.6. Hiding the NavBar link on ask.

Already done in [frontend/.env.production](../frontend/.env.production):
`REACT_APP_SAVITRI_WIKI_URL` is commented out. The guard at
[NavBar.jsx:94](../frontend/src/components/NavBar.jsx#L94)
(`{process.env.REACT_APP_SAVITRI_WIKI_URL && (...)}`) drops the `<li>`
when the var is unset. Rebuild the frontend (§ 0) and redeploy (§ 2) for
the change to land.

To re-expose the link later, uncomment that line — point it at
`https://savitri.thesunlitpath.in/` (the canonical URL), not the
collectedworks subdomain, to avoid making users follow the 301.

### 8.7. Updating wiki content

Edit HTML in [savitri-wiki/](../savitri-wiki/) locally, then run:

```bash
./scripts/deploy_savitri.sh
```

The script ([scripts/deploy_savitri.sh](../scripts/deploy_savitri.sh)) handles
the whole flow: build → rsync to EC2 → sync into `/usr/share/nginx/savitri-wiki/`
→ fix perms → curl-check the canonical URL. Nothing else to restart — nginx
serves files directly off disk, and HTML responses aren't cached so edits show
up on the next request.

#### Source-citation shorthand (the build step)

Each wiki page has a `<h2>Sources</h2>` section listing the books and
chapters the page draws on. Authors write these in a shorthand that points
at splitter filenames:

```html
<li><code>raw/33-34Savitri/section_05_Canto_One__The_Symbol_Dawn.txt</code></li>
<li><code>raw/Letters-on-Savitri/section_05_Part_II.txt</code> — the rapid-transitions technique</li>
```

The shorthand is convenient for drafting (book folder + section filename
both match what the splitter writes) but isn't useful to a reader. On
deploy, [scripts/convert_savitri_sources.py](../scripts/convert_savitri_sources.py)
expands each `<li><code>raw/<book>/<section>.txt</code>(…)</li>` into a
clickable link to the rendered chapter on ask.collectedworksofsriaurobindo.com:

```html
<li><a href="https://ask.collectedworksofsriaurobindo.com/read/sriaurobindo/savitri/canto-one-the-symbol-dawn" target="_blank" rel="noopener">Savitri — Canto One: The Symbol Dawn</a></li>
<li><a href="https://ask.collectedworksofsriaurobindo.com/read/sriaurobindo/letters-on-savitri/part-ii" target="_blank" rel="noopener">Letters on Savitri — Part II</a> — the rapid-transitions technique</li>
```

The converter is a pure source→build transform — it reads `savitri-wiki/`,
writes `savitri-wiki-build/` (gitignored), and never modifies the source
tree. `deploy_savitri.sh` runs it as step [1/4] before rsync. To preview
locally with the links resolved, run the converter manually and serve the
build dir:

```bash
python3 scripts/convert_savitri_sources.py
python3 -m http.server 8000 -d savitri-wiki-build
```

Section title + slug come from `backend/data/out_chapters/sriaurobindo/<book>/metadata.json`
(authoritative — same source the production chapter URLs are generated from).
If you add a new source book to the wiki, extend the `BOOKS` dict at the top
of `convert_savitri_sources.py`. Unrecognized refs are left as `<code>raw/...</code>`
and logged as warnings, so a missing entry shows up immediately at deploy.

## Reference — file map

| Concern | File |
| --- | --- |
| Flask app factory | [backend/app/__init__.py](../backend/app/__init__.py) |
| API routes | [backend/app/routes.py](../backend/app/routes.py) |
| FTS / text search | [backend/scripts/text_search.py](../backend/scripts/text_search.py) |
| Splitter → serving sync | [backend/scripts/sync_from_splitter.sh](../backend/scripts/sync_from_splitter.sh) |
| Search query logger | [backend/app/routes.py `_log_query()`](../backend/app/routes.py) |
| Search query stats CLI | [backend/scripts/helpers/query_stats.py](../backend/scripts/helpers/query_stats.py) |
| Books picker (SPA) | [frontend/src/components/BooksMenu.jsx](../frontend/src/components/BooksMenu.jsx) |
| Global nav | [frontend/src/components/NavBar.jsx](../frontend/src/components/NavBar.jsx) |
| SPA chapter page | [frontend/src/pages/ChapterPage.jsx](../frontend/src/pages/ChapterPage.jsx) |
| Search result card | [frontend/src/components/TextResultCard.jsx](../frontend/src/components/TextResultCard.jsx) |
| Prod build vars | [frontend/.env.production](../frontend/.env.production) |
| nginx config (on EC2) | `/etc/nginx/conf.d/ask.collectedworks.conf` |
| Savitri Study static site | [savitri-wiki/](../savitri-wiki/) |
| Savitri Study nginx (on EC2) | `/etc/nginx/conf.d/savitri.conf` |
