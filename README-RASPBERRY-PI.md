# Brandeis Tracker on a Raspberry Pi – step-by-step guide (using MobaXterm)

This guide takes you from a blank Raspberry Pi to the tracker live at
`https://tracker.<your-domain>`, with:

- **Authentik** for user accounts and sign-in (each person has their own login),
- **shared saving** (everyone sees the same data; Change history shows who changed what),
- a **Cloudflare tunnel** to put it on the internet with no router or firewall changes.

```
phone / laptop ──https──▶ Cloudflare ──tunnel──▶ Raspberry Pi
                                                  ├─ cloudflared        (the tunnel)
                                                  ├─ authentik-server   (sign-in at auth.<domain>, guards tracker.<domain>)
                                                  ├─ authentik-worker + postgresql
                                                  └─ tracker            (the app and its saved data)
```

Plan on about an hour the first time. This guide uses **MobaXterm** on a
Windows PC to connect to the Pi, copy files and open the first-time setup page.
Every command in a grey box is typed (or pasted) into the **MobaXterm terminal
connected to the Pi**, unless the step says otherwise.

### MobaXterm basics (read once)

- **Install:** download MobaXterm *Home Edition* (free) from mobaxterm.mobatek.net
  – the "Installer edition" or "Portable edition" both work.
- **Paste** into the terminal: **right-click** (or Shift+Insert). Ctrl+V does not paste
  by default.
- **Copy** from the terminal: just select the text with the mouse – it's copied.
- **The left panel** (SFTP tab) shows the files on the Pi. You can drag files
  from Windows into it and drag files out of it to Windows.
- **If a session closes** (after `exit` or a reboot), click in the tab and press
  **R** to reconnect, or double-click the saved session under **User sessions**.
- **Don't edit the Pi's files with a Windows editor** (including double-clicking
  them in the left panel). Use `nano` in the terminal as shown in this guide –
  Windows editors can add Windows line endings that break the scripts.

---

## 1. What you need

| Item | Notes |
|---|---|
| Raspberry Pi 4 or 5, **4 GB RAM or more** (8 GB ideal) | Authentik alone uses about 1.5–2 GB. A 2 GB Pi will struggle. |
| Storage: 32 GB+ microSD, or better a **USB SSD** | The database writes constantly; an SSD is faster and lasts much longer than an SD card. |
| Official power supply, network cable (or Wi-Fi) | The Pi has to stay on for the site to be up. |
| A domain name **on Cloudflare** (free plan is fine) | e.g. `example.com`. You'll use `tracker.example.com` and `auth.example.com`. |
| A Windows PC with **MobaXterm**, on the same network as the Pi | To flash the card, copy the zip and do the first setup. |
| `brandeis-tracker.zip` (or part1 + part2) | This package. |

## 2. Prepare the Raspberry Pi

1. On your computer, install **Raspberry Pi Imager** (raspberrypi.com/software).
2. Choose your Pi model, then **Raspberry Pi OS Lite (64-bit)**.
   *It must be 64-bit* – Authentik doesn't run on 32-bit.
3. Choose the SD card / SSD. When asked "apply OS customisation settings", click
   **Edit settings**:
   - hostname: `tracker-pi`
   - username and password (remember them; this guide uses `pi`)
   - Wi-Fi (skip if using a cable), your time zone
   - **Services** tab: **Enable SSH** (password authentication)
