# Deployment — collectedworks21 to EC2

Target: `ask.collectedworksofsriaurobindo.com`
EC2 layout:
- Flask app: `/home/ec2-user/collectedworks21` (proxied at `127.0.0.1:5000`)
- React build: `/usr/share/nginx/html` (served by nginx; `/api/*` proxies to Flask, everything else falls back to `index.html`)
- nginx config: `/etc/nginx/conf.d/ask.collectedworks.conf`

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
TAG=release-2026-04-19   # or same-day suffix: release-2026-04-19-1530

ssh -i "$PEM" "$EC2" "
  set -e
  mkdir -p /home/ec2-user/backups

  APP_OUT=/home/ec2-user/backups/collectedworks21-pre-$TAG.tar.gz
  echo '[backup] flask app → '\$APP_OUT
  tar -czf \$APP_OUT -C /home/ec2-user collectedworks21

  WEB_OUT=/home/ec2-user/backups/nginx-html-pre-$TAG.tar.gz
  echo '[backup] nginx html → '\$WEB_OUT
  sudo tar -czf \$WEB_OUT -C /usr/share/nginx html
  sudo chown ec2-user:ec2-user \$WEB_OUT

  echo '[backup] done.'
  ls -lh \$APP_OUT \$WEB_OUT
  echo '[backup] all snapshots:'
  ls -lh /home/ec2-user/backups/
"
```

Housekeeping — prune old tarballs after a release is confirmed healthy
(keep the last 3–5 of each kind so you can roll back more than one step):
```bash
ssh -i "$PEM" "$EC2" '
  ls -1t /home/ec2-user/backups/collectedworks21-pre-*.tar.gz | tail -n +6 | xargs -r rm -v
  ls -1t /home/ec2-user/backups/nginx-html-pre-*.tar.gz     | tail -n +6 | xargs -r rm -v
'
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
      --exclude '__pycache__/' --exclude '*.pyc' \
      --exclude 'backend/backup/' --exclude 'frontend/src/backup/' \
      --exclude '.DS_Store' --exclude '*.zip' \
      ./ "$EC2":/home/ec2-user/collectedworks21/

# EC2 — restart gunicorn so the new code is loaded
ssh -i "$PEM" "$EC2" 'sudo systemctl restart gunicorn'
```

The `--delete` is safe: excluded paths (`backend/db/`, `backend/indexes/`,
etc.) are not walked at all, so rsync will not remove files inside them.

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

## 3. Data assets — `chapters.db` and `out_chapters/`

Both are `.gitignore`d and ship out-of-band. Any schema change to
`chapters.db` (e.g. the b.5 `parent_toc_title` column) means the EC2 copy
must be refreshed alongside the code; otherwise API SELECTs 500.

```bash
# chapters.db — atomic swap so in-flight Flask requests don't see a half-copy
rsync -av -e "ssh -i $PEM" backend/db/chapters.db \
      "$EC2":/home/ec2-user/collectedworks21/backend/db/chapters.db.tmp
ssh -i "$PEM" "$EC2" '
  mv /home/ec2-user/collectedworks21/backend/db/chapters.db.tmp \
     /home/ec2-user/collectedworks21/backend/db/chapters.db
'

# out_chapters/ — same excludes as sync_from_splitter.sh
rsync -av --delete -e "ssh -i $PEM" \
      --exclude "raw_section_*.txt" --exclude "diagnostic.*" \
      --exclude "toc.json" --exclude "toc.txt" \
      backend/data/out_chapters/ \
      "$EC2":/home/ec2-user/collectedworks21/backend/data/out_chapters/
```

Restart gunicorn again after a DB swap — existing workers hold the old
file handle until they recycle:
```bash
ssh -i "$PEM" "$EC2" 'sudo systemctl restart gunicorn'
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
```

## 5. Rollback

Since deploys are rsync-based (§ 1) rather than git-based, `git checkout` on
EC2 does not roll back the code. Roll back by extracting the tarball
captured in § 0.5 over the live prod folder.

If you skipped § 0.5, there's no snapshot to restore from — your only
option is to re-deploy a known-good release from local.

```bash
TAG=release-2026-04-19   # same suffix used in § 0.5 snapshot

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

  sudo systemctl restart gunicorn
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

## Reference — file map

| Concern | File |
| --- | --- |
| Flask app factory | [backend/app/__init__.py](../backend/app/__init__.py) |
| API routes | [backend/app/routes.py](../backend/app/routes.py) |
| FTS / text search | [backend/scripts/text_search.py](../backend/scripts/text_search.py) |
| Splitter → serving sync | [backend/scripts/sync_from_splitter.sh](../backend/scripts/sync_from_splitter.sh) |
| SPA chapter page | [frontend/src/pages/ChapterPage.jsx](../frontend/src/pages/ChapterPage.jsx) |
| Search result card | [frontend/src/components/TextResultCard.jsx](../frontend/src/components/TextResultCard.jsx) |
| Prod build vars | [frontend/.env.production](../frontend/.env.production) |
| nginx config (on EC2) | `/etc/nginx/conf.d/ask.collectedworks.conf` |
