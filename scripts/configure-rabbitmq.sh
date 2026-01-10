#!/bin/bash
set -e

# RabbitMQ Configuration Script
# Usage: ./configure-rabbitmq.sh
# Requires 'jq' and 'curl'

echo "🐰 RabbitMQ Remote Configuration Utility"
echo "   This script configures Users and Permissions via the RabbitMQ Management API." 
echo ""

# Defautls
DEFAULT_HOST="mws03-52071.wykr.es"
DEFAULT_MGMT_PORT="443" # Usually 443 for https panel
DEFAULT_SCHEME="https"

read -p "RabbitMQ Management Host [$DEFAULT_HOST]: " MGMT_HOST
MGMT_HOST=${MGMT_HOST:-$DEFAULT_HOST}

read -p "Management Port [$DEFAULT_MGMT_PORT]: " MGMT_PORT
MGMT_PORT=${MGMT_PORT:-$DEFAULT_MGMT_PORT}

read -p "Admin User [admin]: " ADMIN_USER
ADMIN_USER=${ADMIN_USER:-admin}

echo -n "Admin Password: "
read -s ADMIN_PASS
echo ""

BASE_URL="$DEFAULT_SCHEME://$MGMT_HOST:$MGMT_PORT/api"

echo "🔍 Testing connection to $BASE_URL..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -u "$ADMIN_USER:$ADMIN_PASS" "$BASE_URL/overview")

if [ "$HTTP_CODE" -ne 200 ]; then
    echo "❌ Connection failed! HTTP Code: $HTTP_CODE"
    echo "   Check credentials and URL."
    exit 1
fi
echo "✅ Connection successful."

# --- Helper Functions ---

create_user() {
    local user="$1"
    local pass="$2"
    local tag="$3"
    
    echo "👤 Creating user '$user'..."
    curl -s -u "$ADMIN_USER:$ADMIN_PASS" \
        -H "Content-Type: application/json" \
        -X PUT -d "{\"password\":\"$pass\", \"tags\":\"$tag\"}" \
        "$BASE_URL/users/$user" | jq .
}

set_permissions() {
    local user="$1"
    local vhost="$2" # usually "/" (needs encoding as %2f)
    local conf="$3"
    local write="$4"
    local read="$5"

    # URL Encode vhost if it is "/"
    if [ "$vhost" = "/" ]; then
        vhost_encoded="%2f"
    else
        vhost_encoded="$vhost"
    fi

    echo "🔑 Setting permissions for '$user' on vhost '$vhost'..."
    curl -s -u "$ADMIN_USER:$ADMIN_PASS" \
        -H "Content-Type: application/json" \
        -X PUT -d "{\"configure\":\"$conf\", \"write\":\"$write\", \"read\":\"$read\"}" \
        "$BASE_URL/permissions/$vhost_encoded/$user" | jq .
}

# --- Configuration Steps ---

echo ""
echo "--- 1. Hub API User ---"
echo "The Hub API needs full access to 'nodes/#' topics."
read -p "Create 'hub_api' user? [Y/n]: " DO_HUB
if [[ "$DO_HUB" =~ ^[Yy]?$ ]]; then
    read -p "Hub API Username [hub_api]: " HUB_USER
    HUB_USER=${HUB_USER:-hub_api}
    
    echo -n "Hub API Password: "
    read -s HUB_PASS
    echo ""
    
    create_user "$HUB_USER" "$HUB_PASS" "monitoring" # 'monitoring' tag allows limited UI access, or '' for none
    
    # Permissions for MQTT on default vhost /
    # Configure: .* (needed for auto-creating queues if any), Write: .*, Read: .*
    # Or strict: Write: ^nodes/.*, Read: ^nodes/.*
    # For Hub, we give broad access.
    set_permissions "$HUB_USER" "/" ".*" ".*" ".*"
fi

echo ""
echo "--- 2. Edge Node User ---"
echo "Each Raspberry Pi should ideally have its own user."
read -p "Create new Node user? [Y/n]: " DO_NODE
if [[ "$DO_NODE" =~ ^[Yy]?$ ]]; then
    read -p "Node ID (e.g. node_01): " NODE_ID
    NODE_USER="node_$NODE_ID"
    
    echo -n "Node Password: "
    read -s NODE_PASS
    echo ""
    
    create_user "$NODE_USER" "$NODE_PASS" ""
    
    # Permissions:
    # Topic structure: nodes/{id}/...
    # The RabbitMQ MQTT plugin maps topics like 'nodes.node_01.telemetry'
    # Default exchange is 'amq.topic'
    
    # NOTE: Regex permissions in RabbitMQ apply to resource NAMES (queues/exchanges).
    # For MQTT, this is tricky. Often simpler to give write/read access to 'amq.topic' exchange
    # and restrict via Topic Permissions (available in newer RabbitMQ versions).
    
    # Giving basic vhost access
    set_permissions "$NODE_USER" "/" ".*" ".*" ".*"
    
    echo "⚠️  Note: Setting topic-level restrictions (ACLs) requires the 'Topic Permissions' plugin or careful regex."
    echo "   For now, we granted basic vhost access. Ensure your application logic validates IDs."
fi

echo ""
echo "--- 3. MQTT Plugin Check ---"
echo "Checking enabled plugins..."
curl -s -u "$ADMIN_USER:$ADMIN_PASS" "$BASE_URL/nodes" | jq '.[].enabled_plugins'

echo ""
echo "✅ Configuration steps complete."
