# Triage backend — deployment & Cloudflare Access runbook (build step 3)

Goal: expose the triage backend at `https://triage-api.<domain>` through a
Cloudflare Tunnel, gated by Cloudflare Access so only your Google identity can
reach it, and verify end-to-end from the work laptop.

The backend code already enforces the Access identity header as defence in
depth (see `TRIAGE_REQUIRE_CF_ACCESS` in `triage/config.py`). The steps below
are the operational glue — most must be run by you (interactive login + the
Cloudflare dashboard).

---

## 0. Prerequisite — a domain on Cloudflare  ⚠️ blocking

A named tunnel's hostname can only be created in a DNS zone Cloudflare manages,
and Access requires Zero Trust. Pick one:

- **Move an existing domain:** Cloudflare dashboard → *Add a site* → enter your
  domain → choose the Free plan → Cloudflare gives you two nameservers → set
  those at your current registrar. Propagation is usually minutes–hours.
- **Register a new domain:** Cloudflare dashboard → *Registrar* → register one
  (it lands on Cloudflare DNS automatically).

Then enable **Zero Trust** (dashboard → Zero Trust → pick a team name → Free
plan). This is what provides Access.

> Until a domain is on Cloudflare, the rest of this runbook can't run. The
> backend, frontend, and config below are all ready and waiting for it.

---

## 1. Install cloudflared on jim-server (systemd)

```bash
# Cloudflare apt repo (Debian/Ubuntu):
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update && sudo apt-get install -y cloudflared
cloudflared --version
```

## 2. Authenticate & create the tunnel  (interactive — run via `! …`)

```bash
cloudflared tunnel login            # opens a browser; pick your domain/zone
cloudflared tunnel create triage    # prints a TUNNEL_UUID + writes creds json
```

The credentials JSON lands in `~/.cloudflared/<TUNNEL_UUID>.json`.

## 3. Tunnel config

```bash
sudo mkdir -p /etc/cloudflared
sudo cp triage/deploy/cloudflared-config.yml.example /etc/cloudflared/config.yml
# Move the tunnel creds where root's service can read them, then edit config:
sudo cp ~/.cloudflared/<TUNNEL_UUID>.json /root/.cloudflared/   # mkdir if needed
sudoedit /etc/cloudflared/config.yml   # fill in <TUNNEL_UUID> and <DOMAIN>
```

## 4. Create the DNS record for the hostname

```bash
cloudflared tunnel route dns triage triage-api.<domain>
```

## 5. Run cloudflared as a service

```bash
sudo cloudflared service install      # generates the systemd unit from config.yml
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared
```

## 6. Cloudflare Access application (Zero Trust dashboard)

Zero Trust → **Access → Applications → Add an application → Self-hosted**:

- **Application domain:** `triage-api.<domain>` (whole host).
- **Policy:** Action *Allow*; Include → *Emails* → `jimbarrett27@gmail.com`.
- **CORS settings (important):** the SPA calls this host cross-origin, so the
  browser sends an unauthenticated `OPTIONS` preflight that Access would
  otherwise challenge. In the application's CORS settings:
  - Access-Control-Allow-Origins: `https://<your-site-domain>`
  - Allow credentials: on
  - Methods: GET, POST · Headers: `*`
- Leave `/healthz` reachable — it's open in the app and used for probes.

> The `/triage` SPA route itself is **not** gated here (your site is on App
> Engine, not Cloudflare). That's fine per the design: the route fetches
> nothing until a request clears Access on this API. If you later move the site
> behind Cloudflare, add a second Access app for `<site>/triage`.

## 7. Backend production env + service

```bash
sudo cp triage/deploy/triage.env.example /etc/triage.env
sudoedit /etc/triage.env             # set TRIAGE_ALLOWED_ORIGINS to your site
sudo cp triage/deploy/triage-backend.service.example \
        /etc/systemd/system/triage-backend.service
sudo systemctl daemon-reload
sudo systemctl enable --now triage-backend
curl -s localhost:8077/healthz       # {"status":"ok"}
```

## 8. Verify end-to-end (from the work laptop)

- `https://triage-api.<domain>/healthz` → `{"status":"ok"}` (open).
- `https://triage-api.<domain>/api/triage/queue` in a browser → redirected to
  the Access login; after signing in as the allowed email → JSON.
- Point the Angular app's API base at `https://triage-api.<domain>` (replacing
  the dev proxy) and load `/triage` — it should list papers once you're past
  Access. (Frontend base-URL switch is a small follow-up.)

### Quick negative checks
- Signing in with a different Google account → blocked by the Access policy.
- A direct request without the Access header (only possible if the backend were
  reachable off-tunnel) → 403 from the backend's own guard.
