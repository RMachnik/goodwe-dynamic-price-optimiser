#!/usr/bin/env python3
"""
Test Performance Baseline and Regression Detection

This script measures test execution time and identifies slowest tests to:
1. Establish performance baselines
2. Detect performance regressions
3. Track trends over time
"""

import subprocess
import re
import json
import sys
from datetime import datetime
from pathlib import Path


def run_tests_with_timing():
    """Run pytest with timing information"""
    print("Running tests with performance metrics...")
    
    result = subprocess.run(
        ['python', '-m', 'pytest', 'test/', '--durations=20', '-q', '--tb=no'],
        capture_output=True,
        text=True,
        timeout=300
    )
    
    return result.stdout, result.returncode


def parse_test_metrics(output):
    """Extract timing and count metrics from pytest output"""
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'total_time': 0.0,
        'test_count': 0,
        'passed': 0,
        'failed': 0,
        'skipped': 0,
        'slowest_tests': []
    }
    
    # Extract total time
    time_match = re.search(r'(\d+) passed.*in ([\d.]+)s', output)
    if time_match:
        metrics['passed'] = int(time_match.group(1))
        metrics['total_time'] = float(time_match.group(2))
        metrics['test_count'] = metrics['passed']
    
    # Extract failed/skipped
    failed_match = re.search(r'(\d+) failed', output)
    if failed_match:
        metrics['failed'] = int(failed_match.group(1))
        metrics['test_count'] += metrics['failed']
    
    skipped_match = re.search(r'(\d+) skipped', output)
    if skipped_match:
        metrics['skipped'] = int(skipped_match.group(1))
        metrics['test_count'] += metrics['skipped']
    
    # Extract slowest tests
    duration_section = re.search(
        r'slowest durations.*?\n(.*?)(?:\n\n|\Z)',
        output,
        re.DOTALL | re.IGNORECASE
    )
    
    if duration_section:
        for line in duration_section.group(1).split('\n'):
            # Match lines like: "0.50s call     test/test_file.py::test_method"
            match = re.match(r'([\d.]+)s\s+\w+\s+(.+)', line.strip())
            if match:
                metrics['slowest_tests'].append({
                    'duration': float(match.group(1)),
                    'test': match.group(2)
                })
    
    return metrics


def save_metrics(metrics, filepath='test_performance.jsonl'):
    """Append metrics to historical log"""
    with open(filepath, 'a') as f:
        f.write(json.dumps(metrics) + '\n')


def load_baseline(filepath='test_performance.jsonl'):
    """Load most recent baseline metrics"""
    if not Path(filepath).exists():
        return None
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
        if lines:
            return json.loads(lines[-1])
    return None


def compare_with_baseline(current, baseline, threshold=1.2):
    """Compare current metrics with baseline and alert on regressions"""
    if not baseline:
        print("ℹ️  No baseline found. Current run will be used as baseline.")
        return True
    
    print("\n📊 Performance Comparison")
    print("=" * 60)
    print(f"Baseline total time: {baseline['total_time']:.2f}s")
    print(f"Current total time:  {current['total_time']:.2f}s")
    
    if current['total_time'] > baseline['total_time'] * threshold:
        slowdown = (current['total_time'] / baseline['total_time'] - 1) * 100
        print(f"\n⚠️  PERFORMANCE REGRESSION DETECTED!")
        print(f"   Tests are {slowdown:.1f}% slower than baseline")
        print(f"   Threshold: {threshold}x ({threshold*100:.0f}%)")
        
        # Identify newly slow tests
        baseline_slow = {t['test']: t['duration'] for t in baseline.get('slowest_tests', [])}
        current_slow = {t['test']: t['duration'] for t in current.get('slowest_tests', [])}
        
        print("\n   Newly slow or slower tests:")
        for test, duration in current_slow.items():
            baseline_duration = baseline_slow.get(test, 0)
            if duration > baseline_duration * 1.5:  # 50% slower
                print(f"     - {test}: {baseline_duration:.2f}s → {duration:.2f}s")
        
        return False
    else:
        improvement = (1 - current['total_time'] / baseline['total_time']) * 100
        if improvement > 5:
            print(f"✅ Tests are {improvement:.1f}% faster than baseline")
        else:
            print(f"✅ Performance within acceptable range")
        return True


def display_summary(metrics):
    """Display current test metrics summary"""
    print("\n" + "=" * 60)
    print("📈 Test Performance Summary")
    print("=" * 60)
    print(f"Total tests:     {metrics['test_count']}")
    print(f"Passed:          {metrics['passed']}")
    print(f"Failed:          {metrics['failed']}")
    print(f"Skipped:         {metrics['skipped']}")
    print(f"Total time:      {metrics['total_time']:.2f}s")
    print(f"Avg time/test:   {metrics['total_time']/max(metrics['test_count'],1)*1000:.1f}ms")
    
    if metrics['slowest_tests']:
        print(f"\n⏱️  Top 10 Slowest Tests:")
        for i, test in enumerate(metrics['slowest_tests'][:10], 1):
            print(f"  {i:2d}. {test['duration']:6.2f}s  {test['test']}")


def main():
    """Main execution"""
    print("🧪 Test Performance Baseline Tool")
    print("=" * 60)
    
    # Run tests and collect metrics
    try:
        output, returncode = run_tests_with_timing()
        
        if returncode != 0:
            print(f"\n⚠️  Tests failed with return code {returncode}")
            if output:
                # Still try to parse what we can
                pass
            else:
                print("No test output available")
                sys.exit(1)
        
        metrics = parse_test_metrics(output)
        
        # Display current metrics
        display_summary(metrics)
        
        # Load baseline and compare
        baseline = load_baseline()
        passed = compare_with_baseline(metrics, baseline)
        
        # Save current metrics as new baseline
        save_metrics(metrics)
        print(f"\n💾 Metrics saved to test_performance.jsonl")
        
        # Exit with error code if regression detected
        if not passed:
            print("\n❌ Performance regression detected!")
            sys.exit(1)
        else:
            print("\n✅ Performance check passed!")
            sys.exit(0)
            
    except subprocess.TimeoutExpired:
        print("\n⏰ Test execution timed out (>5 minutes)")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
