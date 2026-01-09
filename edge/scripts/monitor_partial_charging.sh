#!/bin/bash
#
# Partial Charging Monitor
# Analyzes partial charging decisions and provides insights
#
# Usage: ./scripts/monitor_partial_charging.sh [date]
# Example: ./scripts/monitor_partial_charging.sh 2025-12-03
#          ./scripts/monitor_partial_charging.sh  (defaults to today)

# Determine date to analyze
if [ -n "$1" ]; then
    TARGET_DATE="$1"
else
    TARGET_DATE=$(date +%Y-%m-%d)
fi

# Log file location
LOG_FILE="/opt/goodwe-dynamic-price-optimiser/logs/master_coordinator.log"
if [ ! -f "$LOG_FILE" ]; then
    # Fallback to local logs for development
    LOG_FILE="logs/master_coordinator.log"
fi

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Error: Log file not found at $LOG_FILE"
    exit 1
fi

echo "============================================="
echo "   Partial Charging Analysis"
echo "   Date: $TARGET_DATE"
echo "============================================="
echo ""

# 1. Blocked partial charges (money saved)
echo "🚫 BLOCKED Partial Charges (Good decisions - saved money):"
echo "-----------------------------------------------------------"
BLOCKED_COUNT=$(grep "$TARGET_DATE" "$LOG_FILE" | grep -c "Partial charging blocked at")

if [ "$BLOCKED_COUNT" -gt 0 ]; then
    grep "$TARGET_DATE" "$LOG_FILE" | grep "Partial charging blocked at" | \
        sed 's/.*Partial charging blocked at //' | \
        awk -F'% SOC: current price ' '{
            soc=$1
            rest=$2
            split(rest, arr, " > max acceptable ")
            current_price=arr[1]
            split(arr[2], arr2, " PLN")
            threshold=arr2[1]
            saved=((current_price - threshold) * 2.5)  # Assume 2.5 kWh partial charge
            printf("  • SOC: %s%% | Price: %s PLN/kWh | Threshold: %s | Approx saved: %.2f PLN\n", 
                   soc, current_price, threshold, saved)
        }'
    
    # Calculate total estimated savings
    TOTAL_SAVED=$(grep "$TARGET_DATE" "$LOG_FILE" | grep "Partial charging blocked at" | \
        awk -F'current price ' '{split($2, a, " > max acceptable "); split(a[1], p1, " "); split(a[2], p2, " "); 
             price_diff=(p1[1]-p2[1]); if(price_diff>0) sum+=price_diff*2.5} END {printf "%.2f", sum}')
    
    echo ""
    echo "  📊 Total blocked: $BLOCKED_COUNT charges"
    echo "  💰 Estimated savings: $TOTAL_SAVED PLN (assumes 2.5 kWh avg)"
else
    echo "  ℹ️  No blocked partial charges today"
fi

echo ""
echo ""

# 2. Approved partial charges
echo "✅ APPROVED Partial Charges:"
echo "-----------------------------------------------------------"
APPROVED_COUNT=$(grep "$TARGET_DATE" "$LOG_FILE" | grep -c "💡 Partial charging analysis")

if [ "$APPROVED_COUNT" -gt 0 ]; then
    grep "$TARGET_DATE" "$LOG_FILE" | grep "💡 Partial charging analysis" | \
        sed 's/.*💡 Partial charging analysis at //' | \
        awk -F'% SOC: Charge ' '{
            soc=$1
            rest=$2
            split(rest, arr, " kWh now at ")
            kwh=arr[1]
            split(arr[2], arr2, " PLN/kWh")
            price=arr2[1]
            split(arr2[2], arr3, "Extra cost: ")
            if (length(arr3) > 1) {
                split(arr3[2], arr4, " PLN")
                extra_cost=arr4[1]
                printf("  • SOC: %s%% | Charge: %s kWh @ %s PLN/kWh | Extra cost: %s PLN\n", 
                       soc, kwh, price, extra_cost)
            }
        }'
    
    # Calculate total extra cost
    TOTAL_EXTRA=$(grep "$TARGET_DATE" "$LOG_FILE" | grep "💡 Partial charging analysis" | \
        awk -F'Extra cost: ' '{if(NF>1){split($2, a, " PLN"); sum+=a[1]}} END {printf "%.2f", sum}')
    
    echo ""
    echo "  📊 Total approved: $APPROVED_COUNT charges"
    echo "  💸 Total extra cost paid: $TOTAL_EXTRA PLN (vs waiting for better price)"
else
    echo "  ℹ️  No approved partial charges today"
fi

echo ""
echo ""

# 3. Completed partial charging sessions
echo "📝 COMPLETED Partial Charging Sessions:"
echo "-----------------------------------------------------------"
SESSION_COUNT=$(grep "$TARGET_DATE" "$LOG_FILE" | grep -c "Partial charging session recorded")

if [ "$SESSION_COUNT" -gt 0 ]; then
    grep "$TARGET_DATE" "$LOG_FILE" | grep "Partial charging session recorded" | \
        sed 's/.*Partial charging session recorded: target SOC //' | \
        awk -F'%, required ' '{
            soc=$1
            rest=$2
            split(rest, arr, " kWh, until ")
            kwh=arr[1]
            time=arr[2]
            printf("  • Target SOC: %s%% | Energy: %s kWh | Until: %s\n", soc, kwh, time)
        }'
    
    echo ""
    echo "  📊 Total sessions: $SESSION_COUNT"
    
    # Alert if too many sessions
    if [ "$SESSION_COUNT" -gt 4 ]; then
        echo "  ⚠️  WARNING: Excessive partial charging sessions (>4)"
    fi
else
    echo "  ℹ️  No completed partial charging sessions today"
fi

echo ""
echo ""

# 4. Summary and recommendations
echo "📈 SUMMARY & RECOMMENDATIONS:"
echo "-----------------------------------------------------------"

# Calculate net impact
NET_IMPACT=$(echo "$TOTAL_SAVED - $TOTAL_EXTRA" | bc 2>/dev/null || echo "0")

if [ "$APPROVED_COUNT" -eq 0 ] && [ "$BLOCKED_COUNT" -eq 0 ]; then
    echo "  ℹ️  No partial charging decisions made today"
    echo "  ✅ System is likely using full charging windows effectively"
elif [ "$BLOCKED_COUNT" -gt "$APPROVED_COUNT" ]; then
    echo "  ✅ Good decision ratio: More blocks than approvals"
    echo "  💰 Net estimated benefit: $NET_IMPACT PLN"
    echo "  📊 Decision quality: Excellent"
else
    echo "  ⚠️  More approvals than blocks - review thresholds"
    echo "  💸 Net cost impact: $NET_IMPACT PLN"
    
    if [ "$APPROVED_COUNT" -gt 3 ]; then
        echo "  💡 Consider: Review SOC-aware thresholds in config"
    fi
fi

# Check for expensive partial charges
EXPENSIVE=$(grep "$TARGET_DATE" "$LOG_FILE" | grep "💡 Partial charging analysis" | \
    grep -E "now at (0\.[8-9]|[1-9]\.[0-9])" | wc -l)

if [ "$EXPENSIVE" -gt 0 ]; then
    echo ""
    echo "  ⚠️  Found $EXPENSIVE partial charge(s) above 0.80 PLN/kWh"
    echo "  💡 Recommendation: Review SOC levels and price thresholds"
fi

echo ""
echo "============================================="
echo "Analysis complete for $TARGET_DATE"
echo "============================================="
