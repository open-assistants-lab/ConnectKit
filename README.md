# ConnectKit

> **Purposefully built for AI Agents.** ConnectKit gives agents access to user SaaS accounts — Gmail, Calendar, Drive, GitHub, Slack, and more — through one YAML file per service. OAuth, API keys, token vault, and tool discovery handled automatically. Used in production by the [Executive Assistant](https://github.com/open-assistants-lab) agent system.

> **Embedded. Local. Open source.** No cloud APIs, no hosted auth services, no internet connection required for setup. Runs entirely on-device with an encrypted SQLite credential vault + local YAML specs. Ships as a single Python package with zero external infrastructure dependencies.

**Connect AI agents to SaaS.** One YAML file per service. OAuth, token vault, and tool discovery — handled automatically.

```python
from connectkit import ConnectKitBridge

bridge = ConnectKitBridge(user_id="alice")
await bridge.discover()

# Agent gets tools for all connected services
tools = bridge.get_tool_definitions()
# → [google-workspace__gmail_list, github__issue_list, ...]

# Show the connector catalog
catalog = bridge.list_available()
# → [{name: "google-workspace", connected: true, ...}, ...]
```

## Why ConnectKit?

Every AI agent that needs access to user SaaS accounts ends up wiring three things together: OAuth flows, credential storage, and CLI tool wrappers. You build `/auth/google/login`, `/auth/google/callback`, token refresh logic, subprocess calls for `gws gmail list`... then you do it again for GitHub, again for Outlook.

ConnectKit does all of that once, done right. One YAML file per service. No Python code per connector.

| Feature | Status |
|---------|--------|
| YAML-based connector spec (no Python code per service) | ✅ |
| Encrypted SQLite credential vault (Fernet) | ✅ |
| Universal OAuth 2.0 router (one endpoint, all services) | ✅ |
| CLI adapter backend (wraps any SaaS CLI) | ✅ |
| MCP adapter backend (connects to MCP servers) | ✅ |
| Connector catalog (list available services + status) | ✅ |
| Agent meta-tools (list, connect, disconnect, health) | ✅ |
| Per-user credential isolation | ✅ |
| No external API dependencies (works offline) | ✅ |
| 4 connectors shipped (Google Workspace, Microsoft 365, GitHub, Firecrawl) | ✅ |

## Installation

```bash
pip install connectkit
```

## Core Concepts

### One YAML file per service

```yaml
# connectors/google-workspace.yaml
name: google-workspace
display: "Google Workspace"
setup_guide_url: "https://developers.google.com/workspace/guides/create-credentials"
auth:
  type: oauth2
  oauth2:
    authorize_url: https://accounts.google.com/o/oauth2/v2/auth
    token_url: https://oauth2.googleapis.com/token
    scopes:
      - https://www.googleapis.com/auth/gmail.readonly
      - https://www.googleapis.com/auth/calendar.readonly
  required_fields:
    - name: client_id
      label: "Client ID"
      input_type: text
    - name: client_secret
      label: "Client Secret"
      input_type: password
tool_source:
  type: cli
  command: gws
  install: npm install -g @googleworkspace/cli
  env_mapping:
    access_token: GWS_ACCESS_TOKEN
tool_descriptions:
  - name: google_workspace__gmail_messages_list
    description: "List recent emails from the user's Gmail inbox"
```

### Auth types

| Type | Use for | Example |
|------|---------|---------|
| `oauth2` | Services with OAuth 2.0 (Google, Microsoft, GitHub, Slack) | User clicks Connect → browser authorization → tokens vaulted |
| `api_key` | Services with API keys (Firecrawl, Stripe, Twilio) | User pastes key into form → stored in vault |
| `none` | No auth needed (local tools, agent-browser) | Auto-connected |

### Tool source backends

| Backend | How it works | Best for |
|---------|-------------|----------|
| **CLI** | Subprocess with per-user env vars | Services with good CLIs (gws, gh, m365, firecrawl) |
| **MCP** | MCP server with vault token injection | Services with MCP servers (gws mcp, dropbox-mcp) |
| **HTTP** | Declarative REST client (deferred) | Services with REST APIs only |

### CredentialVault

All tokens are stored in an encrypted SQLite database (Fernet encryption). One vault per user. Master key from `CONNECTKIT_VAULT_KEY` env var.

```python
from connectkit import CredentialVault

vault = CredentialVault("./data/users/alice")
vault.store_token("google-workspace", "oauth2", {
    "access_token": "ya29...", "refresh_token": "1//..."
})
token = vault.get_token("google-workspace")
```

### OAuth flow

```python
# 1. User fills in client_id + client_secret → stored in vault
# 2. Flutter renders "Connect" button → opens:
#    GET /auth/login?service=google-workspace&user_id=alice
# 3. Browser redirects to Google OAuth → user authorizes
# 4. Google redirects to:
#    GET /auth/callback?code=...&state=...
# 5. Gateway exchanges code for tokens → stores in vault
# 6. Google Workspace: ✅ Connected
```

OAuth states are Fernet-encrypted and self-contained — any vault with the same key can validate them (10-minute TTL).

## Shipped Connectors

| Connector | Auth | Backend | Tools |
|-----------|------|---------|-------|
| **Google Workspace** | OAuth2 | GWS CLI | Gmail, Calendar, Drive, Contacts |
| **Microsoft 365** | OAuth2 | M365 CLI | Outlook, Calendar, OneDrive |
| **GitHub** | OAuth2 | gh CLI | Issues, PRs, repos, search |
| **Firecrawl** | API Key | Firecrawl CLI | Scrape, search, crawl |

## License

MIT — see [LICENSE](LICENSE).

## Author

Eddy Xu

## Status

Alpha — actively developed, API may evolve. Core spec model, vault, OAuth router, and adapter backends are stable with full test coverage (125+ tests). Currently used in production in the Executive Assistant agent system.
