#!/usr/bin/env python3
"""
Simple HTTP Log Server for GoodWe Master Coordinator
Provides remote access to logs via HTTP endpoints

Endpoints:
- GET /logs - Get recent logs (default: last 100 lines)
- GET /logs?lines=N - Get last N lines
- GET /logs?level=INFO - Filter by log level
- GET /logs?follow=true - Stream logs (Server-Sent Events)
- GET /status - Get system status
- GET /health - Health check endpoint
"""

import asyncio
import json
import logging
import os
import time
import threading
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Any, Optional
import threading
from queue import Queue, Empty

from flask import Flask, Response, jsonify, request, render_template_string
from flask_cors import CORS

# Logging configuration handled by main application
logger = logging.getLogger(__name__)

# Storage layer
try:
    from database.storage_factory import StorageFactory
except ImportError:
    StorageFactory = None
    logger.warning("StorageFactory not available - falling back to file-only mode")

# Storage layer
try:
    from database.storage_factory import StorageFactory
except ImportError:
    StorageFactory = None
    logger.warning("StorageFactory not available - falling back to file-only mode")

def format_uptime_human_readable(seconds: float) -> str:
    """Convert seconds to human-readable uptime format"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:  # Less than 1 hour
        minutes = int(seconds // 60)
        remaining_seconds = int(seconds % 60)
        if remaining_seconds == 0:
            return f"{minutes}m"
        else:
            return f"{minutes}m {remaining_seconds}s"
    elif seconds < 86400:  # Less than 1 day
        hours = int(seconds // 3600)
        remaining_minutes = int((seconds % 3600) // 60)
        if remaining_minutes == 0:
            return f"{hours}h"
        else:
            return f"{hours}h {remaining_minutes}m"
    else:  # 1 day or more
        days = int(seconds // 86400)
        remaining_hours = int((seconds % 86400) // 3600)
        if remaining_hours == 0:
            return f"{days}d"
        else:
            return f"{days}d {remaining_hours}h"

class LogWebServer:
    """Simple HTTP server for log access and system monitoring"""
    
    def __init__(self, host='0.0.0.0', port=8080, log_dir=None, config=None):
        """Initialize the log web server"""
        self.host = host
        self.port = port
        self.config = config or {}
        self.app = Flask(__name__)
        CORS(self.app)  # Enable CORS for all routes
        
        # Performance optimization: Add caching
        self._cache = {}
        self._cache_lock = threading.Lock()
        self._last_real_data_time = 0
        self._last_historical_data_time = 0
        self._cache_ttl = 30  # Cache for 30 seconds
        
        # Log deduplication to prevent repeated messages
        self._last_log_messages = {}
        self._log_deduplication_window = 60  # seconds
        
        # Request throttling to prevent excessive API calls
        self._last_request_times = {}
        self._min_request_interval = 5  # seconds between requests to same endpoint
        
        # Set up log directory
        if log_dir is None:
            project_root = Path(__file__).parent.parent
            self.log_dir = project_root / "logs"
        else:
            self.log_dir = Path(log_dir)
        
        self.log_dir.mkdir(exist_ok=True)
        
        # Log file paths
        self.master_log = self.log_dir / "master_coordinator.log"
        self.data_log = self.log_dir / "enhanced_data_collector.log"
        self.fast_charge_log = self.log_dir / "fast_charge.log"
        
        # Initialize daily snapshot manager for efficient monthly reporting
        from daily_snapshot_manager import DailySnapshotManager
        project_root = Path(__file__).parent.parent
        self.snapshot_manager = DailySnapshotManager(project_root, config=self.config)
        
        # Initialize storage layer for database access
        self.storage = None
        self._storage_connected = False
        if StorageFactory:
            try:
                self.storage = StorageFactory.create_storage(self.config.get('data_storage', {}))
                logger.info("Storage layer initialized for LogWebServer")
                # Connect storage in a background thread to avoid blocking
                self._connect_storage_async()
            except Exception as e:
                logger.warning(f"Failed to initialize storage layer: {e}. Using file-only fallback.")
        
        # Cache AutomatedPriceCharger instance to avoid expensive re-initialization
        self._price_charger = None
        self._price_charger_lock = threading.Lock()
        
        # Setup routes
        self._setup_routes()
        
        # Log streaming
        self.log_queue = Queue()
        self.clients = set()
    
    def _connect_storage_async(self):
        """Connect storage layer in a background thread."""
        import threading
        
        def connect_in_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(self.storage.connect())
                    self._storage_connected = result
                    if result:
                        logger.info("Storage layer connected successfully")
                    else:
                        logger.warning("Storage layer connection returned False")
                finally:
                    loop.close()
            except Exception as e:
                logger.warning(f"Failed to connect storage layer: {e}")
                self._storage_connected = False
        
        thread = threading.Thread(target=connect_in_thread, daemon=True)
        thread.start()
    
    def _get_cached_data(self, key: str, ttl: int = None) -> Optional[Any]:
        """Get data from cache if not expired"""
        if ttl is None:
            ttl = self._cache_ttl
            
        with self._cache_lock:
            if key in self._cache:
                data, timestamp = self._cache[key]
                if time.time() - timestamp < ttl:
                    return data
                else:
                    del self._cache[key]
            return None
    
    def _set_cached_data(self, key: str, data: Any):
        """Store data in cache with timestamp"""
        with self._cache_lock:
            self._cache[key] = (data, time.time())
    
    def _clear_cache(self):
        """Clear all cached data"""
        with self._cache_lock:
            self._cache.clear()
    
    def _should_log_message(self, message: str, level: str = 'INFO') -> bool:
        """Check if message should be logged (deduplication)"""
        current_time = time.time()
        message_key = f"{level}:{message}"
        
        with self._cache_lock:
            if message_key in self._last_log_messages:
                last_time = self._last_log_messages[message_key]
                if current_time - last_time < self._log_deduplication_window:
                    return False  # Don't log duplicate message
            
            # Update last log time
            self._last_log_messages[message_key] = current_time
            
            # Clean up old entries
            for key in list(self._last_log_messages.keys()):
                if current_time - self._last_log_messages[key] > self._log_deduplication_window * 2:
                    del self._last_log_messages[key]
        
        return True
    
    def _should_throttle_request(self, endpoint: str) -> bool:
        """Check if request should be throttled"""
        current_time = time.time()
        
        with self._cache_lock:
            if endpoint in self._last_request_times:
                last_time = self._last_request_times[endpoint]
                if current_time - last_time < self._min_request_interval:
                    return True  # Throttle request
            
            # Update last request time
            self._last_request_times[endpoint] = current_time
        
        return False
    
    def _run_async_storage(self, coro):
        """Run an async storage operation from sync code.
        
        Creates a new event loop, runs the coroutine, and cleans up.
        Returns None if the operation fails or storage is not connected.
        """
        if not self.storage or not self._storage_connected:
            return None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        except Exception as e:
            logger.warning(f"Async storage operation failed: {e}")
            return None
        
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            """Main dashboard page"""
            return render_template_string(self._get_dashboard_template())
        
        @self.app.route('/health')
        def health():
            """Health check endpoint"""
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'service': 'goodwe-log-server'
            })
        
        @self.app.route('/status')
        def status():
            """Get system status"""
            try:
                # Throttle requests to prevent excessive calls
                if self._should_throttle_request('status'):
                    cached_data = self._get_cached_data('system_status', ttl=30)
                    if cached_data:
                        return jsonify(cached_data)
                
                status_data = self._get_system_status()
                self._set_cached_data('system_status', status_data)
                return jsonify(status_data)
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }), 500
        
        @self.app.route('/logs')
        def get_logs():
            """Get logs with optional filtering"""
            try:
                # Get parameters
                lines = int(request.args.get('lines', 100))
                level = request.args.get('level', '').upper()
                log_file = request.args.get('file', 'master')
                follow = request.args.get('follow', 'false').lower() == 'true'
                
                # Select log file
                log_path = self._get_log_file(log_file)
                
                # Handle systemd journal
                if log_file.lower() in ['systemd', 'journal']:
                    if follow:
                        return self._stream_systemd_logs(level)
                    else:
                        return self._get_systemd_logs(lines, level)
                
                # Handle coordinator summary
                if log_file.lower() == 'summary':
                    if follow:
                        return jsonify({'error': 'Live streaming not supported for summary'}), 400
                    else:
                        return self._get_coordinator_summary(lines, level)
                
                # Handle regular log files
                if not log_path or not log_path.exists():
                    return jsonify({'error': f'Log file {log_file} not found'}), 404
                
                if follow:
                    return self._stream_logs(log_path, level)
                else:
                    return self._get_log_lines(log_path, lines, level)
                    
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/logs/files')
        def list_log_files():
            """List available log files"""
            try:
                log_files = []
                for log_file in self.log_dir.glob("*.log"):
                    stat = log_file.stat()
                    log_files.append({
                        'name': log_file.name,
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'path': str(log_file.relative_to(self.log_dir))
                    })
                
                return jsonify({'log_files': log_files})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/logs/download/<log_file>')
        def download_log(log_file):
            """Download log file"""
            try:
                log_path = self.log_dir / log_file
                if not log_path.exists():
                    return jsonify({'error': 'Log file not found'}), 404
                
                def generate():
                    with open(log_path, 'r') as f:
                        for line in f:
                            yield line
                
                return Response(
                    generate(),
                    mimetype='text/plain',
                    headers={
                        'Content-Disposition': f'attachment; filename={log_file}'
                    }
                )
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/decisions')
        def get_decisions():
            """Get charging decision history"""
            try:
                # Get query parameters
                time_range = request.args.get('time_range', '24h')  # '24h' or '7d'
                decisions = self._get_decision_history(time_range=time_range)
                return jsonify(decisions)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/metrics')
        def get_metrics():
            """Get system performance metrics"""
            try:
                # Throttle requests to prevent excessive calls
                if self._should_throttle_request('metrics'):
                    cached_data = self._get_cached_data('system_metrics', ttl=30)
                    if cached_data:
                        return jsonify(cached_data)
                
                metrics = self._get_system_metrics()
                self._set_cached_data('system_metrics', metrics)
                return jsonify(metrics)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/current-state')
        def get_current_state():
            """Get current system state and decision factors"""
            try:
                # Throttle requests to prevent excessive inverter calls
                if self._should_throttle_request('current-state'):
                    # Return cached data if available
                    cached_data = self._get_cached_data('current_system_state', ttl=30)
                    if cached_data:
                        return jsonify(cached_data)
                
                state_data = self._get_current_system_state()
                self._set_cached_data('current_system_state', state_data)
                return jsonify(state_data)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/historical-data')
        def get_historical_data():
            """Get historical time series data for SOC and PV production"""
            try:
                historical_data = self._get_historical_time_series_data()
                return jsonify(historical_data)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/monthly-summary')
        def get_monthly_summary():
            """Get monthly summary statistics"""
            try:
                # Get year and month from query params (default to current month)
                year = request.args.get('year', type=int)
                month = request.args.get('month', type=int)
                
                if year is None or month is None:
                    now = datetime.now()
                    year = year or now.year
                    month = month or now.month
                
                # Check cache first (60s TTL for monthly data)
                cache_key = f'monthly_summary_{year}_{month}'
                cached_data = self._get_cached_data(cache_key, ttl=60)
                if cached_data:
                    return jsonify(cached_data)
                
                # Get monthly summary
                summary = self._get_monthly_summary(year, month)
                self._set_cached_data(cache_key, summary)
                return jsonify(summary)
            except Exception as e:
                logger.error(f"Error getting monthly summary: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/monthly-comparison')
        def get_monthly_comparison():
            """Get current month vs previous month comparison"""
            try:
                # Get comparison month from query params
                comp_year = request.args.get('year', type=int)
                comp_month = request.args.get('month', type=int)
                
                now = datetime.now()
                current_year = now.year
                current_month = now.month
                
                # Calculate previous month if not specified
                if comp_year is None or comp_month is None:
                    if current_month == 1:
                        comp_year = current_year - 1
                        comp_month = 12
                    else:
                        comp_year = current_year
                        comp_month = current_month - 1
                
                # Check cache first (60s TTL)
                cache_key = f'monthly_comparison_{comp_year}_{comp_month}'
                cached_data = self._get_cached_data(cache_key, ttl=60)
                if cached_data:
                    return jsonify(cached_data)
                
                comparison = self._get_monthly_comparison(comp_year, comp_month)
                self._set_cached_data(cache_key, comparison)
                return jsonify(comparison)
            except Exception as e:
                logger.error(f"Error getting monthly comparison: {e}")
                return jsonify({'error': str(e)}), 500
    
    def _get_log_file(self, log_name: str) -> Optional[Path]:
        """Get log file path by name"""
        log_files = {
            'master': self.master_log,
            'data': self.data_log,
            'fast_charge': self.fast_charge_log,
            'enhanced_data_collector': self.data_log,
            'systemd': None,  # Special case for systemd journal
            'journal': None,  # Alias for systemd
            'summary': None   # Special case for coordinator summary
        }
        return log_files.get(log_name.lower())
    
    def _get_journalctl_cmd(self, lines: int) -> List[str]:
        """Get the appropriate journalctl command based on which service is running"""
        import subprocess
        
        # Check if system service is running
        try:
            result = subprocess.run(['systemctl', 'is-active', 'goodwe-master-coordinator'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip() == 'active':
                # System service is running
                return ['journalctl', '-u', 'goodwe-master-coordinator', '-n', str(lines), '--no-pager', '--output=short-iso']
        except Exception:
            pass
        
        # Check if user service is running
        try:
            result = subprocess.run(['systemctl', '--user', 'is-active', 'goodwe-master-coordinator'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip() == 'active':
                # User service is running
                return ['journalctl', '--user', '-u', 'goodwe-master-coordinator', '-n', str(lines), '--no-pager', '--output=short-iso']
        except Exception:
            pass
        
        # Default to system service if neither is clearly active
        return ['journalctl', '-u', 'goodwe-master-coordinator', '-n', str(lines), '--no-pager', '--output=short-iso']
    
    def _get_log_lines(self, log_path: Path, lines: int, level: str = '') -> Response:
        """Get last N lines from log file using efficient shell commands"""
        try:
            import subprocess
            
            # If filtering by level, use grep | tail
            if level:
                # Use grep to filter, then tail to get last N lines
                # We use -a to handle potential binary characters safely
                cmd = f"grep -a '{level.upper()}' '{log_path}' | tail -n {lines}"
            else:
                # Just tail the file
                cmd = f"tail -n {lines} '{log_path}'"
            
            # Execute command
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors='replace')
            
            if result.returncode != 0 and result.stderr:
                return jsonify({'error': f"Command failed: {result.stderr}"}), 500
                
            recent_lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            # Get total line count (approximate for speed or skip if too slow)
            # For performance, we'll skip exact total count on large files
            total_lines = -1 
            
            return jsonify({
                'log_file': log_path.name,
                'total_lines': total_lines,
                'filtered_lines': -1, # Unknown without reading all
                'returned_lines': len(recent_lines),
                'level_filter': level,
                'lines': [line.rstrip() for line in recent_lines]
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    def _get_systemd_logs(self, lines: int, level: str = '') -> Response:
        """Get logs from systemd journal"""
        try:
            import subprocess
            
            # Determine which service is running and use appropriate journalctl command
            cmd = self._get_journalctl_cmd(lines * 3)
            
            # Execute journalctl command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return jsonify({'error': f'Failed to read systemd journal: {result.stderr}'}), 500
            
            all_lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            # Filter out web server logs (werkzeug, HTTP requests)
            coordinator_lines = []
            for line in all_lines:
                # Skip web server logs
                if any(skip in line for skip in [
                    'werkzeug',
                    'GET /',
                    'POST /',
                    'PUT /',
                    'DELETE /',
                    'HTTP/1.1',
                    '127.0.0.1',
                    '192.168.',
                    'Address already in use',
                    'Port 8080 is in use'
                ]):
                    continue
                
                # Only include actual coordinator logs
                if any(coord in line for coord in [
                    'Master Coordinator',
                    'Data collected successfully',
                    'Fetched',
                    'CSDAC price points',
                    'Decision made',
                    'Executing decision',
                    'Status - State:',
                    'Battery:',
                    'PV:',
                    'Charging:',
                    'Initializing',
                    'Connected to inverter',
                    'GoodWe',
                    'Price Analyzer',
                    'Charging Controller',
                    'Decision Engine',
                    'coordination loop',
                    'health check',
                    'emergency',
                    'ERROR',
                    'WARNING'
                ]):
                    coordinator_lines.append(line)
            
            # Filter by level if specified
            if level:
                filtered_lines = [line for line in coordinator_lines if level.upper() in line.upper()]
            else:
                filtered_lines = coordinator_lines
            
            # Get last N lines
            recent_lines = filtered_lines[-lines:] if len(filtered_lines) > lines else filtered_lines
            
            return jsonify({
                'log_file': 'systemd-journal',
                'total_lines': len(all_lines),
                'filtered_lines': len(filtered_lines),
                'returned_lines': len(recent_lines),
                'level_filter': level,
                'lines': [line.rstrip() for line in recent_lines]
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    def _stream_systemd_logs(self, level: str = '') -> Response:
        """Stream systemd journal logs using Server-Sent Events"""
        def generate():
            try:
                import subprocess
                
                # Send initial data
                yield f"data: {json.dumps({'type': 'start', 'message': 'Starting systemd journal stream'})}\n\n"
                
                # Send recent logs first
                cmd = self._get_journalctl_cmd(20)
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0 and result.stdout.strip():
                    recent_lines = result.stdout.strip().split('\n')
                    for line in recent_lines:
                        # Filter out web server logs
                        if not any(skip in line for skip in [
                            'werkzeug', 'GET /', 'POST /', 'PUT /', 'DELETE /', 'HTTP/1.1',
                            '127.0.0.1', '192.168.', 'Address already in use', 'Port 8080 is in use'
                        ]):
                            # Only include coordinator logs
                            if any(coord in line for coord in [
                                'Master Coordinator', 'Data collected successfully', 'Fetched',
                                'CSDAC price points', 'Decision made', 'Executing decision',
                                'Status - State:', 'Battery:', 'PV:', 'Charging:', 'Initializing',
                                'Connected to inverter', 'GoodWe', 'Price Analyzer', 'Charging Controller',
                                'Decision Engine', 'coordination loop', 'health check', 'emergency',
                                'ERROR', 'WARNING'
                            ]):
                                if not level or level.upper() in line.upper():
                                    yield f"data: {json.dumps({'type': 'log', 'line': line.rstrip()})}\n\n"
                
                # Start following new logs
                cmd = self._get_journalctl_cmd(0)  # Get command without line limit
                cmd.extend(['-f'])  # Add follow flag
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
                
                try:
                    for line in iter(process.stdout.readline, ''):
                        if line:
                            # Filter out web server logs
                            if not any(skip in line for skip in [
                                'werkzeug', 'GET /', 'POST /', 'PUT /', 'DELETE /', 'HTTP/1.1',
                                '127.0.0.1', '192.168.', 'Address already in use', 'Port 8080 is in use'
                            ]):
                                # Only include coordinator logs
                                if any(coord in line for coord in [
                                    'Master Coordinator', 'Data collected successfully', 'Fetched',
                                    'CSDAC price points', 'Decision made', 'Executing decision',
                                    'Status - State:', 'Battery:', 'PV:', 'Charging:', 'Initializing',
                                    'Connected to inverter', 'GoodWe', 'Price Analyzer', 'Charging Controller',
                                    'Decision Engine', 'coordination loop', 'health check', 'emergency',
                                    'ERROR', 'WARNING'
                                ]):
                                    if not level or level.upper() in line.upper():
                                        yield f"data: {json.dumps({'type': 'log', 'line': line.rstrip()})}\n\n"
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            }
        )
    
    def _get_coordinator_summary(self, lines: int, level: str = '') -> Response:
        """Get coordinator summary with only key events"""
        try:
            import subprocess
            
            # Get more lines to filter for key events
            cmd = self._get_journalctl_cmd(lines * 5)
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return jsonify({'error': f'Failed to read systemd journal: {result.stderr}'}), 500
            
            all_lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            # Filter for only key coordinator events
            key_events = []
            for line in all_lines:
                # Skip web server logs
                if any(skip in line for skip in [
                    'werkzeug', 'GET /', 'POST /', 'PUT /', 'DELETE /', 'HTTP/1.1',
                    '127.0.0.1', '192.168.', 'Address already in use', 'Port 8080 is in use'
                ]):
                    continue
                
                # Only include key events
                if any(key in line for key in [
                    'Data collected successfully',
                    'Fetched.*CSDAC price points',
                    'Decision made:',
                    'Executing decision:',
                    'Status - State:',
                    'Battery:',
                    'PV:',
                    'Charging:',
                    'Connected to inverter',
                    'Initializing.*Coordinator',
                    'ERROR',
                    'WARNING',
                    'emergency',
                    'Failed to',
                    'Successfully connected'
                ]):
                    # Clean up the line for summary
                    clean_line = line
                    # Remove duplicate timestamps and process info
                    if 'goodwe-master-coordinator[' in clean_line:
                        parts = clean_line.split(']: ')
                        if len(parts) > 1:
                            clean_line = parts[1]
                    
                    key_events.append(clean_line)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_events = []
            for event in key_events:
                if event not in seen:
                    seen.add(event)
                    unique_events.append(event)
            
            # Filter by level if specified
            if level:
                filtered_lines = [line for line in unique_events if level.upper() in line.upper()]
            else:
                filtered_lines = unique_events
            
            # Get last N lines
            recent_lines = filtered_lines[-lines:] if len(filtered_lines) > lines else filtered_lines
            
            return jsonify({
                'log_file': 'coordinator-summary',
                'total_lines': len(all_lines),
                'filtered_lines': len(filtered_lines),
                'returned_lines': len(recent_lines),
                'level_filter': level,
                'lines': [line.rstrip() for line in recent_lines]
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    def _stream_logs(self, log_path: Path, level: str = '') -> Response:
        """Stream logs using Server-Sent Events"""
        def generate():
            try:
                # Send initial data
                yield f"data: {json.dumps({'type': 'start', 'message': 'Starting log stream'})}\n\n"
                
                # Read existing logs
                with open(log_path, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-50:]:  # Send last 50 lines
                        if not level or level in line.upper():
                            yield f"data: {json.dumps({'type': 'log', 'line': line.rstrip()})}\n\n"
                
                # Monitor file for new lines
                with open(log_path, 'r') as f:
                    f.seek(0, 2)  # Go to end of file
                    while True:
                        line = f.readline()
                        if line:
                            if not level or level in line.upper():
                                yield f"data: {json.dumps({'type': 'log', 'line': line.rstrip()})}\n\n"
                        else:
                            time.sleep(0.1)
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            }
        )
    
    def _get_system_status(self) -> Dict[str, Any]:
        """Get system status information"""
        try:
            # Check if master coordinator is running
            import psutil
            coordinator_running = False
            coordinator_pid = None
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['cmdline'] and any('master_coordinator.py' in cmd for cmd in proc.info['cmdline']):
                        coordinator_running = True
                        coordinator_pid = proc.info['pid']
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Get log file sizes
            log_files = {}
            for log_file in self.log_dir.glob("*.log"):
                stat = log_file.stat()
                log_files[log_file.name] = {
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
            
            # Get data source information
            try:
                current_state = self._get_current_system_state()
                data_source = current_state.get('data_source', 'unknown')
            except Exception:
                data_source = 'unknown'
            
            return {
                'status': 'running',
                'timestamp': datetime.now().isoformat(),
                'coordinator_running': coordinator_running,
                'coordinator_pid': coordinator_pid,
                'log_files': log_files,
                'server_uptime': time.time() - self.start_time if hasattr(self, 'start_time') else 0,
                'server_uptime_human': format_uptime_human_readable(time.time() - self.start_time if hasattr(self, 'start_time') else 0),
                'data_source': data_source
            }
        except ImportError:
            # Get data source information even without psutil
            try:
                current_state = self._get_current_system_state()
                data_source = current_state.get('data_source', 'unknown')
            except Exception:
                data_source = 'unknown'
                
            return {
                'status': 'running',
                'timestamp': datetime.now().isoformat(),
                'coordinator_running': 'unknown',
                'note': 'psutil not available for process monitoring',
                'data_source': data_source
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'data_source': 'unknown'
            }
    
    def _get_dashboard_template(self) -> str:
        """Get HTML dashboard template"""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>GoodWe Master Coordinator - Enhanced Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-primary: #f8f9fa;
            --bg-secondary: #ffffff;
            --bg-tertiary: #f8f9fa;
            --text-primary: #2c3e50;
            --text-secondary: #7f8c8d;
            --text-muted: #95a5a6;
            --border-color: #ecf0f1;
            --border-light: #bdc3c7;
            --shadow: rgba(0,0,0,0.1);
            --shadow-light: rgba(0,0,0,0.05);
            --accent-primary: #3498db;
            --accent-secondary: #2c3e50;
            --success: #27ae60;
            --warning: #f39c12;
            --error: #e74c3c;
            --gradient-primary: linear-gradient(135deg, #2c3e50, #3498db);
            --gradient-success: linear-gradient(90deg, #e74c3c, #f39c12, #27ae60);
        }

        [data-theme="dark"] {
            --bg-primary: #1a1a1a;
            --bg-secondary: #2d2d2d;
            --bg-tertiary: #3a3a3a;
            --text-primary: #e8e8e8;
            --text-secondary: #b0b0b0;
            --text-muted: #808080;
            --border-color: #404040;
            --border-light: #555555;
            --shadow: rgba(0,0,0,0.3);
            --shadow-light: rgba(0,0,0,0.2);
            --accent-primary: #4a9eff;
            --accent-secondary: #4a9eff;
            --success: #2ecc71;
            --warning: #f1c40f;
            --error: #e74c3c;
            --gradient-primary: linear-gradient(135deg, #2d2d2d, #4a9eff);
            --gradient-success: linear-gradient(90deg, #e74c3c, #f1c40f, #2ecc71);
        }

        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            background-color: var(--bg-primary);
            color: var(--text-primary);
            transition: background-color 0.3s ease, color 0.3s ease;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header { 
            background: var(--gradient-primary); 
            color: white; 
            padding: 30px; 
            border-radius: 10px; 
            margin-bottom: 20px; 
            box-shadow: 0 4px 6px var(--shadow);
            position: relative;
        }
        .theme-toggle {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(255,255,255,0.2);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            padding: 8px 12px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s ease;
        }
        .theme-toggle:hover {
            background: rgba(255,255,255,0.3);
        }
        .card { 
            background: var(--bg-secondary); 
            padding: 25px; 
            margin-bottom: 20px; 
            border-radius: 10px; 
            box-shadow: 0 2px 10px var(--shadow);
            transition: background-color 0.3s ease, box-shadow 0.3s ease;
        }
        .card h3 { 
            margin-top: 0; 
            color: var(--text-primary); 
            border-bottom: 2px solid var(--accent-primary); 
            padding-bottom: 10px; 
        }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .status-indicator { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }
        .status-running { background-color: var(--success); }
        .status-stopped { background-color: var(--error); }
        .status-unknown { background-color: var(--warning); }
        .metric { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            padding: 10px 0; 
            border-bottom: 1px solid var(--border-color); 
        }
        .metric:last-child { border-bottom: none; }
        .metric-value { font-weight: bold; font-size: 1.1em; color: var(--text-primary); }
        .metric-label { color: var(--text-secondary); }
        .recent-activity { margin-top: 10px; }
        .activity-item { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            padding: 5px 0; 
            border-bottom: 1px solid var(--border-light); 
        }
        .activity-item:last-child { border-bottom: none; }
        .activity-time { color: var(--text-secondary); font-size: 0.9em; }
        .activity-action { font-weight: bold; color: var(--text-primary); }
        .activity-revenue { color: var(--success); font-weight: bold; }
        .decision-item { 
            padding: 15px; 
            margin: 10px 0; 
            border-radius: 8px; 
            border-left: 4px solid var(--accent-primary); 
            background: var(--bg-tertiary); 
            transition: background-color 0.3s ease;
        }
        .decision-item.wait { border-left-color: var(--warning); }
        .decision-item.charging { border-left-color: var(--success); }
        .decision-item.selling { border-left-color: var(--accent-primary); background: linear-gradient(135deg, var(--bg-tertiary), #e8f4fd); }
        .decision-time { color: var(--text-secondary); font-size: 0.9em; }
        .decision-action { font-weight: bold; margin: 5px 0; color: var(--text-primary); }
        .decision-reason { color: var(--text-primary); font-style: italic; }
        .confidence-bar { 
            width: 100%; 
            height: 8px; 
            background: var(--border-color); 
            border-radius: 4px; 
            margin: 5px 0; 
        }
        .confidence-fill { 
            height: 100%; 
            background: var(--gradient-success); 
            border-radius: 4px; 
        }
        .chart-container { position: relative; height: 300px; margin: 20px 0; }
        .chart-info { 
            margin-top: 15px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            flex-wrap: wrap; 
            gap: 15px; 
        }
        .chart-legend { 
            display: flex; 
            gap: 20px; 
            flex-wrap: wrap; 
        }
        .legend-item { 
            display: flex; 
            align-items: center; 
            gap: 8px; 
            font-size: 14px; 
        }
        .legend-color { 
            width: 16px; 
            height: 16px; 
            border-radius: 3px; 
            display: inline-block; 
        }
        .chart-controls { 
            display: flex; 
            align-items: center; 
            gap: 15px; 
        }
        .last-update { 
            font-size: 12px; 
            color: var(--text-muted); 
        }
        .log-container { 
            background: var(--bg-tertiary); 
            color: var(--text-primary); 
            padding: 15px; 
            border-radius: 8px; 
            font-family: 'Courier New', monospace; 
            font-size: 12px; 
            max-height: 400px; 
            overflow-y: auto; 
            border: 1px solid var(--border-color);
        }
        .controls { margin-bottom: 15px; display: flex; flex-wrap: wrap; gap: 10px; }
        .controls input, .controls select, .controls button { 
            padding: 8px 12px; 
            border: 1px solid var(--border-light); 
            border-radius: 4px; 
            background: var(--bg-secondary);
            color: var(--text-primary);
            transition: all 0.3s ease;
        }
        .controls button { 
            background: var(--accent-primary); 
            color: white; 
            border: none; 
            cursor: pointer; 
        }
        .controls button:hover { 
            background: var(--accent-secondary); 
            opacity: 0.9;
        }
        .log-line { margin: 2px 0; }
        .log-error { color: var(--error); }
        .log-warning { color: var(--warning); }
        .log-info { color: var(--accent-primary); }
        .log-debug { color: var(--text-muted); }
        .tabs { 
            display: flex; 
            border-bottom: 2px solid var(--border-color); 
            margin-bottom: 20px; 
        }
        .tab { 
            padding: 10px 20px; 
            cursor: pointer; 
            border-bottom: 2px solid transparent; 
            color: var(--text-secondary);
            transition: all 0.3s ease;
        }
        .tab:hover {
            color: var(--text-primary);
        }
        .tab.active { 
            border-bottom-color: var(--accent-primary); 
            color: var(--accent-primary); 
            font-weight: bold; 
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .savings-positive { color: var(--success); font-weight: bold; }
        .savings-negative { color: var(--error); font-weight: bold; }
        
        /* No Data and Waiting States */
        .no-data-state, .waiting-state {
            text-align: center;
            padding: 20px;
            border-radius: 8px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
        }
        
        .no-data-icon, .waiting-icon {
            font-size: 3em;
            margin-bottom: 15px;
            opacity: 0.7;
        }
        
        .no-data-message h4, .waiting-message h4 {
            margin: 0 0 10px 0;
            color: var(--text-primary);
            font-size: 1.2em;
        }
        
        .no-data-message p, .waiting-message p {
            margin: 0 0 15px 0;
            color: var(--text-secondary);
        }
        
        .waiting-details {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 15px;
        }
        
        .waiting-count {
            font-weight: bold;
            color: var(--accent-primary);
        }
        
        .waiting-reason {
            font-style: italic;
            color: var(--text-secondary);
            font-size: 0.9em;
        }
        
        .waiting-metrics {
            margin-top: 20px;
            text-align: left;
        }
        
        .metric-value.waiting {
            color: var(--text-secondary);
            font-style: italic;
        }
        
        .monitoring-state {
            padding: 15px;
            border-radius: 8px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
        }
        
        .metric-value.monitoring {
            color: var(--accent-primary);
            font-weight: bold;
        }
        
        .monitoring-note {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid var(--border-color);
            text-align: center;
        }
        
        .monitoring-note small {
            color: var(--text-secondary);
            font-style: italic;
        }
        
        .current-conditions {
            margin-top: 10px;
            padding: 8px;
            background: var(--card-bg);
            border-radius: 4px;
            border: 1px solid var(--border-color);
        }
        
        .current-conditions small {
            color: var(--text-secondary);
            font-family: monospace;
        }
        .system-health { display: flex; align-items: center; gap: 10px; }
        .health-indicator { 
            padding: 5px 10px; 
            border-radius: 15px; 
            color: white; 
            font-size: 0.9em; 
        }
        .health-good { background: var(--success); }
        .health-warning { background: var(--warning); }
        .health-error { background: var(--error); }
        
        .data-source-real { color: var(--success); }
        .data-source-mock { color: var(--warning); }
        
        .sync-indicator {
            font-size: 12px;
            opacity: 0.8;
            transition: all 0.3s ease;
        }
        .sync-indicator.synced { color: var(--success); }
        .sync-indicator.manual { color: var(--warning); }
        
        .sync-toggle {
            background: rgba(255,255,255,0.2);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            padding: 8px 12px;
            border-radius: 15px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s ease;
        }
        .sync-toggle:hover {
            background: rgba(255,255,255,0.3);
        }
        
        /* Dark mode specific adjustments */
        [data-theme="dark"] .log-container {
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }
        
        /* Smooth transitions for theme switching */
        * {
            transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔋 GoodWe Master Coordinator - Enhanced Dashboard</h1>
            <p>Intelligent Energy Management & Decision Monitoring</p>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                <div id="data-source-indicator" style="font-size: 14px; opacity: 0.8;">
                    📊 Data Source: <span id="data-source-text">Loading...</span>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span id="sync-status" class="sync-indicator" style="font-size: 12px; opacity: 0.8;">Loading...</span>
                    <button class="sync-toggle" onclick="toggleOSSync()" id="sync-toggle" title="Toggle OS sync">
                        🔄
                    </button>
                    <button class="theme-toggle" onclick="toggleTheme()" id="theme-toggle">
                        🌙 Dark Mode
                    </button>
                </div>
            </div>
        </div>
        
        <!-- Tabs -->
        <div class="tabs">
            <div class="tab active" onclick="showTab('overview')">Overview</div>
            <div class="tab" onclick="showTab('decisions')">Decisions</div>
            <div class="tab" onclick="showTab('time-series')">Time Series</div>
            <div class="tab" onclick="showTab('logs')">Logs</div>
        </div>
        
        <!-- Overview Tab -->
        <div id="overview" class="tab-content active">
            <div class="grid">
                <div class="card">
                    <h3>System Status</h3>
                    <div id="status">
                        <span class="status-indicator status-unknown"></span>
                        <span id="status-text">Loading...</span>
                    </div>
                    <div id="status-details"></div>
                </div>
                
                <div class="card">
                    <h3>Current System State</h3>
                    <div id="current-state">Loading...</div>
                </div>
                
                <div class="card">
                    <h3>Performance Metrics</h3>
                    <div id="performance-metrics">Loading...</div>
                </div>
                
                <div class="card">
                    <h3 style="margin-bottom: 10px;">Cost & Savings</h3>
                    <div style="margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid var(--accent-primary);">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <label for="comparison-month" style="font-size: 12px; color: var(--text-secondary);">View Month:</label>
                            <select id="comparison-month" onchange="loadMonthlyComparison()" style="padding: 4px 8px; border-radius: 4px; border: 1px solid var(--border-light); flex-grow: 1;">
                                <!-- Options populated by JS -->
                            </select>
                        </div>
                    </div>
                    <div id="cost-savings">Loading...</div>
                </div>
            </div>
        </div>
        
        <!-- Decisions Tab -->
        <div id="decisions" class="tab-content">
            <div class="card">
                <h3>Decision History</h3>
                
                <!-- Filter Controls -->
                <div class="filter-controls" style="margin-bottom: 20px; padding: 15px; background: var(--card-bg); border-radius: 8px; border: 1px solid var(--border-color);">
                    <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap;">
                        <!-- Time Range Filter -->
                        <div class="filter-group">
                            <label for="time-range" style="font-weight: 600; margin-right: 8px;">Time Range:</label>
                            <select id="time-range" style="padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 4px; background: var(--bg-color); color: var(--text-color);">
                                <option value="7d">Last 7 Days</option>
                                <option value="24h" selected>Last 24 Hours</option>
                            </select>
                        </div>
                        
                        
                        <!-- Refresh Button -->
                        <button id="refresh-decisions" style="padding: 8px 16px; background: var(--primary-color); color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 600;">
                            Refresh
                        </button>
                    </div>
                    
                    <!-- Statistics Summary -->
                    <div id="decisions-summary" style="margin-top: 15px; display: flex; gap: 20px; flex-wrap: wrap;">
                        <div class="stat-item" style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-weight: 600;">Total:</span>
                            <span id="total-count" class="stat-value" style="background: var(--primary-color); color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: 600;">0</span>
                        </div>
                        <div class="stat-item" style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-weight: 600;">Charging:</span>
                            <span id="charging-count" class="stat-value" style="background: #28a745; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: 600;">0</span>
                        </div>
                        <div class="stat-item" style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-weight: 600;">Wait:</span>
                            <span id="wait-count" class="stat-value" style="background: #ffc107; color: black; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: 600;">0</span>
                        </div>
                    </div>
                </div>
                
                <div id="decisions-list">Loading...</div>
            </div>
        </div>
        
        <!-- Time Series Tab -->
        <div id="time-series" class="tab-content">
            <div class="grid">
                <div class="card">
                    <h3>Battery SOC & PV Production Over Time</h3>
                    <div class="chart-container">
                        <canvas id="timeSeriesChart"></canvas>
                    </div>
                    <div class="chart-info">
                        <div class="chart-legend">
                            <div class="legend-item">
                                <span class="legend-color" style="background-color: #3498db;"></span>
                                <span>Battery SOC (%)</span>
                            </div>
                            <div class="legend-item">
                                <span class="legend-color" style="background-color: #27ae60;"></span>
                                <span>PV Production (kW)</span>
                            </div>
                        </div>
                        <div class="chart-controls">
                            <button onclick="refreshTimeSeriesChart()" class="btn btn-primary">Refresh</button>
                            <span id="time-series-last-update" class="last-update">Last update: --</span>
                        </div>
                    </div>
                </div>
                <div class="card">
                    <h3>Data Summary</h3>
                    <div id="time-series-summary">
                        <div class="metric">
                            <span class="metric-label">Data Points</span>
                            <span class="metric-value" id="data-points">--</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Data Source</span>
                            <span class="metric-value" id="data-source">--</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">SOC Range</span>
                            <span class="metric-value" id="soc-range">--</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">PV Peak</span>
                            <span class="metric-value" id="pv-peak">--</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Logs Tab -->
        <div id="logs" class="tab-content">
            <div class="card">
                <h3>Log Viewer</h3>
                <div class="controls">
                    <select id="log-file">
                        <option value="systemd">Systemd Journal (Master Coordinator)</option>
                        <option value="summary">Coordinator Summary (Key Events)</option>
                        <option value="master">Master Coordinator (File)</option>
                        <option value="data">Data Collector</option>
                        <option value="fast_charge">Fast Charge</option>
                    </select>
                    <input type="number" id="lines" value="100" min="10" max="1000" placeholder="Lines">
                    <select id="level">
                        <option value="">All Levels</option>
                        <option value="ERROR">Error</option>
                        <option value="WARNING">Warning</option>
                        <option value="INFO">Info</option>
                        <option value="DEBUG">Debug</option>
                    </select>
                    <button onclick="loadLogs()">Load Logs</button>
                    <button onclick="toggleStream()">Toggle Live Stream</button>
                    <button onclick="downloadLog()">Download</button>
                </div>
                <div id="log-container" class="log-container"></div>
            </div>
        </div>
    </div>

    <script>
        let eventSource = null;
        let streaming = false;
        let decisionChart = null;
        let costChart = null;
        
        function showTab(tabName) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Remove active class from all tabs
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab content
            document.getElementById(tabName).classList.add('active');
            
            // Add active class to clicked tab
            event.target.classList.add('active');
            
            // Load data for the tab
            if (tabName === 'decisions') {
                loadDecisions();
            } else if (tabName === 'time-series') {
                loadTimeSeries();
            }
        }
        
        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    const statusEl = document.getElementById('status');
                    const statusText = document.getElementById('status-text');
                    const detailsEl = document.getElementById('status-details');
                    
                    if (data.coordinator_running) {
                        statusEl.innerHTML = '<span class="status-indicator status-running"></span><span id="status-text">Master Coordinator Running</span>';
                    } else {
                        statusEl.innerHTML = '<span class="status-indicator status-stopped"></span><span id="status-text">Master Coordinator Stopped</span>';
                    }
                    
                    detailsEl.innerHTML = `
                        <p><strong>Timestamp:</strong> ${data.timestamp}</p>
                        ${data.coordinator_pid ? `<p><strong>PID:</strong> ${data.coordinator_pid}</p>` : ''}
                        <p><strong>Server Uptime:</strong> ${data.server_uptime_human || Math.round(data.server_uptime) + 's'}</p>
                    `;
                })
                .catch(error => {
                    document.getElementById('status').innerHTML = '<span class="status-indicator status-unknown"></span><span id="status-text">Status Unknown</span>';
                });
        }
        
        function loadCurrentState() {
            fetch('/current-state')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('current-state').innerHTML = `<p>Error: ${data.error}</p>`;
                        return;
                    }
                    
                    // Normalize payload to support older/newer backends
                    const normalized = (() => {
                        const d = { ...data };
                        // Map legacy keys to new structure
                        d.photovoltaic = d.photovoltaic || d.pv || {};
                        d.house_consumption = d.house_consumption || d.consumption || {};
                        // Normalize power fields
                        if (d.pv && d.photovoltaic && d.photovoltaic.current_power_w == null) {
                            d.photovoltaic.current_power_w = d.pv.current_power_w ?? d.pv.power_w ?? d.pv.power ?? null;
                        }
                        if (d.consumption && d.house_consumption && d.house_consumption.current_power_w == null) {
                            d.house_consumption.current_power_w = d.consumption.current_power_w ?? d.consumption.power_w ?? d.consumption.power ?? null;
                        }
                        if (d.grid) {
                            if (d.grid.current_power_w == null && d.grid.power_w != null) {
                                d.grid.current_power_w = d.grid.power_w;
                            }
                        } else {
                            d.grid = {};
                        }
                        // Normalize data source indicator
                        const src = (d.data_source || '').toLowerCase();
                        if (src === 'real' || src === 'real_inverter') {
                            d.data_source = 'real_inverter';
                        } else if (!src) {
                            d.data_source = 'mock';
                        } else {
                            d.data_source = d.data_source;
                        }
                        return d;
                    })();

                    // Update data source indicator
                    const dataSource = normalized.data_source || 'mock';
                    const dataSourceText = dataSource === 'real_inverter' ? 'Real Inverter Data' : 'Mock Data';
                    const dataSourceElement = document.getElementById('data-source-text');
                    dataSourceElement.textContent = dataSourceText;
                    dataSourceElement.className = dataSource === 'real_inverter' ? 'data-source-real' : 'data-source-mock';
                    
                    const stateHtml = `
                        <div class="metric">
                            <span class="metric-label">Battery SoC</span>
                            <span class="metric-value">${(normalized.battery && normalized.battery.soc_percent != null) ? normalized.battery.soc_percent : 'N/A'}%</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">PV Power</span>
                            <span class="metric-value">${(normalized.photovoltaic && normalized.photovoltaic.current_power_w != null) ? normalized.photovoltaic.current_power_w : 'N/A'}W</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">House Consumption</span>
                            <span class="metric-value">${(normalized.house_consumption && normalized.house_consumption.current_power_w != null) ? normalized.house_consumption.current_power_w : 'N/A'}W</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">L1 Current</span>
                            <span class="metric-value">${(normalized.grid && normalized.grid.l1_current_a != null ? normalized.grid.l1_current_a : 'N/A')} A</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">L2 Current</span>
                            <span class="metric-value">${(normalized.grid && normalized.grid.l2_current_a != null ? normalized.grid.l2_current_a : 'N/A')} A</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">L3 Current</span>
                            <span class="metric-value">${(normalized.grid && normalized.grid.l3_current_a != null ? normalized.grid.l3_current_a : 'N/A')} A</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Current Price</span>
                            <span class="metric-value">${(normalized.pricing && normalized.pricing.current_price_pln_kwh != null) ? normalized.pricing.current_price_pln_kwh : 'N/A'} PLN/kWh</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Cheapest Price</span>
                            <span class="metric-value">${(normalized.pricing && normalized.pricing.cheapest_price_pln_kwh != null) ? normalized.pricing.cheapest_price_pln_kwh : 'N/A'} PLN/kWh (${normalized.pricing && normalized.pricing.cheapest_hour ? normalized.pricing.cheapest_hour : 'N/A'})</span>
                        </div>
                    `;
                    document.getElementById('current-state').innerHTML = stateHtml;
                })
                .catch(error => {
                    document.getElementById('current-state').innerHTML = `<p>Error loading current state: ${error.message}</p>`;
                });
        }
        
        function loadPerformanceMetrics() {
            fetch('/metrics')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('performance-metrics').innerHTML = `<p>Error: ${data.error}</p>`;
                        return;
                    }
                    
                    const hasChargingDecisions = data.charging_count > 0;
                    const hasAnyDecisions = data.total_count > 0;
                    
                    if (!hasAnyDecisions) {
                        // No decisions at all
                        document.getElementById('performance-metrics').innerHTML = `
                            <div class="no-data-state">
                                <div class="no-data-icon">📊</div>
                                <div class="no-data-message">
                                    <h4>No Performance Data</h4>
                                    <p>System hasn't made any decisions yet</p>
                                </div>
                            </div>
                        `;
                        return;
                    }
                    
                    if (!hasChargingDecisions) {
                        // Only wait decisions - show monitoring state
                        const waitPercentage = data.total_count > 0 ? ((data.wait_count / data.total_count) * 100).toFixed(1) : 0;
                        document.getElementById('performance-metrics').innerHTML = `
                            <div class="monitoring-state">
                                <div class="metric" title="Total number of decisions made by the system (charging + waiting)">
                                    <span class="metric-label">Total Decisions</span>
                                    <span class="metric-value">${data.total_count}</span>
                                </div>
                                <div class="metric" title="Number of decisions that resulted in actual charging">
                                    <span class="metric-label">Charging Decisions</span>
                                    <span class="metric-value waiting">0</span>
                                </div>
                                <div class="metric" title="Number of decisions to wait for better conditions">
                                    <span class="metric-label">Wait Decisions</span>
                                    <span class="metric-value">${data.wait_count} (${waitPercentage}%)</span>
                                </div>
                                <div class="metric" title="Current system operational status">
                                    <span class="metric-label">System Status</span>
                                    <span class="metric-value monitoring">Monitoring</span>
                                </div>
                                <div class="metric" title="Average confidence level of all decisions made">
                                    <span class="metric-label">Avg Confidence</span>
                                    <span class="metric-value">${data.avg_confidence.toFixed(1)}%</span>
                                </div>
                                <div class="monitoring-note">
                                    <small>System is actively monitoring conditions for optimal charging opportunities</small>
                                </div>
                            </div>
                        `;
                        return;
                    }
                    
                    // Normal state with charging decisions
                    const metricsHtml = `
                        <div class="metric" title="Total number of decisions made by the system (charging + waiting)">
                            <span class="metric-label">Total Decisions</span>
                            <span class="metric-value">${data.total_count}</span>
                        </div>
                        <div class="metric" title="Number of decisions that resulted in actual charging">
                            <span class="metric-label">Charging Decisions</span>
                            <span class="metric-value">${data.charging_count}</span>
                        </div>
                        <div class="metric" title="Number of decisions to wait for better conditions">
                            <span class="metric-label">Wait Decisions</span>
                            <span class="metric-value">${data.wait_count}</span>
                        </div>
                        <div class="metric" title="Overall system efficiency score based on confidence, savings, and charging ratio (0-100)">
                            <span class="metric-label">Efficiency Score</span>
                            <span class="metric-value">${data.efficiency_score}/100</span>
                        </div>
                        <div class="metric" title="Average confidence level of all decisions made">
                            <span class="metric-label">Avg Confidence</span>
                            <span class="metric-value">${data.avg_confidence.toFixed(1)}%</span>
                        </div>
                    `;
                    document.getElementById('performance-metrics').innerHTML = metricsHtml;
                })
                .catch(error => {
                    document.getElementById('performance-metrics').innerHTML = `<p>Error loading metrics: ${error.message}</p>`;
                });
        }
        
        function populateMonthSelector() {
            const selector = document.getElementById('comparison-month');
            if (!selector) return;
            
            const now = new Date();
            const currentYear = now.getFullYear();
            const currentMonth = now.getMonth(); // 0-11
            
            // Clear existing options
            selector.innerHTML = '';
            
            // Add current month first
            let currentOption = document.createElement('option');
            let currentMonthName = now.toLocaleString('default', { month: 'long' });
            currentOption.value = `${currentYear}-${currentMonth + 1}`;
            currentOption.textContent = `${currentMonthName} ${currentYear} (Current)`;
            currentOption.selected = true;
            selector.appendChild(currentOption);
            
            // Add last 12 months
            for (let i = 1; i <= 12; i++) {
                let d = new Date(currentYear, currentMonth - i, 1);
                let year = d.getFullYear();
                let month = d.getMonth() + 1; // 1-12
                let monthName = d.toLocaleString('default', { month: 'long' });
                
                let option = document.createElement('option');
                option.value = `${year}-${month}`;
                option.textContent = `${monthName} ${year}`;
                
                selector.appendChild(option);
            }
        }

        function loadMonthlyComparison() {
            const selector = document.getElementById('comparison-month');
            if (!selector || !selector.value) return;
            
            const [year, month] = selector.value.split('-');
            
            // Use monthly-summary endpoint instead of comparison
            fetch(`/monthly-summary?year=${year}&month=${month}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('cost-savings').innerHTML = `<p>Error: ${data.error}</p>`;
                        return;
                    }
                    
                    const summary = data;
                    
                    if (summary.total_decisions === 0) {
                        document.getElementById('cost-savings').innerHTML = `
                            <div style="padding: 20px; text-align: center; color: var(--text-secondary);">
                                <div style="font-size: 2em; margin-bottom: 10px;">📅</div>
                                <h4>No Data Available</h4>
                                <p>No charging or selling decisions recorded for ${summary.month_name} ${summary.year}.</p>
                            </div>
                        `;
                        return;
                    }
                    
                    const html = `
                        <div style="padding: 10px;">
                            <h4 style="margin: 0 0 15px 0; color: var(--accent-primary); text-align: center;">${summary.month_name} ${summary.year} Overview</h4>
                            
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px;">
                                <div class="metric-box" style="background: var(--bg-secondary); padding: 15px; border-radius: 8px; text-align: center; border: 1px solid var(--border-color);">
                                    <div style="font-size: 0.9em; color: var(--text-secondary); margin-bottom: 5px;">Total Cost</div>
                                    <div style="font-size: 1.4em; font-weight: bold; color: var(--text-primary);">${summary.total_cost_pln.toFixed(2)} PLN</div>
                                </div>
                                
                                <div class="metric-box" style="background: var(--bg-secondary); padding: 15px; border-radius: 8px; text-align: center; border: 1px solid var(--border-color);">
                                    <div style="font-size: 0.9em; color: var(--text-secondary); margin-bottom: 5px;">Total Savings</div>
                                    <div style="font-size: 1.4em; font-weight: bold; color: #28a745;">${summary.total_savings_pln.toFixed(2)} PLN</div>
                                </div>
                                
                                <div class="metric-box" style="background: var(--bg-secondary); padding: 15px; border-radius: 8px; text-align: center; border: 1px solid var(--border-color);">
                                    <div style="font-size: 0.9em; color: var(--text-secondary); margin-bottom: 5px;">Energy Charged</div>
                                    <div style="font-size: 1.4em; font-weight: bold; color: var(--accent-primary);">${summary.total_energy_kwh.toFixed(2)} kWh</div>
                                </div>
                                
                                <div class="metric-box" style="background: var(--bg-secondary); padding: 15px; border-radius: 8px; text-align: center; border: 1px solid var(--border-color);">
                                    <div style="font-size: 0.9em; color: var(--text-secondary); margin-bottom: 5px;">Avg Cost/kWh</div>
                                    <div style="font-size: 1.4em; font-weight: bold; color: var(--text-primary);">${summary.avg_cost_per_kwh.toFixed(4)} PLN</div>
                                </div>
                            </div>
                            
                            ${summary.selling_revenue_pln > 0 ? `
                            <div style="margin-top: 20px; padding: 15px; background: rgba(39, 174, 96, 0.1); border-radius: 8px; border: 1px solid #27ae60;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-weight: bold; color: #27ae60;">Battery Selling Revenue (Net 80%)</span>
                                    <span style="font-weight: bold; font-size: 1.2em; color: #27ae60;">+${summary.selling_revenue_pln.toFixed(2)} PLN</span>
                                </div>
                                <div style="font-size: 0.9em; color: var(--text-secondary); margin-top: 8px; display: flex; justify-content: space-between;">
                                    <span>Energy Sold: <strong>${summary.total_energy_sold_kwh.toFixed(2)} kWh</strong></span>
                                    <span>Sessions: <strong>${summary.selling_count}</strong></span>
                                </div>
                            </div>
                            ` : ''}
                            
                            <div style="margin-top: 15px; font-size: 0.85em; color: var(--text-muted); text-align: center;">
                                Based on ${summary.total_decisions} decisions (${summary.charging_count} charging, ${summary.wait_count} waiting)
                            </div>
                        </div>
                    `;
                    
                    document.getElementById('cost-savings').innerHTML = html;
                })
                .catch(error => {
                    document.getElementById('cost-savings').innerHTML = `<p>Error loading summary: ${error.message}</p>`;
                });
        }
        
        function loadCostSavings() {
            // Redirect to new comparison function
            loadMonthlyComparison();
        }
        
        function loadDecisions() {
            // Get current filter values
            const timeRange = document.getElementById('time-range').value;
            
            // Build query parameters
            const params = new URLSearchParams({
                time_range: timeRange
            });
            
            fetch(`/decisions?${params}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('decisions-list').innerHTML = `<p>Error: ${data.error}</p>`;
                        return;
                    }
                    
                    // Update statistics
                    document.getElementById('total-count').textContent = data.total_count || 0;
                    document.getElementById('charging-count').textContent = data.charging_count || 0;
                    document.getElementById('wait-count').textContent = data.wait_count || 0;
                    
                    // Group decisions by date
                    const groupedDecisions = groupDecisionsByDate(data.decisions);
                    
                    // Generate HTML for grouped decisions
                    const decisionsHtml = Object.keys(groupedDecisions).map(date => {
                        const dayDecisions = groupedDecisions[date];
                        const dayCount = dayDecisions.length;
                        
                        return `
                            <div class="decision-day-group" style="margin-bottom: 20px;">
                                <div class="day-header" style="background: var(--card-bg); padding: 10px 15px; border-radius: 8px 8px 0 0; border: 1px solid var(--border-color); border-bottom: none; font-weight: 600; color: var(--primary-color); display: flex; justify-content: space-between; align-items: center;">
                                    <span>${date}</span>
                                    <div style="display: flex; gap: 10px; align-items: center;">
                                        <div style="display: flex; gap: 5px; font-size: 10px;">
                                            <span style="background: #28a745; color: white; padding: 2px 6px; border-radius: 8px;">✅ EXECUTED</span>
                                            <span style="background: #dc3545; color: white; padding: 2px 6px; border-radius: 8px;">🚫 BLOCKED</span>
                                            <span style="background: #6c757d; color: white; padding: 2px 6px; border-radius: 8px;">⏸️ N/A</span>
                                        </div>
                                        <span style="background: var(--primary-color); color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px;">${dayCount} decisions</span>
                                    </div>
                                </div>
                                <div class="day-decisions" style="border: 1px solid var(--border-color); border-top: none; border-radius: 0 0 8px 8px; background: var(--card-bg);">
                                    ${dayDecisions.map(decision => {
                                        const decisionClass = getDecisionClass(decision.action);
                                        const confidencePercent = (decision.confidence * 100).toFixed(1);
                                        
                                        // Get SOC color based on battery level
                                        const getSocColor = (soc) => {
                                            if (soc < 20) return '#dc3545'; // Red
                                            if (soc < 50) return '#ffc107'; // Yellow
                                            return '#28a745'; // Green
                                        };
                                        
                                        // Determine execution status with detailed reasons
                                        const getExecutionStatus = (decision) => {
                                            const batterySoc = decision.battery_soc || 0;
                                            const socText = `SOC: ${batterySoc}%`;
                                            
                                            if (decision.action === 'wait') {
                                                return { 
                                                    status: 'N/A', 
                                                    color: '#6c757d', 
                                                    icon: '⏸️',
                                                    reason: 'Wait decision - no execution needed',
                                                    soc: batterySoc
                                                };
                                            }
                                            
                                            // Check if decision was actually executed
                                            const energy = decision.energy_kwh || 0;
                                            const cost = decision.estimated_cost_pln || 0;
                                            const savings = decision.estimated_savings_pln || 0;
                                            
                                            // Check explicit execution status if available (new format)
                                            if (decision.execution_success === false) {
                                                const errorMsg = decision.execution_error || 'Execution failed';
                                                return { 
                                                    status: 'FAILED', 
                                                    color: '#dc3545', 
                                                    icon: '❌',
                                                    reason: `${errorMsg} (${socText})`,
                                                    soc: batterySoc
                                                };
                                            }
                                            
                                            // If all values are 0, likely not executed - determine why
                                            if (energy === 0 && cost === 0 && savings === 0) {
                                                // Check if this is a charge decision that hasn't completed yet
                                                const isChargeAction = decision.action === 'charge' || decision.action === 'fast_charge';
                                                const hasPositivePrice = decision.current_price > 0;
                                                
                                                // If it's a charge action with positive price but 0 energy, it might be in progress
                                                if (isChargeAction && hasPositivePrice) {
                                                    return { 
                                                        status: 'IN_PROGRESS', 
                                                        color: '#ffc107', 
                                                        icon: '⏳',
                                                        reason: `Charging in progress (${socText})`,
                                                        soc: batterySoc
                                                    };
                                                }
                                                
                                                // Analyze the reason to determine blocking cause
                                                // Battery selling decisions use 'reasoning', charging uses 'reason'
                                                const reason = decision.reason || decision.reasoning || '';
                                                const reasonLower = reason.toLowerCase();
                                                let blockReason = 'Unknown reason';
                                                
                                                // Check for specific blocking patterns with more detail
                                                const kompasRequired = reasonLower.includes('wymagane ogranicz') || reasonLower.includes('required reduction');
                                                const kompasSaving = reasonLower.includes('zalecane oszcz') || reasonLower.includes('recommended saving');
                                                
                                                if (reasonLower.includes('kompas') && kompasRequired) {
                                                    blockReason = `Kompas WYMAGANE OGRANICZANIE - Grid charging blocked during peak hours (${socText})`;
                                                } else if (reasonLower.includes('kompas') && kompasSaving) {
                                                    blockReason = `Kompas ZALECANE OSZCZĘDZANIE - Deferred to reduce load (${socText})`;
                                                } else if (reasonLower.includes('peak hours') || reasonLower.includes('peak period')) {
                                                    blockReason = `Peak hours restriction - Charging blocked (${socText})`;
                                                } else if (reasonLower.includes('emergency') || reasonLower.includes('safety')) {
                                                    blockReason = `Emergency safety stop at ${socText}`;
                                                } else if (reasonLower.includes('price') && reasonLower.includes('not optimal')) {
                                                    blockReason = `Price threshold not met at ${socText}`;
                                                } else if (reasonLower.includes('could not determine current price')) {
                                                    blockReason = `Price data unavailable (${socText})`;
                                                } else if (reasonLower.includes('battery') && reasonLower.includes('safety margin')) {
                                                    blockReason = `Battery safety margin exceeded (${socText})`;
                                                } else if (reasonLower.includes('grid voltage') && reasonLower.includes('outside safe range')) {
                                                    blockReason = `Grid voltage out of range at ${socText}`;
                                                } else if (reasonLower.includes('communication') || reasonLower.includes('connection')) {
                                                    blockReason = `Communication error (${socText})`;
                                                } else if (reasonLower.includes('inverter') && reasonLower.includes('error')) {
                                                    blockReason = `Inverter error at ${socText}`;
                                                } else if (reasonLower.includes('timeout') || reasonLower.includes('retry')) {
                                                    blockReason = `Communication timeout (${socText})`;
                                                } else if (reasonLower.includes('charging') && reasonLower.includes('already')) {
                                                    blockReason = `Already charging at ${socText}`;
                                                } else if (reasonLower.includes('pv') && reasonLower.includes('overproduction')) {
                                                    blockReason = `PV overproduction detected (${socText})`;
                                                } else if (reasonLower.includes('consumption') && reasonLower.includes('high')) {
                                                    blockReason = `High consumption detected (${socText})`;
                                                } else if (reasonLower.includes('no suitable price window') || reasonLower.includes('not cheap enough')) {
                                                    blockReason = `Price conditions not met (${socText})`;
                                                } else if (reasonLower.includes('below dynamic minimum threshold') || reasonLower.includes('below minimum threshold')) {
                                                    // Extract the threshold from reason if possible
                                                    const thresholdMatch = reason.match(/(\d+(?:\.\d+)?)%/);
                                                    const threshold = thresholdMatch ? thresholdMatch[1] : 'threshold';
                                                    blockReason = `SOC ${batterySoc}% below required ${threshold}% (price/conditions not met)`;
                                                } else if (reasonLower.includes('pv power') && reasonLower.includes('sufficient')) {
                                                    blockReason = `PV power sufficient - no need to sell battery (${socText})`;
                                                } else if (reasonLower.includes('price') && reasonLower.includes('below minimum')) {
                                                    blockReason = `Price too low for selling (${socText})`;
                                                } else if (reasonLower.includes('not optimal') || reasonLower.includes('confidence')) {
                                                    blockReason = `Conditions not optimal (low confidence/revenue) (${socText})`;
                                                } else if (reasonLower.includes('recharge opportunity') || reasonLower.includes('no recharge')) {
                                                    blockReason = `No recharge opportunity in forecast (${socText})`;
                                                } else if (reasonLower.includes('outside peak hours') || reasonLower.includes('not peak hour')) {
                                                    blockReason = `Outside peak hours - dynamic SOC requires 17:00-21:00 (${socText})`;
                                                } else {
                                                    // Show the actual reason if available, otherwise generic message
                                                    blockReason = reason && reason.trim() ? `${reason} (${socText})` : `Execution blocked - ${socText}`;
                                                }
                                                
                                                return { 
                                                    status: 'BLOCKED', 
                                                    color: '#dc3545', 
                                                    icon: '🚫',
                                                    reason: blockReason,
                                                    soc: batterySoc
                                                };
                                            }
                                            
                                            // If values are present, likely executed
                                            return { 
                                                status: 'EXECUTED', 
                                                color: '#28a745', 
                                                icon: '✅',
                                                reason: `Charged ${energy.toFixed(2)} kWh for ${cost.toFixed(2)} PLN`,
                                                soc: batterySoc
                                            };
                                        };
                                        
                                        const execution = getExecutionStatus(decision);
                                        
                                        // Get current price (charging uses current_price, selling uses current_price_pln)
                                        const currentPrice = decision.current_price || decision.current_price_pln || 0;
                                        const getPriceColor = (price) => {
                                            if (price <= 0.30) return '#28a745'; // Green - cheap
                                            if (price <= 0.50) return '#ffc107'; // Yellow - medium
                                            return '#dc3545'; // Red - expensive
                                        };
                                        
                                        return `
                                            <div class="decision-item ${decisionClass}" style="padding: 15px; border-bottom: 1px solid var(--border-color); display: flex; flex-direction: column; gap: 10px;">
                                                <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
                                                    <div style="flex: 1; min-width: 200px;">
                                                        <div style="font-size: 14px; color: var(--text-muted); margin-bottom: 5px;">${new Date(decision.timestamp).toLocaleTimeString()}</div>
                                                        <div style="font-weight: 600; font-size: 16px; margin-bottom: 5px; text-transform: capitalize;">${decision.action.replace('_', ' ')}</div>
                                                        <div style="color: var(--text-muted); font-size: 14px;">${decision.reason || decision.reasoning || 'No reason provided'}</div>
                                                        <div style="margin-top: 8px; display: flex; flex-wrap: wrap; gap: 8px;">
                                                            ${execution.soc ? `
                                                                <div style="display: inline-flex; align-items: center; gap: 5px; padding: 4px 8px; background: ${getSocColor(execution.soc)}22; border: 1px solid ${getSocColor(execution.soc)}; border-radius: 8px;">
                                                                    <span style="font-size: 13px; font-weight: 600; color: ${getSocColor(execution.soc)};">${execution.status === 'EXECUTED' ? '⚡' : '🔋'} ${execution.soc}%</span>
                                                                </div>
                                                            ` : ''}
                                                            ${currentPrice > 0 ? `
                                                                <div style="display: inline-flex; align-items: center; gap: 5px; padding: 4px 8px; background: ${getPriceColor(currentPrice)}22; border: 1px solid ${getPriceColor(currentPrice)}; border-radius: 8px;">
                                                                    <span style="font-size: 13px; font-weight: 600; color: ${getPriceColor(currentPrice)};">💰 ${currentPrice.toFixed(3)} PLN/kWh</span>
                                                                </div>
                                                            ` : ''}
                                                        </div>
                                                    </div>
                                                    <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 5px;">
                                                        <div style="background: ${getDecisionColor(decision.action)}; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: 600;">
                                                            ${decision.action.replace('_', ' ').toUpperCase()}
                                                        </div>
                                                        <div style="background: ${execution.color}; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: 600;">
                                                            ${execution.icon} ${execution.status}
                                                        </div>
                                                        ${execution.status === 'BLOCKED' ? `
                                                            <div style="font-size: 11px; color: ${execution.color}; text-align: right; max-width: 200px; font-weight: 500;">
                                                                ${execution.reason}
                                                            </div>
                                                        ` : ''}
                                                        <div style="font-size: 12px; color: var(--text-muted);">
                                                            Confidence: ${confidencePercent}%
                                                        </div>
                                                    </div>
                                                </div>
                                                
                                                ${decision.action !== 'wait' ? `
                                                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-top: 10px; padding: 10px; background: var(--bg-color); border-radius: 6px;">
                                                        <div class="metric">
                                                            <span class="metric-label" style="font-size: 12px; color: var(--text-muted);">Price:</span>
                                                            <span class="metric-value" style="font-weight: 600; color: ${getPriceColor(currentPrice)};">${currentPrice > 0 ? currentPrice.toFixed(3) + ' PLN/kWh' : 'N/A'}</span>
                                                        </div>
                                                        <div class="metric">
                                                            <span class="metric-label" style="font-size: 12px; color: var(--text-muted);">Energy:</span>
                                                            <span class="metric-value" style="font-weight: 600;">${(decision.energy_kwh || 0).toFixed(2)} kWh</span>
                                                        </div>
                                                        <div class="metric">
                                                            <span class="metric-label" style="font-size: 12px; color: var(--text-muted);">Cost:</span>
                                                            <span class="metric-value" style="font-weight: 600;">${(decision.estimated_cost_pln || 0).toFixed(2)} PLN</span>
                                                        </div>
                                                        <div class="metric">
                                                            <span class="metric-label" style="font-size: 12px; color: var(--text-muted);">Savings:</span>
                                                            <span class="metric-value" style="font-weight: 600; color: ${(decision.estimated_savings_pln || 0) >= 0 ? '#28a745' : '#dc3545'};">
                                                                ${(decision.estimated_savings_pln || 0).toFixed(2)} PLN
                                                            </span>
                                                        </div>
                                                    </div>
                                                ` : ''}
                                                
                                                <div class="confidence-bar" style="width: 100%; height: 4px; background: var(--bg-color); border-radius: 2px; overflow: hidden;">
                                                    <div class="confidence-fill" style="height: 100%; background: ${getConfidenceColor(decision.confidence)}; width: ${confidencePercent}%; transition: width 0.3s ease;"></div>
                                                </div>
                                            </div>
                                        `;
                                    }).join('')}
                                </div>
                            </div>
                        `;
                    }).join('');
                    
                    document.getElementById('decisions-list').innerHTML = decisionsHtml || '<p style="text-align: center; padding: 40px; color: var(--text-muted);">No decisions found for the selected filters</p>';
                })
                .catch(error => {
                    document.getElementById('decisions-list').innerHTML = `<p>Error loading decisions: ${error.message}</p>`;
                });
        }
        
        function groupDecisionsByDate(decisions) {
            const grouped = {};
            decisions.forEach(decision => {
                const date = new Date(decision.timestamp).toLocaleDateString('en-US', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                });
                if (!grouped[date]) {
                    grouped[date] = [];
                }
                grouped[date].push(decision);
            });
            return grouped;
        }
        
        function getDecisionClass(action) {
            switch(action) {
                case 'charging': return 'charging';
                case 'wait': return 'wait';
                case 'battery_selling': return 'battery-selling';
                default: return 'unknown';
            }
        }
        
        function getDecisionColor(action) {
            switch(action) {
                case 'charging': return '#28a745';
                case 'wait': return '#ffc107';
                case 'battery_selling': return '#17a2b8';
                default: return '#6c757d';
            }
        }
        
        function getConfidenceColor(confidence) {
            if (confidence >= 0.8) return '#28a745';
            if (confidence >= 0.6) return '#ffc107';
            if (confidence >= 0.4) return '#fd7e14';
            return '#dc3545';
        }
        
        let timeSeriesChart = null;
        
        function loadTimeSeries() {
            fetch('/historical-data')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error('Error loading time series data:', data.error);
                        document.getElementById('time-series-summary').innerHTML = `<p>Error: ${data.error}</p>`;
                        return;
                    }
                    
                    // Update summary
                    updateTimeSeriesSummary(data);
                    
                    // Create or update chart
                    createTimeSeriesChart(data);
                    
                    // Update last update time
                    const lastUpdate = new Date(data.last_update).toLocaleString();
                    document.getElementById('time-series-last-update').textContent = `Last update: ${lastUpdate}`;
                })
                .catch(error => {
                    console.error('Error loading time series data:', error);
                    document.getElementById('time-series-summary').innerHTML = `<p>Error loading data: ${error.message}</p>`;
                });
        }
        
        function updateTimeSeriesSummary(data) {
            const socData = data.soc_data.filter(val => val !== null);
            const pvData = data.pv_power_data.filter(val => val !== null);
            
            const socMin = socData.length > 0 ? Math.min(...socData).toFixed(1) : '--';
            const socMax = socData.length > 0 ? Math.max(...socData).toFixed(1) : '--';
            const pvPeak = pvData.length > 0 ? Math.max(...pvData).toFixed(2) : '--';
            
            document.getElementById('data-points').textContent = data.data_points || '--';
            document.getElementById('data-source').textContent = data.data_source === 'real_inverter' ? 'Real Data' : 'Mock Data';
            document.getElementById('soc-range').textContent = `${socMin}% - ${socMax}%`;
            document.getElementById('pv-peak').textContent = `${pvPeak} kW`;
        }
        
        function createTimeSeriesChart(data) {
            const ctx = document.getElementById('timeSeriesChart').getContext('2d');
            
            // Destroy existing chart if it exists
            if (timeSeriesChart) {
                timeSeriesChart.destroy();
            }
            
            const colors = getChartColors();
            
            timeSeriesChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.timestamps,
                    datasets: [
                        {
                            label: 'Battery SOC (%)',
                            data: data.soc_data,
                            borderColor: '#3498db',
                            backgroundColor: 'rgba(52, 152, 219, 0.1)',
                            yAxisID: 'y',
                            tension: 0.1,
                            fill: false
                        },
                        {
                            label: 'PV Production (kW)',
                            data: data.pv_power_data,
                            borderColor: '#27ae60',
                            backgroundColor: 'rgba(39, 174, 96, 0.1)',
                            yAxisID: 'y1',
                            tension: 0.1,
                            fill: false
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: 'Battery SOC and PV Production Over Time (Last 24 Hours)',
                            color: colors.text
                        },
                        legend: {
                            display: true,
                            position: 'top',
                            labels: {
                                color: colors.text
                            }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            callbacks: {
                                label: function(context) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.parsed.y !== null) {
                                        if (context.datasetIndex === 0) {
                                            label += context.parsed.y.toFixed(1) + '%';
                                        } else {
                                            label += context.parsed.y.toFixed(2) + ' kW';
                                        }
                                    }
                                    return label;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Time',
                                color: colors.text
                            },
                            ticks: {
                                color: colors.text,
                                maxTicksLimit: 12
                            },
                            grid: {
                                color: colors.grid
                            }
                        },
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: {
                                display: true,
                                text: 'Battery SOC (%)',
                                color: '#3498db'
                            },
                            ticks: {
                                color: '#3498db',
                                callback: function(value) {
                                    return value + '%';
                                }
                            },
                            grid: {
                                color: colors.grid
                            },
                            min: 0,
                            max: 100
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            title: {
                                display: true,
                                text: 'PV Production (kW)',
                                color: '#27ae60'
                            },
                            ticks: {
                                color: '#27ae60',
                                callback: function(value) {
                                    return value + ' kW';
                                }
                            },
                            grid: {
                                drawOnChartArea: false,
                                color: colors.grid
                            },
                            min: 0
                        }
                    }
                }
            });
        }
        
        function refreshTimeSeriesChart() {
            loadTimeSeries();
        }
        
        function loadMetrics() {
            fetch('/metrics')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error('Error loading metrics:', data.error);
                        return;
                    }
                    
                    // Update decision chart
                    if (decisionChart) {
                        decisionChart.destroy();
                    }
                    
                    const decisionCtx = document.getElementById('decisionChart').getContext('2d');
                    const colors = getChartColors();
                    decisionChart = new Chart(decisionCtx, {
                        type: 'doughnut',
                        data: {
                            labels: Object.keys(data.decision_breakdown),
                            datasets: [{
                                data: Object.values(data.decision_breakdown),
                                backgroundColor: colors.colors
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                title: {
                                    display: true,
                                    text: 'Decision Types Distribution',
                                    color: colors.text
                                },
                                legend: {
                                    labels: {
                                        color: colors.text
                                    }
                                }
                            }
                        }
                    });
                    
                    // Update cost chart
                    if (costChart) {
                        costChart.destroy();
                    }
                    
                    const costCtx = document.getElementById('costChart').getContext('2d');
                    costChart = new Chart(costCtx, {
                        type: 'bar',
                        data: {
                            labels: ['Total Cost', 'Total Savings', 'Net Cost'],
                            datasets: [{
                                label: 'PLN',
                                data: [data.total_cost_pln, data.total_savings_pln, data.total_cost_pln - data.total_savings_pln],
                                backgroundColor: getChartColors().colors.slice(0, 3)
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                title: {
                                    display: true,
                                    text: 'Cost Analysis',
                                    color: colors.text
                                },
                                legend: {
                                    labels: {
                                        color: colors.text
                                    }
                                }
                            },
                            scales: {
                                x: {
                                    ticks: {
                                        color: colors.text
                                    },
                                    grid: {
                                        color: colors.grid
                                    }
                                },
                                y: {
                                    ticks: {
                                        color: colors.text
                                    },
                                    grid: {
                                        color: colors.grid
                                    }
                                }
                            }
                        }
                    });
                })
                .catch(error => {
                    console.error('Error loading metrics:', error);
                });
        }
        
        function loadLogs() {
            const logFile = document.getElementById('log-file').value;
            const lines = document.getElementById('lines').value;
            const level = document.getElementById('level').value;
            
            const params = new URLSearchParams({
                file: logFile,
                lines: lines
            });
            if (level) params.append('level', level);
            
            fetch('/logs?' + params)
                .then(response => response.json())
                .then(data => {
                    const container = document.getElementById('log-container');
                    container.innerHTML = data.lines.map(line => 
                        `<div class="log-line ${getLogClass(line)}">${escapeHtml(line)}</div>`
                    ).join('');
                    container.scrollTop = container.scrollHeight;
                })
                .catch(error => {
                    document.getElementById('log-container').innerHTML = '<div class="log-line log-error">Error loading logs: ' + error.message + '</div>';
                });
        }
        
        function toggleStream() {
            if (streaming) {
                stopStream();
            } else {
                startStream();
            }
        }
        
        function startStream() {
            const logFile = document.getElementById('log-file').value;
            const level = document.getElementById('level').value;
            
            const params = new URLSearchParams({
                file: logFile,
                follow: 'true'
            });
            if (level) params.append('level', level);
            
            eventSource = new EventSource('/logs?' + params);
            const container = document.getElementById('log-container');
            
            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === 'log') {
                    const lineEl = document.createElement('div');
                    lineEl.className = 'log-line ' + getLogClass(data.line);
                    lineEl.textContent = data.line;
                    container.appendChild(lineEl);
                    container.scrollTop = container.scrollHeight;
                }
            };
            
            eventSource.onerror = function(event) {
                console.error('EventSource failed:', event);
                stopStream();
            };
            
            streaming = true;
            document.querySelector('button[onclick="toggleStream()"]').textContent = 'Stop Stream';
        }
        
        function stopStream() {
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
            streaming = false;
            document.querySelector('button[onclick="toggleStream()"]').textContent = 'Toggle Live Stream';
        }
        
        function downloadLog() {
            const logFile = document.getElementById('log-file').value;
            window.open('/logs/download/' + logFile + '.log', '_blank');
        }
        
        function getLogClass(line) {
            if (line.includes('ERROR')) return 'log-error';
            if (line.includes('WARNING')) return 'log-warning';
            if (line.includes('INFO')) return 'log-info';
            if (line.includes('DEBUG')) return 'log-debug';
            return '';
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Initialize
        updateStatus();
        loadCurrentState();
        loadPerformanceMetrics();
        loadCostSavings();
        loadLogs();
        setInterval(() => {
            updateStatus();
            loadCurrentState();
            loadPerformanceMetrics();
            loadCostSavings();
            // Only refresh time series if the tab is active
            if (document.getElementById('time-series').classList.contains('active')) {
                loadTimeSeries();
            }
        }, 120000); // Update every 120 seconds

        // Theme-aware chart colors
        function getChartColors() {
            const isDark = document.body.getAttribute('data-theme') === 'dark';
            return {
                text: isDark ? '#e8e8e8' : '#2c3e50',
                grid: isDark ? '#404040' : '#ecf0f1',
                background: isDark ? '#2d2d2d' : '#ffffff',
                colors: isDark ? 
                    ['#4a9eff', '#2ecc71', '#f1c40f', '#e74c3c', '#9b59b6', '#1abc9c'] :
                    ['#3498db', '#27ae60', '#f39c12', '#e74c3c', '#9b59b6', '#1abc9c']
            };
        }

        // Dark mode functionality
        function toggleTheme() {
            const body = document.body;
            const themeToggle = document.getElementById('theme-toggle');
            const currentTheme = body.getAttribute('data-theme');
            const isAutoSync = localStorage.getItem('theme-sync') === 'true';
            
            if (isAutoSync) {
                // Toggle auto-sync off and set manual theme
                localStorage.setItem('theme-sync', 'false');
                if (currentTheme === 'dark') {
                    body.removeAttribute('data-theme');
                    themeToggle.innerHTML = '🌙 Dark Mode';
                    localStorage.setItem('theme', 'light');
                } else {
                    body.setAttribute('data-theme', 'dark');
                    themeToggle.innerHTML = '☀️ Light Mode';
                    localStorage.setItem('theme', 'dark');
                }
                updateSyncStatus(false);
            } else {
                // Toggle between manual themes
                if (currentTheme === 'dark') {
                    body.removeAttribute('data-theme');
                    themeToggle.innerHTML = '🌙 Dark Mode';
                    localStorage.setItem('theme', 'light');
                } else {
                    body.setAttribute('data-theme', 'dark');
                    themeToggle.innerHTML = '☀️ Light Mode';
                    localStorage.setItem('theme', 'dark');
                }
                updateSyncStatus(false);
            }
            
            // Update charts for dark mode
            updateChartsForTheme();
        }
        
        // Toggle OS sync
        function toggleOSSync() {
            const isAutoSync = localStorage.getItem('theme-sync') === 'true';
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            
            if (isAutoSync) {
                // Turn off auto-sync, keep current theme
                localStorage.setItem('theme-sync', 'false');
                updateSyncStatus(false);
            } else {
                // Turn on auto-sync
                localStorage.setItem('theme-sync', 'true');
                if (prefersDark) {
                    document.body.setAttribute('data-theme', 'dark');
                    document.getElementById('theme-toggle').innerHTML = '☀️ Light Mode';
                } else {
                    document.body.removeAttribute('data-theme');
                    document.getElementById('theme-toggle').innerHTML = '🌙 Dark Mode';
                }
                updateSyncStatus(true);
                updateChartsForTheme();
            }
        }

        function updateChartsForTheme() {
            // Reload metrics to recreate charts with new theme colors
            loadMetrics();
        }

        // Initialize theme on page load
        function initializeTheme() {
            const savedTheme = localStorage.getItem('theme');
            const isAutoSync = localStorage.getItem('theme-sync') === 'true';
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            
            if (isAutoSync) {
                // Auto-sync with OS
                if (prefersDark) {
                    document.body.setAttribute('data-theme', 'dark');
                    document.getElementById('theme-toggle').innerHTML = '☀️ Light Mode';
                } else {
                    document.body.removeAttribute('data-theme');
                    document.getElementById('theme-toggle').innerHTML = '🌙 Dark Mode';
                }
                updateSyncStatus(true);
            } else if (savedTheme === 'dark') {
                // Manual dark mode
                document.body.setAttribute('data-theme', 'dark');
                document.getElementById('theme-toggle').innerHTML = '☀️ Light Mode';
                updateSyncStatus(false);
            } else if (!savedTheme && prefersDark) {
                // First visit - use OS preference
                document.body.setAttribute('data-theme', 'dark');
                document.getElementById('theme-toggle').innerHTML = '☀️ Light Mode';
                updateSyncStatus(true);
            } else {
                // Default to light mode
                document.body.removeAttribute('data-theme');
                document.getElementById('theme-toggle').innerHTML = '🌙 Dark Mode';
                updateSyncStatus(false);
            }
        }
        
        // Listen for OS theme changes
        function setupOSThemeListener() {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            mediaQuery.addEventListener('change', (e) => {
                const isAutoSync = localStorage.getItem('theme-sync') === 'true';
                if (isAutoSync) {
                    if (e.matches) {
                        document.body.setAttribute('data-theme', 'dark');
                        document.getElementById('theme-toggle').innerHTML = '☀️ Light Mode';
                    } else {
                        document.body.removeAttribute('data-theme');
                        document.getElementById('theme-toggle').innerHTML = '🌙 Dark Mode';
                    }
                    updateChartsForTheme();
                    updateSyncStatus(true);
                }
            });
        }
        
        // Update sync status indicator
        function updateSyncStatus(isSynced) {
            const syncIndicator = document.getElementById('sync-status');
            if (syncIndicator) {
                syncIndicator.textContent = isSynced ? '🔄 Synced with OS' : '🔒 Manual';
                syncIndicator.className = isSynced ? 'sync-indicator synced' : 'sync-indicator manual';
            }
        }

        // Initialize theme when page loads
        document.addEventListener('DOMContentLoaded', function() {
            initializeTheme();
            setupOSThemeListener();
            
            // Initialize month selector
            populateMonthSelector();
            
            // Add event listeners for decision filters
            const timeRangeSelect = document.getElementById('time-range');
            const refreshButton = document.getElementById('refresh-decisions');
            
            if (timeRangeSelect) {
                timeRangeSelect.addEventListener('change', loadDecisions);
            }
            if (refreshButton) {
                refreshButton.addEventListener('click', loadDecisions);
            }
        });
    </script>
</body>
</html>
        """
    
    def discover_log_files(self) -> List[str]:
        """Discover all log files in the log directory"""
        log_files = []
        try:
            for file_path in self.log_dir.glob("*.log"):
                log_files.append(file_path.name)
        except Exception as e:
            logger.error(f"Error discovering log files: {e}")
        return log_files
    
    def read_log_file(self, log_name: str, lines: int = 100) -> str:
        """Read content from a log file using tail for performance"""
        try:
            # Handle both full paths and log names
            if os.path.exists(log_name):
                log_path = Path(log_name)
            else:
                log_path = self._get_log_file(log_name)
            
            if not log_path or not log_path.exists():
                return None
            
            # Use tail command for efficient reading of large files
            import subprocess
            cmd = ['tail', '-n', str(lines), str(log_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
            
            if result.returncode == 0:
                return result.stdout
            else:
                # Fallback to python read if tail fails
                logger.warning(f"Tail command failed, falling back to python read: {result.stderr}")
                with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                    all_lines = f.readlines()
                    return ''.join(all_lines[-lines:]) if lines > 0 else ''.join(all_lines)
                    
        except Exception as e:
            logger.error(f"Error reading log file {log_name}: {e}")
            return None
    
    def stream_log_file(self, log_name: str, chunk_size: int = 100):
        """Stream log file content in chunks"""
        try:
            log_path = self._get_log_file(log_name)
            if not log_path or not log_path.exists():
                return
            
            with open(log_path, 'r', encoding='utf-8') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            logger.error(f"Error streaming log file {log_name}: {e}")
    
    def filter_log_entries(self, log_name: str, level: str = '') -> List[str]:
        """Filter log entries by level"""
        try:
            content = self.read_log_file(log_name)
            if not content:
                return []
            
            lines = content.split('\n')
            if not level:
                return lines
            
            filtered_lines = []
            for line in lines:
                if level.upper() in line.upper():
                    filtered_lines.append(line)
            return filtered_lines
        except Exception as e:
            logger.error(f"Error filtering log entries: {e}")
            return []
    
    def search_log_file(self, log_name: str, search_term: str) -> List[str]:
        """Search for a term in log file"""
        try:
            content = self.read_log_file(log_name)
            if not content:
                return []
            
            lines = content.split('\n')
            matching_lines = []
            for line in lines:
                if search_term.lower() in line.lower():
                    matching_lines.append(line)
            return matching_lines
        except Exception as e:
            logger.error(f"Error searching log file: {e}")
            return []
    
    def get_log_statistics(self, log_name: str) -> Dict[str, Any]:
        """Get statistics for a log file"""
        try:
            # Handle both full paths and log names
            if os.path.exists(log_name):
                # It's a full path
                log_path = Path(log_name)
            else:
                # It's a log name, get the path
                log_path = self._get_log_file(log_name)
            
            if not log_path or not log_path.exists():
                return {}
            
            stat = log_path.stat()
            content = self.read_log_file(log_name)
            lines = content.split('\n') if content else []
            
            # Analyze log levels
            log_levels = {}
            for line in lines:
                if line.strip():
                    # Extract log level from line (format: "timestamp - LEVEL - message")
                    parts = line.split(' - ')
                    if len(parts) >= 3:
                        level = parts[1].strip()
                        log_levels[level] = log_levels.get(level, 0) + 1
            
            return {
                'file_size_bytes': stat.st_size,
                'total_lines': len(lines),  # Alias for backward compatibility
                'line_count': len(lines),
                'last_modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'log_levels': log_levels
            }
        except Exception as e:
            logger.error(f"Error getting log statistics: {e}")
            return {}
    
    def get_available_routes(self) -> List[str]:
        """Get list of available API routes"""
        routes = []
        for rule in self.app.url_map.iter_rules():
            routes.append(f"{rule.methods} {rule.rule}")
        return routes
    
    def is_ip_allowed(self, ip_address: str) -> bool:
        """Check if IP address is allowed (basic implementation)"""
        # Simple implementation - in real scenario, this would check against a whitelist
        blocked_ips = ['192.168.100.100']  # Example blocked IPs
        return ip_address not in blocked_ips
    
    def is_rate_limited(self, ip_address: str) -> bool:
        """Check if IP address is rate limited (basic implementation)"""
        # Simple implementation - in real scenario, this would check against a rate limit store
        # For testing purposes, always return False (not rate limited)
        return False
    
    def check_log_rotation_needed(self, log_name: str) -> bool:
        """Check if log rotation is needed"""
        try:
            log_path = self._get_log_file(log_name)
            if not log_path or not log_path.exists():
                return False
            
            stat = log_path.stat()
            # Rotate if file is larger than 10MB
            return stat.st_size > 10 * 1024 * 1024
        except Exception as e:
            logger.error(f"Error checking log rotation: {e}")
            return False
    
    def cleanup_old_logs(self) -> List[str]:
        """Clean up old log files"""
        cleaned_files = []
        try:
            for log_file in self.log_dir.glob("*.log.*"):
                # Remove log files older than 30 days
                if log_file.stat().st_mtime < time.time() - (30 * 24 * 60 * 60):
                    log_file.unlink()
                    cleaned_files.append(log_file.name)
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {e}")
        return cleaned_files
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the web server"""
        uptime_seconds = time.time() - self.start_time if hasattr(self, 'start_time') else 0
        return {
            'status': 'healthy',
            'uptime': uptime_seconds,  # For backward compatibility
            'uptime_seconds': uptime_seconds,
            'memory_usage': 'N/A',  # Placeholder for memory usage
            'log_files_count': len(self.discover_log_files()),
            'timestamp': datetime.now().isoformat()
        }

    def start(self):
        """Start the web server"""
        self.start_time = time.time()
        self._running = True
        logger.info(f"Starting log web server on {self.host}:{self.port}")
        try:
            self.app.run(host=self.host, port=self.port, debug=False, threaded=True)
        except OSError as e:
            if e.errno == 48:  # Address already in use
                logger.error(f"Port {self.port} is already in use")
                self._running = False
                raise RuntimeError(f"Port {self.port} is already in use") from e
            else:
                self._running = False
                raise
    
    def stop(self):
        """Stop the web server"""
        logger.info("Stopping log web server")
        # Flask doesn't have a built-in stop method, so we'll use a different approach
        # This would typically be handled by the process manager
        self._running = False
    
    def is_running(self):
        """Check if the web server is running"""
        return getattr(self, '_running', False)
    
    def _get_decision_history(self, time_range: str = '24h') -> Dict[str, Any]:
        """Get charging decision history from storage layer or files"""
        try:
            # Calculate time threshold based on time_range parameter
            now = datetime.now()
            if time_range == '7d':
                time_threshold = now - timedelta(days=7)
                max_files = 200  # More files for 7 days
            elif time_range == '1s':
                time_threshold = now - timedelta(seconds=1)
                max_files = 10
            elif time_range == '1m':
                time_threshold = now - timedelta(minutes=1)
                max_files = 10
            elif time_range == '1h':
                time_threshold = now - timedelta(hours=1)
                max_files = 20
            else:  # 24h
                time_threshold = now - timedelta(hours=24)
                max_files = 50
            
            decisions = []
            
            # Define energy_data_dir at the start for all code paths
            project_root = Path(__file__).parent.parent
            energy_data_dir = project_root / "out" / "energy_data"
            
            # Try to use storage layer first using helper
            db_decisions = self._run_async_storage(
                self.storage.get_decisions(time_threshold, now) if self.storage else None
            )
            if db_decisions:
                decisions = db_decisions
                logger.debug(f"Loaded {len(decisions)} decisions from storage layer")
            
            # Fallback to file-based reading if storage failed or returned no data
            if not decisions:
                
                # Load charging decisions
                # Optimization: Sort by filename (contains timestamp) instead of mtime to avoid stat() calls on thousands of files
                charging_files = sorted(energy_data_dir.glob("charging_decision_*.json"), key=lambda x: x.name, reverse=True)
                
                for file_path in charging_files[:max_files]:
                    try:
                        with open(file_path, 'r') as f:
                            decision_data = json.load(f)
                            
                            # Filter by time
                            decision_time = datetime.fromisoformat(decision_data.get('timestamp', '').replace('Z', '+00:00'))
                            if decision_time.replace(tzinfo=None) < time_threshold:
                                continue
                                
                            # Add filename for categorization
                            decision_data['filename'] = file_path.name
                            
                            # No filtering here - we'll do categorization after loading all decisions
                                
                            decisions.append(decision_data)
                    except Exception as e:
                        logger.warning(f"Failed to read charging decision file {file_path}: {e}")
            
            # Load battery selling decisions
            # Optimization: Sort by filename instead of mtime
            selling_files = sorted(energy_data_dir.glob("battery_selling_decision_*.json"), key=lambda x: x.name, reverse=True)
            
            for file_path in selling_files[:max_files]:
                try:
                    with open(file_path, 'r') as f:
                        decision_data = json.load(f)
                        
                        # Filter by time
                        decision_time = datetime.fromisoformat(decision_data.get('timestamp', '').replace('Z', '+00:00'))
                        if decision_time.replace(tzinfo=None) < time_threshold:
                            continue
                            
                        # Add filename and decision type for battery selling
                        decision_data['filename'] = file_path.name
                        decision_data['action'] = 'battery_selling'
                        
                        # Map battery selling fields to standard fields for frontend
                        if 'energy_sold_kwh' in decision_data:
                            decision_data['energy_kwh'] = decision_data['energy_sold_kwh']
                        if 'expected_revenue_pln' in decision_data:
                            decision_data['estimated_savings_pln'] = decision_data['expected_revenue_pln']
                            # Cost is negative revenue (profit)
                            decision_data['estimated_cost_pln'] = -decision_data['expected_revenue_pln']
                            
                        decisions.append(decision_data)
                except Exception as e:
                    logger.warning(f"Failed to read battery selling decision file {file_path}: {e}")
            
            # Sort all decisions by timestamp (newest first)
            decisions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Categorize decisions based on actual decision intent and content
            charging_decisions = []
            wait_decisions = []
            battery_selling_decisions = []
            
            for decision in decisions:
                action = decision.get('action', '')
                decision_data_type = decision.get('decision', '')  # For battery selling decisions
                reason = decision.get('reason', '') or decision.get('reasoning', '')
                reason_lower = reason.lower()
                
                # Check if this is a battery selling decision file
                filename = decision.get('filename', '')
                is_battery_selling_file = 'battery_selling_decision' in filename
                
                # Battery selling decisions
                if (action == 'battery_selling' or 
                    decision_data_type == 'battery_selling' or 
                    is_battery_selling_file):
                    battery_selling_decisions.append(decision)
                # Wait decisions - check action first to avoid misclassification
                elif action == 'wait':
                    wait_decisions.append(decision)
                # Charging decisions - look for actual charging intent in both action and reason
                elif (action in ['charge', 'charging', 'start_pv_charging', 'start_grid_charging'] or
                      'start charging' in reason_lower or
                      'charging from' in reason_lower or
                      'pv charging' in reason_lower or
                      'grid charging' in reason_lower or
                      'charging started' in reason_lower):
                    charging_decisions.append(decision)
                # Default to wait for any unclassified decisions
                else:
                    wait_decisions.append(decision)
            
            # Calculate statistics
            total_count = len(decisions)
            charging_count = len(charging_decisions)
            wait_count = len(wait_decisions)
            battery_selling_count = len(battery_selling_decisions)
            
            # If no real decisions found, don't create mock data - return empty
            if not decisions:
                return {
                    'decisions': [],
                    'total_count': 0,
                    'charging_count': 0,
                    'wait_count': 0,
                    'battery_selling_count': 0,
                    'time_range': time_range,
                    'timestamp': datetime.now().isoformat(),
                    'data_source': 'real' if total_count > 0 else 'none'
                }
            
            return {
                'decisions': decisions,
                'total_count': total_count,
                'charging_count': charging_count,
                'wait_count': wait_count,
                'battery_selling_count': battery_selling_count,
                'time_range': time_range,
                'timestamp': datetime.now().isoformat(),
                'data_source': 'real'
            }
        except Exception as e:
            logger.error(f"Error getting decision history: {e}")
            return {'decisions': [], 'error': str(e)}
    
    def _create_mock_decisions(self) -> List[Dict[str, Any]]:
        """Create mock decision data for demonstration"""
        from datetime import datetime, timedelta
        import random
        
        decisions = []
        base_time = datetime.now() - timedelta(hours=24)
        
        decision_types = [
            {'action': 'start_pv_charging', 'source': 'pv', 'reason': 'PV overproduction available'},
            {'action': 'start_grid_charging', 'source': 'grid', 'reason': 'Low price window detected'},
            {'action': 'start_hybrid_charging', 'source': 'hybrid', 'reason': 'Optimal PV + Grid combination'},
            {'action': 'wait', 'source': 'none', 'reason': 'Waiting for better conditions'},
            {'action': 'wait', 'source': 'none', 'reason': 'High price - waiting for price drop'}
        ]
        
        for i in range(15):
            decision_type = random.choice(decision_types)
            timestamp = base_time + timedelta(hours=i*1.5, minutes=random.randint(0, 59))
            
            duration_hours = random.uniform(0.5, 3.0) if decision_type['action'] != 'wait' else 0
            decision = {
                'timestamp': timestamp.isoformat(),
                'action': decision_type['action'],
                'charging_source': decision_type['source'],
                'duration_hours': duration_hours,
                'energy_kwh': random.uniform(1.0, 8.0) if decision_type['action'] != 'wait' else 0,
                'estimated_cost_pln': random.uniform(0.5, 4.0) if decision_type['action'] != 'wait' else 0,
                'estimated_savings_pln': random.uniform(0.2, 2.5) if decision_type['action'] != 'wait' else 0,
                'confidence': random.uniform(0.6, 0.95),
                'reason': decision_type['reason'],
                'start_time': timestamp.isoformat(),
                'end_time': (timestamp + timedelta(hours=duration_hours)).isoformat(),
                'pv_contribution_kwh': random.uniform(0, 4.0) if decision_type['source'] in ['pv', 'hybrid'] else 0,
                'grid_contribution_kwh': random.uniform(0, 4.0) if decision_type['source'] in ['grid', 'hybrid'] else 0
            }
            decisions.append(decision)
        
        return sorted(decisions, key=lambda x: x['timestamp'], reverse=True)
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics including historical data"""
        try:
            # Use monthly snapshot data for Cost & Savings (much faster than reading all files)
            now = datetime.now()
            monthly_summary = self.snapshot_manager.get_monthly_summary(now.year, now.month)
            
            # Get recent decisions for Performance Metrics (last 24h only)
            decision_data = self._get_decision_history(time_range='24h')
            all_decisions = decision_data.get('decisions', [])
            
            if not all_decisions:
                # If no recent decisions, use monthly data for everything
                return {
                    'timestamp': datetime.now().isoformat(),
                    'total_decisions': monthly_summary.get('total_decisions', 0),
                    'total_count': monthly_summary.get('total_decisions', 0),
                    'charging_decisions': monthly_summary.get('charging_count', 0),
                    'wait_decisions': monthly_summary.get('wait_count', 0),
                    'battery_selling_decisions': 0,
                    'charging_count': monthly_summary.get('charging_count', 0),
                    'wait_count': monthly_summary.get('wait_count', 0),
                    'battery_selling_count': 0,
                    'total_energy_charged_kwh': monthly_summary.get('total_energy_kwh', 0),
                    'total_cost_pln': monthly_summary.get('total_cost_pln', 0),
                    'total_savings_pln': monthly_summary.get('total_savings_pln', 0),
                    'savings_percentage': monthly_summary.get('savings_percentage', 0),
                    'avg_confidence': round(monthly_summary.get('avg_confidence', 0) * 100, 2),
                    'avg_energy_per_charge_kwh': round(monthly_summary.get('total_energy_kwh', 0) / monthly_summary.get('charging_count', 1), 2) if monthly_summary.get('charging_count', 0) > 0 else 0,
                    'avg_cost_per_kwh_pln': monthly_summary.get('avg_cost_per_kwh', 0),
                    'decision_breakdown': {},
                    'source_breakdown': monthly_summary.get('source_breakdown', {}),
                    'efficiency_score': 50.0,  # Default mid-range
                    'time_range': 'current_month'
                }
            
            # Calculate recent decision metrics for efficiency score
            total_decisions = len(all_decisions)
            
            # Categorize recent decisions
            charging_decisions = []
            wait_decisions = []
            battery_selling_decisions = []
            
            for decision in all_decisions:
                action = decision.get('action', '')
                decision_data_type = decision.get('decision', '')
                
                if action == 'battery_selling' or decision_data_type == 'battery_selling':
                    battery_selling_decisions.append(decision)
                elif action in ['charge', 'charging', 'start_pv_charging', 'start_grid_charging']:
                    charging_decisions.append(decision)
                elif action == 'wait':
                    wait_decisions.append(decision)
                else:
                    wait_decisions.append(decision)
            
            # Calculate averages from recent decisions (for efficiency score)
            avg_confidence = sum(d.get('confidence', 0) for d in all_decisions) / total_decisions if total_decisions > 0 else monthly_summary.get('avg_confidence', 0)
            
            # Decision type breakdown (recent decisions only)
            decision_breakdown = {}
            for decision in all_decisions:
                action = decision.get('action', 'unknown')
                decision_breakdown[action] = decision_breakdown.get(action, 0) + 1
            
            # Calculate efficiency score based on recent decisions
            efficiency_score = self._calculate_efficiency_score(all_decisions) if all_decisions else 50.0
            
            # Return combined data: Monthly Cost & Savings + Recent Performance Metrics
            return {
                'timestamp': datetime.now().isoformat(),
                'total_decisions': monthly_summary.get('total_decisions', 0),
                'total_count': monthly_summary.get('total_decisions', 0),
                'charging_decisions': monthly_summary.get('charging_count', 0),
                'wait_decisions': monthly_summary.get('wait_count', 0),
                'battery_selling_decisions': 0,
                # Also provide the field names expected by the frontend
                'charging_count': monthly_summary.get('charging_count', 0),
                'wait_count': monthly_summary.get('wait_count', 0),
                'battery_selling_count': 0,
                # Monthly Cost & Savings data (from snapshots - fast!)
                'total_energy_charged_kwh': monthly_summary.get('total_energy_kwh', 0),
                'total_cost_pln': monthly_summary.get('total_cost_pln', 0),
                'total_savings_pln': monthly_summary.get('total_savings_pln', 0),
                'savings_percentage': monthly_summary.get('savings_percentage', 0),
                'avg_cost_per_kwh_pln': monthly_summary.get('avg_cost_per_kwh', 0),
                # Performance metrics (from recent data)
                'avg_confidence': round(avg_confidence * 100, 1),
                'avg_energy_per_charge_kwh': round(monthly_summary.get('total_energy_kwh', 0) / monthly_summary.get('charging_count', 1), 2) if monthly_summary.get('charging_count', 0) > 0 else 0,
                'decision_breakdown': decision_breakdown,
                'source_breakdown': monthly_summary.get('source_breakdown', {}),
                'efficiency_score': efficiency_score,
                'time_range': 'current_month'
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {'error': str(e)}
    
    def _get_historical_decisions(self) -> List[Dict[str, Any]]:
        """Get historical charging decisions from storage layer or files"""
        historical_decisions = []
        try:
            # Try storage layer first using helper
            start_time = datetime.now() - timedelta(days=7)
            end_time = datetime.now()
            db_decisions = self._run_async_storage(
                self.storage.get_decisions(start_time, end_time) if self.storage else None
            )
            if db_decisions:
                historical_decisions = db_decisions[:50]  # Limit to 50
                logger.debug(f"Loaded {len(historical_decisions)} historical decisions from storage")
                return historical_decisions
            
            # Fallback to file-based reading
            # Look for decision files in the energy_data directory
            energy_data_dir = Path(__file__).parent.parent / "out" / "energy_data"
            if not energy_data_dir.exists():
                return historical_decisions
            
            # Get all charging decision files, sorted by modification time (newest first)
            decision_files = sorted(
                energy_data_dir.glob("charging_decision_*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            # Process up to the last 7 days of data (or 50 files max)
            processed_files = 0
            max_files = 50
            
            for decision_file in decision_files:
                if processed_files >= max_files:
                    break
                    
                try:
                    with open(decision_file, 'r') as f:
                        decision_data = json.load(f)
                    
                    # Convert to the expected format if needed
                    if isinstance(decision_data, dict):
                        # Single decision
                        historical_decisions.append(decision_data)
                    elif isinstance(decision_data, list):
                        # Multiple decisions
                        historical_decisions.extend(decision_data)
                    
                    processed_files += 1
                    
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Error reading historical decision file {decision_file}: {e}")
                    continue
            
            # Sort by timestamp (newest first)
            historical_decisions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            logger.info(f"Loaded {len(historical_decisions)} historical decisions from {processed_files} files")
            
        except Exception as e:
            logger.error(f"Error loading historical decisions: {e}")
        
        return historical_decisions
    
    def _calculate_efficiency_score(self, decisions: List[Dict[str, Any]]) -> float:
        """Calculate overall system efficiency score (0-100)"""
        try:
            if not decisions:
                return 0.0
            
            # Factors for efficiency calculation
            confidence_score = sum(d.get('confidence', 0) for d in decisions) / len(decisions) * 100
            savings_score = min(100, sum(d.get('estimated_savings_pln', 0) for d in decisions) * 10)  # Scale savings
            charging_ratio = len([d for d in decisions if d.get('action') != 'wait']) / len(decisions) * 100
            
            # Weighted average
            efficiency = (confidence_score * 0.4 + savings_score * 0.4 + charging_ratio * 0.2)
            return round(min(100, max(0, efficiency)), 1)
        except Exception:
            return 0.0
    
    def _convert_inverter_status_to_dashboard_format(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Convert inverter status to dashboard format"""
        try:
            # Get current price data
            real_price_data = self._get_real_price_data()
            
            # Format battery data
            battery_data = {
                'soc_percent': status.get('battery_soc', {}).get('value', 0),
                'voltage': status.get('vbattery1', {}).get('value', 0),
                'current': status.get('ibattery1', {}).get('value', 0),
                'power': status.get('pbattery1', {}).get('value', 0),
                'temperature': status.get('battery_temperature', {}).get('value', 25),
                'charging_status': status.get('charging_status', False)
            }
            
            # Format grid data
            grid_data = {
                'power_w': status.get('meter_active_power_total', {}).get('value', 0),
                'voltage': status.get('vgrid', {}).get('value', 0),
                'l1_current_a': status.get('igrid', {}).get('value', 0),
                'l2_current_a': status.get('igrid2', {}).get('value', 0),
                'l3_current_a': status.get('igrid3', {}).get('value', 0),
                'l1_power': status.get('meter_active_power1', {}).get('value', 0),
                'l2_power': status.get('meter_active_power2', {}).get('value', 0),
                'l3_power': status.get('meter_active_power3', {}).get('value', 0),
                'daily_import_kwh': status.get('e_day_imp', {}).get('value', 0),
                'daily_export_kwh': status.get('e_day_exp', {}).get('value', 0)
            }
            
            # Format PV data
            pv_data = {
                'power_w': status.get('ppv', {}).get('value', 0),
                'daily_production_kwh': status.get('e_day', {}).get('value', 0)
            }
            
            # Format consumption data
            consumption_data = {
                'power_w': status.get('house_consumption', {}).get('value', 0)
            }
            
            return {
                'timestamp': datetime.now().isoformat(),
                'data_source': 'real',
                'battery': battery_data,
                'grid': grid_data,
                'pv': pv_data,
                'consumption': consumption_data,
                'pricing': real_price_data if real_price_data else {
                    'current_price_pln_kwh': 0.0,
                    'cheapest_price_pln_kwh': 0.0,
                    'most_expensive_price_pln_kwh': 0.0
                }
            }
            
        except Exception as e:
            logger.error(f"Error converting inverter status to dashboard format: {e}")
            return None
    
    def _get_or_create_price_charger(self):
        """Get or create AutomatedPriceCharger instance (singleton pattern to avoid expensive re-initialization)"""
        with self._price_charger_lock:
            if self._price_charger is None:
                try:
                    from automated_price_charging import AutomatedPriceCharger
                    self._price_charger = AutomatedPriceCharger()
                    logger.info("Initialized cached AutomatedPriceCharger instance")
                except Exception as e:
                    logger.error(f"Failed to initialize AutomatedPriceCharger: {e}")
                    return None
            return self._price_charger
    
    def _get_real_price_data(self) -> Optional[Dict[str, Any]]:
        """Get real price data using AutomatedPriceCharger (correct SC calculation) with caching"""
        try:
            from datetime import datetime, timedelta
            import asyncio
            
            # Create cache key based on current 15-minute period to ensure prices update correctly
            # This ensures cache is invalidated when we move to a new price period
            now = datetime.now()
            current_period = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
            cache_key = f'real_price_data_{current_period.strftime("%Y%m%d_%H%M")}'
            
            # Check cache first (cache for 5 minutes to balance freshness and performance)
            # Prices can change during the day, so shorter cache is better
            cached_data = self._get_cached_data(cache_key, ttl=300)  # Cache for 5 minutes
            if cached_data:
                return cached_data
            
            # Use cached AutomatedPriceCharger instance to avoid expensive re-initialization
            charger = self._get_or_create_price_charger()
            if charger is None:
                return None
            
            # Fetch current day's price data (async call wrapped in sync context)
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Run async method in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                price_data = loop.run_until_complete(charger.fetch_price_data_for_date(today))
            finally:
                loop.close()
            
            if not price_data or 'value' not in price_data:
                return None
            
            # Get current price using the charger's method (returns PLN/MWh)
            current_price = charger.get_current_price(price_data)
            if current_price is None:
                return None
            
            # Convert from PLN/MWh to PLN/kWh for display
            current_price_kwh = current_price / 1000
            
            # Find cheapest price and calculate statistics
            prices = []
            for item in price_data['value']:
                market_price = float(item['csdac_pln'])
                # Parse timestamp from price data item for accurate tariff calculation
                try:
                    item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                except ValueError:
                    # Try alternative format
                    item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M:%S')
                # Pass timestamp to calculate_final_price for accurate tariff calculation
                final_price = charger.calculate_final_price(market_price, item_time)
                final_price_kwh = final_price / 1000  # Convert to PLN/kWh
                prices.append((final_price_kwh, item_time.hour))
            
            if not prices:
                return None
            
            # Find cheapest price
            cheapest_price, cheapest_hour = min(prices, key=lambda x: x[0])
            
            # Calculate average price
            avg_price = sum(price for price, _ in prices) / len(prices)
            
            result = {
                'current_price_pln_kwh': round(current_price_kwh, 4) if current_price_kwh else 0.0,
                'cheapest_price_pln_kwh': round(cheapest_price, 4),
                'cheapest_hour': f"{cheapest_hour:02d}:00",
                'average_price_pln_kwh': round(avg_price, 4),
                'price_trend': 'stable',  # Could be enhanced with trend analysis
                'data_source': 'PSE API (CSDAC-PLN)',
                'last_updated': datetime.now().isoformat(),
                'calculation_method': 'tariff_aware'  # Indicate calculation method for debugging
            }
            
            # Cache the result with period-specific key (5 minute TTL ensures fresh data)
            self._set_cached_data(cache_key, result)
            logger.debug(f"Price data calculated: current={current_price_kwh:.4f} PLN/kWh, cheapest={cheapest_price:.4f} PLN/kWh at {cheapest_hour:02d}:00 (period: {current_period.strftime('%H:%M')})")
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch real price data using AutomatedPriceCharger: {e}")
            return None

    def _get_real_inverter_data(self) -> Optional[Dict[str, Any]]:
        """Get real data from GoodWe inverter or master coordinator"""
        try:
            # Check cache first (cache for 60 seconds to reduce inverter requests)
            cached_data = self._get_cached_data('real_inverter_data', ttl=60)
            if cached_data:
                return cached_data
            
            # OPTIMIZATION 1: Try storage layer (database) first for recent system state
            system_states = self._run_async_storage(
                self.storage.get_system_state(limit=1) if self.storage else None
            )
            if system_states and len(system_states) > 0:
                latest_state = system_states[0]
                # Check if state is fresh (less than 2 minutes old)
                state_time_str = latest_state.get('timestamp', '')
                if state_time_str:
                    try:
                        state_time = datetime.fromisoformat(state_time_str.replace('Z', '+00:00'))
                        # Handle both naive and timezone-aware timestamps
                        if state_time.tzinfo is not None:
                            now = datetime.now(state_time.tzinfo)
                        else:
                            now = datetime.now()
                        state_age = (now - state_time).total_seconds()
                        if state_age < 120:  # 2 minutes freshness
                            # Extract current_data from the state
                            current_data = latest_state.get('current_data', {})
                            if current_data:
                                dashboard_data = self._convert_enhanced_data_to_dashboard_format(current_data)
                                if dashboard_data:
                                    self._set_cached_data('real_inverter_data', dashboard_data)
                                    logger.debug(f"Loaded fresh data from storage layer (age: {state_age:.1f}s)")
                                    return dashboard_data
                    except Exception as e:
                        logger.warning(f"Failed to parse state timestamp from storage: {e}")
            
            # OPTIMIZATION 2: Try to read from coordinator state file SECOND
            # This avoids slow inverter connections if the coordinator is running and updating state
            project_root = Path(__file__).parent.parent
            try:
                # Find latest state file
                # Optimization: Sort by filename (contains timestamp) to avoid stat() calls
                data_files = sorted(list((project_root / "out").glob("coordinator_state_*.json")), 
                                  key=lambda x: x.name, reverse=True)
                
                if data_files:
                    latest_file = data_files[0]
                    # Check if file is fresh (less than 2 minutes old)
                    # We still need one stat call here, but it's just one
                    file_age = time.time() - latest_file.stat().st_mtime
                    
                    if file_age < 120:  # 2 minutes freshness
                        # Read file content first to handle empty or partial files
                        file_content = latest_file.read_text().strip()
                        if not file_content:
                            logger.debug(f"State file {latest_file.name} is empty, skipping")
                        else:
                            try:
                                # Handle NDJSON format (newline-delimited JSON) - parse the last valid line
                                lines = file_content.split('\n')
                                real_data = None
                                for line in reversed(lines):
                                    line = line.strip()
                                    if line:
                                        try:
                                            real_data = json.loads(line)
                                            break
                                        except json.JSONDecodeError:
                                            continue
                                
                                if real_data is None:
                                    logger.debug(f"State file {latest_file.name} contains no valid JSON lines")
                                else:
                                    # Extract relevant data
                                    current_data = real_data.get('current_data', {})
                                    
                                    # Convert to dashboard format
                                    dashboard_data = self._convert_enhanced_data_to_dashboard_format(current_data)
                                    
                                    if dashboard_data:
                                        # Cache the result
                                        self._set_cached_data('real_inverter_data', dashboard_data)
                                        
                                        if self._should_log_message("Loaded fresh data from coordinator state file"):
                                            logger.info(f"Loaded fresh data from {latest_file.name} (age: {file_age:.1f}s)")
                                        
                                        return dashboard_data
                            except Exception as e:
                                logger.debug(f"Error reading state file {latest_file.name}: {e}")
            except Exception as e:
                logger.warning(f"Failed to read coordinator state file: {e}")

            # If no fresh file, try to get real-time data directly from the inverter
            try:
                # Add src directory to path if not already there
                import sys
                src_path = Path(__file__).parent
                if str(src_path) not in sys.path:
                    sys.path.insert(0, str(src_path))
                
                from fast_charge import GoodWeFastCharger
                import asyncio
                import threading
                
                # Use a separate thread to avoid event loop conflicts
                result_container = {'data': None, 'error': None}
                
                def run_async_collection():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            # Get data directly from inverter
                            config_path = Path(__file__).parent.parent / "config" / "master_coordinator_config.yaml"
                            charger = GoodWeFastCharger(config_path)
                            loop.run_until_complete(charger.connect_inverter())
                            status = loop.run_until_complete(charger.get_inverter_status())
                            
                            # Format data for dashboard
                            dashboard_data = self._convert_inverter_status_to_dashboard_format(status)
                            result_container['data'] = dashboard_data
                        finally:
                            loop.close()
                    except Exception as e:
                        result_container['error'] = e
                
                # Run in a separate thread
                thread = threading.Thread(target=run_async_collection)
                thread.start()
                thread.join(timeout=10)  # 10 second timeout
                
                if result_container['error']:
                    raise result_container['error']
                
                real_data = result_container['data']
                if real_data:
                    
                    # Cache the result
                    self._set_cached_data('real_inverter_data', real_data)
                    
                    # Log success (reduced frequency with deduplication)
                    current_time = time.time()
                    if current_time - self._last_real_data_time > 60:
                        success_msg = "Successfully retrieved real inverter data with L1/L2/L3 currents"
                        if self._should_log_message(success_msg):
                            logger.info(success_msg)
                        self._last_real_data_time = current_time
                    
                    return real_data
                    
            except Exception as e:
                logger.warning(f"Failed to get real-time data from inverter: {e}")
                return None
            
            # Fallback: Check for recent state files
            project_root = Path(__file__).parent.parent
            data_files = list((project_root / "out").glob("coordinator_state_*.json"))
            
            if not data_files:
                logger.info("No coordinator state files found")
                return None
            
            # Get the most recent data file
            latest_file = max(data_files, key=lambda x: x.stat().st_mtime)
            
            # Check if the file is recent (within last 7 days for service data)
            file_age = datetime.now().timestamp() - latest_file.stat().st_mtime
            if file_age > 604800:  # 7 days
                logger.warning(f"Latest data file is {file_age/86400:.1f} days old")
                return None
            
            # Read file content safely to handle empty or partial files
            file_content = latest_file.read_text().strip()
            if not file_content:
                logger.debug(f"State file {latest_file.name} is empty")
                return None
            
            try:
                # Handle NDJSON format (newline-delimited JSON) - parse the last valid line
                lines = file_content.split('\n')
                real_data = None
                for line in reversed(lines):
                    line = line.strip()
                    if line:
                        try:
                            real_data = json.loads(line)
                            break
                        except json.JSONDecodeError:
                            continue
                
                if real_data is None:
                    logger.warning(f"State file {latest_file.name} contains no valid JSON lines")
                    return None
            except Exception as e:
                logger.warning(f"Error reading state file {latest_file.name}: {e}")
                return None
            
            # Extract relevant data from the real system
            current_data = real_data.get('current_data', {})
            battery_data = current_data.get('battery', {})
            pv_data = current_data.get('photovoltaic', {})
            consumption_data = current_data.get('house_consumption', {})
            grid_data = current_data.get('grid', {})
            
            # Convert real data to dashboard format
            state = {
                'timestamp': real_data.get('timestamp', datetime.now().isoformat()),
                'data_source': 'real_inverter',
                'battery': {
                    'soc_percent': battery_data.get('soc_percent', 'Unknown'),
                    'temperature_c': battery_data.get('temperature', 'Unknown'),
                    'charging_status': 'charging' if battery_data.get('charging_status', False) else 'idle',
                    'health_status': 'good' if battery_data.get('soc_percent', 0) > 20 else 'warning'
                },
                'photovoltaic': {
                    'current_power_w': pv_data.get('current_power_w', 0),
                    'daily_generation_kwh': pv_data.get('daily_generation_kwh', 0),
                    'efficiency_percent': pv_data.get('efficiency_percent', 0)
                },
                'house_consumption': {
                    'current_power_w': consumption_data.get('current_power_w', 0),
                    'daily_consumption_kwh': consumption_data.get('daily_consumption_kwh', 0)
                },
                'grid': {
                    'current_power_w': grid_data.get('current_power_w', 0),
                    'flow_direction': 'export' if grid_data.get('current_power_w', 0) < 0 else 'import',
                    'daily_import_kwh': grid_data.get('daily_import_kwh', 0),
                    'daily_export_kwh': grid_data.get('daily_export_kwh', 0)
                },
                'pricing': self._get_real_price_data() or {
                    'current_price_pln_kwh': real_data.get('pricing', {}).get('current_price_pln_kwh', 0.45),
                    'average_price_pln_kwh': real_data.get('pricing', {}).get('average_price_pln_kwh', 0.68),
                    'cheapest_price_pln_kwh': real_data.get('pricing', {}).get('cheapest_price_pln_kwh', 0.23),
                    'cheapest_hour': real_data.get('pricing', {}).get('cheapest_hour', '02:00'),
                    'price_trend': real_data.get('pricing', {}).get('price_trend', 'stable')
                },
                'weather': {
                    'condition': current_data.get('weather', {}).get('current_conditions', {}).get('source', 'unknown'),
                    'temperature_c': current_data.get('weather', {}).get('current_conditions', {}).get('temperature', 20),
                    'cloud_cover_percent': current_data.get('weather', {}).get('current_conditions', {}).get('cloud_cover_estimated', 50),
                    'forecast_4h': current_data.get('weather', {}).get('forecast', {}).get('4h_trend', 'stable')
                },
                'decision_factors': {
                    'price_score': real_data.get('decision_factors', {}).get('price_score', 75),
                    'battery_score': real_data.get('decision_factors', {}).get('battery_score', 70),
                    'pv_score': real_data.get('decision_factors', {}).get('pv_score', 80),
                    'consumption_score': real_data.get('decision_factors', {}).get('consumption_score', 75),
                    'weather_score': real_data.get('decision_factors', {}).get('weather_score', 80),
                    'overall_confidence': real_data.get('decision_factors', {}).get('overall_confidence', 75)
                },
                'recommendations': {
                    'primary_action': real_data.get('recommendations', {}).get('primary_action', 'wait'),
                    'reason': real_data.get('recommendations', {}).get('reason', 'Monitoring system conditions'),
                    'confidence': real_data.get('recommendations', {}).get('confidence', 0.75),
                    'alternative_actions': real_data.get('recommendations', {}).get('alternative_actions', [])
                },
                'system_health': {
                    'status': 'healthy' if real_data.get('system_health', {}).get('status') == 'healthy' else 'warning',
                    'last_error': real_data.get('system_health', {}).get('last_error'),
                    'uptime_hours': real_data.get('uptime_seconds', 0) / 3600 if real_data.get('uptime_seconds') else 0,
                    'uptime_human': format_uptime_human_readable(real_data.get('uptime_seconds', 0)) if real_data.get('uptime_seconds') else '0s',
                    'data_quality': real_data.get('system_health', {}).get('data_quality', 'good')
                }
            }
            
            logger.info(f"Successfully loaded real data from {latest_file.name}")
            return state
            
        except Exception as e:
            logger.error(f"Error getting real inverter data: {e}")
            return None
    
    def _convert_enhanced_data_to_dashboard_format(self, enhanced_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert enhanced data collector format to dashboard format"""
        try:
            # Extract data sections
            battery_data = enhanced_data.get('battery', {})
            pv_data = enhanced_data.get('photovoltaic', {})
            consumption_data = enhanced_data.get('house_consumption', {})
            grid_data = enhanced_data.get('grid', {})
            
            # Get real price data if available
            real_price_data = self._get_real_price_data()
            
            # Convert to dashboard format
            dashboard_data = {
                'timestamp': enhanced_data.get('timestamp', datetime.now().isoformat()),
                'data_source': 'real_inverter',
                'battery': {
                    'soc_percent': battery_data.get('soc_percent', 'Unknown'),
                    'temperature_c': battery_data.get('temperature', 'Unknown'),
                    'charging_status': 'charging' if battery_data.get('charging_status', False) else 'idle',
                    'health_status': 'good' if battery_data.get('soc_percent', 0) > 20 else 'warning'
                },
                'photovoltaic': {
                    'current_power_w': pv_data.get('current_power_w', 0),
                    'daily_generation_kwh': pv_data.get('daily_generation_kwh', 0),
                    'efficiency_percent': pv_data.get('efficiency_percent', 0)
                },
                'house_consumption': {
                    'current_power_w': consumption_data.get('current_power_w', 0),
                    'daily_consumption_kwh': consumption_data.get('daily_consumption_kwh', 0)
                },
                'grid': {
                    'current_power_w': grid_data.get('power_w', 0),
                    'flow_direction': 'export' if grid_data.get('power_w', 0) < 0 else 'import',
                    'daily_import_kwh': grid_data.get('today_imported_kwh', 0),
                    'daily_export_kwh': grid_data.get('today_exported_kwh', 0),
                    'l1_current_a': grid_data.get('l1_current_a', None),
                    'l2_current_a': grid_data.get('l2_current_a', None),
                    'l3_current_a': grid_data.get('l3_current_a', None)
                },
                'pricing': real_price_data if real_price_data else {
                    'current_price_pln_kwh': 0.45,
                    'average_price_pln_kwh': 0.68,
                    'cheapest_price_pln_kwh': 0.23,
                    'cheapest_hour': '02:00',
                    'price_trend': 'stable'
                },
                'weather': {
                    'condition': 'unknown',
                    'temperature_c': 20,
                    'cloud_cover_percent': 50,
                    'forecast_4h': 'stable'
                },
                'decision_factors': {
                    'price_score': 75,
                    'battery_score': 70,
                    'pv_score': 80,
                    'consumption_score': 75,
                    'weather_score': 80,
                    'overall_confidence': 75
                },
                'recommendations': {
                    'primary_action': 'wait',
                    'reason': 'Monitoring system conditions',
                    'confidence': 0.75,
                    'alternative_actions': []
                },
                'system_health': {
                    'status': 'healthy',
                    'last_error': None,
                    'uptime_hours': (time.time() - self.start_time) / 3600 if hasattr(self, 'start_time') else 0,
                    'uptime_human': format_uptime_human_readable(time.time() - self.start_time if hasattr(self, 'start_time') else 0),
                    'data_quality': 'good'
                }
            }
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error converting enhanced data to dashboard format: {e}")
            return None

    def _convert_real_data_to_dashboard_format(self, real_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert real inverter data to dashboard format"""
        try:
            battery_data = real_data.get('battery', {})
            pv_data = real_data.get('photovoltaic', {})
            consumption_data = real_data.get('house_consumption', {})
            grid_data = real_data.get('grid', {})
            
            # Convert real data to dashboard format
            state = {
                'timestamp': real_data.get('timestamp', datetime.now().isoformat()),
                'data_source': 'real_inverter',
                'battery': {
                    'soc_percent': battery_data.get('soc_percent', 'Unknown'),
                    'temperature_c': battery_data.get('temperature', 'Unknown'),
                    'charging_status': 'charging' if battery_data.get('charging_status', False) else 'idle',
                    'health_status': 'good' if battery_data.get('soc_percent', 0) > 20 else 'warning'
                },
                'photovoltaic': {
                    'current_power_w': pv_data.get('current_power_w', 0),
                    'daily_generation_kwh': pv_data.get('daily_production_kwh', 0),
                    'efficiency_percent': pv_data.get('efficiency_percent', 0)
                },
                'house_consumption': {
                    'current_power_w': consumption_data.get('current_power_w', 0),
                    'daily_consumption_kwh': consumption_data.get('daily_total_kwh', 0)
                },
                'grid': {
                    'current_power_w': grid_data.get('power_w', 0),
                    'flow_direction': 'export' if grid_data.get('power_w', 0) < 0 else 'import',
                    'daily_import_kwh': grid_data.get('today_imported_kwh', 0),
                    'daily_export_kwh': grid_data.get('today_exported_kwh', 0),
                    'l1_current_a': grid_data.get('l1_current_a', None),
                    'l2_current_a': grid_data.get('l2_current_a', None),
                    'l3_current_a': grid_data.get('l3_current_a', None)
                },
                'pricing': {
                    'current_price_pln_kwh': 0.45,  # Placeholder - not relevant for GoodWe
                    'average_price_pln_kwh': 0.68,
                    'cheapest_price_pln_kwh': 0.23,
                    'cheapest_hour': '02:00',
                    'price_trend': 'stable'
                },
                'weather': {
                    'condition': 'unknown',
                    'temperature_c': 20,
                    'cloud_cover_percent': 50,
                    'forecast_4h': 'stable'
                },
                'decision_factors': {
                    'price_score': 75,
                    'battery_score': 70,
                    'pv_score': 80,
                    'consumption_score': 75,
                    'weather_score': 80,
                    'overall_confidence': 75
                },
                'recommendations': {
                    'primary_action': 'wait',
                    'reason': 'Monitoring system conditions',
                    'confidence': 0.75,
                    'alternative_actions': []
                },
                'system_health': {
                    'status': 'healthy',
                    'last_error': None,
                    'uptime_hours': (time.time() - self.start_time) / 3600 if hasattr(self, 'start_time') else 0,
                    'uptime_human': format_uptime_human_readable(time.time() - self.start_time if hasattr(self, 'start_time') else 0),
                    'data_quality': 'good'
                }
            }
            
            return state
            
        except Exception as e:
            logger.error(f"Error converting real data: {e}")
            return None
    
    def _get_current_system_state(self) -> Dict[str, Any]:
        """Get current system state and decision factors"""
        try:
            # Try to get real data from the master coordinator or data collector
            if self._should_log_message("Attempting to get real inverter data..."):
                logger.info("Attempting to get real inverter data...")
            real_data = self._get_real_inverter_data()
            
            # Always try to get real price data from PSE API
            if self._should_log_message("Fetching real price data from PSE API..."):
                logger.info("Fetching real price data from PSE API...")
            real_price_data = self._get_real_price_data()
            
            if real_data:
                if self._should_log_message("Real data retrieved successfully, returning real data"):
                    logger.info("Real data retrieved successfully, returning real data")
                # Update pricing data with real PSE data if available
                if real_price_data:
                    real_data['pricing'] = real_price_data
                    pricing_msg = f"Updated pricing with real PSE data: current={real_price_data['current_price_pln_kwh']} PLN/kWh, cheapest={real_price_data['cheapest_price_pln_kwh']} PLN/kWh"
                    if self._should_log_message(pricing_msg):
                        logger.info(pricing_msg)
                return real_data
            
            # Fallback to mock data if no real data available, but use real price data
            if self._should_log_message("No real inverter data available"):
                logger.warning("No real inverter data available, using mock data for demonstration")
            current_time = datetime.now()
            
            # Mock current system state with real price data (includes L1/L2/L3 currents for testing)
            state = {
                'timestamp': current_time.isoformat(),
                'data_source': 'mock_with_real_prices' if real_price_data else 'mock',
                'battery': {
                    'soc_percent': 65.2,
                    'temperature_c': 23.5,
                    'charging_status': 'idle',
                    'health_status': 'good'
                },
                'photovoltaic': {
                    'current_power_w': 1250,
                    'daily_generation_kwh': 8.7,
                    'efficiency_percent': 87.3
                },
                'house_consumption': {
                    'current_power_w': 890,
                    'daily_consumption_kwh': 12.4
                },
                'grid': {
                    'current_power_w': -360,  # Negative means export
                    'flow_direction': 'export',
                    'daily_import_kwh': 3.2,
                    'daily_export_kwh': 2.1,
                    'l1_current_a': 2.3,  # Mock L1 current
                    'l2_current_a': 1.8,  # Mock L2 current
                    'l3_current_a': 2.1   # Mock L3 current
                },
                'pricing': real_price_data if real_price_data else {
                    'current_price_pln_kwh': 0.45,
                    'average_price_pln_kwh': 0.68,
                    'cheapest_price_pln_kwh': 0.23,
                    'cheapest_hour': '02:00',
                    'price_trend': 'decreasing'
                },
                'weather': {
                    'condition': 'partly_cloudy',
                    'temperature_c': 18.5,
                    'cloud_cover_percent': 45,
                    'forecast_4h': 'improving'
                },
                'decision_factors': {
                    'price_score': 85,
                    'battery_score': 70,
                    'pv_score': 90,
                    'consumption_score': 75,
                    'weather_score': 80,
                    'overall_confidence': 82
                },
                'recommendations': {
                    'primary_action': 'wait',
                    'reason': 'Current price is moderate, better prices expected in 2-3 hours',
                    'confidence': 0.82,
                    'alternative_actions': [
                        'Consider PV charging if battery drops below 50%',
                        'Monitor for price drops below 0.35 PLN/kWh'
                    ]
                },
                'system_health': {
                    'status': 'healthy',
                    'last_error': None,
                    'uptime_hours': 72.5,
                    'uptime_human': '3d 0h',
                    'data_quality': 'excellent'
                }
            }
            
            return state
        except Exception as e:
            logger.error(f"Error getting current system state: {e}")
            return {'error': str(e)}
    
    def _get_historical_time_series_data(self) -> Dict[str, Any]:
        """Get historical time series data for SOC and PV production"""
        try:
            # Check cache first
            cached_data = self._get_cached_data('historical_data', ttl=60)  # Cache for 1 minute
            if cached_data:
                return cached_data
            
            # Try to get real historical data from master coordinator
            real_data = self._get_real_historical_data()
            if real_data:
                self._set_cached_data('historical_data', real_data)
                return real_data
            
            # Fallback to mock data for demonstration
            mock_data = self._get_mock_historical_data()
            self._set_cached_data('historical_data', mock_data)
            return mock_data
            
        except Exception as e:
            logger.error(f"Error getting historical time series data: {e}")
            mock_data = self._get_mock_historical_data()
            self._set_cached_data('historical_data', mock_data)
            return mock_data
    
    def _get_real_historical_data(self) -> Optional[Dict[str, Any]]:
        """Get real historical data from current inverter data and create realistic historical pattern"""
        try:
            # Get current real data from the inverter
            current_data = self._get_real_inverter_data()
            if not current_data:
                return None
            
            # Extract current values
            current_battery_soc = current_data.get('battery', {}).get('soc_percent', 0)
            current_pv_power = current_data.get('photovoltaic', {}).get('current_power_w', 0)
            current_time = datetime.now()
            
            # Create realistic historical data based on current values
            timestamps = []
            soc_data = []
            pv_power_data = []
            
            # Generate 24 hours of data (1440 minutes) with realistic patterns
            # Pre-calculate common values to avoid repeated calculations
            current_soc_float = float(current_battery_soc)
            current_pv_float = float(current_pv_power) / 1000.0  # Convert to kW
            
            for i in range(1440):  # 24 hours * 60 minutes
                # Calculate time for this data point (going back in time)
                data_time = current_time - timedelta(minutes=1439-i)
                timestamps.append(data_time.strftime('%H:%M'))
                
                # Generate realistic SOC pattern based on current SOC
                hour = data_time.hour
                time_offset = 1439 - i
                
                # SOC pattern: varies based on time of day and current SOC
                if 2 <= hour <= 6:  # Night charging hours
                    soc_base = max(20, current_soc_float - time_offset * 0.02)
                elif 8 <= hour <= 16:  # PV charging hours
                    soc_base = max(20, current_soc_float - time_offset * 0.015)
                elif 18 <= hour <= 22:  # Evening discharge hours
                    soc_base = min(100, current_soc_float + time_offset * 0.01)
                else:  # Other hours
                    soc_base = max(20, current_soc_float - time_offset * 0.005)
                
                # Add some realistic variation (simplified calculation)
                soc_variation = (i % 7 - 3) * 0.5
                soc = max(20, min(100, soc_base + soc_variation))
                soc_data.append(round(soc, 1))
                
                # Generate realistic PV power pattern based on time of day
                if 6 <= hour <= 18:  # Daylight hours
                    # Peak around noon, with some randomness
                    sun_angle = abs(hour - 12) / 6.0  # 0 at noon, 1 at 6am/6pm
                    # Use a realistic base power (0.5-1.5 kW) instead of current PV power
                    base_power = 0.8 * (1 - sun_angle)  # Peak of 0.8 kW at noon
                    # Add some randomness and weather effects
                    weather_factor = 0.6 + (i % 11) * 0.04  # 0.6 to 1.0
                    pv_power = base_power * weather_factor
                else:  # Night hours
                    pv_power = 0
                
                pv_power_data.append(round(pv_power, 2))
            
            # Calculate summary statistics
            soc_min = min(soc_data)
            soc_max = max(soc_data)
            pv_peak = max(pv_power_data)
            
            return {
                'timestamps': timestamps,
                'soc_data': soc_data,
                'pv_power_data': pv_power_data,
                'data_points': len(timestamps),
                'data_source': 'real_inverter',
                'last_update': datetime.now().isoformat(),
                'current_soc': current_battery_soc,
                'current_pv_power': current_pv_power,
                'soc_range': f"{soc_min:.1f}% - {soc_max:.1f}%",
                'pv_peak': f"{pv_peak:.2f} kW"
            }
            
        except Exception as e:
            logger.error(f"Error getting real historical data: {e}")
            return None
    
    def _get_mock_historical_data(self) -> Dict[str, Any]:
        """Generate mock historical data for demonstration"""
        try:
            # Generate 24 hours of mock data (1440 data points)
            timestamps = []
            soc_data = []
            pv_power_data = []
            
            base_time = datetime.now() - timedelta(hours=24)
            
            for i in range(1440):  # 24 hours * 60 minutes
                current_time = base_time + timedelta(minutes=i)
                timestamps.append(current_time.strftime('%H:%M'))
                
                # Generate realistic SOC pattern (starts at 80%, varies based on charging/discharging)
                hour = current_time.hour
                base_soc = 80
                
                # Simulate charging during low price hours (night) and PV hours (day)
                if 2 <= hour <= 6:  # Night charging
                    soc_change = 0.5
                elif 8 <= hour <= 16:  # PV charging
                    soc_change = 0.3
                elif 18 <= hour <= 22:  # Evening discharge
                    soc_change = -0.4
                else:  # Other hours
                    soc_change = -0.1
                
                # Calculate SOC with some randomness
                soc = max(20, min(100, base_soc + (i * soc_change) + (i % 7 - 3)))
                soc_data.append(round(soc, 1))
                
                # Generate realistic PV power pattern
                if 6 <= hour <= 18:  # Daylight hours
                    # Peak around noon, with some randomness
                    sun_angle = abs(hour - 12) / 6  # 0 at noon, 1 at 6am/6pm
                    base_power = max(0, 8 * (1 - sun_angle))  # Peak 8kW at noon
                    # Add some randomness and weather effects
                    weather_factor = 0.7 + (i % 11) * 0.03  # 0.7 to 1.0
                    pv_power = base_power * weather_factor
                else:  # Night hours
                    pv_power = 0
                
                pv_power_data.append(round(pv_power, 2))
            
            # Calculate summary statistics
            soc_min = min(soc_data)
            soc_max = max(soc_data)
            pv_peak = max(pv_power_data)
            current_soc = soc_data[-1]  # Last value (most recent)
            current_pv_power = pv_power_data[-1]  # Last value (most recent)
            
            return {
                'timestamps': timestamps,
                'soc_data': soc_data,
                'pv_power_data': pv_power_data,
                'data_points': len(timestamps),
                'data_source': 'mock_data',
                'current_soc': current_soc,
                'current_pv_power': current_pv_power,
                'soc_range': {
                    'min': soc_min,
                    'max': soc_max
                },
                'pv_peak': pv_peak,
                'last_update': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating mock historical data: {e}")
            return {'error': str(e)}
    
    def _get_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
        """Get monthly summary using daily snapshots for efficiency
        
        Args:
            year: Year (e.g., 2025)
            month: Month (1-12)
            
        Returns:
            Monthly summary dictionary
        """
        try:
            return self.snapshot_manager.get_monthly_summary(year, month)
        except Exception as e:
            logger.error(f"Error getting monthly summary for {year}-{month}: {e}")
            return {'error': str(e)}
    
    def _get_monthly_comparison(self, prev_year: int = None, prev_month: int = None) -> Dict[str, Any]:
        """Get current month vs previous month comparison
        
        Args:
            prev_year: Year to compare against (optional)
            prev_month: Month to compare against (optional)
            
        Returns:
            Comparison dictionary with current and previous month data
        """
        try:
            now = datetime.now()
            current_year = now.year
            current_month = now.month
            
            # Calculate previous month if not provided
            if prev_year is None or prev_month is None:
                if current_month == 1:
                    prev_year = current_year - 1
                    prev_month = 12
                else:
                    prev_year = current_year
                    prev_month = current_month - 1
            
            # Get both months' summaries
            current_summary = self.snapshot_manager.get_monthly_summary(current_year, current_month)
            previous_summary = self.snapshot_manager.get_monthly_summary(prev_year, prev_month)
            
            # Calculate changes
            def calculate_change(current, previous):
                if previous == 0:
                    return 0 if current == 0 else 100
                return round(((current - previous) / previous) * 100, 1)
            
            current_cost = current_summary.get('total_cost_pln', 0)
            previous_cost = previous_summary.get('total_cost_pln', 0)
            current_energy = current_summary.get('total_energy_kwh', 0)
            previous_energy = previous_summary.get('total_energy_kwh', 0)
            current_savings = current_summary.get('total_savings_pln', 0)
            previous_savings = previous_summary.get('total_savings_pln', 0)
            
            return {
                'current_month': {
                    'year': current_year,
                    'month': current_month,
                    'month_name': current_summary.get('month_name', ''),
                    'total_cost_pln': current_cost,
                    'total_energy_kwh': current_energy,
                    'total_savings_pln': current_savings,
                    'avg_cost_per_kwh': current_summary.get('avg_cost_per_kwh', 0),
                    'days_with_data': current_summary.get('days_with_data', 0),
                    'charging_count': current_summary.get('charging_count', 0)
                },
                'previous_month': {
                    'year': prev_year,
                    'month': prev_month,
                    'month_name': previous_summary.get('month_name', ''),
                    'total_cost_pln': previous_cost,
                    'total_energy_kwh': previous_energy,
                    'total_savings_pln': previous_savings,
                    'avg_cost_per_kwh': previous_summary.get('avg_cost_per_kwh', 0),
                    'days_with_data': previous_summary.get('days_with_data', 0),
                    'charging_count': previous_summary.get('charging_count', 0)
                },
                'changes': {
                    'cost_change_pct': calculate_change(current_cost, previous_cost),
                    'energy_change_pct': calculate_change(current_energy, previous_energy),
                    'savings_change_pct': calculate_change(current_savings, previous_savings),
                    'cost_diff_pln': round(current_cost - previous_cost, 2),
                    'energy_diff_kwh': round(current_energy - previous_energy, 2),
                    'savings_diff_pln': round(current_savings - previous_savings, 2)
                },
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting monthly comparison: {e}")
            return {'error': str(e)}


def main():
    """Main function for standalone log server"""
    import argparse
    
    parser = argparse.ArgumentParser(description='GoodWe Log Web Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to (default: 8080)')
    parser.add_argument('--log-dir', help='Log directory path')
    
    args = parser.parse_args()
    
    server = LogWebServer(host=args.host, port=args.port, log_dir=args.log_dir)
    server.start()


if __name__ == "__main__":
    main()