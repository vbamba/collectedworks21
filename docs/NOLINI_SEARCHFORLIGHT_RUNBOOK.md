# Nolini-SearchForLight — EC2 Runbook

Last updated: 2026-09-19

This box is separate from the `ask.collectedworksofsriaurobindo.com` server covered in
`OPERATIONS_HARDENING.md`. Different instance, different login user, different key.

It does two things:

- Serves a site over Apache on ports 80/443
- Runs a nightly job that pulls two database backups from an external host and reloads them

## Why this document exists

Two problems cost several hours on 2026-09-18, and both will happen again:

1. **Getting locked out of SSH by our own security software.** The symptom looks exactly like an
   AWS or network failure, so the natural instinct is to go dig through security groups. That is
   the wrong place to look, every time.
2. **A scheduling trap in the import script** that can quietly load yesterday's data with no error
   message. Nothing alerts on it. You would only notice by spotting stale records downstream.

---

## Connection facts

| Item | Value |
|---|---|
| Instance ID | `i-0783980c2300d9257` |
| Name tag | `Nolini-SearchforLight` (instance) / `CollectedWorksNolini-EC2` (Elastic IP) — note the lowercase `f` in the AWS tag |
| Public IP | `35.80.179.155` — **Elastic IP**, survives reboot and stop/start |
| Region | `us-west-2` |
| AWS account | `975050364606` |
| OS | Ubuntu 24.04, Apache 2.4.58 |
| Server timezone | `Etc/UTC` |
| **SSH user** | **`ubuntu`** |
| Key | `~/Projects/aws-ssh-keys/sriaurola.pem` |

```bash
ssh -i ~/Projects/aws-ssh-keys/sriaurola.pem ubuntu@35.80.179.155
```

Two things that waste time if you forget them:

- The login user is **`ubuntu`**. Not `root`, not `admin`, not `vbamba`. Wrong usernames are what
  cause the lockout described below, so guessing is actively harmful here.
- Root has no password, so `su root` will always fail. Use `sudo -i`.

---

## Scenario: "I can't SSH in"

This happened on 2026-09-18. The sequence looked like this:

```
$ ssh -i sriaurola.pem root@35.80.179.155
root@35.80.179.155: Permission denied (publickey).

$ ssh -i sriaurola.pem admin@35.80.179.155
ssh: connect to host 35.80.179.155 port 22: Connection refused
```

### How to read those two messages

They mean very different things, and the difference is the whole diagnosis:

- **"Permission denied (publickey)"** means SSH answered you. The network is fine, the server is
  fine, the daemon is fine. You simply failed to authenticate.
- **"Connection refused"** immediately afterward means something started actively rejecting you
  between one attempt and the next.

A server does not lose its network in the gap between two commands. Something on the box decided
to block you — and that something is **fail2ban**, which is installed here. It watches for failed
logins and bans the source IP. Its default action on Ubuntu rejects the connection outright, which
is exactly the "Connection refused" you see.

### Confirm it in 10 seconds

```bash
nc -vz -w 6 35.80.179.155 22
nc -vz -w 6 35.80.179.155 80
```

**If 80 answers and 22 refuses, it is fail2ban.** The machine is healthy and reachable; only you
are being turned away. Do not go inspect security groups — a network-level problem would take down
80 as well.

### Getting back in

You cannot SSH in, so use **AWS Systems Manager Session Manager** instead. This instance has the
`EC2-SSM-CloudWatch-Role` attached, and Session Manager works over a connection the server makes
*outward* to AWS. It needs no inbound port at all, which is why fail2ban cannot block it.

1. AWS Console → EC2 → select `i-0783980c2300d9257` → **Connect** → **Session Manager** tab
2. You land as `ssm-user`. Then:

```bash
sudo fail2ban-client status sshd
sudo fail2ban-client set sshd unbanip <your-ip>
sudo fail2ban-client status sshd
```

The second status should report `Currently banned: 0`. SSH works again immediately.

Find your current IP with `curl -s https://checkip.amazonaws.com`.

> **Paste one line at a time.** The Session Manager browser terminal drops multi-line pastes — it
> echoes the extra lines but never runs them. This silently cost us a round trip: the unban
> appeared to have been issued when it never executed. Chain commands with `;` on a single line
> instead.

### Stop it recurring

`/etc/fail2ban/jail.local` has an `ignoreip` entry for the office/home IP. Note that **a home IP
from most ISPs is dynamic**, so that entry goes stale on its own and this will eventually happen
again. Session Manager is the reliable way back in — treat it as the primary recovery path, not
the fallback.

To verify the whitelist is actually in effect:

```bash
sudo fail2ban-client get sshd ignoreip
```

### What is NOT the problem

Ruled out by direct inspection on 2026-09-18, so skip these:

- Security group — allows 22 from `0.0.0.0/0`
- Network ACLs — allow all
- Route table — internet gateway attached and active
- Instance health — both AWS status checks pass
- `ufw` — **inactive** on this box
- The key — `sriaurola.pem` fingerprint matches the AWS key pair exactly

