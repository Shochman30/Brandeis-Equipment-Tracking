# Running the tracker on Linux with Docker, Authentik and a Cloudflare tunnel

*Setting up on a Raspberry Pi? Follow [README-RASPBERRY-PI.md](README-RASPBERRY-PI.md) instead – it's the same setup, step by step.*

This runs the tracker as a real shared web app: everyone signs in with their own
account, edits are saved on the server so everybody sees the same copy, and the
Change history tab shows who made each change.

```
browser ── https ──▶ Cloudflare ── tunnel ──▶ cloudflared ──▶ authentik-server:9000
                                                               │  auth.<domain>    → Authentik sign-in / admin
                                                               │  tracker.<domain> → checks sign-in, then
                                                               ▼
                                                           tracker:8080  (data in the tracker-data volume)
```

Nothing is opened on your router or firewall: `cloudflared` makes an outgoing
connection to Cloudflare. The tracker container has no published port, so the
only way in is through Authentik.

| Container | What it is |
|---|---|
| `tracker` | This repository: `server/app.py` (Python standard library only) serving `index.html`, the drawings and the saved data |
| `authentik-server`, `authentik-worker`, `postgresql` | Authentik 2026.8 – user accounts, sign-in, groups |
| `cloudflared` | Cloudflare tunnel |

## Roles

Access is managed entirely in Authentik, with groups that are created for you:

| Authentik group | In the tracker |
|---|---|
| `tracker-viewers` | Can open and read the tracker, download reports. "View only". |
| `tracker-editors` | Can also edit and **Save changes**. |
| `tracker-owners` (and `authentik Admins`) | Editors who can also set/change the Change history password. |
| no tracker group | Authentik refuses access. |

Group names can be changed with `EDITOR_GROUPS` / `OWNER_GROUPS` in `.env`.

## What you need

- A Linux machine (any distribution with Docker; 2 CPU cores and 4 GB RAM is
  comfortable – Authentik needs about 2 GB on its own) that stays on.
- Docker Engine with the Compose plugin:
  `curl -fsSL https://get.docker.com | sudo sh` then `sudo usermod -aG docker $USER` and log out/in.
- A domain on Cloudflare (free plan is fine), e.g. `example.com`. You will use
  two names under it: `tracker.example.com` and `auth.example.com`.

## 1. Get the code and fill in `.env`

```bash
git clone https://github.com/Shochman30/Brandeis-Equipment-Tracking.git
cd Brandeis-Equipment-Tracking
cp .env.example .env
sed -i "s|^PG_PASS=.*|PG_PASS=$(openssl rand -hex 32)|" .env
sed -i "s|^AUTHENTIK_SECRET_KEY=.*|AUTHENTIK_SECRET_KEY=$(openssl rand -hex 50)|" .env
nano .env     # set TRACKER_HOST and AUTHENTIK_HOST to your two names
```

Leave `CLOUDFLARE_TUNNEL_TOKEN` empty until step 3. `.env` holds secrets – it is in
`.gitignore`, never commit it.

## 2. Start everything except the tunnel, and create the Authentik admin

Do the first-time Authentik setup **before** the tunnel is up, so nobody else
can reach the setup page first.

```bash
docker compose up -d --build tracker postgresql authentik-server authentik-worker
docker compose logs -f authentik-worker    # wait ~1–2 minutes, then Ctrl-C
```

Open `http://localhost:9000/if/flow/initial-setup/` on that machine. (From
another computer: `ssh -L 9000:localhost:9000 you@server`, then open the same
address locally.) Set the admin email and password.

The blueprint in `authentik/blueprints/brandeis-tracker.yaml` is applied
automatically. In the Authentik admin (`Admin interface` button) you should
now see under **Applications → Applications** "Brandeis Energization &
Startup Tracker", and under **Directory → Groups** the three `tracker-*` groups.
If it's not there yet, check **Customization → Blueprints** → "Brandeis tracker".

Then the one manual step:

**Applications → Outposts → authentik Embedded Outpost → Edit**
1. Under *Applications*, move **Brandeis tracker** to the selected side.
2. Under *Advanced settings*, set `authentik_host: https://auth.example.com/`
   (your `AUTHENTIK_HOST`).
3. **Update**.

## 3. Create the Cloudflare tunnel

