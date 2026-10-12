# CloudVPS cutover (auto160 → 93.125.82.184)

## Target (current)

| Item | Value |
|------|--------|
| Host | `93.125.82.184` |
| User | `root` |
| App dir | `/root/auto160` |
| SSH (local) | `ssh -i ~/.ssh/auto160_cloudvps root@93.125.82.184` |
| RAM | ~4 GiB (after resource upgrade) |
| GitHub secrets | `VM_HOST`, `VM_USER=root`, `VM_SSH_KEY`, `VM_APP_DIR=/root/auto160` |

Previous probe host `62.182.102.93` and legacy Yandex `89.169.178.29` are not the Actions target.

## Bring-up notes

- Until DNS A records point here and certbot issues certs, nginx uses `scripts/nginx-auto160-http.conf` (HTTP :80 → API).
- `PUBLIC_SITE_URL` stays as in `.env.vm` until `/etc/letsencrypt/live/auto160.ru/fullchain.pem` exists; then deploy forces `https://auto160.ru`.
- `AUTOPLIUS_SCRAPE_DSN` private `10.129.x` from the old VPC will not work — fix DSN or expect `autoplius-sync` errors.
- Old prod `.env.vm` was unreachable at cutover; new host got a fresh `.env.vm` (rotate S3/SMTP/API keys from backups when available).

## After DNS

```bash
ssh -i ~/.ssh/auto160_cloudvps root@93.125.82.184
certbot --nginx -d auto160.ru -d www.auto160.ru --non-interactive --agree-tos -m you@example.com --redirect
# optional .by:
# certbot --nginx -d auto160.by -d www.auto160.by ...
APP_DIR=/root/auto160 bash /root/auto160/scripts/apply-nginx-vm.sh
```
