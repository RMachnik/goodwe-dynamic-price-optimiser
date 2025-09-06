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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import threading
from queue import Queue, Empty

from flask import Flask, Response, jsonify, request, render_template_string
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LogWebServer:
    """Simple HTTP server for log access and system monitoring"""
    
    def __init__(self, host='0.0.0.0', port=8080, log_dir=None):
        """Initialize the log web server"""
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        CORS(self.app)  # Enable CORS for all routes
        
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
        
        # Setup routes
        self._setup_routes()
        
        # Log streaming
        self.log_queue = Queue()
        self.clients = set()
        
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
                # Try to get status from master coordinator if available
                status_data = self._get_system_status()
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
    
    def _get_log_lines(self, log_path: Path, lines: int, level: str = '') -> Response:
        """Get last N lines from log file"""
        try:
            with open(log_path, 'r') as f:
                all_lines = f.readlines()
            
            # Filter by level if specified
            if level:
                filtered_lines = [line for line in all_lines if level in line.upper()]
            else:
                filtered_lines = all_lines
            
            # Get last N lines
            recent_lines = filtered_lines[-lines:] if len(filtered_lines) > lines else filtered_lines
            
            return jsonify({
                'log_file': log_path.name,
                'total_lines': len(all_lines),
                'filtered_lines': len(filtered_lines),
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
            
            # Build journalctl command
            cmd = ['journalctl', '--user', '-u', 'goodwe-master-coordinator', '-n', str(lines * 3), '--no-pager', '--output=short-iso']
            
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
                cmd = ['journalctl', '--user', '-u', 'goodwe-master-coordinator', '-n', '20', '--no-pager', '--output=short-iso']
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
                cmd = ['journalctl', '--user', '-u', 'goodwe-master-coordinator', '-f', '--no-pager', '--output=short-iso']
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
            cmd = ['journalctl', '--user', '-u', 'goodwe-master-coordinator', '-n', str(lines * 5), '--no-pager', '--output=short-iso']
            
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
            
            return {
                'status': 'running',
                'timestamp': datetime.now().isoformat(),
                'coordinator_running': coordinator_running,
                'coordinator_pid': coordinator_pid,
                'log_files': log_files,
                'server_uptime': time.time() - self.start_time if hasattr(self, 'start_time') else 0
            }
        except ImportError:
            return {
                'status': 'running',
                'timestamp': datetime.now().isoformat(),
                'coordinator_running': 'unknown',
                'note': 'psutil not available for process monitoring'
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _get_dashboard_template(self) -> str:
        """Get HTML dashboard template"""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>GoodWe Master Coordinator - Log Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .card { background: white; padding: 20px; margin-bottom: 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .log-container { background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 5px; font-family: 'Courier New', monospace; font-size: 12px; max-height: 400px; overflow-y: auto; }
        .controls { margin-bottom: 15px; }
        .controls input, .controls select, .controls button { margin-right: 10px; padding: 5px; }
        .status-indicator { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 5px; }
        .status-running { background-color: #27ae60; }
        .status-stopped { background-color: #e74c3c; }
        .status-unknown { background-color: #f39c12; }
        .log-line { margin: 2px 0; }
        .log-error { color: #e74c3c; }
        .log-warning { color: #f39c12; }
        .log-info { color: #3498db; }
        .log-debug { color: #95a5a6; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔋 GoodWe Master Coordinator - Log Dashboard</h1>
            <p>Remote monitoring and log access</p>
        </div>
        
        <div class="card">
            <h3>System Status</h3>
            <div id="status">
                <span class="status-indicator status-unknown"></span>
                <span id="status-text">Loading...</span>
            </div>
            <div id="status-details"></div>
        </div>
        
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

    <script>
        let eventSource = null;
        let streaming = false;
        
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
                        <p><strong>Server Uptime:</strong> ${Math.round(data.server_uptime)}s</p>
                    `;
                })
                .catch(error => {
                    document.getElementById('status').innerHTML = '<span class="status-indicator status-unknown"></span><span id="status-text">Status Unknown</span>';
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
        loadLogs();
        setInterval(updateStatus, 30000); // Update status every 30 seconds
    </script>
</body>
</html>
        """
    
    def start(self):
        """Start the web server"""
        self.start_time = time.time()
        logger.info(f"Starting log web server on {self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=False, threaded=True)
    
    def stop(self):
        """Stop the web server"""
        logger.info("Stopping log web server")
        # Flask doesn't have a built-in stop method, so we'll use a different approach
        # This would typically be handled by the process manager


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