1. Cloudflare dashboard → **Zero Trust** → **Networks → Tunnels** → **Create a
   tunnel** → type **Cloudflared** → name it (e.g. `brandeis-tracker`) → Save.
2. On the install page choose **Docker**. The command shown ends with
   `--token eyJ...`. Copy just the token into `.env` as
   `CLOUDFLARE_TUNNEL_TOKEN=eyJ...`. (Don't run the shown command.)
3. Add two **public hostnames** (newer dashboards call them *published
   application routes*), both pointing at the same service:

   | Subdomain | Domain | Service type | URL |
   |---|---|---|---|
   | `auth` | `example.com` | HTTP | `authentik-server:9000` |
   | `tracker` | `example.com` | HTTP | `authentik-server:9000` |

   Authentik tells the two apart by the host name.
4. Start the tunnel:

   ```bash
   docker compose up -d cloudflared
   docker compose logs cloudflared     # look for "Registered tunnel connection"
   ```

Open `https://tracker.example.com` – you are sent to `auth.example.com` to sign
in, and come back to the tracker. Your admin account is in `authentik Admins`,
so it opens as owner.

## 4. Add people

**Directory → Users → Create** (or **Directory → Invitations** if you set up
email in `.env`), then open the user → **Groups → Add to existing group** →
`tracker-viewers`, `tracker-editors` or `tracker-owners`. Each person can turn
on two-factor sign-in under their own Authentik settings, or you can require it
in the default authentication flow.

## Day-to-day

```bash
docker compose ps                     # everything "healthy"/"running"?
docker compose logs -f tracker        # who opened/saved what
git pull && docker compose up -d --build   # update to a newer version of this repo
```

### Backups

Saved data lives in the `tracker-data` volume; every save also keeps the
previous copy in `/data/backups` (last 200, set with `KEEP_BACKUPS`). To copy
it off the machine, and to back up Authentik's users:

```bash
docker compose cp tracker:/data ./backup-tracker-$(date +%F)
docker compose exec -T postgresql pg_dump -U authentik authentik > backup-authentik-$(date +%F).sql
```

To restore an older tracker copy, copy one of the `backups/state-*.json` files
over `/data/state.json` and add 1 to `version` in `/data/meta.json` (so pages
that were open before can't save over the restored copy).

### Loading a new export from the Claude tracker

The server's saved data wins over the data built into `index.html`. To replace
it with a fresh export:

```bash
python3 sync/sync_from_artifact.py path/to/artifact.html   # updates index.html
docker compose up -d --build tracker
docker compose exec tracker python3 server/app.py seed --force
```

`seed --force` keeps a backup of what was on the server before replacing it.
Anything saved on the server since the last export is replaced, so do this only
when the Claude tracker is the one people have been updating.

## Trying it on your own computer (no sign-in)

```bash
docker build -t brandeis-tracker .
docker run --rm -p 127.0.0.1:8080:8080 -e AUTH_MODE=none brandeis-tracker
```

Open `http://localhost:8080`. `AUTH_MODE=none` makes everyone an owner, so
never expose that to a network.

## Troubleshooting

- **Authentik restarts in a loop, log says "Address family not supported by
  protocol"** – IPv6 is off on the host. Uncomment the three
  `AUTHENTIK_LISTEN__*` lines in `.env` and `docker compose up -d`.
- **"Not Found" from Authentik on tracker.example.com** – the provider isn't
  added to the embedded outpost yet (step 2), or the Cloudflare hostname
  doesn't match `TRACKER_HOST`.
- **Redirect goes to `localhost:9000` after sign-in** – set `authentik_host`
  on the embedded outpost (step 2).
- **"Permission denied" after sign-in** – the user isn't in any tracker group.
- **Save button missing ("View only")** – the user is only in `tracker-viewers`.

## Security notes

- The tracker trusts the `X-authentik-*` headers that Authentik's proxy adds.
  Authentik overwrites any such headers sent by a browser, but anything that
  can reach `tracker:8080` directly (another container on the same Docker
  network) could fake them. Don't publish port 8080 or attach untrusted
  containers to this network.
- The Change history password is still only a screen inside the page (as in
  the Claude version): anyone with tracker access can read the history in the
  page source. Use Authentik groups for real access control.
- Port 9000 is bound to `127.0.0.1` only, for setup and as a fallback. Remove
  that `ports:` entry in `docker-compose.yml` if you don't need it.
