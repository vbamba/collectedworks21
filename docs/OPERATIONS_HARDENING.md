# Operations Hardening Runbook

Last updated: 2026-04-08

This runbook captures the production hardening and recovery steps applied for:
- `ask.collectedworksofsriaurobindo.com` (CollectedWorks backend + frontend proxy)
- `vikmere.com`
- `metagrace.io`
- `vikmeresoftware.com` (TLS redirect domain to `vikmere.com`)

## Server Layout

- Server app root (CollectedWorks): `/home/ec2-user/collectedworks21`
- CollectedWorks backend: `/home/ec2-user/collectedworks21/backend`
- Vikmere app: `/home/ec2-user/apps/vikmere-web`
- Metagrace app: `/home/ec2-user/apps/metagrace-web`

## Service Names

- `collectedworks.service` (Gunicorn backend on `127.0.0.1:5000`)
- `vikmere.service` (Next.js app on `127.0.0.1:3000`)
- `metagrace.service` (Next.js app; verify port in unit/nginx)
- `nginx.service`

## Standard Restart Commands

Use service-specific restarts (do not restart unrelated app units):

```bash
sudo systemctl restart collectedworks.service
sudo systemctl restart vikmere.service
sudo systemctl restart metagrace.service
sudo nginx -t && sudo systemctl reload nginx
```

Status check:

```bash
sudo systemctl --no-pager --full status collectedworks.service vikmere.service metagrace.service nginx
```

## Systemd Hardening Applied

Drop-in files are used (do not edit base unit unless needed):

- `/etc/systemd/system/collectedworks.service.d/10-hardening.conf`
- `/etc/systemd/system/collectedworks.service.d/30-security.conf`
- `/etc/systemd/system/vikmere.service.d/10-hardening.conf`
- `/etc/systemd/system/vikmere.service.d/20-node-memory.conf`
- `/etc/systemd/system/vikmere.service.d/30-security.conf`
- `/etc/systemd/system/metagrace.service.d/10-hardening.conf`
- `/etc/systemd/system/metagrace.service.d/20-node-memory.conf`
- `/etc/systemd/system/metagrace.service.d/30-security.conf`

Important settings:
- `Restart=always`
- `RestartSec=5`
- `NoNewPrivileges=true`
- `PrivateTmp=true`
- `PrivateDevices=true`
- `ProtectSystem=full`
- `LimitNOFILE=65535`
- Node services memory/runtime guardrails:
  - `NODE_OPTIONS=--max-old-space-size=512`
  - `MemoryMax=900M`
  - `NEXT_TELEMETRY_DISABLED=1`

Apply changes:

```bash
sudo systemctl daemon-reload
sudo systemctl restart collectedworks.service vikmere.service metagrace.service
```

## Nginx Hardening Applied

Global config:
- `/etc/nginx/conf.d/00-security-global.conf`

Includes:
- `/etc/nginx/snippets/site-security.conf`

Site files include the snippet:
- `/etc/nginx/conf.d/ask.collectedworks.conf`
- `/etc/nginx/conf.d/vikmere.conf`
- `/etc/nginx/conf.d/metagrace.conf`

### Active controls

- `server_tokens off`
- security headers:
  - `X-Content-Type-Options`
  - `X-Frame-Options`
  - `Referrer-Policy`
  - `Permissions-Policy`
  - `Strict-Transport-Security`
- rate limiting and connection limiting
- `client_max_body_size 10m`

### Important note about rate-limit zones

There was a prior config error:
- `the shared memory zone "perip" is already declared for a different use`

To avoid collisions, unique names were used:
- `sec_req_v1`
- `sec_conn_v1`

Always run:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## CollectedWorks CORS Hardening

The backend CORS config in `backend/app/__init__.py` was changed from wildcard origins to explicit trusted origins.

Allowed origins:
- `https://ask.collectedworksofsriaurobindo.com`
- `https://vikmere.com`
- `https://www.vikmere.com`
- `https://metagrace.io`
- `https://www.metagrace.io`

Optional extension:
- `CORS_EXTRA_ORIGINS` env var (comma-separated)

Scoped to:
- `/api/*` only

## Vikmere 502 Recovery Runbook

Symptom:
- `502 Bad Gateway` for `https://vikmere.com`
- nginx error log contains:
  - `connect() failed (111: Connection refused) while connecting to upstream ... 127.0.0.1:3000`

Checks:

```bash
sudo systemctl --no-pager --full status vikmere.service
sudo ss -lntp "( sport = :3000 )"
sudo tail -n 100 /var/log/nginx/error.log | egrep -i 'vikmere|upstream|502|connect\(\) failed|refused'
```

Recovery:

```bash
sudo fuser -k 3000/tcp || true
sudo systemctl restart vikmere.service
sudo nginx -t && sudo systemctl reload nginx
```

Verify:

```bash
curl -Ik --resolve vikmere.com:443:127.0.0.1 https://vikmere.com/
```

## vikmeresoftware.com TLS Redirect Runbook

Goal:
- Serve valid TLS for `vikmeresoftware.com` / `www.vikmeresoftware.com`
- 301 redirect to `https://vikmere.com`

Certificate:

```bash
sudo certbot certonly --nginx \
  -d vikmeresoftware.com \
  -d www.vikmeresoftware.com \
  -m <your-email> \
  --agree-tos --non-interactive
```

Nginx redirect vhost:
- `/etc/nginx/conf.d/vikmeresoftware-redirect.conf`

Validate:

```bash
sudo nginx -t && sudo systemctl reload nginx
curl -Ik --resolve vikmeresoftware.com:443:127.0.0.1 https://vikmeresoftware.com/
```

## Verification Commands

Services enabled:

```bash
sudo systemctl is-enabled collectedworks.service vikmere.service metagrace.service
```

Ports:

```bash
sudo ss -lntp | egrep ':5000|:3000|:3001|gunicorn|node'
```

Domain checks:

```bash
curl -Ik --resolve ask.collectedworksofsriaurobindo.com:443:127.0.0.1 https://ask.collectedworksofsriaurobindo.com/
curl -Ik --resolve vikmere.com:443:127.0.0.1 https://vikmere.com/
curl -Ik --resolve metagrace.io:443:127.0.0.1 https://metagrace.io/
```

## Backup/Snapshot Recommendation

Create infra config snapshot after changes:

```bash
sudo tar -czf /home/ec2-user/hardening-snapshot-$(date +%F-%H%M%S).tgz \
  /etc/systemd/system/collectedworks.service* \
  /etc/systemd/system/vikmere.service* \
  /etc/systemd/system/metagrace.service* \
  /etc/nginx/conf.d \
  /etc/nginx/snippets
```

## Known Observations

- `vikmere.service` was previously observed as `inactive (dead)` with `Result=success`. With `Restart=on-failure`, this can stay down if stopped cleanly. `Restart=always` mitigates this.
- Old logs include historical Next.js/network probe errors and one historical OOM event (earlier period). Keep memory guardrails and monitor with:

```bash
sudo journalctl -u vikmere.service -n 200 --no-pager
sudo dmesg -T | egrep -i 'oom|out of memory|killed process'
```