4. Write it, put it in the Pi, power on, wait 2–3 minutes.
5. **Create a MobaXterm session for the Pi** (once; it's saved for next time):
   1. Open MobaXterm → click **Session** (top left) → **SSH**.
   2. **Remote host:** `tracker-pi.local`
      (if that isn't found later, use the Pi's IP address from your router, e.g. `192.168.1.50`).
   3. Tick **Specify username** and enter `pi` (your username from step 3). Port stays `22`.
   4. Open the **Bookmark settings** tab and set **Session name** to `Tracker Pi`.
   5. Click **OK**. Accept the "new host key" question, then type the Pi's
      password (nothing shows while typing – that's normal) and press Enter.
      MobaXterm may offer to save the password; that's up to you.

   You now have a terminal on the Pi (the prompt looks like `pi@tracker-pi:~ $`)
   and the Pi's files in the left panel.
6. Update the Pi and install unzip – paste this into the terminal:

   ```bash
   sudo apt update && sudo apt full-upgrade -y && sudo apt install -y unzip
   sudo reboot
   ```

   The session disconnects. Wait a minute, click in the tab and press **R** to reconnect.

## 3. Create the Cloudflare tunnel

You can do this from any browser.

1. Make sure your domain is in your Cloudflare account and active.
2. Go to **Cloudflare dashboard → Zero Trust → Networks → Tunnels**
   → **Create a tunnel** → **Cloudflared** → name it `brandeis-tracker` → **Save tunnel**.
3. On the "Install and run a connector" page pick **Docker**. You'll see a
   command ending in `--token eyJhIjoi...`. **Copy that long token** (everything
   after `--token`) and keep it for step 5. Don't run the command itself.
4. Click **Next** and add the first **public hostname** (newer dashboards call
   it a *published application route*):
   - Subdomain `auth`, Domain `example.com`
   - Service: Type **HTTP**, URL `authentik-server:9000`
   - **Save**
5. Add a second public hostname the same way:
   - Subdomain `tracker`, Domain `example.com`
   - Service: Type **HTTP**, URL `authentik-server:9000` (yes, the same – Authentik decides what to show by name)

The tunnel shows as "Inactive/Down" until step 9. That's expected.

## 4. Copy the zip to the Pi and unpack it

The package comes either as one file, `brandeis-tracker.zip`, or as two parts,
`brandeis-tracker-part1.zip` and `brandeis-tracker-part2.zip` (part 2 holds the
rest of the drawings). Copy whichever you have.

**Upload with MobaXterm:**
1. In the terminal, type `cd ~` and press Enter, so the left panel shows your home
   folder (`/home/pi`). (Tick **Follow terminal folder** at the bottom of the left
   panel if it doesn't follow.)
2. In Windows Explorer, select the zip file(s) and **drag them into the left
   panel**. Wait for the transfer to finish (progress shows at the bottom).
   Upload the **zip files** – don't unzip them on Windows first.

**Unpack them on the Pi** (terminal):

```bash
cd ~
for z in brandeis-tracker*.zip; do unzip -o "$z"; done
cd brandeis-tracker
ls
ls *.jpg | wc -l      # should print 68
```

You should see `docker-compose.yml`, `Dockerfile`, `index.html`, the `.jpg`
drawings, `server/`, `authentik/`, `pi-setup.sh` and this guide. If the count
is not 68, part 2 is missing.

## 5. Run the setup script

```bash
bash pi-setup.sh
```

It will:
- check the Pi is 64-bit and has enough memory,
- install Docker if it's missing,
- create `.env` (the settings file) with freshly generated passwords,
- ask for your domain (e.g. `example.com`), the two names (press Enter to accept
  `tracker.example.com` / `auth.example.com`), and the **tunnel token** from step 3.

If it installed Docker, reconnect so you can use Docker without `sudo`: type
`exit`, press **R** to reconnect, then:

```bash
cd ~/brandeis-tracker
```

To check or change settings later: `nano .env` (Ctrl-O Enter to save, Ctrl-X to exit).
`.env` contains passwords – don't share it.

## 6. Start the tracker and Authentik (tunnel still off)

```bash
docker compose up -d --build tracker postgresql authentik-server authentik-worker
```

The first time this downloads about 1.5 GB and builds the tracker; on a Pi
allow **10–15 minutes**. Then check:

```bash
docker compose ps
```

Wait until `authentik-server` and `authentik-worker` say **healthy** (re-run
the command every minute or so; the first start on a Pi can take 5 minutes).

> The tunnel stays off until Authentik has an admin account, so nobody on the
> internet can reach the first-time setup page before you do.

## 7. Create your Authentik admin account

Authentik's admin page is only reachable from the Pi itself for now. Use a
MobaXterm **SSH tunnel** to bring it to your PC:

1. In MobaXterm click **Tunneling** (top toolbar) → **New SSH tunnel**.
2. Select **Local port forwarding** and fill in the three boxes:

   | Box | Field | Value |
   |---|---|---|
   | My computer with MobaXterm | Forwarded port | `9000` |
   | SSH server | SSH server / SSH login / SSH port | `tracker-pi.local` / `pi` / `22` |
   | Remote server | Remote server / Remote port | `localhost` / `9000` |

3. Click **Save**. In the tunnel list, name it `Authentik setup` and click the
   **▶ start** button (enter the Pi's password if asked). Leave the list open.

   *Alternative:* click **Start local terminal** in MobaXterm and paste
   `ssh -L 9000:localhost:9000 pi@tracker-pi.local` – keep that tab open.

Then, in your PC's browser, go to:

**http://localhost:9000/if/flow/initial-setup/**

Enter your email and a strong password. This is the **admin** account (it can
also use the tracker as an owner).

Then click **Admin interface** (top right) and check that the tracker was set up
automatically:
- **Applications → Applications**: "Brandeis Energization & Startup Tracker" is listed.
- **Directory → Groups**: `tracker-viewers`, `tracker-editors`, `tracker-owners` exist.

(If they're missing, wait a minute and refresh. **Customization → Blueprints**
→ "Brandeis tracker" shows whether it applied.)

## 8. Connect the tracker to Authentik's proxy (one-time)

Still in the Authentik admin:

1. **Applications → Outposts**.
2. On **authentik Embedded Outpost**, click the **Edit** (pencil) icon.
3. Under **Applications**, select **Brandeis tracker** and move it to the
   selected list (arrow button).
4. Open **Advanced settings**. In the configuration text find the line
   `authentik_host:` and set it to your sign-in address, with `https://` and a
   trailing slash:

   ```yaml
   authentik_host: https://auth.example.com/
   ```

5. Click **Update**.

## 9. Turn on the tunnel

Back in the Pi's terminal:

```bash
docker compose up -d cloudflared
docker compose logs cloudflared
```

Look for `Registered tunnel connection` (usually 4 of them). In the Cloudflare
dashboard the tunnel now shows **Healthy**.

Open **https://tracker.example.com** on any device. You're sent to
`auth.example.com` to sign in with the admin account, then back to the tracker,
showing **"All changes saved"** and a **Save changes** button.

You can stop the `Authentik setup` tunnel from step 7 now (**Tunneling** → ■ stop).
Keep it saved – it's handy if you ever need Authentik while the internet is down.

## 10. Add the people who will use it

In the Authentik admin (**https://auth.example.com/if/admin/**):

1. **Directory → Users → Create**: username, name (this is the name shown in
   Change history), email → **Create**.
2. Open the user → **Set password** (or use **Create recovery link** and send
   them the link so they choose their own).
3. On the user's page → **Groups** tab → **Add to existing group** → pick one:

| Group | What they can do |
|---|---|
| `tracker-viewers` | Look at everything and download reports; "View only". |
| `tracker-editors` | Also edit and **Save changes**. |
| `tracker-owners` | Editors who can also set the Change history password. |
| *(no tracker group)* | Can't open the tracker at all. |

Tip: under each user's **Settings → MFA devices** they can add an
authenticator app for two-step sign-in.

---

## Everyday use

All commands are run inside `~/brandeis-tracker`.

| Task | Command |
|---|---|
| Is everything running? | `docker compose ps` |
| See recent activity / errors | `docker compose logs --tail 50 tracker` (or `authentik-server`, `cloudflared`) |
| Restart everything | `docker compose restart` |
| Stop everything | `docker compose down` (data is kept) |
| Start everything | `docker compose up -d` |

**After a power cut or reboot** everything starts by itself (Docker starts on
boot and the containers are set to `restart: unless-stopped`). Give the Pi
3–5 minutes.

### Backups

Every save keeps the previous version inside the tracker (last 200). To make a
copy you can take off the Pi:

```bash
cd ~/brandeis-tracker
docker compose cp tracker:/data ./backup-tracker-$(date +%F)
docker compose exec -T postgresql pg_dump -U authentik authentik > backup-authentik-$(date +%F).sql
```

Then copy them to your PC: in MobaXterm's left panel open `brandeis-tracker`,
select the `backup-…` folder and `.sql` file and **drag them to a Windows folder**
(or right-click → **Download**).

To roll the tracker back to an earlier save: copy one of the files in
`backups/` over `/data/state.json`, and add 1 to `version` in `/data/meta.json`:

```bash
docker compose exec tracker ls /data/backups | tail
docker compose exec tracker cp /data/backups/state-XXXXXXXX-before-save.json /data/state.json
docker compose exec tracker sh -c 'python3 -c "import json;p=\"/data/meta.json\";m=json.load(open(p));m[\"version\"]+=1;json.dump(m,open(p,\"w\"))"'
```

### Loading a new export from the Claude tracker

Data saved on the Pi takes priority over the data built into `index.html`.
To replace it with a new export (this overwrites what was saved on the Pi;
a backup is kept), first drag the exported `artifact.html` from Windows into the
left panel's home folder (`/home/pi`), then:

```bash
cd ~/brandeis-tracker
python3 sync/sync_from_artifact.py ~/artifact.html     # updates index.html
docker compose up -d --build tracker
docker compose exec tracker python3 server/app.py seed --force
```

### Updating to a new version of this package

Drag the new zip file(s) into `/home/pi` in MobaXterm's left panel as in step 4
(say **yes** to overwrite the old zips), then unpack over the old folder (your `.env` and saved data are not in the zip, so they're kept):

```bash
cd ~ && for z in brandeis-tracker*.zip; do unzip -o "$z"; done
cd brandeis-tracker && docker compose up -d --build
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `pi-setup.sh` says the system isn't 64-bit | Re-flash with **Raspberry Pi OS (64-bit)**. |
| `authentik-server` keeps restarting; log says *Address family not supported by protocol* | IPv6 is off. In `.env` remove the `#` from the three `AUTHENTIK_LISTEN__` lines, then `docker compose up -d`. (`pi-setup.sh` normally does this for you.) |
| `docker: permission denied` | Reconnect after installing Docker (`exit`, then **R**), or run `sudo usermod -aG docker $USER` first. |
| MobaXterm: *Network error: Connection timed out* / host not found | The Pi is off or not on the network, or `tracker-pi.local` isn't resolving – edit the session (right-click → **Edit session**) and use the Pi's IP address from your router. |
| MobaXterm tunnel won't start: *port 9000 already in use* | Another program on your PC uses 9000. In the tunnel use forwarded port `9001` instead and open `http://localhost:9001/if/flow/initial-setup/`. |
| `pi-setup.sh: $'\r': command not found` | A file was changed by a Windows editor. Re-upload the zip(s), unzip again (step 4), and edit only with `nano`. |
| Pasting does nothing | Right-click in the terminal (or Shift+Insert); Ctrl+V doesn't paste by default. |
| Pi very slow / containers killed | Not enough memory. Use a 4 GB+ Pi, close other programs, or add swap (if your Pi has `/etc/dphys-swapfile`: `sudo nano /etc/dphys-swapfile`, set `CONF_SWAPSIZE=2048`, then `sudo systemctl restart dphys-swapfile`; check with `free -h`). |
| Cloudflare shows error **1033** | The tunnel isn't connected: `docker compose logs cloudflared`. Usually a wrong/missing `CLOUDFLARE_TUNNEL_TOKEN` in `.env`; fix it and `docker compose up -d cloudflared`. |
| Cloudflare shows **502 Bad Gateway** | Authentik isn't ready yet (wait), or the hostname's service isn't exactly `http://authentik-server:9000`. |
| tracker.example.com shows an Authentik **"Not Found"** page | Step 8 not done, or the Cloudflare hostname differs from `TRACKER_HOST` in `.env`. |
| After signing in you land on `localhost:9000` | `authentik_host` not set in step 8. |
| "Permission denied" after signing in | That user isn't in any `tracker-…` group (step 10). |
| No **Save changes** button ("View only") | The user is only in `tracker-viewers`. |
| "Someone else saved first" | Two people edited at the same time; the page reloads with the latest version – redo your edit and save. |
| Forgot the admin password | `docker compose exec authentik-worker ak create_recovery_key 10 akadmin` and open the printed link (replace the start with `https://auth.example.com`). Use your admin's username if it isn't `akadmin`. |

## Security notes

- Only Authentik is reachable from the internet; the tracker itself has no open
  port and trusts the user details Authentik passes along.
- Port 9000 is open **only on the Pi itself** (for step 7 and emergencies).
- The Change history password is just a screen inside the page; real access
  control is the Authentik groups.
- Keep the Pi updated: `sudo apt update && sudo apt full-upgrade -y` monthly,
  and `docker compose pull && docker compose up -d` to update Authentik and cloudflared.
- Before putting project data online, confirm with Dimeo and Brandeis that
  this is allowed.
