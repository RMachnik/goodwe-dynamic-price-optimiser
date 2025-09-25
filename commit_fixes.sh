#!/bin/bash

echo "📝 Committing fixes for inverter data and UI JavaScript errors..."

cd /home/rmachnik/sources/goodwe-dynamic-price-optimiser

# Check git status
echo "🔍 Checking git status..."
git status

echo ""
echo "📋 Files modified:"
echo "  - src/fast_charge.py (improved inverter connection reliability)"
echo "  - src/log_web_server.py (fixed API data structure for frontend)"
echo "  - test_inverter_connection.py (fixed test script)"
echo "  - restart_and_test.sh (service restart script)"

echo ""
echo "🚀 Committing changes..."

# Add modified files
git add src/fast_charge.py
git add src/log_web_server.py  
git add test_inverter_connection.py
git add restart_and_test.sh

# Commit with descriptive message
git commit -m "Fix inverter data retrieval and UI JavaScript errors

🔧 Inverter Connection Improvements:
- Enhanced error handling with retry logic for inverter connections
- Added automatic reconnection when connection is lost
- Improved logging with attempt tracking
- Added ensure_connection() method for robust connection management

🖥️ UI JavaScript Error Fix:
- Fixed 'Cannot read properties of undefined (reading current_power_w)' error
- Added current_power_w aliases to API response for frontend compatibility
- Added missing flow_direction property to grid data
- Ensured consistent data structure across all data sources

🧪 Test Script Fixes:
- Updated test_inverter_connection.py to use correct goodwe.connect() method
- Fixed deprecated Inverter() constructor usage

🔄 Service Management:
- Added restart_and_test.sh script for easy service restart and testing

These fixes resolve intermittent inverter communication issues and eliminate
JavaScript errors in the web dashboard, making the system more reliable."

echo ""
echo "✅ Commit completed!"
echo ""
echo "📊 Commit details:"
git log --oneline -1
echo ""
echo "🌿 To push to remote:"
echo "   git push origin main"