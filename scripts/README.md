# GoodWe Cloud Hub - Deployment Scripts

Automated scripts for deploying the Cloud Hub infrastructure.

## Quick Start

### 1. Backup Raspberry Pi (Phase 3 Only)
```bash
./scripts/backup-rasp.sh
```
> **Note**: Only needed when deploying edge agent to Pi (Phase 3).
> VPS-only deployment does NOT require this step.

- **Stops** the `goodwe-coordinator` service for consistent backup
- Backs up database, config, git state to `~/Desktop/backups/`
- **Restarts** the service automatically after backup

### 1b. Restore Raspberry Pi (Emergency Recovery)
```bash
./scripts/restore-rasp.sh ~/Desktop/backups/pre-cloud-deployment-20260110
```
- Restores database, config, and git state from backup
- Restarts service after restore

### 2. Setup VPS (First Time Only)
```bash
./scripts/deploy-vps-setup.sh
```
Installs Docker, creates users, configures firewall.

### 2. Setup Production Secrets (Securely)
```bash
# For VPS (Hub API)
./scripts/manage-secrets.sh vps

# For Raspberry Pi (Edge Node)
./scripts/manage-secrets.sh rasp
```
Interactively prompts for your Database and MQTT passwords and writes them directly to the server's `.env` file via SSH. **No secrets are stored locally.**

### 3. Configure RabbitMQ
```bash
./scripts/configure-rabbitmq.sh
```
Connects to your managed RabbitMQ API and creates the required users (`hub_api`, `node_01`) and sets permissions.

### 4. Deploy Hub API
```bash
# Deploy (assumes secrets are already set)
./scripts/deploy-hub-api.sh
```

### 4. Deploy Dashboard
```bash
# Build and deploy to VPS
./scripts/deploy-dashboard.sh

# Or build only (for Vercel/Netlify)
./scripts/deploy-dashboard.sh build-only
```

### 5. Setup SSL (Optional but Recommended)
```bash
ssh -p 10358 root@srv26.mikr.us
cd /home/goodwe/goodwe-cloud-hub
./setup-nginx.sh
# Then follow prompts to get SSL certificate
```

## Available Scripts

| Script | Purpose | Prerequisites |
|--------|---------|--------------|
| `backup-rasp.sh` | Backup Raspberry Pi | SSH access to Rasp |
| `deploy-vps-setup.sh` | Initial VPS setup | Root SSH to VPS |
| `deploy-hub-api.sh` | Deploy Hub API | VPS setup done, .env configured |
| `deploy-dashboard.sh` | Build & deploy Dashboard | Hub API deployed |
| `setup-nginx.sh` | Configure Nginx + SSL | Domain DNS configured |

## Connection Details

```bash
# Raspberry Pi
ssh rmachnik@192.168.33.10

# VPS
ssh -p 10358 root@srv26.mikr.us
```

## Deployment Checklist

- [ ] Backup Raspberry Pi (`./scripts/backup-rasp.sh`)
- [ ] Setup VPS (`./scripts/deploy-vps-setup.sh`)
- [ ] Provision managed PostgreSQL (Supabase/Neon)
- [ ] Provision managed MQTT broker (CloudAMQP/HiveMQ)
- [ ] Create `hub-api/.env` with production credentials
- [ ] Deploy Hub API (`./scripts/deploy-hub-api.sh`)
- [ ] Build Dashboard (`./scripts/deploy-dashboard.sh build-only`)
- [ ] Deploy Dashboard (Vercel or `./scripts/deploy-dashboard.sh`)
- [ ] Setup SSL (`./scripts/setup-nginx.sh`)
- [ ] Update CORS_ORIGINS in hub-api/.env
- [ ] Test complete flow

## Rollback

If something goes wrong:

```bash
# Raspberry Pi (only if you modified it - you shouldn't need this for Phase 1)
ssh rmachnik@192.168.33.10
cd ~/sources/goodwe-dynamic-price-optimiser
git checkout <commit-from-backup>
cp ~/backups/pre-cloud-deployment-*/config.yaml.backup ./config/config.yaml

# VPS (just stop services)
ssh -p 10358 root@srv26.mikr.us
cd /home/goodwe/goodwe-cloud-hub
docker-compose -f docker-compose.prod.yml down
```

## Troubleshooting

**API won't start:**
```bash
ssh -p 10358 root@srv26.mikr.us 'docker logs goodwe-hub-api'
```

**Dashboard shows connection error:**
- Check CORS_ORIGINS in hub-api/.env
- Verify API is accessible: `curl http://srv26.mikr.us:40314/health`

**Database connection failed:**
- Check DATABASE_URL in hub-api/.env
- Verify PostgreSQL is accessible from VPS IP

## Security Notes

- Never commit `.env` files to git
- Use strong JWT_SECRET_KEY (generate with `openssl rand -hex 32`)
- Keep MQTT credentials secure
- Enable firewall on VPS (done automatically by setup script)
- Use SSL in production (setup-nginx.sh helps with this)
