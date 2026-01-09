import json
import sys
from datetime import datetime

har_path = "/Users/rafalmachnik/sources/goodwe-dynamic-price-optimiser/192.168.33.10-charging-over-night.har"

try:
    with open(har_path, "r") as f:
        har = json.load(f)

    all_decisions = []
    for entry in har["log"]["entries"]:
        if "/decisions" in entry["request"]["url"]:
            content = entry["response"]["content"].get("text", "")
            if content:
                try:
                    data = json.loads(content)
                    decisions = data.get("decisions", [])
                    if isinstance(decisions, list):
                        all_decisions.extend(decisions)
                except:
                    pass
    
    # Sort by timestamp
    all_decisions.sort(key=lambda x: x.get("timestamp", ""))
    
    # deduplicate
    unique_decisions = []
    seen_ts = set()
    for d in all_decisions:
        ts = d.get("timestamp")
        if ts not in seen_ts:
            seen_ts.add(ts)
            unique_decisions.append(d)
    
    print(f"Extracted {len(unique_decisions)} unique decisions.")
    
    for d in unique_decisions:
        ts_str = d.get("timestamp", "Unknown")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            hour = ts.hour
        except:
            hour = -1
            
        # Focus on night hours (22-06) and afternoon valley (13-15)
        is_t2_window = (hour >= 22 or hour < 6) or (hour >= 13 and hour < 15)
        
        if is_t2_window:
            action = d.get("action", "unknown")
            reason = d.get("reason", "no reason")
            soc = d.get("battery_soc", "??")
            tariff = d.get("tariff_zone", "MISSING")
            print(f"{ts_str} | SOC: {soc}% | ACTION: {action} | TARIFF: {tariff} | REASON: {reason}")

except Exception as e:
    print(f"Error: {e}")
