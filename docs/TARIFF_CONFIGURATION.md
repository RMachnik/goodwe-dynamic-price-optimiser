# Tariff Configuration Guide

Complete guide to configuring Polish electricity tariffs in the GoodWe Dynamic Price Optimiser.

## Overview

The system now supports accurate electricity pricing for multiple Polish tariffs by including distribution costs (składnik dystrybucyjny) in addition to market prices and SC component.

### Price Components

```
Final Price = Market Price (CSDAC) + SC Component + Distribution Price
```

1. **Market Price** (Cena rynkowa)
   - Variable every 15 minutes
   - From PSE CSDAC-PLN API
   - Reflects energy commodity cost
   
2. **SC Component** (Składnik cenotwórczy)
   - Fixed at 0.0892 PLN/kWh
   - Same for all tariffs
   - Regulatory component

3. **Distribution Price** (Opłata dystrybucyjna)
   - Variable by tariff type
   - Can be time-based or grid-load-based
   - Significant impact on final price

## Supported Tariffs

### G12w - Two-Zone Tariff (Recommended for Home Users)

**Type**: Time-based  
**Best For**: Households with night charging capability

**Distribution Prices**:
- **Peak** (06:00-22:00): 0.3566 PLN/kWh
- **Off-Peak** (22:00-06:00): 0.0749 PLN/kWh

**Configuration**:
```yaml
electricity_tariff:
  tariff_type: "g12w"
  sc_component_pln_kwh: 0.0892
```

**Example Pricing**:
```
Night (02:00):
  Market: 0.25 PLN/kWh
  SC: 0.0892 PLN/kWh
  Distribution: 0.0749 PLN/kWh (off-peak)
  Final: 0.4141 PLN/kWh ✓ CHEAP

Day (14:00):
  Market: 0.65 PLN/kWh
  SC: 0.0892 PLN/kWh
  Distribution: 0.3566 PLN/kWh (peak)
  Final: 1.0958 PLN/kWh ✗ EXPENSIVE
```

---

### G14dynamic - Dynamic Tariff (Grid-Aware)

**Type**: Kompas-based (grid load status)  
**Best For**: Advanced users wanting to support grid stability

**⚠️ REQUIRES**: PSE Peak Hours (Kompas Energetyczny) API integration

**Distribution Prices by Kompas Status**:
| Status | Color | Distribution Price | When |
|--------|-------|-------------------|------|
| RECOMMENDED USAGE | 🟢 Green | 0.0145 PLN/kWh | Low grid load - charging encouraged |
| NORMAL USAGE | 🟡 Yellow | 0.0578 PLN/kWh | Normal grid load |
| RECOMMENDED SAVING | 🟠 Orange | 0.4339 PLN/kWh | High grid load - reduce usage |
| REQUIRED REDUCTION | 🔴 Red | 2.8931 PLN/kWh | Critical grid load - charging discouraged |

**Configuration**:
```yaml
electricity_tariff:
  tariff_type: "g14dynamic"
  sc_component_pln_kwh: 0.0892

pse_peak_hours:
  enabled: true  # REQUIRED!
  api_url: "https://api.raporty.pse.pl/api/pdgsz"
  update_interval_minutes: 60
```

**Example Pricing**:
```
Green Status (Low Grid Load):
  Market: 0.30 PLN/kWh
  SC: 0.0892 PLN/kWh
  Distribution: 0.0145 PLN/kWh
  Final: 0.4037 PLN/kWh ✓ VERY CHEAP

Red Status (Grid Overload):
  Market: 0.70 PLN/kWh
  SC: 0.0892 PLN/kWh
  Distribution: 2.8931 PLN/kWh
  Final: 3.6823 PLN/kWh ✗ EXTREMELY EXPENSIVE
```

**Benefits**:
- Lowest prices during green status
- Supports grid stability
- Dynamic pricing reflects real-time conditions

**Drawbacks**:
- Requires internet connection for Kompas API
- Prices can be very high during red status
- More complex than fixed tariffs

---

### G11 - Single-Zone Tariff

**Type**: Static  
**Best For**: Simple setups, no time-of-use optimization

**Distribution Price**: 0.3125 PLN/kWh (24/7)

**Configuration**:
```yaml
electricity_tariff:
  tariff_type: "g11"
  sc_component_pln_kwh: 0.0892
```

**Example Pricing**:
```
Any Time:
  Market: 0.50 PLN/kWh
  SC: 0.0892 PLN/kWh
  Distribution: 0.3125 PLN/kWh
  Final: 0.9017 PLN/kWh
```

---

### G12 - Two-Zone Tariff