A useful check to *skip*: the Narad instance (`54.218.177.7`) cannot be used as a jump host to test
port 22. Its security group only permits ports 80 and 443 outbound, so an SSH probe from there
times out no matter what the target is doing. That misleading result sent us down a wrong path.

---

## The pharmacy import job

Runs from **vbamba's** crontab (not root's, not ubuntu's):

```cron
# 16:45 UTC = 10:45am Mountain (MDT) / 9:45am (MST). Must stay after 02:30 UTC
# or the script's IST 0800 cutoff flips target_date to the previous day.
45 16 * * * /home/vbamba/bin/import_pharmacy.sh >> /home/vbamba/logs/pharmacy_import.log 2>&1
```

What it does each run: downloads `pharmacy` and `medical` SQL dumps from `162.241.194.125`, resets
and reimports both databases, archives each file locally and remotely, then prunes both archives at
7 days.

```bash
tail -30 /home/vbamba/logs/pharmacy_import.log
```

### The 02:30 UTC rule — read before changing the schedule

The script does not simply grab the newest file. It decides **which day's backup to look for** by
comparing the current time *in India Standard Time* against an `0800` cutoff. You can see it
in the log:

```
(medical) IST now=2000, cutoff=0800, target_date=2026-09-18
```

0800 IST is **02:30 UTC**. So:

> **Any schedule earlier than 02:30 UTC makes the job import the previous day's data.**

There is no error and no warning. The run reports success. You would only find out by noticing the
data is a day behind.

The current 16:45 UTC slot lands at 22:15 IST — well past the cutoff, and still 1h45m clear of IST
midnight. Keep any future schedule inside roughly **03:00–18:00 UTC** and this stays safe. Note the
upper bound: past about 18:30 UTC the job crosses into the next IST day and `target_date` moves
forward, which is the same stale-data failure from the other direction.

### Do not use CRON_TZ on this server

The obvious way to pin the job to Mountain time regardless of daylight saving is:

```cron
CRON_TZ=America/Denver
0 9 * * * ...
```

**This does not work here, and it fails silently.** Ubuntu ships the Debian Vixie fork of cron
(`3.0pl1-184ubuntu2`), which has no `CRON_TZ` support — that is a cronie feature, found on
RHEL/Fedora/Amazon Linux. Debian's cron treats the line as an ordinary environment variable,
ignores it for scheduling, and runs the job in UTC anyway. Setting `CRON_TZ=America/Denver` with
`0 9` fires the job at **3:00 AM Mountain**, six hours off, with nothing in any log to indicate
a problem.

Check before trusting it:

```bash
strings /usr/sbin/cron | grep -i cron_tz    # empty output = not supported
```

Because of this, the schedule is **set directly in UTC** and drifts one hour across daylight
saving: 10:45am Mountain in summer, 9:45am in winter. For an unattended database import that nobody is
waiting on, that drift does not matter, and a plain crontab line is far easier to maintain than
the alternative.

If exact local time ever does matter, the correct tool is a systemd timer, which handles time zones
natively:

```ini
[Timer]
OnCalendar=*-*-* 09:00:00 America/Denver
Persistent=true
```

Verify any such expression *before* relying on it — this prints the next three fire times:

```bash
systemd-analyze calendar --iterations=3 '*-*-* 09:00:00 America/Denver'
```

### Confirming a schedule change took effect

```bash
crontab -l | grep -v '^#'
sudo journalctl -u cron --since "10 min ago" --no-pager | grep -i reload
```

Look for `(vbamba) RELOAD (crontabs/vbamba)`. Cron only polls once a minute, so allow a minute
before concluding anything. Then confirm against the next day's log:

```bash
grep "$(date -u +%Y-%m-%d)" /home/vbamba/logs/pharmacy_import.log | head -3
```

---

## Known gaps

None of these are urgent, but they are real:

- **The log never rotates.** `pharmacy_import.log` is append-only and was ~775 KB as of
  2026-09-18. A `logrotate` config using `copytruncate` would fix it — `copytruncate` specifically,
  because the cron line holds the file open with `>>` and a plain rotate would leave cron writing
  to a deleted file.
- **Database passwords are passed on the mysql command line.** This produces the
  `Using a password on the command line interface can be insecure` warning in every run. Anyone who
  can run `ps` while the import is going can read them. A `~/.my.cnf` at mode 0600 is the standard
  fix.
- **Port 22 is open to `0.0.0.0/0`** in the security group. Since Session Manager provides access
  without any inbound port, narrowing this costs little.
- **A reboot is pending** (`*** System restart required ***`). Safe to do whenever: the address is
  an Elastic IP so it survives, and `ufw` is inactive so there is no firewall state to restore.

## IAM note

The `vishal` IAM user has only `ViewOnlyAccess` plus billing policies. It **cannot** reboot the
instance, start a Session Manager session, or read the serial console — those return
`UnauthorizedOperation` / `AccessDeniedException`. Use the AWS Console as root, or an admin
identity, for any of that. The console route is what makes Session Manager available during a
lockout.
