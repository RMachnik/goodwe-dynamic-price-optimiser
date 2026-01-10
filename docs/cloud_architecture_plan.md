# Multi-Tenant Cloud Architecture Plan (V5.0 - Production Live)

Distributed energy optimization with central management and local resilience.

## 🎯 Implementation Status

**✅ Phase 1-3 COMPLETE**: End-to-end verified system with premium Cloud UI & Real Edge Agent.
**🚀 Next**: Phase 5 (Advanced Analytics & Scaling)

---

## 1. System Components

### 1.1 Central Hub API & Dashboard (VPS) - **✅ VERIFIED**
- **Backend Engine**: FastAPI (Python) - *High-performance async.*
- **Frontend Engine**: React + Vite + TypeScript - *Premium glassmorphism UI.*
- **Purpose**: Aggregated Management with AI Decision Visibility.
- **Admin Dashboard**: Full visibility, user management, remote command center, **financial analytics**.
- **User Dashboard**: Scoped view of their node's history and status.
- **Latency**: Near real-time (5s telemetry polling).
- **Communication Core**: Centralized `MQTTManager` (singleton) for shared broker connection between background workers and API routers.
- **Authentication**: JWT with `/auth/me` endpoint for user profile retrieval.
- **CORS**: Configured for localhost dev and production domain.

### 1.2 Local Dashboard (Raspberry Pi)
- **Purpose**: Real-time Diagnostics (sub-second polling).
- **Benefit**: Offline-first. Works even without internet.

### 1.3 Message Broker - **✅ VERIFIED (AMQP)**
- **Protocol**: RabbitMQ AMQP (TCP/SSL) used for production to bypass Cloudflare MQTT limitations.
- **Isolation**: Separate users for Hub (`hub_api`) and Nodes (`node_X`).
- **Access Control**: Strict vhost permissions.

#### 1.3.1 AMQP Security (Implemented)
- **Authentication**: Username/password per client.
- **ACLs**: Strict routing key isolation - nodes can only publish to `nodes.{id}.telemetry`.
- **Verification**: E2E test confirms ACL enforcement and tenant isolation.

---

## 2. Communication Strategy

Since nodes have no public IPs, they must **initiate all connections** (Outbound).

| Pattern | Use Case | Notes |
| :--- | :--- | :--- |
| **Webhooks (REST)** | Stats / Telemetry | Stateless, reliable. |
| **AMQP (Push)** | Telemetry | **✅ Implemented via Pika** |
| **Reverse SSH** | Debugging | Already implemented. |

### 2.1 Topic Design - **✅ Implemented**
(AMQP Routing Keys)
```text
nodes.{node_id}.status      # Node publishes: heartbeat
nodes.{node_id}.telemetry   # Node publishes: periodic stats
nodes.{node_id}.commands    # Hub publishes: RESTART, UPDATE
```

### 2.2 Telemetry Schema - **✅ Enhanced**
Standardized JSON payload verified in E2E tests.

### 2.3 Heartbeat & "Last Seen" Logic
- Agent publishes to `nodes.{id}.status` every **60 seconds**.
- Hub stores `last_seen_at` timestamp in DB.
- **Offline Alert**: If `now - last_seen_at > 5 minutes`, Hub marks node as `OFFLINE`.

---

## 3. Architecture Overview

```mermaid
graph TD
    subgraph "Central Services (VPS)"
        HubDB[(PostgreSQL)]
        Broker["RabbitMQ (AMQP)"]
    end

    subgraph "Cloud Hub (VPS)" 
        API["Hub API (FastAPI)"]
        Dashboard["Hub Dashboard (React)"]
    end

    subgraph "Edge Node (RPi)"
        App["Coordinator"]
        Agent["Cloud Reporter (Pika)"]
    end

    App -- "Local API" --> Agent
    Agent -- "Telemetry (AMQP)" --> Broker
    Broker -- "Consume" --> API
    API -- "Store" --> HubDB
    Dashboard -- "Fetch Nodes" --> API
```

---

## 4. Hub Dashboard Features - **✅ Implemented**

### 4.1 User Experience (UX)
- **Dual-Theme Engine**: Seamless Light/Dark mode synced with OS.
- **Mobile-First**: Bottom navigation bar and adaptive sidebar.
- **Glassmorphism**: Translucent panels with backdrop blur.
- **Maintainability**: Atom-based UI components (Card, Button, Input).

### 4.2 Core Pages
- **Login**: Semantic theming, form validation.
- **Fleet Overview**: Card grid showing real-time status.
- **Node Detail**: Performance charts and remote actions.

### 4.3 Data Connectivity
- **TanStack Query**: Aggressive caching, background refetching.
- **Real-time Updates**: Polling-based live dashboard.

### 4.4 Testing & Quality - **✅ All Tests Passing**
- **Playwright E2E Suite**: Login, Theme, Navigation verified.
- **Production Build**: Vite optimized build deployed to Nginx.

---

## 5. Security - **✅ Hardened**
- **Node Auth**: Dedicated credentials per node.
- **Encryption**: All traffic over SSL/TLS.
- **AMQP ACLs**: Strict Broker Access Control. 
- **Database Migrations**: Alembic manages schema versions.
- **JWT Authentication**: Secure token-based auth.
- **CORS**: Configured allow-list.

---

## 6. Service Distribution

| Service | Host | Status |
| :--- | :--- | :--- |
| Master Coordinator | RPi | Existing |
| Management Agent | RPi | **✅ Deployed (AMQP)** |
| Cloud Hub API | VPS | **✅ Live (Port 40314)** |
| Hub Dashboard | VPS | **✅ Live (Port 40315)** |
| PostgreSQL | Managed | Configured |
| Message Broker | RabbitMQ | **✅ Verified (AMQP)** |

---

## 7. Next Steps & Recommendations

### ✅ Completed Milestones
- **Backend Deployment**: Running on `srv26.mikr.us` (Port 40314).
- **Dashboard Deployment**: Running on `srv26.mikr.us` (Port 40315).
- **Edge Deployment**: Raspberry Pi (`rasp-01`) successfully reporting telemetry.
- **UX Overhaul**: Full Glassmorphism redesign validation.

### 🚀 Future Roadmap (Phase 5)
1.  **SSL/TLS Enforcement**:
    - Obtain Let's Encrypt certificates for the VPS domain.
    - Switch RabbitMQ to use MQTTS/AMQPS (8883/5671).
2.  **Advanced Analytics**:
    - Add "Cost vs Savings" historical charts to dashboard.
    - Implement predictive solar forcasting (ML model).
3.  **Multi-Node Scaling**:
    - Verify behavior with 10+ mock nodes.
    - Implement pagination on Nodes table.

---

## 8. Success Metrics (Post-Launch)
- **Uptime**: Hub API availability (target: 99.9%).
- **Latency**: Dashboard load time (target: < 2s).
- **Node Health**: % of nodes online (target: > 95%).
- **Migration**: 100% of telemetry via AMQP.

---

**Document Status**: V5.0 - Production Live
**Last Updated**: 2026-01-10
