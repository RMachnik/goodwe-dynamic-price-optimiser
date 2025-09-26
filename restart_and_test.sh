#!/bin/bash

echo "🔄 Restarting GoodWe services..."

# Kill existing processes
pkill -f "python.*log_web_server" 2>/dev/null
pkill -f "python.*master_coordinator" 2>/dev/null

# Wait a moment
sleep 3

# Start master coordinator
echo "🚀 Starting Master Coordinator..."
cd /home/rmachnik/sources/goodwe-dynamic-price-optimiser
source venv/bin/activate
nohup python src/master_coordinator.py --non-interactive > logs/master_coordinator_nohup.log 2>&1 &

# Wait for coordinator to start
sleep 5

# Start web server
echo "🌐 Starting Web Server..."
nohup python src/log_web_server.py > logs/web_server.log 2>&1 &

# Wait for web server to start
sleep 3

echo "✅ Services restarted!"

# Test the API
echo "🧪 Testing API response..."
sleep 2

# Test current state endpoint
echo "Testing /current-state endpoint..."
curl -s http://192.168.33.13:8080/current-state | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    
    # Check required properties
    required = [
        ('photovoltaic', 'current_power_w'),
        ('house_consumption', 'current_power_w'),
        ('grid', 'current_power_w'),
        ('grid', 'flow_direction')
    ]
    
    all_good = True
    for section, prop in required:
        if section in data and prop in data[section]:
            print(f'✅ {section}.{prop}: {data[section][prop]}')
        else:
            print(f'❌ {section}.{prop}: MISSING')
            all_good = False
    
    if all_good:
        print('🎉 API fix successful! JavaScript error should be resolved.')
    else:
        print('⚠️  API still has missing properties.')
        
except Exception as e:
    print(f'❌ Error testing API: {e}')
"

echo "🌐 Web dashboard: http://192.168.33.13:8080"
echo "📊 Check the browser console for JavaScript errors"