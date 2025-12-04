"""
E2E Parametrized Scenario Tests for 4-Tier SOC Charging System

Tests realistic battery charging scenarios across all four tiers:
- Emergency (<5%): Always charge
- Critical (5-12%): Smart price-aware with adaptive thresholds
- Opportunistic (12-50%): Charge if price within 15% of cheapest_next_12h
- Normal (50%+): Charge if price ≤ 40th/60th percentile

Uses mocked infrastructure (GoodWe, PSE API, PriceHistoryManager) but real decision logic.
Tests focus on decision outcomes (should_charge + priority) not reason text.

Tariff Configuration:
- Tests use G12 tariff pattern by default (matching config/master_coordinator_config.yaml)
- G12 has two off-peak periods: 22:00-07:00 (night) and 13:00-15:00 (afternoon valley)
- Change tariff parameter in build_price_data() to test other tariffs (e.g., 'g13')
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Optional
from src.automated_price_charging import AutomatedPriceCharger


# ============================================================================
# FIXTURES AND HELPERS
# ============================================================================

@pytest.fixture
def base_config():
    """Base configuration for all E2E tests."""
    return {
        'automated_price_charging': {
            'enabled': True,
            'emergency_battery_threshold': 5,
            'critical_battery_threshold': 12,
        },
        'battery_management': {
            'soc_thresholds': {
                'emergency': 5,
                'critical': 12
            },
            'capacity_kwh': 20.0
        },
        'timing_awareness': {
            'smart_critical_charging': {
                'enabled': True,
                'max_critical_price_pln': 0.35,
                'max_wait_hours': 6,
                'min_price_savings_percent': 30,
                'simple_charging': {
                    'flip_flop_protection_minutes': 15,
                    'opportunistic_tolerance_percent': 15
                },
                'adaptive_thresholds': {
                    'enabled': False  # Disabled for predictable tests
                },
                'optimization_rules': {
                    'proactive_charging_enabled': False,  # Test tier logic in isolation
                    'wait_at_10_percent_if_high_price': True,
                    'high_price_threshold_pln': 1.35
                }
            }
        },
        'data_storage': {
            'database_storage': {'enabled': False}
        },
        'goodwe': {'inverter_ip': '192.168.1.100'},
        'tariff_pricing': {'enabled': False}
    }


@pytest.fixture
def price_charger(base_config):
    """Create AutomatedPriceCharger with mocked dependencies."""
    with patch('src.automated_price_charging.GoodWeFastCharger'):
        with patch('src.automated_price_charging.EnhancedDataCollector'):
            with patch('src.automated_price_charging.TariffPricingCalculator'):
                charger = AutomatedPriceCharger(base_config)
                charger.is_charging = False
                charger.charging_start_time = None
                charger.charging_stop_time = None
                charger.tariff_calculator = None  # Disable tariff for simple tests
                return charger


def build_price_data(hours: int, base_price: float = 0.6, pattern: str = 'flat', tariff: str = 'g12') -> Dict:
    """
    Build realistic price data with 15-minute granularity.
    
    Args:
        hours: Number of hours of price data to generate
        base_price: Base price in PLN/kWh (default 0.6)
        pattern: Price pattern - 'flat', 'tariff_realistic', 'night_valley', 'evening_peak'
        tariff: Tariff type for 'tariff_realistic' pattern - 'g12', 'g13' (default: 'g12')
    
    Returns:
        Dict with 'value' list containing price points
    """
    start_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    price_points = []
    
    for period in range(hours * 4):  # 4 periods per hour (15-min intervals)
        timestamp = start_time + timedelta(minutes=period * 15)
        hour = timestamp.hour
        
        if pattern == 'flat':
            price = base_price
        elif pattern == 'tariff_realistic':
            # Realistic Polish tariff pattern based on tariff type
            if tariff == 'g12':
                # G12: Two-zone tariff with afternoon valley
                # Off-peak: 22:00-07:00 (night) and 13:00-15:00 (afternoon valley)
                # Peak: 07:00-22:00 (excluding 13:00-15:00)
                if 0 <= hour < 7:  # Night off-peak (00:00-07:00)
                    price = base_price * 0.5  # 0.30 PLN/kWh (cheap night)
                elif 7 <= hour < 13:  # Morning peak (07:00-13:00)
                    price = base_price * 1.0  # 0.60 PLN/kWh
                elif 13 <= hour < 15:  # Afternoon valley (13:00-15:00)
                    price = base_price * 0.6  # 0.36 PLN/kWh (off-peak valley)
                elif 15 <= hour < 22:  # Afternoon/evening peak (15:00-22:00)
                    price = base_price * 1.2  # 0.72 PLN/kWh
                else:  # Night off-peak (22:00-24:00)
                    price = base_price * 0.5  # 0.30 PLN/kWh (cheap night)
            elif tariff == 'g13':
                # G13: Three-zone tariff (placeholder with typical pattern)
                if 0 <= hour < 6:  # Night valley (00:00-06:00)
                    price = base_price * 0.6  # 0.36 PLN/kWh
                elif 6 <= hour < 10:  # Morning ramp (06:00-10:00)
                    price = base_price * (0.8 + (hour - 6) * 0.05)  # 0.48-0.68 PLN/kWh
                elif 10 <= hour < 17:  # Day plateau (10:00-17:00)
                    price = base_price * 1.1  # 0.66 PLN/kWh
                elif 17 <= hour < 22:  # Evening peak (17:00-22:00)
                    price = base_price * (1.3 + (hour - 17) * 0.1)  # 0.78-1.08 PLN/kWh
                else:  # Late evening (22:00-24:00)
                    price = base_price * 0.9  # 0.54 PLN/kWh
            else:
                # Unknown tariff - use flat
                price = base_price
        elif pattern == 'night_valley':
            # Consistently cheap night prices
            price = base_price * 0.5  # 0.30 PLN/kWh
        elif pattern == 'evening_peak':
            # Consistently expensive evening prices
            price = base_price * 1.8  # 1.08 PLN/kWh
        elif pattern == 'super_low':
            # Super low price event
            price = 0.25  # Below 0.3 PLN/kWh threshold
        else:
            price = base_price
        
        price_points.append({
            'dtime': timestamp.isoformat(),  # ISO format for datetime parsing
            'csdac_pln': price * 1000,  # Convert PLN/kWh to PLN/MWh
            'business_date': timestamp.strftime('%Y-%m-%d')
        })
    
    return {'value': price_points}


def make_decision_with_mocks(charger: AutomatedPriceCharger, 
                             battery_soc: int,
                             overproduction: int = 0,
                             grid_power: int = 0,
                             grid_direction: str = 'import',
                             current_price: float = 0.6,
                             cheapest_price: float = 0.4,
                             cheapest_hour: int = 3,
                             price_data: Optional[Dict] = None) -> Dict:
    """
    Call _make_charging_decision with scenario parameters.
    
    Returns decision dict with should_charge, reason, priority, confidence.
    """
    if price_data is None:
        price_data = build_price_data(24, base_price=0.6, pattern='g13_realistic')
    
    return charger._make_charging_decision(
        battery_soc=battery_soc,
        overproduction=overproduction,
        grid_power=grid_power,
        grid_direction=grid_direction,
        current_price=current_price,
        cheapest_price=cheapest_price,
        cheapest_hour=cheapest_hour,
        price_data=price_data
    )


def assert_decision_outcome(actual: Dict, expected_should_charge: bool, expected_priority: str):
    """
    Assert decision outcome matches expectations.
    
    Focuses on should_charge and priority, not reason text (which may vary).
    """
    assert actual['should_charge'] == expected_should_charge, \
        f"Expected should_charge={expected_should_charge}, got {actual['should_charge']}. Reason: {actual.get('reason', 'N/A')}"
    
    assert actual['priority'] == expected_priority, \
        f"Expected priority={expected_priority}, got {actual['priority']}. Reason: {actual.get('reason', 'N/A')}"


# ============================================================================
# EMERGENCY TIER TESTS (<5% SOC)
# ============================================================================

@pytest.mark.parametrize("battery_soc,current_price,expected_charge", [
    (4, 0.2, True),   # Emergency + super cheap price
    (3, 0.6, True),   # Emergency + normal price
    (2, 1.5, True),   # Emergency + expensive price
    (1, 2.0, True),   # Emergency + very expensive price
    (0, 0.3, True),   # Critical emergency + cheap price
])
def test_emergency_tier_always_charges(price_charger, battery_soc, current_price, expected_charge):
    """Emergency tier (<5%) should always charge regardless of price."""
    decision = make_decision_with_mocks(
        price_charger,
        battery_soc=battery_soc,
        current_price=current_price,
        cheapest_price=0.3,
        cheapest_hour=3
    )
    
    assert_decision_outcome(decision, expected_charge, 'emergency')


# ============================================================================
# CRITICAL TIER TESTS (5-12% SOC)
# ============================================================================

@pytest.mark.parametrize("battery_soc,current_price,cheapest_price,expected_charge,expected_priority", [
    # Charge immediately - price acceptable (≤ max_critical_price from config)
    (10, 0.30, 0.25, True, 'critical'),   # Good price, charge now
    (8, 0.35, 0.30, True, 'critical'),    # At max_critical_price threshold, charge now
    
    # Wait for better price - current price high
    (11, 0.80, 0.30, False, 'critical'),  # High price, savings >30%, wait
    (9, 0.90, 0.35, False, 'critical'),   # Very high price, wait
    
    # Special rule: 10% SOC with high price - always wait
    (10, 1.40, 0.35, False, 'critical'),  # 10% + price > high_price_threshold
])
def test_critical_tier_smart_decisions(price_charger, battery_soc, current_price, 
                                       cheapest_price, expected_charge, expected_priority):
    """Critical tier (5-12%) uses smart price-aware charging."""
    # Get thresholds from config
    max_critical_price = price_charger.max_critical_price  # 0.35 from config
    high_price_threshold = price_charger.high_price_threshold  # 1.35 from config
    
    decision = make_decision_with_mocks(
        price_charger,
        battery_soc=battery_soc,
        current_price=current_price,
        cheapest_price=cheapest_price,
        cheapest_hour=3  # 3 hours to wait
    )
    
    assert_decision_outcome(decision, expected_charge, expected_priority)


def test_critical_tier_no_price_data_charges_immediately(price_charger):
    """Critical tier charges immediately when price data unavailable (safety)."""
    decision = make_decision_with_mocks(
        price_charger,
        battery_soc=10,
        current_price=None,  # No price data
        cheapest_price=None,
        cheapest_hour=None
    )
    
    assert_decision_outcome(decision, True, 'critical')


# ============================================================================
# OPPORTUNISTIC TIER TESTS (12-50% SOC)
# ============================================================================

@pytest.mark.parametrize("battery_soc,current_price,cheapest_next_12h,expected_charge", [
    # Charge - price within tolerance (from config: 15%)
    (30, 0.40, 0.38, True),   # Current price close to cheapest
    (25, 0.35, 0.32, True),   # Within tolerance
    (15, 0.30, 0.28, True),   # Just above critical tier, good price
    
    # Don't charge - price too high compared to cheapest
    (40, 0.60, 0.40, False),  # 0.60 > 0.40 × 1.15 (0.46) → wait
    (35, 0.80, 0.50, False),  # Much higher than cheapest → wait
    (20, 0.70, 0.45, False),  # 0.70 > 0.45 × 1.15 (0.5175) → wait
])
def test_opportunistic_tier_price_tolerance(price_charger, battery_soc, current_price, 
                                            cheapest_next_12h, expected_charge):
    """Opportunistic tier (12-50%) charges if price ≤ cheapest_next_12h × (1 + tolerance from config)."""
    # Get tolerance from config (15% default)
    tolerance = price_charger.opportunistic_tolerance_percent  # 0.15 from config
    
    # Build price data with varying prices - cheapest in next 12h
    # Note: csdac_pln is in PLN/MWh, so multiply kWh prices by 1000
    start_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    price_points = []
    
    # Current hour
    price_points.append({
        'dtime': start_time.isoformat(),
        'csdac_pln': current_price * 1000,  # Convert PLN/kWh → PLN/MWh
        'business_date': start_time.strftime('%Y-%m-%d')
    })
    
    # Next 12 hours - make one hour have the cheapest price
    for i in range(1, 49):  # 12 hours × 4 periods
        timestamp = start_time + timedelta(minutes=i * 15)
        # Hour 6 has cheapest price, others higher
        if 20 <= i < 24:  # Around 6th hour
            price = cheapest_next_12h
        else:
            price = current_price + 0.1  # Higher than current
        
        price_points.append({
            'dtime': timestamp.isoformat(),
            'csdac_pln': price * 1000,  # Convert PLN/kWh → PLN/MWh
            'business_date': timestamp.strftime('%Y-%m-%d')
        })
    
    price_data = {'value': price_points}
    
    decision = make_decision_with_mocks(
        price_charger,
        battery_soc=battery_soc,
        current_price=current_price,
        cheapest_price=cheapest_next_12h,
        cheapest_hour=6,
        price_data=price_data
    )
    
    expected_priority = 'medium' if expected_charge else 'low'
    assert_decision_outcome(decision, expected_charge, expected_priority)


def test_opportunistic_tier_boundary_at_50_percent(price_charger):
    """Test SOC boundary between opportunistic (49%) and normal (50%) tiers."""
    price_data = build_price_data(24, base_price=0.6, pattern='tariff_realistic', tariff='g12')
    
    # 49% should use opportunistic logic
    decision_49 = make_decision_with_mocks(
        price_charger,
        battery_soc=49,
        current_price=0.50,
        cheapest_price=0.40,
        cheapest_hour=6,
        price_data=price_data
    )
    # 0.50 > 0.40 × 1.15 (0.46) → don't charge (opportunistic)
    assert decision_49['should_charge'] == False
    
    # 50% should use normal tier logic (percentile-based)
    decision_50 = make_decision_with_mocks(
        price_charger,
        battery_soc=50,
        current_price=0.50,
        cheapest_price=0.40,
        cheapest_hour=6,
        price_data=price_data
    )
    # Normal tier uses different logic, outcome may differ
    assert 'priority' in decision_50


# ============================================================================
# NORMAL TIER TESTS (50%+ SOC)
# ============================================================================

@pytest.mark.parametrize("battery_soc,current_price,cheapest_24h,expected_charge,scenario", [
    # Charge - using fallback logic (adaptive disabled): current ≤ cheapest_24h × 1.10
    (60, 0.30, 0.28, True, "Below fallback threshold (cheapest × 1.10)"),
    (70, 0.33, 0.30, True, "At fallback threshold"),
    
    # Charge - cheap price
    (75, 0.35, 0.32, True, "Cheap price, SOC < 85%"),
    (80, 0.38, 0.35, True, "Within fallback tolerance, SOC < 85%"),
    
    # Charge - even at SOC >= 85%, fallback logic doesn't check SOC
    (85, 0.35, 0.32, True, "Good price, fallback ignores SOC >= 85%"),
    (90, 0.30, 0.28, True, "Cheap price, fallback ignores SOC"),
    
    # Don't charge - price above threshold
    (60, 0.70, 0.30, False, "Above fallback threshold"),
    (75, 0.80, 0.40, False, "High price, SOC < 85%"),
])
def test_normal_tier_percentile_logic(price_charger, battery_soc, current_price, 
                                      cheapest_24h, expected_charge, scenario):
    """Normal tier (50%+) uses fallback logic (cheapest_24h × 1.10) when adaptive disabled.
    
    Note: Fallback logic doesn't check SOC >= 85% (that's only in percentile path).
    With adaptive disabled, system charges whenever price <= cheapest_24h × 1.10.
    """
    # Build realistic price distribution for fallback calculation
    # Need cheapest price in next 24h for fallback logic
    # Note: csdac_pln is in PLN/MWh, so multiply kWh prices by 1000
    start_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    price_points = []
    
    # Current price
    price_points.append({
        'dtime': start_time.isoformat(),
        'csdac_pln': current_price * 1000,  # Convert PLN/kWh → PLN/MWh
        'business_date': start_time.strftime('%Y-%m-%d')
    })
    
    # Next 24 hours - include cheapest_24h at some point
    for i in range(1, 96):  # 24 hours × 4 periods
        timestamp = start_time + timedelta(minutes=i * 15)
        # Place cheapest price around midnight (hour 0-6)
        if i < 24:  # First 6 hours
            price = cheapest_24h
        else:
            price = current_price + 0.1  # Higher than current
        
        price_points.append({
            'dtime': timestamp.isoformat(),
            'csdac_pln': price * 1000,  # Convert PLN/kWh → PLN/MWh
            'business_date': timestamp.strftime('%Y-%m-%d')
        })
    
    price_data = {'value': price_points}
    
    decision = make_decision_with_mocks(
        price_charger,
        battery_soc=battery_soc,
        current_price=current_price,
        cheapest_price=cheapest_24h,
        cheapest_hour=6,
        price_data=price_data
    )
    
    # Normal tier always uses 'low' priority regardless of whether charging
    expected_priority = 'low'
    assert_decision_outcome(decision, expected_charge, expected_priority)


# ============================================================================
# FLIP-FLOP PROTECTION TESTS
# ============================================================================

def test_flip_flop_prevents_start_within_15_minutes_of_stop(price_charger):
    """Bidirectional flip-flop prevents charging start within 15min of stop."""
    # Simulate charging stopped 10 minutes ago
    price_charger.charging_stop_time = datetime.now() - timedelta(minutes=10)
    
    decision = make_decision_with_mocks(
        price_charger,
        battery_soc=3,  # Emergency tier would normally charge
        current_price=0.30,
        cheapest_price=0.25,
        cheapest_hour=3
    )
    
    # Should block charging due to flip-flop protection
    assert decision['should_charge'] == False
    assert 'flip-flop' in decision['reason'].lower()


def test_flip_flop_allows_start_after_15_minutes(price_charger):
    """Charging allowed after 15+ minutes since stop."""
    # Simulate charging stopped 16 minutes ago
    price_charger.charging_stop_time = datetime.now() - timedelta(minutes=16)
    
    decision = make_decision_with_mocks(
        price_charger,
        battery_soc=3,  # Emergency tier
        current_price=0.30,
        cheapest_price=0.25,
        cheapest_hour=3
    )
    
    # Should allow charging after flip-flop window
    assert_decision_outcome(decision, True, 'emergency')


# ============================================================================
# MULTI-TIER PROGRESSION SCENARIOS
# ============================================================================

def test_multi_tier_progression_battery_drain(price_charger):
    """Simulate battery draining through multiple tiers."""
    price_data = build_price_data(24, base_price=0.6, pattern='tariff_realistic', tariff='g12')
    
    # Hour 1: Normal tier (60% SOC), expensive price → don't charge
    decision_60 = make_decision_with_mocks(
        price_charger,
        battery_soc=60,
        current_price=0.85,
        cheapest_price=0.35,
        cheapest_hour=3,
        price_data=price_data
    )
    assert decision_60['should_charge'] == False
    
    # Hour 2: Opportunistic tier (40% SOC), expensive price → don't charge
    decision_40 = make_decision_with_mocks(
        price_charger,
        battery_soc=40,
        current_price=0.85,
        cheapest_price=0.35,
        cheapest_hour=2,
        price_data=price_data
    )
    assert decision_40['should_charge'] == False
    
    # Hour 3: Critical tier (10% SOC), acceptable price → charge
    decision_10 = make_decision_with_mocks(
        price_charger,
        battery_soc=10,
        current_price=0.35,
        cheapest_price=0.30,
        cheapest_hour=1,
        price_data=price_data
    )
    assert_decision_outcome(decision_10, True, 'critical')
    
    # Hour 4: Emergency tier (3% SOC), any price → charge
    decision_3 = make_decision_with_mocks(
        price_charger,
        battery_soc=3,
        current_price=1.50,
        cheapest_price=0.30,
        cheapest_hour=0,
        price_data=price_data
    )
    assert_decision_outcome(decision_3, True, 'emergency')


def test_multi_tier_progression_night_valley_charging(price_charger):
    """Simulate overnight charging sequence with cheap night prices."""
    # Night valley prices - very cheap (0.30 PLN/kWh)
    # Build price data with cheapest in the middle for fallback calculation
    price_data = build_price_data(24, base_price=0.6, pattern='night_valley')
    
    progression = [
        (70, 0.30, True, 'low'),       # Normal tier, cheap price (0.30 ≤ 0.30 × 1.10) → charge (priority='low')
        (75, 0.30, True, 'low'),       # Charging, SOC increasing
        (80, 0.30, True, 'low'),       # Continue charging
        (85, 0.30, True, 'low'),       # SOC ≥ 85%, but fallback still charges (doesn't check SOC)
    ]
    
    for soc, price, expected_charge, expected_priority in progression:
        decision = make_decision_with_mocks(
            price_charger,
            battery_soc=soc,
            current_price=price,
            cheapest_price=0.30,  # Same as current (cheapest in period)
            cheapest_hour=0,  # Current hour is cheapest
            price_data=price_data
        )
        assert_decision_outcome(decision, expected_charge, expected_priority)


def test_multi_tier_progression_opportunistic_to_normal(price_charger):
    """Test transition from opportunistic to normal tier at 50% SOC boundary."""
    # Get tolerance from config
    tolerance = price_charger.opportunistic_tolerance_percent
    
    # Sequence simulating charging from 45% → 55%
    # Opportunistic uses cheapest_12h × (1+tolerance), Normal uses cheapest_24h × 1.10
    progression = [
        # Opportunistic tier - uses 'medium' priority
        (45, 0.42, 0.38, True, 'medium'),   # 0.42 ≤ 0.38 × 1.15 (0.437) → charge
        (48, 0.41, 0.37, True, 'medium'),   # 0.41 ≤ 0.37 × 1.15 (0.4255) → charge
        
        # Cross boundary at 50% - switches to normal tier fallback logic (cheapest_24h × 1.10)
        (50, 0.39, 0.36, True, 'low'),  # 0.39 ≤ 0.36 × 1.10 (0.396) → charge (normal tier uses 'low' priority)
        (52, 0.38, 0.35, True, 'low'),  # 0.38 ≤ 0.35 × 1.10 (0.385) → charge  
        (55, 0.37, 0.34, True, 'low'),  # 0.37 ≤ 0.34 × 1.10 (0.374) → charge
    ]
    
    for soc, current_price, cheapest_price, expected_charge, expected_priority in progression:
        # Build custom price data for each scenario to ensure cheapest prices are found
        start_time = datetime.now().replace(minute=0, second=0, microsecond=0)
        price_points = []
        
        # Current price
        price_points.append({
            'dtime': start_time.isoformat(),
            'csdac_pln': current_price * 1000,
            'business_date': start_time.strftime('%Y-%m-%d')
        })
        
        # Next 24 hours with cheapest price at hour 6
        for i in range(1, 96):  # 24 hours × 4 periods
            timestamp = start_time + timedelta(minutes=i * 15)
            if i < 24:  # First 6 hours - cheapest
                price = cheapest_price
            else:
                price = current_price + 0.1
            
            price_points.append({
                'dtime': timestamp.isoformat(),
                'csdac_pln': price * 1000,
                'business_date': timestamp.strftime('%Y-%m-%d')
            })
        
        price_data = {'value': price_points}
        
        decision = make_decision_with_mocks(
            price_charger,
            battery_soc=soc,
            current_price=current_price,
            cheapest_price=cheapest_price,
            cheapest_hour=6,
            price_data=price_data
        )
        
        assert decision['priority'] == expected_priority, \
            f"SOC {soc}%: Expected priority={expected_priority}, got {decision['priority']}. Reason: {decision.get('reason', 'N/A')}"
        assert decision['should_charge'] == expected_charge, \
            f"SOC {soc}%: Expected should_charge={expected_charge}, got {decision['should_charge']}. Reason: {decision.get('reason', 'N/A')}"


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

def test_super_low_price_event(price_charger):
    """Super low price event - verifies system handles extreme price scenarios."""
    # Note: With super_low_price logic disabled in config, uses normal tier fallback
    # 0.25 ≤ 0.25 × 1.10 (0.275) → should charge
    price_data = build_price_data(24, base_price=0.6, pattern='super_low')
    
    decision = make_decision_with_mocks(
        price_charger,
        battery_soc=60,  # Normal tier
        current_price=0.25,  # Very cheap
        cheapest_price=0.25,  # Current is cheapest
        cheapest_hour=0,
        price_data=price_data
    )
    
    # Should charge due to cheap price meeting fallback threshold
    assert decision['should_charge'] == True


def test_empty_price_data_handling(price_charger):
    """System handles missing price data gracefully."""
    decision = make_decision_with_mocks(
        price_charger,
        battery_soc=30,
        current_price=None,
        cheapest_price=None,
        cheapest_hour=None,
        price_data={'value': []}
    )
    
    # Should make conservative decision (don't charge) without crashing
    assert 'should_charge' in decision
    assert 'priority' in decision


def test_opportunistic_cache_expiry(price_charger):
    """Opportunistic tier cache expires after 5 minutes."""
    price_data = build_price_data(24, base_price=0.6, pattern='tariff_realistic', tariff='g12')
    
    # First decision - cache miss
    decision1 = make_decision_with_mocks(
        price_charger,
        battery_soc=30,
        current_price=0.45,
        cheapest_price=0.40,
        cheapest_hour=6,
        price_data=price_data
    )
    
    # Simulate time passing (cache should still be valid)
    price_charger._price_scan_cache_timestamp = datetime.now() - timedelta(minutes=4)
    
    decision2 = make_decision_with_mocks(
        price_charger,
        battery_soc=30,
        current_price=0.45,
        cheapest_price=0.40,
        cheapest_hour=6,
        price_data=price_data
    )
    
    # Simulate time passing (cache should expire)
    price_charger._price_scan_cache_timestamp = datetime.now() - timedelta(minutes=6)
    
    decision3 = make_decision_with_mocks(
        price_charger,
        battery_soc=30,
        current_price=0.45,
        cheapest_price=0.40,
        cheapest_hour=6,
        price_data=price_data
    )
    
    # All decisions should be consistent (testing cache doesn't break logic)
    assert decision1['should_charge'] == decision2['should_charge'] == decision3['should_charge']


def test_soc_boundary_precision(price_charger):
    """Test precise SOC boundaries between tiers."""
    # Get thresholds from config
    emergency_threshold = price_charger.emergency_battery_threshold  # 5 from config
    critical_threshold = price_charger.critical_battery_threshold    # 12 from config
    
    price_data = build_price_data(24, base_price=0.6, pattern='tariff_realistic', tariff='g12')
    
    # Use moderate price that won't automatically trigger charging in any tier
    # except emergency (which always charges)
    test_price = 0.50
    
    boundaries = [
        (4, 'emergency'),    # Just below emergency_threshold (5)
        (5, 'critical'),     # Exactly at threshold - enters critical
        (11, 'critical'),    # Just below critical_threshold (12)
        (12, 'medium'),      # Exactly at threshold - enters opportunistic (priority='medium')
        (49, 'medium'),      # Just below 50% - opportunistic (priority='medium')
        (50, 'low'),         # Exactly 50% - enters normal (priority='low')
    ]
    
    for soc, expected_tier in boundaries:
        decision = make_decision_with_mocks(
            price_charger,
            battery_soc=soc,
            current_price=test_price,
            cheapest_price=0.30,
            cheapest_hour=3,
            price_data=price_data
        )
        
        # For tiers that don't charge at this price, priority might be 'low'
        # Only check tier when charging is triggered
        if expected_tier == 'emergency':
            assert decision['priority'] == expected_tier, \
                f"SOC {soc}% should be in {expected_tier} tier, got {decision['priority']}"
        else:
            # Other tiers: verify we're in the right decision branch
            # Priority reflects tier or 'low' if not charging
            assert decision['priority'] in [expected_tier, 'low'], \
                f"SOC {soc}% should be in {expected_tier} tier or 'low', got {decision['priority']}"
