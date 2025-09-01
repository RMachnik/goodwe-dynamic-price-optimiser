# Automated Price-Based Charging System for GoodWe Inverter

This system automatically controls your GoodWe inverter's battery charging based on real-time Polish electricity market prices, optimizing costs and maximizing savings.

## 🎯 **What It Does**

- **Real-time Price Monitoring**: Fetches live electricity prices from Polish market (PSE)
- **Smart Charging Decisions**: Automatically starts/stops charging based on price thresholds
- **Cost Optimization**: Finds optimal charging windows to minimize electricity costs
- **Full Integration**: Works seamlessly with your existing GoodWe inverter setup

## 🚀 **Key Features**

### **Price Analysis**
- Fetches 15-minute interval price data from Polish electricity market
- Analyzes daily price patterns and trends
- Identifies optimal charging windows based on price thresholds
- Calculates potential savings for each charging period

### **Automated Control**
- Monitors prices every 15 minutes (configurable)
- Automatically starts charging when prices are low
- Stops charging when prices become high
- Respects maximum charging time limits
- Monitors battery SoC and stops when target reached

### **Smart Scheduling**
- Finds multiple optimal charging windows per day
- Ensures no overlap between charging periods
- Prioritizes windows with highest savings
- Adapts to daily price variations

## 📊 **Polish Electricity Market Analysis (August 31, 2025)**

Based on the analysis of your requested date:

### **Price Statistics**
- **Minimum Price**: 116.83 PLN/MWh
- **Maximum Price**: 687.04 PLN/MWh  
- **Average Price**: 426.44 PLN/MWh
- **Price Range**: 570.21 PLN/MWh (5.9x difference!)

### **Optimal Charging Window**
- **Best Time**: 11:15 - 15:15 (4 hours)
- **Average Price**: 227.22 PLN/MWh
- **Savings**: 199.22 PLN/MWh (46.7% savings!)
- **Cost**: 908.88 PLN/MWh total for 4 hours

### **Price Distribution**
- 🟢 **Very Low (0-200 PLN/MWh)**: 4.2% of periods
- 🟡 **Low (200-400 PLN/MWh)**: 20.8% of periods  
- 🟡 **Medium (400-600 PLN/MWh)**: 62.5% of periods
- 🔴 **High (600+ PLN/MWh)**: 12.5% of periods

## 🛠 **Installation & Setup**

### **Prerequisites**
- Python 3.8+
- GoodWe inverter with network connectivity
- Working fast charging setup (from previous script)

### **Installation**
```bash
# Install dependencies
pip3 install requests PyYAML

# Ensure your GoodWe configuration is working
python3 fast_charge.py --status
```

## 🎮 **Usage**

### **1. Run the Automated System**
```bash
python3 automated_price_charging.py
```

### **2. Choose Your Option**
The system will show you today's electricity prices and optimal charging windows, then offer:

1. **Start monitoring and automatic charging** - Full automation
2. **Show current status** - Check inverter and battery status
3. **Start charging now** - Manual start if price is optimal
4. **Stop charging** - Manual stop if active
5. **Exit** - Close the system

### **3. Automated Operation**
When you choose option 1, the system will:
- Check prices every 15 minutes
- Automatically start charging during low-price periods
- Stop charging when prices rise or targets are met
- Log all activities for monitoring

## ⚙️ **Configuration**

### **Price Thresholds**
The system automatically calculates optimal price thresholds:
- **Default**: 25th percentile of daily prices
- **Customizable**: Set your own threshold in the code
- **Dynamic**: Adapts to daily price variations

### **Charging Parameters**
- **Check Interval**: 15 minutes (configurable)
- **Max Charging Time**: 4 hours (configurable)
- **Target Duration**: 4-hour charging windows
- **Savings Threshold**: 15% minimum savings

## 📈 **Cost Savings Example**

### **Scenario: 4-Hour Charging Session**
- **High Price Period**: 600 PLN/MWh = 2,400 PLN for 4 hours
- **Low Price Period**: 227 PLN/MWh = 908 PLN for 4 hours
- **Savings**: 1,492 PLN (62.2% cost reduction!)

### **Daily Savings Potential**
- **Conservative**: 15-25% savings on charging costs
- **Aggressive**: 40-60% savings during optimal windows
- **Annual Impact**: Significant reduction in electricity bills

