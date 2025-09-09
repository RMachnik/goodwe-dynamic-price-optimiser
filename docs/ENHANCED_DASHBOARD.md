# Enhanced Dashboard Documentation

This document provides comprehensive information about the Enhanced Dashboard for the GoodWe Dynamic Price Optimiser system.

## 🌐 **Overview**

The Enhanced Dashboard is a modern web interface that provides real-time monitoring, decision intelligence, and performance analytics for your energy management system. It offers comprehensive visibility into charging decisions, cost optimization, and system health.

## 🚀 **Quick Start**

### **Starting the Dashboard**
```bash
# Activate virtual environment
source venv/bin/activate

# Start the dashboard server
python src/log_web_server.py --port 8080

# Access the dashboard
open http://localhost:8080
```

### **Default Access**
- **Local Access**: http://localhost:8080
- **Network Access**: http://your-server-ip:8080
- **Auto-refresh**: Data updates every 30 seconds

## 🎯 **Dashboard Features**

### **Tabbed Interface**
The dashboard is organized into four main tabs:

#### **📊 Overview Tab**
- **System Status**: Real-time system health and status indicators
- **Current State**: Battery SoC, PV power, consumption, grid flow
- **Performance Metrics**: Efficiency scores and decision counts
- **Cost & Savings**: Real-time cost tracking and savings analysis

#### **🎯 Decisions Tab**
- **Recent Decisions Timeline**: Last 15 charging decisions with full details
- **Decision Reasoning**: Why each decision was made with confidence scores
- **Cost Impact Analysis**: Energy, cost, and savings for each decision
- **Decision Quality Metrics**: Visual confidence indicators and efficiency scoring

#### **📈 Metrics Tab**
- **Interactive Charts**: Decision analytics and cost analysis visualizations
- **Performance Trends**: Historical performance and efficiency trends
- **Cost Analysis**: Detailed cost breakdown and savings analysis
- **System Health**: Uptime, data quality, and error tracking

#### **📝 Logs Tab**
- **Real-time Log Streaming**: Live log updates with filtering
- **Log Level Filtering**: Filter by ERROR, WARNING, INFO, DEBUG
- **Multiple Log Files**: Master Coordinator, Data Collector, Fast Charge
- **Log Download**: Export logs for analysis

## 📡 **API Endpoints**

### **Decision Intelligence**
- `GET /decisions` - Charging decision history
- `GET /metrics` - System performance metrics
- `GET /current-state` - Real-time system state

### **System Information**
- `GET /health` - Health check endpoint
- `GET /status` - System status and coordinator information

### **Log Access**
- `GET /logs` - Get recent logs with filtering options
- `GET /logs/stream` - Real-time log streaming

## 🔧 **Technical Details**

### **Architecture**
- **Backend**: Flask-based web server
- **Frontend**: HTML/CSS/JavaScript with Chart.js
- **Data Source**: Real-time system data and decision history
- **Updates**: 30-second auto-refresh intervals

### **Data Sources**
- **Decision History**: Reads from `out/energy_data/charging_decision_*.json`
- **System State**: Real-time data from master coordinator
- **Performance Metrics**: Calculated from decision history
- **Mock Data**: Generated for demonstration when no real data available

### **Key Metrics**
- **Decision Count**: Total charging decisions made
- **Efficiency Score**: Weighted score based on confidence, savings, and charging ratio
- **Cost Savings**: Total savings compared to baseline pricing
- **System Health**: Uptime, data quality, and error rates

## 🎨 **User Interface**

### **Design Features**
- **Modern Tabbed Interface**: Clean, organized layout
- **Responsive Design**: Works on desktop and mobile devices
- **Real-time Updates**: Auto-refreshing data without page reload
- **Interactive Charts**: Chart.js visualizations for data analysis
- **Color-coded Status**: Visual indicators for system health and decision quality

### **Navigation**
- **Tab Navigation**: Click tabs to switch between views
- **Auto-refresh**: Data updates automatically every 30 seconds
- **Manual Refresh**: Refresh button for immediate updates
- **Log Streaming**: Toggle real-time log streaming on/off

## 📊 **Decision Intelligence**

### **Decision Timeline**
- **Recent Decisions**: Shows last 15 charging decisions
- **Decision Details**: Action, source, duration, energy, cost, savings
- **Confidence Scores**: Visual confidence indicators (0-100%)
- **Reasoning**: Detailed explanation of why each decision was made

### **Performance Analytics**
- **Decision Breakdown**: Charging vs. wait decisions
- **Source Analysis**: PV vs. grid charging decisions
- **Cost Analysis**: Total costs and savings over time
- **Efficiency Metrics**: System performance and optimization

## 🔍 **Troubleshooting**

### **Common Issues**
- **No Data Displayed**: Check if decision files exist in `out/energy_data/`
- **Dashboard Not Loading**: Verify Flask dependencies are installed
- **Port Already in Use**: Try a different port or kill existing processes
- **Mock Data Only**: Real data requires active master coordinator

### **Dependencies**
```bash
# Required packages
pip install flask flask-cors psutil

# Or install from requirements
pip install -r requirements.txt
```

### **File Locations**
- **Decision Files**: `out/energy_data/charging_decision_*.json`
- **Log Files**: `logs/` directory
- **Configuration**: `config/master_coordinator_config.yaml`

## 🚀 **Advanced Usage**

### **Custom Port**
```bash
# Use custom port
python src/log_web_server.py --port 9090
```

### **API Integration**
```bash
# Get decision history
curl http://localhost:8080/decisions

# Get system metrics
curl http://localhost:8080/metrics

# Get current state
curl http://localhost:8080/current-state
```

### **Log Streaming**
```bash
# Stream logs via API
curl http://localhost:8080/logs/stream
```

## 📈 **Performance Monitoring**

### **Key Performance Indicators**
- **Decision Efficiency**: Percentage of optimal decisions made
- **Cost Savings**: Total savings compared to baseline
- **System Uptime**: Percentage of time system is operational
- **Data Quality**: Accuracy and completeness of collected data

### **Optimization Insights**
- **Price Optimization**: How well the system identifies low-price windows
- **PV Utilization**: Efficiency of PV energy usage
- **Battery Management**: Optimal battery charging and discharging
- **Grid Interaction**: Minimizing grid dependency

## 🔮 **Future Enhancements**

### **Planned Features**
- **Alert System**: Price alerts and system notifications
- **Mobile App**: Native mobile application
- **Advanced Analytics**: Machine learning insights
- **Export Functionality**: Data export for external analysis
- **Custom Dashboards**: User-configurable dashboard layouts

### **Integration Opportunities**
- **Home Assistant**: Direct integration with HA dashboard
- **External APIs**: Integration with other energy management systems
- **Data Export**: CSV/JSON export for analysis
- **Webhooks**: Real-time notifications to external systems

---

For more information about the system architecture and configuration, see the [Project Plan](PROJECT_PLAN_Enhanced_Energy_Management.md) and [README](../README.md).
