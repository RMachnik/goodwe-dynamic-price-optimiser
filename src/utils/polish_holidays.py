#!/usr/bin/env python3
"""
Polish Holiday Detection Module

Detects Polish public holidays (fixed and movable) for G13s tariff implementation.
On holidays and weekends, G13s tariff applies a flat 0.110 PLN/kWh distribution rate.
"""

from datetime import datetime, date
from typing import Union
import logging

logger = logging.getLogger(__name__)


class PolishHolidayDetector:
    """Detector for Polish public holidays and free days."""
    
    # Fixed holidays in Poland (month, day)
    FIXED_HOLIDAYS = [
        (1, 1),    # New Year's Day (Nowy Rok)
        (1, 6),    # Epiphany (Trzech Króli)
        (5, 1),    # Labour Day (Święto Pracy)
        (5, 3),    # Constitution Day (Święto Konstytucji 3 Maja)
        (8, 15),   # Assumption of Mary (Wniebowzięcie Najświętszej Maryi Panny)
        (11, 1),   # All Saints' Day (Wszystkich Świętych)
        (11, 11),  # Independence Day (Narodowe Święto Niepodległości)
        (12, 25),  # Christmas Day (Boże Narodzenie)
        (12, 26),  # Second Day of Christmas (Drugi Dzień Bożego Narodzenia)
    ]
    
    def __init__(self):
        """Initialize the Polish holiday detector."""
        self._easter_cache = {}
    
    def _calculate_easter(self, year: int) -> date:
        """
        Calculate Easter Sunday date using Meeus/Jones/Butcher algorithm.
        
        Args:
            year: Year to calculate Easter for
            
        Returns:
            date: Easter Sunday date
        """
        if year in self._easter_cache:
            return self._easter_cache[year]
        
        # Meeus/Jones/Butcher algorithm for Gregorian calendar
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        
        easter = date(year, month, day)
        self._easter_cache[year] = easter
        return easter
    
    def _get_movable_holidays(self, year: int) -> list[date]:
        """
        Get movable holidays for a given year.
        
        Args:
            year: Year to get holidays for
            
        Returns:
            list[date]: List of movable holiday dates
        """
        easter = self._calculate_easter(year)
        
        # Calculate movable holidays relative to Easter
        from datetime import timedelta
        
        holidays = [
            easter,  # Easter Sunday (Wielkanoc)
            easter + timedelta(days=1),  # Easter Monday (Poniedziałek Wielkanocny)
            easter + timedelta(days=49),  # Pentecost (Zielone Świątki) - 7 weeks after Easter
            easter + timedelta(days=60),  # Corpus Christi (Boże Ciało) - 60 days after Easter
        ]
        
        return holidays
    
    def is_polish_holiday(self, check_date: Union[datetime, date]) -> bool:
        """
        Check if a given date is a Polish public holiday.
        
        Args:
            check_date: Date to check (datetime or date object)
            
        Returns:
            bool: True if the date is a Polish public holiday
        """
        # Convert datetime to date if needed
        if isinstance(check_date, datetime):
            check_date = check_date.date()
        
        # Check fixed holidays
        for month, day in self.FIXED_HOLIDAYS:
            if check_date.month == month and check_date.day == day:
                return True
        
        # Check movable holidays
        movable_holidays = self._get_movable_holidays(check_date.year)
        if check_date in movable_holidays:
            return True
        
        return False
    
    def is_weekend(self, check_date: Union[datetime, date]) -> bool:
        """
        Check if a given date is a weekend (Saturday or Sunday).
        
        Args:
            check_date: Date to check (datetime or date object)
            
        Returns:
            bool: True if the date is a weekend
        """
        # Convert datetime to date if needed
        if isinstance(check_date, datetime):
            check_date = check_date.date()
        
        # weekday(): Monday=0, Sunday=6
        return check_date.weekday() in [5, 6]  # Saturday or Sunday
    
    def is_free_day(self, check_date: Union[datetime, date]) -> bool:
        """
        Check if a given date is a free day (weekend or holiday).
        
        For G13s tariff, free days use a flat distribution rate of 0.110 PLN/kWh
        for all hours.
        
        Args:
            check_date: Date to check (datetime or date object)
            
        Returns:
            bool: True if the date is a free day (weekend or holiday)
        """
        return self.is_weekend(check_date) or self.is_polish_holiday(check_date)
    
    def get_holiday_name(self, check_date: Union[datetime, date]) -> str:
        """
        Get the name of the holiday if the date is a Polish public holiday.
        
        Args:
            check_date: Date to check (datetime or date object)
            
        Returns:
            str: Name of the holiday or empty string if not a holiday
        """
        # Convert datetime to date if needed
        if isinstance(check_date, datetime):
            check_date = check_date.date()
        
        # Fixed holidays with names
        fixed_holiday_names = {
            (1, 1): "Nowy Rok (New Year's Day)",
            (1, 6): "Trzech Króli (Epiphany)",
            (5, 1): "Święto Pracy (Labour Day)",
            (5, 3): "Święto Konstytucji 3 Maja (Constitution Day)",
            (8, 15): "Wniebowzięcie Najświętszej Maryi Panny (Assumption of Mary)",
            (11, 1): "Wszystkich Świętych (All Saints' Day)",
            (11, 11): "Narodowe Święto Niepodległości (Independence Day)",
            (12, 25): "Boże Narodzenie (Christmas Day)",
            (12, 26): "Drugi Dzień Bożego Narodzenia (Second Day of Christmas)",
        }
        
        # Check fixed holidays
        for (month, day), name in fixed_holiday_names.items():
            if check_date.month == month and check_date.day == day:
                return name
        
        # Check movable holidays
        easter = self._calculate_easter(check_date.year)
        from datetime import timedelta
        
        if check_date == easter:
            return "Wielkanoc (Easter Sunday)"
        elif check_date == easter + timedelta(days=1):
            return "Poniedziałek Wielkanocny (Easter Monday)"
        elif check_date == easter + timedelta(days=49):
            return "Zielone Świątki (Pentecost)"
        elif check_date == easter + timedelta(days=60):
            return "Boże Ciało (Corpus Christi)"
        
        return ""


# Global instance for easy access
_detector = PolishHolidayDetector()


def is_polish_holiday(check_date: Union[datetime, date]) -> bool:
    """
    Check if a given date is a Polish public holiday.
    
    Args:
        check_date: Date to check
        
    Returns:
        bool: True if the date is a Polish public holiday
    """
    return _detector.is_polish_holiday(check_date)


def is_weekend(check_date: Union[datetime, date]) -> bool:
    """
    Check if a given date is a weekend.
    
    Args:
        check_date: Date to check
        
    Returns:
        bool: True if the date is a weekend
    """
    return _detector.is_weekend(check_date)


def is_free_day(check_date: Union[datetime, date]) -> bool:
    """
    Check if a given date is a free day (weekend or holiday).
    
    Args:
        check_date: Date to check
        
    Returns:
        bool: True if the date is a free day
    """
    return _detector.is_free_day(check_date)


def get_holiday_name(check_date: Union[datetime, date]) -> str:
    """
    Get the name of the holiday if applicable.
    
    Args:
        check_date: Date to check
        
    Returns:
        str: Name of the holiday or empty string
    """
    return _detector.get_holiday_name(check_date)