**Type**: Time-based  
**Similar to G12w** but with different peak hours

**Distribution Prices**:
- **Peak** (07:00-22:00): 0.3566 PLN/kWh
- **Off-Peak** (22:00-07:00): 0.0749 PLN/kWh

**Configuration**:
```yaml
electricity_tariff:
  tariff_type: "g12"
  sc_component_pln_kwh: 0.0892
```

---

### G12as - Two-Zone with Volume Pricing

**Type**: Time-based with shorter peak hours  
**Best For**: Users with solar panels

**Distribution Prices**:
- **Peak** (07:00-13:00): 0.3125 PLN/kWh
- **Off-Peak** (13:00-07:00): 0.0312 PLN/kWh

**Configuration**:
```yaml
electricity_tariff:
  tariff_type: "g12as"
  sc_component_pln_kwh: 0.0892
```

---

## Switching Tariffs

### From G12w to G14dynamic

1. **Enable PSE Peak Hours**:
```yaml
pse_peak_hours:
  enabled: true
```

2. **Change Tariff Type**:
```yaml
electricity_tariff:
  tariff_type: "g14dynamic"
```

3. **Restart System**:
```bash
./scripts/manage_services.sh restart
```

4. **Verify Configuration**:
```bash
python src/master_coordinator.py --status
```

### From G14dynamic to G12w

1. **Change Tariff Type**:
```yaml
electricity_tariff:
  tariff_type: "g12w"
```

2. **(Optional) Disable PSE Peak Hours**:
```yaml
pse_peak_hours:
  enabled: false  # Optional, can leave enabled
```

3. **Restart System**

## Validation

The system validates tariff configuration on startup:

### G14dynamic Validation
```
✓ Tariff type: g14dynamic
✓ PSE Peak Hours: enabled
✓ Distribution pricing: kompas_based
→ System ready
```

### Error Example
```
✗ G14dynamic tariff requires PSE Peak Hours (Kompas) to be enabled!
✗ Please set pse_peak_hours.enabled = true in configuration
→ System will not start
```

## Impact on Charging Decisions

### G12w Example
```
Night Period (23:00):
  Final Price: 0.41 PLN/kWh
  Decision: CHARGE (off-peak + low market price)

Day Period (14:00):
  Final Price: 1.10 PLN/kWh
  Decision: DON'T CHARGE (peak + high market price)
```

### G14dynamic Example
```
Green Status + Low Market:
  Final Price: 0.40 PLN/kWh
  Decision: CHARGE (encouraged by grid)

Red Status + High Market:
  Final Price: 3.68 PLN/kWh
  Decision: DON'T CHARGE (critical grid load)
```

## Price Comparison

### Typical Night Charging (02:00)

| Tariff | Distribution | Final Price | Savings vs G11 |
|--------|-------------|-------------|----------------|
| G12w | 0.0749 | 0.41 PLN/kWh | 54% |
| G14dynamic (green) | 0.0145 | 0.34 PLN/kWh | 62% |
| G11 | 0.3125 | 0.66 PLN/kWh | - |

**Market price: 0.25 PLN/kWh**

### Peak Time Comparison (18:00)

| Tariff | Distribution | Final Price | Cost vs G11 |
|--------|-------------|-------------|-------------|
| G12w | 0.3566 | 1.14 PLN/kWh | +27% |
| G14dynamic (red) | 2.8931 | 3.68 PLN/kWh | +310% |
| G11 | 0.3125 | 0.90 PLN/kWh | - |

**Market price: 0.50 PLN/kWh**

## Best Practices

### For G12w Users
1. ✓ Charge during 22:00-06:00 (off-peak)
2. ✓ Avoid charging during 06:00-22:00 (peak)
3. ✓ Simple and predictable pricing

### For G14dynamic Users
1. ✓ Monitor Kompas status regularly
2. ✓ Charge aggressively during green status
3. ✓ Avoid all grid usage during red status
4. ✓ Support grid stability
5. ✓ Ensure reliable internet connection

### General Tips
1. ✓ Verify tariff configuration after changes
2. ✓ Check system logs for pricing decisions
3. ✓ Monitor actual electricity bills
4. ✓ Compare with https://www.gadek.pl/api for validation

### G13s - Seasonal Three-Zone Tariff (NEW!)

**Type**: Seasonal & day-type-aware time-based  
**Best For**: Users wanting optimal pricing across all seasons

**⚠️ REQUIRES**: Polish holiday detection for free day pricing

**Seasonal Structure**:
- **Summer**: April 1 - September 30
- **Winter**: October 1 - March 31

**Distribution Prices (Working Days)**:

