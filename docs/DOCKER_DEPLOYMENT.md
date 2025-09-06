# 🐳 Docker Deployment Guide

This guide covers deploying the GoodWe Dynamic Price Optimiser using Docker containers.

## 📋 **Prerequisites**

- Docker Engine 20.10+
- Docker Compose 2.0+
- 2GB RAM minimum (4GB recommended)
- 10GB disk space for data persistence

## 🚀 **Quick Start**

### **1. Clone and Build**
```bash
git clone https://github.com/rafalmachnik/goodwe-dynamic-price-optimiser.git
cd goodwe-dynamic-price-optimiser

# Simple setup (recommended for development)
docker compose -f docker-compose.simple.yml up --build

# Or use the management script
./scripts/docker_manage.sh build
```

### **2. Configure Your System**
```bash
# Edit your configuration
nano config/master_coordinator_config.yaml

# Update inverter IP address
# Update any other settings as needed
```

### **3. Start the Service**
```bash
# Start the container (runs in detached mode - survives SSH disconnection)
./scripts/docker_manage.sh start

# Check status
./scripts/docker_manage.sh status
```

> **✅ SSH-Safe**: The Docker setup runs in detached mode and will continue running even after you close your SSH session. The container has `restart: unless-stopped` policy for automatic recovery.

## 📁 **Volume Mounting Strategy**

### **Development Environment**
```yaml
volumes:
  - ./config:/app/config:ro      # Read-only config files
  - ./data:/app/data             # Persistent data storage
  - ./logs:/app/logs             # Application logs
  - ./out:/app/out               # Generated files
```

### **Production Environment**
```yaml
volumes:
  - /opt/goodwe-dynamic-price-optimiser/config:/app/config:ro
  - goodwe_data:/app/data
  - goodwe_logs:/app/logs
  - goodwe_out:/app/out
```

## 🔧 **Configuration Management**

### **Host Configuration Files**
Place your configuration files in the `config/` directory:

```bash
config/
├── master_coordinator_config.yaml    # Main configuration (includes all settings)
└── user_*.yaml                       # User-specific overrides (optional)
```

### **Background Operation & SSH Safety**
The Docker setup is designed to run safely in the background:

- **Detached Mode**: Containers run with `docker-compose up -d` (detached)
- **Restart Policy**: `restart: unless-stopped` ensures automatic recovery
- **SSH-Safe**: Continues running after SSH session disconnection
- **Health Checks**: Built-in monitoring and automatic restart on failure

### **Environment Variables**
```bash
# Set in docker-compose.yml or .env file
PYTHONPATH=/app/src
TZ=Europe/Warsaw
LOG_LEVEL=INFO
CONFIG_PATH=/app/config/master_coordinator_config.yaml
```

## 📊 **Data Persistence**

### **Data Directory Structure**
```
data/
├── energy_data/              # Energy monitoring data
│   ├── 2024-01-15.json      # Daily energy data
│   └── historical/           # Historical data
├── schedules/                # Charging schedules
│   └── charging_schedule_*.json
└── cache/                    # Cached data
    └── price_cache.json
```

### **Log Directory Structure**
```
logs/
├── master_coordinator.log    # Main application logs
├── data_collector.log        # Data collection logs
├── fast_charge.log          # Fast charging logs
└── archived/                 # Archived logs
    └── 2024-01-15/
```

## 🛠️ **Management Commands**

### **Docker Management Script**
```bash
# Build image
./scripts/docker_manage.sh build

# Start container
./scripts/docker_manage.sh start

# Stop container
./scripts/docker_manage.sh stop

# Restart container
./scripts/docker_manage.sh restart

# View logs
./scripts/docker_manage.sh logs

# Check status
./scripts/docker_manage.sh status

# Open shell in container
./scripts/docker_manage.sh shell

# Clean up resources
./scripts/docker_manage.sh clean
```

### **Direct Docker Commands**
```bash
# Build image
docker build -t goodwe-dynamic-price-optimiser .

# Run container
docker run -d \
  --name goodwe-optimiser \
  --network host \
  -v $(pwd)/config:/app/config:ro \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/out:/app/out \
  goodwe-dynamic-price-optimiser

# View logs
docker logs -f goodwe-optimiser

# Execute command in container
docker exec -it goodwe-optimiser /bin/bash
```

## 🔍 **Monitoring & Health Checks**

### **Health Check Endpoint**
```bash
# Check container health
curl http://localhost:8080/health

# Expected response
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "uptime": "2h 15m",
  "version": "1.0.0"
}
```

### **Container Health Status**
```bash
# Check health status
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# View health check logs
docker inspect goodwe-optimiser | jq '.[0].State.Health'
```

## 🔒 **Security Considerations**

### **Container Security**
- **Non-root user**: Container runs as `goodwe` user (UID 1000)
- **Read-only configs**: Configuration files mounted read-only
- **Resource limits**: Memory and CPU limits enforced
- **Network isolation**: Uses host networking for inverter access

### **Data Security**
- **Volume permissions**: Proper ownership and permissions
- **Backup strategy**: Regular backups of persistent data
- **Access control**: Limit access to configuration files

## 📈 **Production Deployment**

### **Production Docker Compose**
```bash
# Deploy production environment
docker-compose -f docker-compose.prod.yml up -d

# Scale if needed
docker-compose -f docker-compose.prod.yml up -d --scale goodwe-optimiser=2
```

### **Production Considerations**
- **Resource limits**: Set appropriate memory and CPU limits
- **Log rotation**: Configure log rotation to prevent disk full
- **Monitoring**: Set up monitoring and alerting
- **Backups**: Implement regular backup strategy
- **Updates**: Plan for rolling updates

## 🐛 **Troubleshooting**

### **Common Issues**

#### **Container Won't Start**
```bash
# Check logs
docker logs goodwe-optimiser

# Check configuration
docker exec -it goodwe-optimiser cat /app/config/master_coordinator_config.yaml
```

#### **Permission Issues**
```bash
# Fix ownership
sudo chown -R 1000:1000 data logs out

# Check permissions
ls -la data/ logs/ out/
```

#### **Network Issues**
```bash
# Test inverter connectivity
docker exec -it goodwe-optimiser ping 192.168.33.15

# Check port access
docker exec -it goodwe-optimiser nc -zv 192.168.33.15 8899
```

### **Debug Mode**
```bash
# Run in debug mode
docker run -it --rm \
  --network host \
  -v $(pwd)/config:/app/config:ro \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  goodwe-dynamic-price-optimiser \
  python src/master_coordinator.py --test --debug
```

## 🔄 **Updates & Maintenance**

### **Updating the Application**
```bash
# Pull latest changes
git pull origin master

# Rebuild image
./scripts/docker_manage.sh build

# Restart with new image
./scripts/docker_manage.sh restart
```

### **Data Backup**
```bash
# Backup data directory
tar -czf backup-$(date +%Y%m%d).tar.gz data/ logs/ out/

# Restore from backup
tar -xzf backup-20240115.tar.gz
```

### **Log Management**
```bash
# View log sizes
du -sh logs/*

# Clean old logs
find logs/ -name "*.log" -mtime +30 -delete

# Archive logs
tar -czf logs-$(date +%Y%m%d).tar.gz logs/
```

## 📚 **Additional Resources**

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Docker Volume Management](https://docs.docker.com/storage/volumes/)
- [Docker Health Checks](https://docs.docker.com/engine/reference/builder/#healthcheck)
