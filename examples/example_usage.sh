#!/bin/bash
# Example usage script for GoodWe Fast Charging
# This script demonstrates various ways to use the fast_charge.py script

echo "GoodWe Inverter Fast Charging - Example Usage"
echo "=============================================="
echo ""

# Check if Python script exists
if [ ! -f "fast_charge.py" ]; then
    echo "Error: fast_charge.py not found in current directory"
    exit 1
fi

# Check if config file exists
if [ ! -f "fast_charge_config.yaml" ]; then
    echo "Error: fast_charge_config.yaml not found in current directory"
    echo "Please create the configuration file first"
    exit 1
fi

echo "Available commands:"
echo ""

echo "1. Check current inverter status:"
echo "   python fast_charge.py"
echo ""

echo "2. Start fast charging:"
echo "   python fast_charge.py --start"
echo ""

echo "3. Start fast charging with monitoring:"
echo "   python fast_charge.py --start --monitor"
echo ""

echo "4. Stop fast charging:"
echo "   python fast_charge.py --stop"
echo ""

echo "5. Show detailed status:"
echo "   python fast_charge.py --status"
echo ""

echo "6. Monitor existing charging:"
echo "   python fast_charge.py --monitor"
echo ""

echo "7. Use custom configuration:"
echo "   python fast_charge.py --config my_config.yaml --start"
echo ""

echo "8. Get help:"
echo "   python fast_charge.py --help"
echo ""

echo "Example workflow:"
echo "================="
echo "1. Check status: python fast_charge.py"
echo "2. Start charging: python fast_charge.py --start --monitor"
echo "3. Monitor progress (Ctrl+C to stop monitoring)"
echo "4. Check final status: python fast_charge.py --status"
echo ""

echo "Safety notes:"
echo "============="
echo "- Always check your configuration before starting"
echo "- Monitor the first few minutes of charging"
echo "- Keep the script running while monitoring"
echo "- Use Ctrl+C to stop monitoring (charging continues)"
echo "- Use --stop to completely stop charging"
echo ""

echo "For more information, see README_fast_charge.md"

