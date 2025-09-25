#!/bin/bash

echo "📝 Committing fixes for real data retrieval and UI JavaScript errors..."

cd /home/rmachnik/sources/goodwe-dynamic-price-optimiser

# Check git status
echo "🔍 Checking git status..."
git status

echo ""
echo "📋 Files modified:"
echo "  - src/fast_charge.py (improved inverter connection reliability)"
echo "  - src/log_web_server.py (fixed import path and API data structure)"
echo "  - test_inverter_connection.py (fixed test script)"
echo "  - diagnose_data_sources.py (diagnostic script)"
echo "  - test_real_data.py (real data testing script)"
echo "  - restart_and_test.sh (service restart script)"

echo ""
echo "🚀 Committing changes..."

# Add modified files
git add src/fast_charge.py
git add src/log_web_server.py  
git add test_inverter_connection.py
git add diagnose_data_sources.py
git add test_real_data.py
git add restart_and_test.sh

# Commit with descriptive message
git commit -m "Fix real data retrieval and UI JavaScript errors

🔧 Real Data Retrieval Fix:
- Fixed import path error in _get_real_inverter_data() method
- Changed 'from src.fast_charge import GoodWeFastCharger' to 'from fast_charge import GoodWeFastCharger'
- Added robust path resolution to ensure src directory is in Python path
- System now successfully retrieves real inverter data instead of falling back to mock data

🖥️ UI JavaScript Error Fix:
- Fixed 'Cannot read properties of undefined (reading current_power_w)' error
- Added current_power_w aliases to API response for frontend compatibility
- Added missing flow_direction property to grid data
- Ensured consistent data structure across all data sources

🔌 Inverter Connection Improvements:
- Enhanced error handling with retry logic for inverter connections
- Added automatic reconnection when connection is lost
- Improved logging with attempt tracking
- Added ensure_connection() method for robust connection management

🧪 Testing and Diagnostics:
- Updated test_inverter_connection.py to use correct goodwe.connect() method
- Added diagnose_data_sources.py for comprehensive data source testing
- Added test_real_data.py for simple real data verification
- Added restart_and_test.sh script for easy service restart and testing

These fixes resolve the core issue where the system was returning mock data
instead of real inverter data, and eliminate JavaScript errors in the web dashboard."

echo ""
echo "✅ Commit completed!"
echo ""
echo "📊 Commit details:"
git log --oneline -1
echo ""
echo "🌿 To push to remote:"
echo "   git push origin main"
echo ""
echo "🔄 To apply fixes:"
echo "   ./restart_and_test.sh"