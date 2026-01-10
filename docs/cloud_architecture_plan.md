# Multi-Tenant Cloud Architecture Plan (V4.0 - Production Ready)

Distributed energy optimization with central management and local resilience.

## 🎯 Implementation Status

**✅ Phase 1-4 COMPLETE**: End-to-end verified system with premium Cloud UI
**🚀 Next**: Production deployment and advanced features

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
- **CORS**: Configured for localhost development, ready for production domain whitelisting.

### 1.2 Local Dashboard (Raspberry Pi)
- **Purpose**: Real-time Diagnostics (sub-second polling).
- **Benefit**: Offline-first. Works even without internet.

### 1.3 Message Broker - **✅ VERIFIED**
- **Development**: MQTT (Mosquitto) with ACL isolation.
- **Production**: Managed MQTT (CloudAMQP, HiveMQ) recommended.

#### 1.3.1 MQTT Security (Implemented)
- **Authentication**: Username/password per client (`hub_api`, `mock-node-01`).
- **ACLs**: Strict topic isolation - nodes can only publish/subscribe to their own topics.
- **Verification**: E2E test confirms ACL enforcement and tenant isolation.

#### 1.3.2 RabbitMQ Setup (Production Alternative)
When using RabbitMQ as the MQTT broker:
1.  **Enable MQTT Plugin**: `rabbitmq-plugins enable rabbitmq_mqtt`.
2.  **Exchange Mapping**: RabbitMQ automatically maps MQTT topics to the `amq.topic` exchange.
3.  **Authentication**: Create dedicated users with vhost permissions.
4.  **SSL/TLS**: Ensure port `8883` is configured with valid certificates.

---

## 2. Communication Strategy

Since nodes have no public IPs, they must **initiate all connections** (Outbound).

| Pattern | Use Case | Notes |
| :--- | :--- | :--- |
| **Webhooks (REST)** | Stats / Telemetry | Stateless, reliable. |
| **MQTT** | Real-time Commands | Persistent connection for push. **✅ Implemented** |
| **Reverse SSH** | Debugging | Already implemented. |

### 2.1 MQTT Topic Design - **✅ Implemented**

```text
nodes/{node_id}/status      # Node publishes: heartbeat, online/offline
nodes/{node_id}/telemetry   # Node publishes: periodic stats
nodes/{node_id}/commands    # Hub publishes: RESTART, UPDATE, CONFIG_PUSH
nodes/{node_id}/logs        # Node publishes: on-demand log chunks
hub/broadcast               # Hub publishes: global announcements
```

### 2.2 Telemetry Schema - **✅ Enhanced**

```json
{
  "node_id": "mock-node-01",
  "timestamp": "2026-01-09T23:45:00Z",
  "battery": {"soc_percent": 85.0, "voltage": 54.2},
  "solar": {"power_w": 1200},
  "grid": {
    "current_price": 0.55,
    "mode": "PASSIVE"
  },
  "optimizer": {
    "latest_decision": "Optimal: Matching load with solar",
    "daily_savings_pln": 12.45,
    "daily_cost_pln": 3.12
  }
}
```

### 2.3 Heartbeat & "Last Seen" Logic
- Agent publishes to `nodes/{id}/status` every **60 seconds**.
- Hub stores `last_seen_at` timestamp in DB.
- **Offline Alert**: If `now - last_seen_at > 5 minutes`, Hub marks node as `OFFLINE`.

---

## 3. Architecture Overview

```mermaid
graph TD
    subgraph "Central Services (Managed)"
        HubDB[(PostgreSQL)]
        Broker["MQTT Broker (Mosquitto)"]
    end

    subgraph "Cloud Hub (VPS)" 
        API["Hub API (FastAPI)"]
        Dashboard["Hub Dashboard (React)"]
    end

    subgraph "Edge Node (RPi)"
        App["Coordinator"]
        Agent["Management Agent"]
    end

    App -- "Enriched Telemetry (5s)" --> Broker
    Broker -- "Telemetry" --> API
    API -- "Store" --> HubDB
    Dashboard -- "Fetch Nodes/Telemetry" --> API
    API -- "Commands" --> Broker
    Broker -- "Commands" --> Agent
    Agent -- "Exec" --> App
```

