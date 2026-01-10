#!/bin/bash
set -e

# Nginx setup script for SSL and reverse proxy
# Run this on VPS after deploying API and Dashboard

echo "🔒 Setting up Nginx with SSL..."

cat << 'EOF'
This script will:
1. Install Nginx and Certbot
2. Configure API reverse proxy
3. Configure Dashboard static hosting
4. Setup SSL certificates

Prerequisites:
- Domain DNS pointing to this VPS
- Ports 80 and 443 open in firewall

Press Enter to continue or Ctrl+C to cancel...
EOF
read

echo "📦 Installing Nginx and Certbot..."
apt update
apt install -y nginx certbot python3-certbot-nginx

echo "🔧 Configuring API reverse proxy..."
cat > /etc/nginx/sites-available/goodwe-api << 'APICONF'
server {
    listen 80;
    server_name api.yourdomain.com;  # CHANGE THIS

    location / {
        proxy_pass http://localhost:40314;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (for future SSE/WebSocket features)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
APICONF

echo "🔧 Configuring Dashboard..."
cat > /etc/nginx/sites-available/goodwe-dashboard << 'DASHCONF'
server {
    listen 80;
    server_name dashboard.yourdomain.com;  # CHANGE THIS
    
    root /home/goodwe/goodwe-cloud-hub/dashboard;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 10240;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
DASHCONF

echo "📝 Enabling sites..."
ln -sf /etc/nginx/sites-available/goodwe-api /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/goodwe-dashboard /etc/nginx/sites-enabled/

# Remove default site
rm -f /etc/nginx/sites-enabled/default

echo "✅ Testing Nginx configuration..."
nginx -t

echo "🔄 Reloading Nginx..."
systemctl reload nginx

echo ""
echo "✅ Nginx configured!"
echo ""
echo "🔒 Now run Certbot to get SSL certificates:"
echo "   certbot --nginx -d api.yourdomain.com -d dashboard.yourdomain.com"
echo ""
echo "⚠️  Remember to:"
echo "   1. Update domain names in Nginx configs above"
echo "   2. Update CORS_ORIGINS in hub-api/.env"
echo "   3. Rebuild dashboard with correct API URL"
