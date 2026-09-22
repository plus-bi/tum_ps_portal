# Deploying on a Google Cloud VM

This runbook deploys the portal as the existing Docker Compose stack on one Compute Engine VM. Caddy is the only public container; Next.js, FastAPI, PostgreSQL, Redis, Celery Worker, and Celery Beat stay on the private Compose network.

## Important ingestion status

Celery Beat is configured to enqueue `app.tasks.ingest_all` every day at 03:00 Europe/Berlin. The current ingestion service reads the audited frozen fixtures in `backend/tests/fixtures/chairs`; it does **not yet download live chair pages**. Before treating the schedule as a production live crawler, connect `ingest_all` to the robots-aware fetcher and add the planned PostgreSQL advisory lock. Do not run both Celery Beat and a second external scheduler for the same task.

## 1. Create the VM and DNS

A practical starting VM is Ubuntu 24.04 LTS, `e2-standard-2` (2 vCPU, 8 GB RAM), with a 30–50 GB balanced persistent disk. Use `e2-standard-4` if OCR or multiple document parsers will run concurrently.

Reserve a static external IP, create an `A` record such as `projects.example.org`, and allow inbound TCP 80 and 443. Allow SSH only through OS Login/IAP or a restricted source range. Do not expose ports 3000, 5432, 6379, or 8000.

Install Git, Docker Engine, and the Docker Compose v2 plugin from Docker's official Ubuntu repository. Enable Docker at boot:

```bash
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Log out and back in after changing group membership.

## 2. Install and configure the portal

Use a stable application directory and clone the repository:

```bash
sudo mkdir -p /opt/tum-ps-portal
sudo chown "$USER":"$USER" /opt/tum-ps-portal
git clone YOUR_REPOSITORY_URL /opt/tum-ps-portal
cd /opt/tum-ps-portal
cp .env.example .env
chmod 600 .env
```

Set at least these production values in `.env`:

```dotenv
POSTGRES_DB=portal
POSTGRES_USER=portal
POSTGRES_PASSWORD=REPLACE_WITH_A_LONG_RANDOM_PASSWORD
DATABASE_URL=postgresql+psycopg://portal:REPLACE_WITH_THE_URL_ENCODED_PASSWORD@postgres:5432/portal

PORTAL_DOMAIN=projects.example.org
PORTAL_HTTP_PORT=80
PORTAL_HTTPS_PORT=443
PUBLIC_URL=https://projects.example.org
```

If the database password contains URL-special characters, percent-encode it in `DATABASE_URL`. Add Clerk, OpenAI, and Resend credentials only when those integrations are enabled. Never commit `.env`; it is excluded by `.gitignore`. For stricter secret management, render `.env` at deployment time from Google Secret Manager.

`NEXT_PUBLIC_API_URL` is not needed for server-side requests in the current container setup; the web container uses `http://api:8000/api/v1` internally.

## 3. Start and verify

Build and start all services:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 caddy api web worker beat
```

Caddy obtains and renews the public TLS certificate automatically after DNS resolves and ports 80/443 are reachable. Its certificate state and PostgreSQL data are stored in named Docker volumes.

Run the initial ingestion after the containers are healthy:

```bash
docker compose exec -T worker python -c "from app.tasks import ingest_all; print(ingest_all.run())"
curl --fail --silent --show-error https://projects.example.org/health
```

The direct Python command runs synchronously and prints per-department results. After live fetching is connected, the regular 03:00 task will be visible in the Beat and worker logs:

```bash
docker compose logs --since=24h beat worker
```

## 4. Start automatically after VM reboot

Every service has `restart: unless-stopped`, and Docker should start the containers after a reboot. For explicit stack-level lifecycle management, create `/etc/systemd/system/tum-project-studies.service`:

```ini
[Unit]
Description=TUM Project Studies Portal
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/tum-ps-portal
ExecStart=/usr/bin/docker compose up -d --remove-orphans
ExecStop=/usr/bin/docker compose stop
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Then enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tum-project-studies.service
```

## 5. Backups and monitoring

Back up PostgreSQL daily to a private, versioned Cloud Storage bucket. A database dump can be produced without publishing the database port:

```bash
mkdir -p backups
docker compose exec -T postgres pg_dump -U portal -d portal | gzip > "backups/portal-$(date -u +%F-%H%M%S).sql.gz"
gcloud storage cp backups/portal-*.sql.gz gs://YOUR_PRIVATE_BACKUP_BUCKET/
```

Run this from a root-owned systemd timer or cron entry, apply a bucket lifecycle policy, and periodically test restoration. Also consider scheduled persistent-disk snapshots; they complement rather than replace logical database dumps.

Install the Google Cloud Ops Agent or another monitor for disk usage, container restarts, `/health`, and failed worker tasks. Configure alerts before relying on unattended ingestion.

## 6. Updating and rollback

Deploy a reviewed commit or release tag rather than an arbitrary working tree:

```bash
cd /opt/tum-ps-portal
git fetch --tags origin
git checkout YOUR_RELEASE_TAG
docker compose build --pull
docker compose up -d --remove-orphans
docker compose ps
```

Before any migration-bearing release, take a database backup. To roll back application code, check out the preceding release tag and rebuild. Do not remove the `postgres_data`, `caddy_data`, or `caddy_config` volumes during updates.

Useful diagnostics:

```bash
docker compose ps
docker compose logs --tail=200 caddy api web worker beat
docker compose exec -T postgres pg_isready -U portal -d portal
docker compose exec -T redis redis-cli ping
```
