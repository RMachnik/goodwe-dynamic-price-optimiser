#!/bin/bash
# Scripts to deploy the Cloud Reporter to Raspberry Pi

PI_HOST="192.168.33.10"
PI_USER="rmachnik"
TARGET_DIR="/home/rmachnik/goodwe-edge"

echo "🚀 Deploying Cloud Reporter to $PI_USER@$PI_HOST..."

# 1. Create directory
ssh $PI_USER@$PI_HOST "mkdir -p $TARGET_DIR"

# 2. Copy files
echo "📦 Copying files..."
scp edge/cloud_reporter.py edge/requirements.txt edge/.env.example $PI_USER@$PI_HOST:$TARGET_DIR/

# 3. Create .env if not exists
ssh $PI_USER@$PI_HOST "if [ ! -f $TARGET_DIR/.env ]; then cp $TARGET_DIR/.env.example $TARGET_DIR/.env; fi"

# 4. Install dependencies in venv
echo "📦 Key Setup: Creating python venv..."
ssh $PI_USER@$PI_HOST "cd $TARGET_DIR && python3 -m venv venv && ./venv/bin/pip install --upgrade pip && ./venv/bin/pip install -r requirements.txt"

echo "✅ Deployment complete!"
echo "---------------------------------------------------"
echo "NEXT STEPS:"
echo "1. SSH into Pi: ssh $PI_USER@$PI_HOST"
echo "2. Edit config: nano $TARGET_DIR/.env"
echo "   (Set AMQP_PASS to your RabbitMQ password)"
echo "3. Run manually to test: $TARGET_DIR/venv/bin/python3 $TARGET_DIR/cloud_reporter.py"
echo "---------------------------------------------------"
