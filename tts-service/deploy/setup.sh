#!/usr/bin/env bash
# One-shot installer for the EYEWAZ Urdu TTS engine on a fresh Ubuntu server
# (Hetzner CX22 or similar, x86/amd64). Run as root:  bash setup.sh
set -euo pipefail

echo "==> Installing Docker…"
apt-get update -y
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

echo "==> Pulling and starting the TTS engine…"
cd "$(dirname "$0")"
docker compose pull
docker compose up -d

echo "==> Waiting for the model to load…"
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8090/healthz >/dev/null 2>&1; then break; fi
  sleep 3
done

echo
echo "Done. Health:"
curl -fsS http://localhost:8090/healthz || true
echo
echo "Next:"
echo " 1) Open Hetzner Cloud Firewall and allow inbound TCP 8090 (or 80/443 for TLS)."
echo " 2) On the EYEWAZ backend set:  SELF_HOST_TTS_URL=http://<this-server-ip>:8090"
echo "    (or https://tts.eyewaz.com if you enabled the Caddy TLS profile)."
echo " 3) In EYEWAZ: Account → dialect → 'Urdu — open-source (free)'."
