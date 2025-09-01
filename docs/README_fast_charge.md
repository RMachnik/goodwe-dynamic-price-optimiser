# GoodWe Inverter Fast Charging Script

This Python script provides a command-line interface to control fast charging on GoodWe inverters with safety features and monitoring capabilities.

## Features

- **Fast Charging Control**: Start/stop fast charging on GoodWe inverters
- **Safety Checks**: Battery temperature, SoC, and grid power monitoring
- **Configuration File**: YAML-based configuration for easy setup
- **Real-time Monitoring**: Track charging progress and battery status
- **Notifications**: Optional webhook and email notifications
- **Logging**: Comprehensive logging to console and file
- **Safety Features**: Automatic stopping when conditions are met

## Requirements

- Python 3.8 or higher
- GoodWe inverter with network connectivity
- Network access to inverter IP address

## Installation

1. **Clone or download the script files:**
   ```bash
   # Make sure you have the following files:
   # - fast_charge.py
   # - fast_charge_config.yaml
   # - requirements.txt
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Make the script executable (Linux/Mac):**
   ```bash
   chmod +x fast_charge.py
   ```

## Configuration

1. **Edit the configuration file:**
   ```bash
   nano fast_charge_config.yaml
   ```

2. **Update inverter settings:**
   ```yaml
   inverter:
     ip_address: "192.168.2.14"  # Your inverter's IP address
     family: "ET"                 # Your inverter family (ET, ES, DT)
     timeout: 1
     retries: 3
   ```

3. **Configure charging parameters:**
   ```yaml
   fast_charging:
     enable: true
     power_percentage: 80        # Charging power (0-100%)
     target_soc: 90              # Target battery level (0-100%)
     max_charging_time: 120      # Max charging time in minutes
   ```

4. **Set safety limits:**
   ```yaml
   safety:
     max_battery_temp: 50        # Max battery temperature (°C)
     min_battery_soc: 10         # Min battery level to start
     max_grid_power: 5000        # Max grid power usage (W)
   ```

## Usage

### Basic Commands

**Show current status:**
```bash
python fast_charge.py
```

**Start fast charging:**
```bash
python fast_charge.py --start
```

**Stop fast charging:**
```bash
python fast_charge.py --stop
```

**Show detailed status:**
```bash
python fast_charge.py --status
```

**Start charging with monitoring:**
```bash
python fast_charge.py --start --monitor
```

**Monitor existing charging:**
```bash
python fast_charge.py --monitor
```

**Use custom config file:**
```bash
python fast_charge.py --config my_config.yaml --start
```

### Command Line Options

- `--config, -c`: Configuration file path (default: fast_charge_config.yaml)
- `--start`: Start fast charging
- `--stop`: Stop fast charging
- `--status`: Show detailed charging status
- `--monitor`: Monitor charging progress
- `--help`: Show help message

## Examples

### Example 1: Quick Charge to 90%
```bash
# Start fast charging to 90% with monitoring
python fast_charge.py --start --monitor
```

### Example 2: Check Current Status
```bash
# See what's happening with the inverter
python fast_charge.py --status
```

### Example 3: Emergency Stop
```bash
# Stop charging immediately
python fast_charge.py --stop
```

## Safety Features

The script includes several safety mechanisms:

1. **Battery Temperature Monitoring**: Stops charging if battery gets too hot
2. **SoC Limits**: Won't start charging if battery is too low
3. **Grid Power Limits**: Prevents excessive grid power consumption
4. **Time Limits**: Automatically stops after maximum charging time
5. **Target SoC**: Stops when desired battery level is reached

## Monitoring

When monitoring is enabled, the script will:

- Check battery status every 30 seconds
- Display current SoC vs target SoC
- Log all activities
- Automatically stop when conditions are met
- Send notifications (if configured)

## Notifications

Configure notifications in the config file:

```yaml
notifications:
  enabled: true
  webhook_url: "https://hooks.slack.com/your-webhook"
  email:
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    username: "your-email@gmail.com"
    password: "your-app-password"
    from_email: "your-email@gmail.com"
    to_email: "notify@example.com"
```

## Troubleshooting

### Common Issues

1. **Connection Failed**
   - Check inverter IP address
   - Verify network connectivity
   - Check firewall settings
   - Ensure inverter is powered on

2. **Authentication Errors**
   - Verify inverter family setting
   - Check communication address
   - Try increasing timeout/retry values

3. **Charging Won't Start**
   - Check safety conditions
   - Verify battery SoC
   - Check temperature limits
   - Review error logs

### Debug Mode

Enable debug logging in config:
```yaml
logging:
  level: "DEBUG"
  log_to_file: true
```

### Log Files

Check the log file for detailed information:
```bash
tail -f fast_charge.log
```

## Advanced Configuration

### Custom Safety Rules

Add custom safety checks by modifying the `check_safety_conditions` method in the script.

### Integration with Home Assistant

This script can be integrated with Home Assistant using:
- Shell command integration
- Automation triggers
- REST API calls

### Scheduled Charging

Use cron or systemd timers to schedule charging:
```bash
# Charge every morning at 6 AM
0 6 * * * /usr/bin/python3 /path/to/fast_charge.py --start --monitor
```

## Support

For issues and questions:
1. Check the logs for error messages
2. Verify configuration settings
3. Test network connectivity to inverter
4. Review GoodWe inverter documentation

## Disclaimer

This script is provided as-is. Use at your own risk. Improper use may damage your inverter or battery system. Always follow manufacturer guidelines and safety recommendations.

## License

This script is part of the GoodWe Home Assistant integration project.