| Time Period | Summer | Winter | Hours |
|------------|--------|---------|-------|
| **Morning Peak** | 0.290 PLN/kWh | 0.340 PLN/kWh | Summer: 7-9h, Winter: 7-10h |
| **Day Off-Peak** | 0.100 PLN/kWh | 0.200 PLN/kWh | Summer: 9-17h, Winter: 10-15h |
| **Evening Peak** | 0.290 PLN/kWh | 0.340 PLN/kWh | Summer: 17-21h, Winter: 15-21h |
| **Night** | 0.110 PLN/kWh | 0.110 PLN/kWh | Both: 21-7h |

**Free Days (Weekends & Holidays)**: All hours use **0.110 PLN/kWh**

**Configuration**:
```yaml
electricity_tariff:
  tariff_type: "g13s"
  sc_component_pln_kwh: 0.0892
```

**Example Pricing**:
```
Summer Working Day Morning Peak (8:00):
  Market: 0.30 PLN/kWh
  SC: 0.0892 PLN/kWh
  Distribution: 0.290 PLN/kWh (morning peak)
  Final: 0.6792 PLN/kWh

Summer Working Day Off-Peak (12:00):
  Market: 0.30 PLN/kWh
  SC: 0.0892 PLN/kWh
  Distribution: 0.100 PLN/kWh (day off-peak)
  Final: 0.4892 PLN/kWh ✓ CHEAP

Winter Working Day Evening Peak (18:00):
  Market: 0.60 PLN/kWh
  SC: 0.0892 PLN/kWh
  Distribution: 0.340 PLN/kWh (evening peak)
  Final: 1.0292 PLN/kWh ✗ EXPENSIVE

Weekend (any hour):
  Market: 0.25 PLN/kWh
  SC: 0.0892 PLN/kWh
  Distribution: 0.110 PLN/kWh (free day)
  Final: 0.4492 PLN/kWh ✓ VERY CHEAP
```

**Benefits**:
- Lowest off-peak prices in summer (0.100 PLN/kWh)
- Predictable night pricing year-round (0.110 PLN/kWh)
- Weekend/holiday flat pricing simplifies planning
- Seasonal awareness optimizes charging strategies

**Best Charging Times**:
- **Summer**: Night (21-7h), Day off-peak (9-17h), weekends
- **Winter**: Night (21-7h), weekends
- **Avoid**: Morning/evening peaks (especially winter)

---

## Adding New Tariffs

To add support for a new tariff:

1. **Add Configuration** (`config/master_coordinator_config.yaml`):
```yaml
distribution_pricing:
  your_tariff:
    type: "time_based"  # or "static", "kompas_based", "seasonal_time_based"
    # ... tariff-specific configuration
```

2. **Extend Tariff Calculator** (if needed):
   - Modify `src/tariff_pricing.py` for complex logic
   - Add new tariff type handler

3. **Add Tests**:
   - Create tests in `test/test_tariff_pricing_*.py`
   - Validate pricing calculations

4. **Update Documentation**:
   - Add to this file
   - Update README.md

## Troubleshooting

### "G14dynamic requires PSE Peak Hours"
**Solution**: Enable PSE Peak Hours in configuration

### G13s showing unexpected prices on holidays
**Explanation**: G13s automatically detects Polish holidays and applies 0.110 PLN/kWh flat pricing. Check system logs to see if the date is recognized as a holiday. All weekends and official Polish holidays use this pricing.

### Prices seem incorrect
**Solution**: 
1. Check tariff_type setting
2. Verify distribution_pricing configuration
3. For G13s, verify the season (summer/winter) and day type (working/free)
4. Compare with https://www.gadek.pl/api
5. Check system logs for detailed pricing breakdown

### System not charging at expected times
**Solution**:
1. Verify final prices in logs
2. Check if distribution price is correct for the time zone
3. For G13s, verify season and day type detection
4. Ensure Kompas data is being received (G14dynamic)

## References

- **PSE CSDAC API**: https://api.raporty.pse.pl/api/csdac-pln
- **PSE Peak Hours API**: https://api.raporty.pse.pl/api/pdgsz
- **Gadek.pl Comparison**: https://www.gadek.pl/api
- **Tariff Rates Source**: Based on Polish distribution network operators (OSD) published rates

## See Also

- [README.md](../README.md) - Main project documentation
- [README_MASTER_COORDINATOR.md](README_MASTER_COORDINATOR.md) - Master coordinator guide
- [GADEK_VALIDATION_SUMMARY.md](GADEK_VALIDATION_SUMMARY.md) - Validation against Gadek API