## 🔍 **Monitoring & Logs**

### **Real-time Monitoring**
- Price checks every 15 minutes
- Charging status updates
- Battery SoC monitoring
- Cost savings calculations

### **Logging**
- All activities logged with timestamps
- Price data and decisions recorded
- Error handling and troubleshooting info
- Performance metrics

## 🚨 **Safety Features**

### **Automatic Stops**
- Maximum charging time reached
- Target battery SoC achieved
- Price no longer optimal
- System errors or failures

### **Manual Override**
- Stop charging at any time
- Manual start/stop control
- Emergency shutdown capability
- Status monitoring

## 🔧 **Troubleshooting**

### **Common Issues**

1. **Price Data Not Available**
   - Check internet connection
   - Verify API endpoint accessibility
   - Check if market data is published

2. **Charging Won't Start**
   - Verify GoodWe inverter connection
   - Check battery SoC and temperature
   - Review safety conditions

3. **Monitoring Stops**
   - Check system logs
   - Verify network connectivity
   - Restart the monitoring process

### **Debug Mode**
Enable detailed logging by modifying the logging level in the script.

## 📱 **Integration Options**

### **Home Assistant**
- Use as a custom integration
- Create automations based on price data
- Integrate with energy dashboard

### **Scheduling**
- Run as a system service
- Use cron jobs for specific times
- Integrate with calendar systems

### **Notifications**
- Email alerts for charging events
- Webhook notifications
- SMS alerts for critical events

## 📊 **API Documentation**

### **Polish Electricity Market API**
- **Endpoint**: `https://api.raporty.pse.pl/api/csdac-pln`
- **Format**: JSON with 15-minute intervals
- **Data**: Price in PLN/MWh, timestamps, periods
- **Update Frequency**: Real-time market data

### **Data Structure**
```json
{
  "value": [
    {
      "dtime": "2025-08-31 00:15",
      "period": "00:00 - 00:15",
      "csdac_pln": 450.10,
      "business_date": "2025-08-31"
    }
  ]
}
```

## 🎯 **Best Practices**

### **Charging Strategy**
1. **Monitor Daily Prices**: Check price trends before setting schedules
2. **Use Multiple Windows**: Split charging across optimal periods
3. **Set Realistic Targets**: Don't chase unrealistic savings
4. **Monitor Performance**: Track actual vs. expected savings

### **System Maintenance**
1. **Regular Updates**: Keep price data current
2. **Log Review**: Monitor system performance
3. **Configuration Review**: Adjust thresholds as needed
4. **Backup Plans**: Have manual charging options ready

## 🔮 **Future Enhancements**

### **Planned Features**
- **Machine Learning**: Predict optimal charging times
- **Weather Integration**: Solar production forecasting
- **Grid Status**: Network stability monitoring
- **Mobile App**: Remote monitoring and control

### **API Expansions**
- **Historical Data**: Price trend analysis
- **Forecasting**: Future price predictions
- **Regional Data**: Local market variations
- **Real-time Updates**: Live price streaming

## 📞 **Support & Community**

### **Getting Help**
1. Check the logs for error messages
2. Verify your configuration settings
3. Test network connectivity
4. Review the troubleshooting section

### **Contributing**
- Report bugs and issues
- Suggest new features
- Share your success stories
- Help improve the documentation

## ⚖️ **Legal & Disclaimer**

### **Important Notes**
- This system is for educational and personal use
- Always follow local electricity regulations
- Monitor system performance regularly
- Use at your own risk and responsibility

### **Data Usage**
- Price data from official Polish market sources
- Respect API rate limits and terms of service
- Store data responsibly and securely
- Comply with data protection regulations

## 🎉 **Success Stories**

### **Expected Results**
- **Cost Reduction**: 20-60% savings on charging costs
- **Automation**: Set and forget operation
- **Optimization**: Always charge at best prices
- **Monitoring**: Full visibility into charging costs

### **Real-world Impact**
- **Monthly Savings**: Significant reduction in electricity bills
- **Environmental**: Better grid utilization
- **Convenience**: Automated operation
- **Control**: Full visibility and control

---

**Ready to start saving on your electricity costs?** 

Run `python3 automated_price_charging.py` and let the system optimize your charging automatically! 🚀⚡🇵🇱
