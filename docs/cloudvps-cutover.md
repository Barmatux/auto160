# CloudVPS cutover (auto160.ru → 62.182.102.93)

Prepare-only checklist. Do **not** cut DNS or flip GitHub Actions until every step below is green.

## Target

| Item | Value |
|------|--------|
| Host | `62.182.102.93` |
| OS | Ubuntu 24.04 |
| RAM | ~1 GiB (+ swap) — tight for full `docker-compose.vm.yml` |
| Disk | ~15 GiB |
| SSH (local) | `ssh -i ~/.ssh/auto160_cloudvps root@62.182.102.93` |
| App dir (planned) | `/root/auto160` |
| RF reachability probe | nginx `rf-test` on `:80` (`/`, `/ping`, `/test.png`) |

Old Yandex VM (`89.169.178.29`, user `admin1`) is the current production source of truth for `.env.vm` / DB dump until cutover.

## Already done

- [x] CloudVPS created, SSH key auth works
- [x] RF test page live from BY network
- [x] Repo scripts: `scripts/bootstrap-cloudvps.sh`, this checklist
- [ ] Docker + app dirs on VPS (`bootstrap-cloudvps.sh`) — run when ready
- [ ] `.env.vm` copied (not committed)
- [ ] GitHub Actions secrets pointed at new host
- [ ] First `deploy-vm.yml` / `deploy-vm.sh` run
- [ ] TLS + DNS A/AAAA → new IP
- [ ] Old VM decommissioned

## 1. Bootstrap host (no app)

On the VPS (after code is present, or copy the script alone):

```bash
ssh -i ~/.ssh/auto160_cloudvps root@62.182.102.93
# paste or scp scripts/bootstrap-cloudvps.sh, then:
bash bootstrap-cloudvps.sh
# or: APP_DIR=/root/auto160 bash /root/auto160/scripts/bootstrap-cloudvps.sh
```

Installs Docker Engine + Compose plugin, ensures swap, creates `/root/auto160/{backend,logs}`. Leaves `rf-test` nginx site alone.

## 2. Secrets / `.env.vm`

Copy from old VM if still reachable; otherwise rebuild from `backend/.env.vm.example`.

```bash
# From a machine that can reach BOTH hosts (adjust paths/keys):
scp -i ~/.ssh/<old_key> admin1@89.169.178.29:~/auto160/backend/.env.vm /tmp/.env.vm
scp -i ~/.ssh/auto160_cloudvps /tmp/.env.vm root@62.182.102.93:/root/auto160/backend/.env.vm
rm /tmp/.env.vm
```

Must review on CloudVPS:

- `PUBLIC_SITE_URL=https://auto160.ru` (keep until DNS cut)
- `AUTOPLIUS_SCRAPE_DSN` — private `10.129.0.33` **will not** resolve from CloudVPS. Options: public/tunnel DSN, VPN, or disable `autoplius-sync` until fixed
- `SMTP_*`, `S3_*`, `SECRET_KEY`, DB password, captcha / OpenAI keys — same as prod
- Postgres: fresh volume on first start unless you restore a dump (see §5)

## 3. GitHub Actions secrets (flip only at cutover)

Repo → Settings → Secrets → Actions:

| Secret | New value |
|--------|-----------|
| `VM_HOST` | `62.182.102.93` |
| `VM_USER` | `root` |
| `VM_SSH_KEY` | private key matching `~/.ssh/auto160_cloudvps` (full PEM) |
| `VM_APP_DIR` | `/root/auto160` (optional; default `/home/$USER/auto160` would be wrong for root) |

Until these change, pushes to `master` still target the old VM.

## 4. First deploy (when you say go)

Preferred path (after secrets flipped):

1. Push any pending `master` commit, or **Actions → Deploy to VM → Run workflow**
2. Or manual:

```bash
ssh -i ~/.ssh/auto160_cloudvps root@62.182.102.93
cd /root/auto160
# first time: git clone <repo> .  (or let Actions rsync)
bash scripts/deploy-vm.sh
```

Pipeline already runs `deploy-vm.sh` → compose up → smoke. Nginx: `bash scripts/apply-nginx-vm.sh` (replaces `rf-test` with `auto160` site). Then certbot for `auto160.ru` / `auto160.by` if needed.

### RAM note

Full stack (api + db + many sync workers) on 1 GiB will OOM without swap thrashing. For first bring-up prefer:

```bash
cd /root/auto160/backend
docker compose --env-file .env.vm -f docker-compose.vm.yml up -d --build db api
# enable sync workers after memory is stable / plan upgraded
```

Or scale the VPS to ≥2 GiB before enabling all workers.

## 5. Database

- **Fresh**: compose creates empty Postgres; run migrations via deploy; seed/admin bootstrap from env.
- **Migrate data**: on old host `pg_dump`, copy, restore into new `auto160-db` after first `up`. Plan downtime window; stop writers on old VM during dump.

## 6. DNS / TLS cutover

1. Confirm `http://62.182.102.93/` serves Auto160 (or health via SSH tunnel) before DNS change
2. Point A records `auto160.ru` / `www` / `auto160.by` → `62.182.102.93`
3. Issue/renew Let’s Encrypt on new host
4. Keep old VM up 24–48h as rollback until traffic and scrapers look healthy

## 7. Post-cutover checks

- [ ] `curl -fsS https://auto160.ru/health` (or `/api` health path used in smoke)
- [ ] Login + email verify SMTP
- [ ] Media from S3
- [ ] av.by sync logs (no crash loop)
- [ ] Autoplius path: either working DSN or worker stopped intentionally
- [ ] RF clients can open the site (not only BY)

## 8. Explicitly out of scope until you ask

- Changing GitHub `VM_*` secrets
- Stopping old VM
- DNS changes
- Running `deploy-vm.sh` / compose up on CloudVPS
