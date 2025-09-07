# 🌐 Public Access via ngrok

This guide explains how to expose your GoodWe Master Coordinator web UI to the public internet using ngrok, a simple and free tunneling service.

## 🚀 **Quick Start**

### **1. Install ngrok**
```bash
# On macOS with Homebrew
brew install ngrok/ngrok/ngrok

# On Linux/Windows, download from https://ngrok.com/download
```

### **2. Get ngrok Authtoken (Required)**
1. Sign up at [ngrok.com](https://ngrok.com/)
2. Go to [Your Authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
3. Copy your authtoken
4. **IMPORTANT**: Never commit your authtoken to Git!
5. Set it using ngrok's secure method:
   ```bash
   ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
   ```
   Replace `YOUR_AUTHTOKEN_HERE` with your actual authtoken.

### **3. Start Your Web Server**
```bash
# Start the Master Coordinator (includes web server)
./scripts/manage_services.sh start

# Or start just the web server
python src/log_web_server.py --host 0.0.0.0 --port 8080
```

### **4. Create Public Tunnel**
```bash
# Using our automated script (recommended)
./scripts/start_ngrok_tunnel.sh

# Or manually
ngrok http 8080
```

## 📡 **Available Scripts**

### **Automated Tunnel Management**
```bash
# Start tunnel with automatic web server management
./scripts/start_ngrok_tunnel.sh
```

### **Test Tunnel**
```bash
# Test ngrok setup
./scripts/test_ngrok.sh
```

## 🔧 **Configuration**

### **ngrok Configuration File** (`ngrok.yml`)
```yaml
version: "2"
authtoken_from_env: true

tunnels:
  goodwe-web-ui-free:
    proto: http
    addr: 8080
    inspect: true              # Enable web interface for tunnel inspection
    bind_tls: true             # Force HTTPS
    host_header: localhost:8080
```

### **Custom Subdomain (Paid Plan)**
If you have a paid ngrok plan, you can use a custom subdomain:
```yaml
tunnels:
  goodwe-web-ui:
    proto: http
    addr: 8080
    subdomain: goodwe-monitor  # Your custom subdomain
    inspect: true
    bind_tls: true
    host_header: localhost:8080
```

## 🌍 **Accessing Your Web UI**

### **Public URL**
Once ngrok is running, you'll see output like:
```
Session Status                online
Account                       your-email@example.com
Version                       3.27.0
Region                        United States (us)
Latency                       45ms
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123.ngrok.io -> http://localhost:8080
```

### **Web Interface**
- **Public URL**: `https://abc123.ngrok.io` (your unique URL)
- **Local Web Interface**: `http://127.0.0.1:4040` (tunnel management)

## 📱 **Usage Examples**

### **Share Your Dashboard**
```bash
# Start tunnel
./scripts/start_ngrok_tunnel.sh

# Share the public URL (e.g., https://abc123.ngrok.io)
# Anyone can now access your GoodWe monitoring dashboard
```

### **Remote Monitoring**
```bash
# Access from anywhere
curl https://your-ngrok-url.ngrok.io/status
curl https://your-ngrok-url.ngrok.io/logs?lines=50
```

### **Mobile Access**
- Open the ngrok URL on your phone
- Monitor your GoodWe system from anywhere
- Real-time log streaming works on mobile

## 🔒 **Security Considerations**

### **Current Security Level**
- ✅ **HTTPS**: All traffic is encrypted
- ✅ **Temporary**: URLs change when tunnel restarts
- ✅ **Secure Auth**: Authtoken stored securely by ngrok
- ⚠️ **Public**: Anyone with the URL can access
- ⚠️ **No Authentication**: No login required

### **🔐 Authtoken Security**
- **✅ Secure Storage**: ngrok stores authtoken in secure system location
- **✅ No Git Exposure**: Authtoken is never committed to version control
- **✅ Local Only**: Authtoken stays on your machine
- **⚠️ Backup**: Keep your authtoken safe - you'll need it for new installations

### **Recommended Security Measures**

#### **1. Add Basic Authentication**
Modify your web server to require authentication:
```python
# In src/log_web_server.py, add before routes:
from flask_httpauth import HTTPBasicAuth
auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    return username == 'admin' and password == 'your_secure_password'

# Protect routes:
@self.app.route('/')
@auth.login_required
def index():
    # ... existing code
```

#### **2. IP Whitelisting**
Restrict access to specific IP addresses:
```python
# Add to your web server
from flask import request, abort

@app.before_request
def limit_remote_addr():
    allowed_ips = ['192.168.1.0/24', '10.0.0.0/8']
    if not any(request.remote_addr.startswith(ip.split('/')[0]) for ip in allowed_ips):
        abort(403)
```

#### **3. Use Environment Variables for Credentials**
```bash
export GOODWE_WEB_USERNAME=admin
export GOODWE_WEB_PASSWORD=your_secure_password
```

## 🛠️ **Troubleshooting**

### **Common Issues**

#### **"ngrok: command not found"**
```bash
# Install ngrok
brew install ngrok/ngrok/ngrok

# Or download from https://ngrok.com/download
```

#### **"Web server not running"**
```bash
# Check if port 8080 is in use
lsof -i :8080

# Start web server
python src/log_web_server.py --host 0.0.0.0 --port 8080
```

#### **"Tunnel failed to start"**
```bash
# Check ngrok status
ngrok version

# Verify authtoken is set
ngrok config check

# If authentication failed, set authtoken
ngrok config add-authtoken YOUR_AUTHTOKEN_HERE

# Check firewall settings
sudo ufw status
```

#### **"authentication failed: Usage of ngrok requires a verified account and authtoken"**
```bash
# This means you need to set your authtoken
# 1. Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
# 2. Set it securely:
ngrok config add-authtoken YOUR_AUTHTOKEN_HERE

# 3. Test again
ngrok http 8080
```

#### **"Connection refused"**
```bash
# Verify web server is accessible locally
curl http://localhost:8080/health

# Check web server logs
tail -f logs/master_coordinator.log
```

### **Debug Mode**
```bash
# Start ngrok with verbose logging
ngrok http 8080 --log=stdout --log-level=debug
```

## 📊 **Monitoring Your Tunnel**

### **ngrok Web Interface**
Access `http://127.0.0.1:4040` to:
- View tunnel status
- Monitor traffic
- Inspect requests/responses
- View tunnel metrics

### **API Endpoints**
```bash
# Get tunnel information
curl http://127.0.0.1:4040/api/tunnels

# Get tunnel metrics
curl http://127.0.0.1:4040/api/requests/http
```

## 🔄 **Automation**

### **Systemd Service (Optional)**
Create a systemd service to automatically start ngrok:

```bash
# Create service file
sudo tee /etc/systemd/system/ngrok-goodwe.service > /dev/null <<EOF
[Unit]
Description=ngrok tunnel for GoodWe Web UI
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/your/project
ExecStart=/usr/local/bin/ngrok start goodwe-web-ui-free --config ngrok.yml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable ngrok-goodwe.service
sudo systemctl start ngrok-goodwe.service
```

## 📈 **Performance Tips**

### **Optimize for Mobile**
- The web UI is already mobile-responsive
- Real-time log streaming works on mobile browsers
- Consider reducing log line count for mobile: `?lines=50`

### **Bandwidth Considerations**
- ngrok free tier has bandwidth limits
- Consider using log filtering: `?level=ERROR`
- Download logs instead of streaming for large files

## 🆘 **Support**

### **ngrok Resources**
- [ngrok Documentation](https://ngrok.com/docs)
- [ngrok Status Page](https://status.ngrok.com/)
- [ngrok Community](https://community.ngrok.com/)

### **GoodWe Project Resources**
- [Project Documentation](../README.md)
- [Remote Access Guide](REMOTE_LOG_ACCESS.md)
- [Master Coordinator Guide](README_MASTER_COORDINATOR.md)

---

## 🎯 **Quick Reference**

| Command | Description |
|---------|-------------|
| `./scripts/start_ngrok_tunnel.sh` | Start tunnel with auto web server management |
| `./scripts/test_ngrok.sh` | Test ngrok setup |
| `ngrok http 8080` | Manual tunnel creation |
| `curl http://127.0.0.1:4040/api/tunnels` | Get tunnel info |
| `lsof -i :8080` | Check if web server is running |

**Public URL Format**: `https://[random-string].ngrok.io`
**Local Management**: `http://127.0.0.1:4040`
