#!/usr/bin/env python3
"""Quick script to fix async test issues"""
import re
import sys

def fix_test_file(filepath):
    """Fix a test file to handle async properly"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    
    # 1. Change unittest.TestCase to unittest.IsolatedAsyncioTestCase
    content = re.sub(
        r'class (\w+)\(unittest\.TestCase\):',
        r'class \1(unittest.IsolatedAsyncioTestCase):',
        content
    )
    
    # 2. Make test methods async (but not setUp/tearDown)
    content = re.sub(
        r'(\n    def )(test_\w+)\(self',
        r'\n    async def \2(self',
        content
    )
    
    # 3. Add await to analyze_and_decide calls
    content = re.sub(
        r'(\w+)\s*=\s*self\.decision_engine\.analyze_and_decide\(',
        r'\1 = await self.decision_engine.analyze_and_decide(',
        content
    )
    
    # 4. Add await to forecast_pv_production calls  
    content = re.sub(
        r'(\w+)\s*=\s*self\.pv_forecaster\.forecast_pv_production\(',
        r'\1 = await self.pv_forecaster.forecast_pv_production(',
        content
    )
    
    # 5. Add await to other common async patterns
    content = re.sub(
        r'(\w+)\s*=\s*(\w+)\.forecast_pv_production\(',
        r'\1 = await \2.forecast_pv_production(',
        content
    )
    
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False

if __name__ == '__main__':
    files = [
        'test/test_scoring_algorithm.py',
        'test/test_weather_integration.py'
    ]
    
    for f in files:
        if fix_test_file(f):
            print(f"Fixed: {f}")
        else:
            print(f"No changes: {f}")
