#!/usr/bin/env bash
# Prepares this Raspberry Pi (or any 64-bit Linux machine) to run the tracker:
# checks the system, installs Docker if needed, and creates .env with fresh
# passwords. Safe to run again: it never overwrites an existing .env.
#
# Usage:  bash pi-setup.sh
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

say "1/4  Checking the system"
arch=$(uname -m)
if [ "$arch" != "aarch64" ] && [ "$arch" != "x86_64" ]; then
  echo "This system is '$arch'. Authentik needs a 64-bit OS."
  echo "Install 'Raspberry Pi OS (64-bit)' (Lite is fine) with Raspberry Pi Imager and try again."
  exit 1
fi
mem_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
echo "Architecture: $arch, memory: ${mem_mb} MB"
if [ "$mem_mb" -lt 3500 ]; then
  echo "WARNING: less than 4 GB of memory. Authentik may be slow or run out of memory."
  echo "A Raspberry Pi 4 or 5 with 4 GB or more is recommended (see the README for adding swap)."
fi

say "2/4  Docker"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "Docker is already installed: $(docker --version)"
else
  echo "Installing Docker (this takes a few minutes)..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  echo "Docker installed. You were added to the 'docker' group."
  NEED_RELOGIN=1
fi

say "3/4  Settings file (.env)"
if [ -f .env ]; then
  echo ".env already exists - leaving it as it is."
else
  cp .env.example .env
  sed -i "s|^PG_PASS=.*|PG_PASS=$(openssl rand -hex 32)|" .env
  sed -i "s|^AUTHENTIK_SECRET_KEY=.*|AUTHENTIK_SECRET_KEY=$(openssl rand -hex 50)|" .env
  read -rp "Your domain on Cloudflare (for example example.com): " domain
  read -rp "Name for the tracker [tracker.$domain]: " th
  read -rp "Name for the sign-in page [auth.$domain]: " ah
  th=${th:-tracker.$domain}; ah=${ah:-auth.$domain}
  sed -i "s|^TRACKER_HOST=.*|TRACKER_HOST=$th|; s|^AUTHENTIK_HOST=.*|AUTHENTIK_HOST=$ah|" .env
  read -rp "Cloudflare tunnel token (paste it, or press Enter to add it later): " tok
  if [ -n "$tok" ]; then
    tok=${tok##* }   # accept the whole "cloudflared ... --token XXX" command too
    sed -i "s|^CLOUDFLARE_TUNNEL_TOKEN=.*|CLOUDFLARE_TUNNEL_TOKEN=$tok|" .env
  fi
  chmod 600 .env
  echo "Created .env (passwords generated). Tracker: https://$th  Sign-in: https://$ah"
fi
# Raspberry Pi OS often has IPv6 turned off; Authentik then can't start unless
# it is told to listen on IPv4 only.
if [ ! -f /proc/net/if_inet6 ] && ! grep -q '^AUTHENTIK_LISTEN__HTTP=' .env; then
  echo "IPv6 is off on this machine - telling Authentik to use IPv4."
  sed -i 's|^# AUTHENTIK_LISTEN__|AUTHENTIK_LISTEN__|' .env
fi

say "4/4  Next steps"
if [ "${NEED_RELOGIN:-}" = 1 ]; then
  echo "Log out and back in (or reboot) so Docker works without sudo, then:"
fi
cat <<'EOF'
  cd into this folder and start everything except the tunnel:
      docker compose up -d --build tracker postgresql authentik-server authentik-worker
  Then follow README-RASPBERRY-PI.md from step 6 (check 'docker compose ps').
EOF
