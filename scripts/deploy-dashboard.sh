#!/bin/bash
set -e

# Dashboard Build and Deploy Script
# Usage: ./deploy-dashboard.sh [build-only|deploy]

MODE="${1:-deploy}"

echo "📱 Building Dashboard..."

cd hub-dashboard

# Check if production env exists
if [ ! -f .env.production ]; then
    echo "⚠️  Warning: .env.production not found, creating from example..."
    cat > .env.production << EOF
VITE_API_BASE_URL=http://srv26.mikr.us:40316
EOF
    echo "  ✓ Created .env.production"
    echo "  ⚠️  Remember to update VITE_API_BASE_URL with your actual domain!"
fi

echo "  ✓ Installing dependencies..."
npm install

echo "  ✓ Building production bundle..."
npm run build

echo "✅ Build complete! Bundle size:"
du -sh dist/

if [ "$MODE" = "build-only" ]; then
    echo ""
    echo "✅ Build-only mode complete!"
    echo "   Built files are in: hub-dashboard/dist/"
    echo ""
    echo "🎯 Deploy options:"
    echo "   1. Vercel: vercel --prod"
    echo "   2. Netlify: netlify deploy --prod"
    echo "   3. VPS: ./deploy-dashboard.sh deploy"
    exit 0
fi

echo ""
echo "📤 Deploying to VPS..."

# Upload to VPS
echo "  ✓ Uploading files..."
scp -P 10358 -r dist/* root@srv26.mikr.us:/home/goodwe/goodwe-cloud-hub/dashboard/

ssh -p 10358 root@srv26.mikr.us << 'ENDSSH'
set -e

echo "  ✓ Setting up Nginx configuration..."

# Create Nginx config for dashboard
cat > /etc/nginx/sites-available/goodwe-dashboard << 'EOF'
server {
    listen 40315;
    server_name _;  # Change this to your domain
    
    root /home/goodwe/goodwe-cloud-hub/dashboard;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 10240;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
EOF

# Enable site if not already enabled
if [ ! -f /etc/nginx/sites-enabled/goodwe-dashboard ]; then
    ln -s /etc/nginx/sites-available/goodwe-dashboard /etc/nginx/sites-enabled/
fi

# Test Nginx config
nginx -t

# Reload Nginx
systemctl reload nginx

echo "✅ Dashboard deployed!"
echo ""
echo "Access at: http://srv26.mikr.us"

ENDSSH

cd ..

echo ""
echo "✅ Dashboard deployment complete!"
echo ""
echo "🌐 Access dashboard:"
echo "   http://srv26.mikr.us"
echo ""
echo "🔒 Next step: Setup SSL"
echo "   ssh -p 10358 root@srv26.mikr.us"
echo "   certbot --nginx -d yourdomain.com"