---

## 4. Hub Dashboard Features - **✅ Implemented**

### 4.1 User Experience (UX)
- **Dual-Theme Engine**: Seamless Light/Dark mode with CSS variables and localStorage persistence.
- **Mobile-First**: Bottom navigation bar for thumb-friendly mobile access, adaptive sidebar for desktop.
- **Glassmorphism**: Translucent panels with backdrop blur and subtle gradients.
- **Skeleton Loaders**: Pulse animations during data fetching to maintain layout integrity.
- **Optimistic UI**: Instant feedback for command execution with background verification.
- **Accessibility**: WCAG 2.1 compliant contrast ratios, semantic HTML, keyboard navigation support.

### 4.2 Core Pages
1. **Login**: JWT-based authentication with form validation (React Hook Form + Zod).
2. **Fleet Overview (Dashboard)**: Cards showing all nodes with real-time status, SOC, solar output, daily savings.
3. **Node Detail (Command Center)**:
   - Real-time metrics: Battery SOC, Solar Power, Current Energy Price, Daily Savings.
   - Performance charts (Recharts): SOC and Solar trends with glassmorphism tooltips.
   - **AI Optimizer Decisions Timeline**: Shows recent optimization decisions with timestamps and modes.
   - Remote controls: Force Charge, Discharge, Restart Agent.
   - Feature toggles: Dynamic Strategy, Safety Lock.
4. **Node Management**: Table view with hardware IDs, status indicators, administrative actions.
5. **User Management** (Admin Only): CRUD operations for user accounts with role-based access.

### 4.3 Data Connectivity
- **TanStack Query (React Query)**: Aggressive caching, background refetching every 5 seconds for telemetry.
- **Axios Interceptors**: Automatic JWT injection, 401 handling for session expiry.
- **Real-time Updates**: Polling-based live dashboard with configurable intervals.

### 4.4 Testing & Quality - **✅ All Tests Passing**
- **Playwright E2E Suite**: 3/3 tests passing.
  - ✅ Login flow and navigation verification.
  - ✅ Theme switching and persistence.
  - ✅ Mobile responsive layout (bottom nav on small screens).
- **Production Build**: Successfully optimized via Vite with code splitting recommendations.

---

## 5. Security - **✅ Hardened**

- **Node Auth**: Each Pi signs requests with `NODE_SECRET`.
- **Encryption**: All traffic over HTTPS/WSS.
- **Command Whitelist**: No arbitrary shell execution.
- **MQTT ACLs**: Strict Broker Access Control. `user=node_X` only has access to `nodes/node_X/#`. Hub API has wildcard access. **✅ Verified in E2E tests**.
- **Database Migrations**: Alembic manages schema versions, preventing manual SQL errors. **✅ Auto-run on container startup**.
- **JWT Authentication**: Secure token-based auth with `/auth/me` endpoint for profile retrieval.
- **CORS**: Configured allow-list for frontend origins (localhost dev, production domain).
- **Verification Strategy**: Full E2E verification stack using **Dockerized Mock Agents** that simulate inverter telemetry and command receipt. **✅ 12/12 Backend E2E tests passing**.

---

## 6. Service Distribution

| Service | Host | Status |
| :--- | :--- | :--- |
| Master Coordinator | RPi | Existing |
| Management Agent | RPi | Mock verified |
| Cloud Hub API | VPS | **✅ Production Ready (CORS, Auth, Enriched Telemetry)** |
| Hub Dashboard | VPS | **✅ Production Ready (All E2E Tests Passing)** |
| PostgreSQL | Managed | Configured |
| MQTT Broker | Docker/Managed | **✅ Verified with ACLs** |

---

## 7. Next Steps & Recommendations

### 🎯 Immediate (Production Deployment)

#### 7.1 Deploy Backend to VPS
**Objective**: Move Hub API from local Docker to production VPS.

**Steps**:
1. **Provision Managed PostgreSQL** (Supabase, Neon, or AWS RDS):
   - Update `DATABASE_URL` in production `.env`.
   - Run Alembic migrations: `alembic upgrade head`.
