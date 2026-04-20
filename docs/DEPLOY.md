# Deployment — collectedworks21 to EC2

Target: `ask.collectedworksofsriaurobindo.com`
EC2 layout:
- Flask app: `/home/ec2-user/collectedworks21` (proxied at `127.0.0.1:5000`)
- React build: `/usr/share/nginx/html` (served by nginx; `/api/*` proxies to Flask, everything else falls back to `index.html`)
- nginx config: `/etc/nginx/conf.d/ask.collectedworks.conf`

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

## 1. Backend — git pull + restart Flask

```bash
# local
git push origin main
git push origin <tag-name>

# EC2
ssh ec2-user@<host>
cd /home/ec2-user/collectedworks21
git fetch --tags
git checkout <tag-name>          # or: git pull origin main

# Pick the one that matches your Flask process manager:
sudo systemctl restart collectedworks
# pm2 restart collectedworks
# pkill -HUP -f gunicorn
```

Verify Flask is healthy before touching nginx:
```bash
curl -s 127.0.0.1:5000/api/chapter_meta?... | head
```

## 2. Frontend — rsync build to nginx root

```bash
# from local
rsync -av --delete frontend/build/ ec2-user@<host>:/tmp/cw-build/
ssh ec2-user@<host> '
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
rsync -av backend/db/chapters.db \
      ec2-user@<host>:/home/ec2-user/collectedworks21/backend/db/chapters.db.tmp
ssh ec2-user@<host> '
  mv /home/ec2-user/collectedworks21/backend/db/chapters.db.tmp \
     /home/ec2-user/collectedworks21/backend/db/chapters.db
'

# out_chapters/ — same excludes as sync_from_splitter.sh
rsync -av --delete \
      --exclude "raw_section_*.txt" --exclude "diagnostic.*" \
      --exclude "toc.json" --exclude "toc.txt" \
      backend/data/out_chapters/ \
      ec2-user@<host>:/home/ec2-user/collectedworks21/backend/data/out_chapters/
```

Restart Flask again after a DB swap — existing connections hold the old file
handle until the worker recycles.

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
ssh ec2-user@<host> 'sudo tail -50 /var/log/nginx/access.log | grep text_search'
```

## 5. Rollback

```bash
ssh ec2-user@<host>
cd /home/ec2-user/collectedworks21
git checkout baseline-2026-04-18
sudo systemctl restart collectedworks

# chapters.db — restore pre-b.5 snapshot (the old schema had no
# parent_toc_title column, so post-b.5 code will 500 against it).
# Keep a backup before each DB swap, e.g.:
#   cp backend/db/chapters.db backend/db/chapters.db.pre-<tag>
```

To roll back nginx assets, keep the previous `build/` tarball locally (or on
EC2 under `/var/backups/nginx-html-<date>/`) and rsync it back into
`/usr/share/nginx/html/`.

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
