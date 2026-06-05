# ConnectKit Strategy

## The Core Insight

**Nango = integration platform that added agent tooling on top.**
**ConnectKit = agent tool runtime that uses connectors as the means, not the end.**

| Dimension | Nango | ConnectKit |
|-----------|-------|------------|
| Core abstraction | TypeScript functions that call APIs | Tools as first-class agent primitives |
| Who writes the integration | Human or AI → TypeScript, deployed to Nango | Agent discovers, connects, and invokes — zero human boilerplate |
| Tool model | Function with Zod schema → exposed via MEP | Tool = (auth + backend) discovered at runtime by the agent |
| Meta-tools | None | Agents manage their own tool belt |

## Positioning

> **ConnectKit: The agent-native tool runtime.**
>
> *Connectors aren't integrations. They're tools your agent discovers, connects, and composes — autonomously.*

| Old message | New message |
|---|---|
| "544+ YAML connector specs" | "Tools your agent can install without human help" |
| "Local OAuth router and encrypted vault" | "Durable, self-healing auth for unattended agents" |
| "CLI and MCP adapters" | "Pluggable backends: CLI, MCP, HTTP, and composed tools" |
| "Own the connector runtime" | "Own your agent's tool belt" |

## Where Nango cannot follow

Nango's architecture is a server with TypeScript functions. This creates structural gaps:

1. **Every new tool requires a deploy** — ConnectKit's YAML-only model means an agent can connect to a new SaaS service by just downloading a spec file. No CI/CD, no deployment.
2. **No local subprocess model** — Nango runs functions server-side. ConnectKit inherits the user's CLI environment: `gws`, `gh`, `aws`, `docker`, etc. are automatically tools.
3. **No local-first** — Nango free self-host is feature-gated. ConnectKit is fully local by design.
4. **No meta-tools** — Nango cannot let agents list, connect, disconnect, or compose tools dynamically because its model is "deploy TypeScript to our runtime." ConnectKit's model is "load a YAML, inject auth, spawn a process."

**The killer slide:** "Nango makes you deploy TypeScript. ConnectKit makes you write five lines of YAML. One requires a DevOps pipeline. The other requires a text editor."

## What to build

### P0 (quick wins, existing code)

1. **Decouple `meta_tools.py` from EA**
   - Currently imports `src.sdk.tools`, `src.config`, `src.app_logging` — EA-internal modules
   - Refactor into `connectkit/meta/` — return generic Pydantic models, not EA-specific ToolDefinition
   - Provide adapters: one dict output for EA, one for LangChain, one for OpenAI SDK
   - **Why:** Meta-tools are the strongest differentiator. They need to work anywhere.

2. **Implement real MCP lifecycle management**
   - Replace `_is_mcp_placeholder` stubs in `runtime.py` with a `MCPServerManager` that:
     - Spawns the MCP server subprocess with injected credentials
     - Calls `tools/list` at runtime to discover real tools
     - Proxies `tools/call` requests with per-user env isolation
     - Handles restart on crash and graceful shutdown
   - **Why:** MCP is the fastest-growing tool protocol. Placeholder stubs undercut credibility.

3. **Add token refresh**
   - OAuth tokens with `refresh_token` are stored but never used
   - Add `refresh_expired_tokens()` to vault, background check in runtime
   - **Why:** "Agent-native" means durable unattended operation. Stale tokens kill that promise.

4. **Switch `tool_descriptions` to JSON Schema**
   - Replace free-text `ToolDescription` with full JSON Schema for params and return types
   - Every connector spec produces an OpenAI-compatible `functions` array
   - **Why:** Agents need structured schemas to reason about tool calls, not free-text help strings.

### P1 (medium-term)

5. **Implement the HTTP backend**
   - `HTTPToolSource` is modeled in `spec.py` but `runtime.py` has no handling for `ToolSourceType.HTTP`
   - Build it: proxy calls through injected auth headers
   - **Why:** Many SaaS APIs are HTTP-native. CLI and MCP are not always available.

6. **Add credential validation on connect**
   - After storing a token, make a test call (e.g., `GET /user` or equivalent)
   - Report connection status as "connected" or "broken" immediately
   - **Why:** Silent failures erode trust in unattended agents.

7. **Add tool deduplication**
   - If a connector has both CLI and MCP sources, pick the best one (MCP > CLI > HTTP) instead of returning duplicate tools
   - **Why:** Agents shouldn't see the same capability twice.

### P2 (moonshot differentiator)

8. **Dynamic tool composition**
   - Build a `compose` meta-tool that lets an agent create new tools at runtime
   - Example: "Create a tool that searches Gmail for invoices, extracts amounts, and writes them to a Google Sheet"
   - ConnectKit chains `gmail.search` → `sheets.append` and registers the result as a named tool
   - **Why:** This is where you leapfrog Nango entirely. They require a human to write a TypeScript function. ConnectKit lets the agent do it.
   - **Message:** "Agents don't just *use* tools. They *compose* them."

## Competitor comparison

| Feature | ConnectKit | Nango (OSS) | Nango (Cloud) | Composio | Arcade |
|---------|-----------|-------------|---------------|----------|--------|
| OSS license | MIT | MIT | Proprietary | Partial | No |
| Self-hosted with full features | Yes | No (feature-gated) | N/A | N/A | No |
| YAML-only connector model | Yes | No (TypeScript) | No (TypeScript) | No | No |
| Local CLI subprocess tools | Yes | No | No | No | No |
| Per-user encrypted vault | Yes | Server-side | Server-side | Server-side | Server-side |
| Meta-tools for agents | Partial (EA-coupled) | No | No | No | No |
| MCP lifecycle management | No (placeholder) | No | Yes (hosted) | Yes | Yes |
| Token refresh | No | Yes | Yes | Yes | Yes |
| Dynamic tool composition | No | No | No | No | No |
| Structured LLM tool schemas | Partial (free-text) | Yes (Zod) | Yes (Zod) | Yes | Yes |

## The narrative

When someone asks "why not just use Nango?":

"Nango connects your app to APIs. ConnectKit connects your agent to tools. That sounds similar but it's a different model: Nango runs TypeScript functions on their server; ConnectKit loads a YAML spec, injects local credentials, and spawns CLI or MCP processes on your machine. One requires a deployment pipeline. The other requires a text editor. One treats tools as API wrappers. The other treats tools as capabilities an agent discovers, connects, and composes autonomously."
