# Remote Log Access Guide

This guide explains how to access your GoodWe Master Coordinator logs remotely via HTTP.

## 🌐 **Web Dashboard**

The Master Coordinator now includes a built-in web server that provides:

- **Real-time log viewing** with live streaming
- **System status monitoring**
- **Log file management** and downloads
- **Filtering by log level** (ERROR, WARNING, INFO, DEBUG)
- **Multiple log file support** (Master Coordinator, Data Collector, Fast Charge)

## 🚀 **Quick Start**

### 1. **Install Dependencies**
```bash
# Install required packages
pip install flask flask-cors psutil

# Or update your virtual environment
source venv/bin/activate
pip install -r requirements.txt
```

### 2. **Start the Master Coordinator**
The web server starts automatically with the Master Coordinator:

```bash
# Using systemd service (recommended)
./scripts/manage_services.sh start

# Or manually
python src/master_coordinator.py
```

### 3. **Access the Dashboard**
Open your web browser and navigate to:
```
http://your-server-ip:8080
```

## 📡 **API Endpoints**

### **Dashboard**
- `GET /` - Main dashboard with web interface

### **System Information**
- `GET /health` - Health check endpoint
- `GET /status` - System status and coordinator information

### **Log Access**
- `GET /logs` - Get recent logs
  - `?lines=N` - Number of lines (default: 100)
  - `?level=INFO` - Filter by log level
  - `?file=master` - Log file (master, data, fast_charge)
  - `?follow=true` - Stream logs (Server-Sent Events)

- `GET /logs/files` - List available log files
- `GET /logs/download/<filename>` - Download log file

## 🔧 **Configuration**

Edit `config/master_coordinator_config.yaml`:

```yaml
# Web Server Configuration
web_server:
  enabled: true                # Enable/disable web server
  host: "0.0.0.0"             # Host to bind to
  port: 8080                  # Port to bind to
  cors_enabled: true          # Enable CORS
```

## 📱 **Usage Examples**

### **View Recent Logs**
```bash
# Get last 50 lines
curl "http://localhost:8080/logs?lines=50"

# Filter by error level
curl "http://localhost:8080/logs?level=ERROR"

# Get data collector logs
curl "http://localhost:8080/logs?file=data"
```

### **Check System Status**
```bash
curl "http://localhost:8080/status"
```

### **Download Log File**
```bash
curl "http://localhost:8080/logs/download/master_coordinator.log" -o master.log
```

### **Stream Live Logs**
```bash
# Using curl with Server-Sent Events
curl -N "http://localhost:8080/logs?follow=true"
```

## 🌍 **Remote Access Setup**

### **1. Firewall Configuration**
```bash
# Allow port 8080 through firewall
sudo ufw allow 8080

# Or for specific IP ranges
sudo ufw allow from 192.168.1.0/24 to any port 8080
```

### **2. Reverse Proxy (Optional)**
For production use, consider setting up a reverse proxy with nginx:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### **3. SSL/HTTPS (Optional)**
For secure access, use a reverse proxy with SSL or configure the Flask app with SSL certificates.

## 🔒 **Security Considerations**

### **Network Security**
- The web server binds to `0.0.0.0` by default (all interfaces)
- Consider restricting to specific IP ranges in production
- Use firewall rules to limit access

### **Authentication (Future Enhancement)**
Currently, the web server has no authentication. For production use, consider:
- Adding basic authentication
- Using API keys
- Implementing OAuth2
- Using a reverse proxy with authentication

### **Systemd Security**
The systemd service includes security restrictions:
- Limited file system access
- Network access restrictions
- Resource limits

## 🐛 **Troubleshooting**

### **Web Server Not Starting**
```bash
# Check if port 8080 is in use
sudo netstat -tlnp | grep 8080

# Check systemd service status
./scripts/manage_services.sh status

# View service logs
./scripts/manage_services.sh logs
```

### **Cannot Access Remotely**
```bash
# Check firewall status
sudo ufw status

# Test local access first
curl http://localhost:8080/health

# Check if service is binding to correct interface
sudo netstat -tlnp | grep 8080
```

### **Log Files Not Found**
```bash
# Check log directory permissions
ls -la logs/

# Verify log files exist
ls -la logs/*.log
```

## 📊 **Dashboard Features**

### **Real-time Monitoring**
- Live log streaming with auto-scroll
- System status indicators
- Process monitoring

### **Log Management**
- Multiple log file support
- Level-based filtering
- Download functionality
- Configurable line count

### **Responsive Design**
- Works on desktop and mobile
- Dark theme for log viewing
- Color-coded log levels

## 🔄 **Integration Examples**

### **Home Assistant Integration**
```yaml
# Add to configuration.yaml
rest:
  - resource: http://your-server:8080/status
    scan_interval: 30
    sensor:
      - name: "GoodWe Coordinator Status"
        value_template: "{{ value_json.status }}"
```

### **Monitoring Scripts**
```bash
#!/bin/bash
# Check coordinator health
STATUS=$(curl -s http://localhost:8080/status | jq -r '.coordinator_running')
if [ "$STATUS" != "true" ]; then
    echo "Coordinator not running!"
    # Send alert
fi
```

### **Log Analysis**
```python
import requests
import json

# Get recent errors
response = requests.get("http://localhost:8080/logs?level=ERROR&lines=100")
errors = response.json()['lines']

# Analyze error patterns
for error in errors:
    print(error)
```

## 🚀 **Advanced Usage**

### **Custom Log Filters**
```bash
# Get logs from specific time period (requires log parsing)
curl "http://localhost:8080/logs?lines=1000" | grep "2024-01-15"
```

### **Automated Monitoring**
```bash
# Create monitoring script
cat > monitor_coordinator.sh << 'EOF'
#!/bin/bash
while true; do
    STATUS=$(curl -s http://localhost:8080/status | jq -r '.coordinator_running')
    if [ "$STATUS" != "true" ]; then
        echo "$(date): Coordinator down!" >> /var/log/coordinator_monitor.log
        # Restart service
        ./scripts/manage_services.sh restart
    fi
    sleep 60
done
EOF

chmod +x monitor_coordinator.sh
```

## 📈 **Performance**

- **Memory Usage**: ~10-20MB for web server
- **CPU Usage**: Minimal impact
- **Network**: Efficient streaming with Server-Sent Events
- **Concurrent Users**: Supports multiple simultaneous connections

## 🔮 **Future Enhancements**

- Authentication and authorization
- Log search and filtering
- Historical log analysis
- Performance metrics dashboard
- Mobile app integration
- WebSocket support for real-time updates