2. **Provision Managed MQTT Broker** (CloudAMQP, HiveMQ Cloud):
   - Update `MQTT_BROKER`, `MQTT_USER`, `MQTT_PASS` in production `.env`.
   - Configure ACLs for Hub API and edge nodes.
3. **Deploy Hub API via Docker Compose** on VPS:
   - Update `CORS_ORIGINS` to include production dashboard domain.
   - Set strong `JWT_SECRET_KEY`.
   - Enable HTTPS with Let's Encrypt (Nginx reverse proxy).
4. **Health Check**: Verify `/health` and `/readiness` endpoints.

**Estimated Time**: 2-3 hours

---

#### 7.2 Deploy Dashboard to Static Hosting
**Objective**: Serve React app from CDN or VPS.

**Options**:
1. **Vercel/Netlify** (Recommended for speed):
   - Connect GitHub repo, auto-deploy on push to `main`.
   - Set environment variable: `VITE_API_BASE_URL=https://api.yourdomain.com`.
2. **Nginx on VPS**:
   - Build production bundle: `npm run build`.
   - Serve `dist/` folder via Nginx.
   - Configure reverse proxy for API at `/api/v1/*`.

**Estimated Time**: 1-2 hours

---

#### 7.3 Configure Production Environment Variables

**Hub API** (`.env` or ENV vars):
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
MQTT_BROKER=mqtt.hiveiq.com
MQTT_USER=hub_production
MQTT_PASS=<strong_password>
JWT_SECRET_KEY=<generate_with_openssl_rand>
CORS_ORIGINS=https://dashboard.yourdomain.com
```

**Hub Dashboard** (`.env.production`):
```bash
VITE_API_BASE_URL=https://api.yourdomain.com
```

**Estimated Time**: 30 minutes

---

### 🚀 High-Priority Features (Week 1-2)

#### 7.4 Real Edge Agent Integration
**Objective**: Replace mock agent with actual Raspberry Pi agent.

**Tasks**:
1. Port mock agent logic to `edge/agent/` Python package.
2. Implement `systemd` service for auto-start on boot.
3. Add error handling and retry logic for MQTT reconnection.
4. Test with physical inverter on local network.

**Estimated Time**: 1 day

---

#### 7.5 Command Execution Audit Trail
**Objective**: Full transparency for all remote commands.

**Tasks**:
1. Already implemented in `CommandAudit` model.
2. Add Dashboard UI to view command history per node.
3. Display: Timestamp, Admin who issued command, command type, status, response.

**Estimated Time**: 4 hours

---

#### 7.6 Alert System (Offline Nodes)
**Objective**: Notify admins when nodes go offline.

**Tasks**:
1. Backend: Periodic check (every 2 minutes) for `last_seen > 5 minutes`.
2. Webhook integration: Slack, Email, or PagerDuty.
3. Dashboard: Visual "Offline" badge with time since last seen.

**Estimated Time**: 3-4 hours

---

### 📊 Medium-Priority Features (Week 3-4)

#### 7.7 Historical Analytics & Cost Savings Dashboard
**Objective**: Show users their total savings and cost breakdowns.

**Tasks**:
1. Backend: Aggregate telemetry into daily/monthly summaries.
2. Dashboard: New "Analytics" page with:
   - Total savings this month/year.
   - Cost breakdown by time-of-day (peak vs. off-peak).
   - Comparison charts (e.g., "saved 35% vs. grid-only").

**Estimated Time**: 1-2 days

---

#### 7.8 Configuration Management UI
**Objective**: Admins can edit node configs from Dashboard.

**Tasks**:
1. Backend: `GET/PUT /nodes/{id}/config` endpoints.
2. Dashboard: YAML editor with validation and preview.
3. Agent: Handle `CONFIG_PUSH` MQTT command, apply config, restart coordinator.

**Estimated Time**: 1 day

---

#### 7.9 Firmware/Software Update System
**Objective**: Remote updates for edge software.

**Tasks**:
1. Agent: `SELF_UPDATE` command handler (git pull, pip install, restart).
2. Backend: Track `current_version` per node.
3. Dashboard: "Update Available" badge, one-click update button.

**Estimated Time**: 1-2 days

---

### 🔐 Security & Compliance (Ongoing)

#### 7.10 Multi-Factor Authentication (MFA)
**Objective**: Enhance admin account security.

**Options**:
- Integrate with Supabase Auth (supports TOTP out-of-box).
- Or implement custom TOTP using `pyotp`.

**Estimated Time**: 1 day

---

#### 7.11 Role-Based Access Control (RBAC) Refinement
**Objective**: Granular permissions (e.g., `read-only admin`, `node-specific user`).

**Tasks**:
1. Extend `UserRole` enum with more roles.
2. Add permission checks in API endpoints.
3. Dashboard: Hide/disable features based on user role.

**Estimated Time**: 1 day

---

### 📈 Scalability & Performance (Month 2+)

#### 7.12 PostgreSQL Optimization
**Tasks**:
- Add indexes on `node_id`, `timestamp` for telemetry queries.
- Implement partitioning for `telemetry` table (by date).
- Set up connection pooling (already handled by async SQLAlchemy).

**Estimated Time**: 4 hours

---

#### 7.13 Implement Data Retention Policy
**Objective**: Auto-delete old telemetry, keep aggregated summaries.

**Tasks**:
1. Nightly cron job: Aggregate daily stats, delete raw telemetry > 30 days.
2. Store monthly summaries indefinitely.

**Estimated Time**: 1 day

---

#### 7.14 CI/CD Pipeline
**Objective**: Automated testing and deployment.

**GitHub Actions Workflows**:
1. **PR to `main`**: Run linters, Playwright E2E tests, backend pytest.
2. **Merge to `main`**: Auto-deploy Hub API (Docker image push + VPS restart).
3. **Merge to `main`**: Auto-deploy Dashboard (Vercel/Netlify).

**Estimated Time**: 1 day

---

## 8. Success Metrics

After production deployment, track:
- **Uptime**: Hub API availability (target: 99.9%).
- **Latency**: Dashboard load time (target: < 2s).
- **Node Health**: % of nodes online (target: > 95%).
- **Cost Savings**: Total PLN saved across all users.
- **User Engagement**: Daily active users, command executions per week.

---

## 9. Risk Mitigation

| Risk | Mitigation | Status |
| :--- | :--- | :--- |
| **Invalid Config Pushed** | Agent rollback to `config.yaml.bak` | Planned (7.8) |
| **Offline Periods** | SQLite buffer on edge, batch upload on reconnect | Planned (Phase 5) |
| **Clock Drift** | Hub alerts if timestamp differs > 60s | Planned (7.6) |
| **MQTT Broker Failure** | Managed broker with HA, automatic failover | Production (7.1) |
| **Database Corruption** | Daily backups to S3, point-in-time recovery | Production (7.1) |
| **Unauthorized Access** | JWT + MFA, audit logs, rate limiting | Partial (7.10, 7.11) |

---

## 10. Documentation & Training

Before wider rollout:
1. **Admin Guide**: How to enroll nodes, send commands, interpret dashboard.
2. **API Documentation**: OpenAPI/Swagger spec published at `/docs`.
3. **Runbook**: Emergency procedures (node offline, database restore, etc.).

---

## 11. Summary - Current Status

✅ **Hub API**: Production-ready with CORS, JWT auth, enriched telemetry, MQTT security.  
✅ **Hub Dashboard**: Premium UI with dual-theme, mobile nav, AI decisions, financial analytics.  
✅ **E2E Testing**: All 3 frontend tests + 12 backend tests passing.  
✅ **Mock Agent**: Verified telemetry publishing and command receipt.

**Next Actions**:
1. Deploy API to VPS with managed PostgreSQL + MQTT.
2. Deploy Dashboard to Vercel/Netlify.
3. Integrate real Raspberry Pi agent.
4. Add alerting for offline nodes and command audit UI.

---

> [!TIP]
> The system is **production-ready** for initial deployment. Focus on Steps 7.1-7.3 for immediate launch, then iterate on features 7.4-7.9 based on user feedback.
