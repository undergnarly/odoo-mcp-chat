# Technical Specification: Odoo AI Agent Microservice for Procurement Automation

## 🎯 Project Goal

Build a production-ready microservice that acts as an **intelligent AI agent waiting for user/agent requests** about Odoo ERP. The agent processes natural language queries and **performs actions** in Odoo using REAL data - not hallucinations.

**Primary Focus**: Automate Procurement Department manager workflows while building a **universal, scalable system** that works with any Odoo module.

**Core Principle**: **DON'T REINVENT THE WHEEL** - Use proven, battle-tested libraries and frameworks. Assemble existing solutions.

**Foundation**: We will **fork and extend** the excellent [`tuanle96/mcp-odoo`](https://github.com/tuanle96/mcp-odoo) library (235⭐, MIT license) which already provides:
- ✅ MCP Server implementation
- ✅ XML-RPC Odoo connection
- ✅ Resource system for read operations
- ✅ Configuration management
- ✅ Docker support

**What We're Adding**:
- 🆕 Write operations (create, update, delete, actions)
- 🆕 Dynamic model/tool discovery
- 🆕 Chainlit web chat UI
- 🆕 LLM-powered intent router
- 🆕 Safety layer (confirmations, audit)
- 🆕 Procurement-specific workflows

**Key Requirement**: The system must **dynamically discover ALL available Odoo models and fields**, so it can answer ANY question and perform ANY action in the Odoo instance.

## 🏗️ Architecture (Based on mcp-odoo Foundation)

```
┌─────────────────────────────────────────────────────┐
│          User / External Agent                      │
│  • Procurement Manager (web chat)                  │
│  • External AI Agent (via API)                     │
│  • LangChain Agent                                  │
│  • Mobile App / Slack Bot                          │
└────────┬────────────────────────────────────────────┘
         │
         │ HTTP / WebSocket / MCP / A2A
         ▼
┌─────────────────────────────────────────────────────┐
│   🎨 OUR WEB UI LAYER (NEW)                        │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│   • Chainlit Web Chat                              │
│   • File upload/download                           │
│   • Interactive UI elements                        │
│   • Multi-user support                             │
└────────┬────────────────────────────────────────────┘
         │
┌────────┴────────────────────────────────────────────┐
│   🧠 OUR INTELLIGENCE LAYER (NEW)                  │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│   • LangChain Agent                                │
│   • Intent Router (NL → Odoo operation)           │
│   • Conversation Memory                            │
│   • Safety Validator                               │
│   • Confirmation Handler                           │
└────────┬────────────────────────────────────────────┘
         │
┌────────┴────────────────────────────────────────────┐
│   🔧 EXTENDED MCP SERVER LAYER (EXTEND)            │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│   🆕 OUR EXTENSIONS:                                │
│   • Dynamic Model Discovery Engine                 │
│   • Write Operations (create, update, delete)     │
│   • Action Methods (approve, send, etc.)          │
│   • Audit Logging System                          │
│   • Permission Checker                             │
│   • Procurement Workflows                          │
│                                                     │
│   ✅ FROM mcp-odoo (tuanle96):                     │
│   • MCP Protocol Implementation                    │
│   • Resources (read operations)                    │
│   • execute_method() tool                          │
│   • XML-RPC Connection                             │
│   • Configuration Management                        │
│   • Error Handling                                 │
└────────┬────────────────────────────────────────────┘
         │
         │ XML-RPC (bidirectional: read AND write)
         ▼
┌─────────────────────────────────────────────────────┐
│              Odoo ERP Instance                      │
│                                                     │
│  📊 READ Operations (via mcp-odoo resources):      │
│  • odoo://models - list all models                │
│  • odoo://model/{name} - model metadata           │
│  • odoo://record/{model}/{id} - get record        │
│  • odoo://search/{model}/{domain} - search        │
│                                                     │
│  ✏️ WRITE Operations (our extensions):             │
│  • create_record() - create new records           │
│  • update_record() - modify records               │
│  • call_action() - execute button actions         │
│  • post_message() - chatter messages              │
│  • attach_file() - file attachments               │
└─────────────────────────────────────────────────────┘
```

**Key Architecture Principle**: 
We're building a **layered system** where each layer adds value without breaking the foundation. The `mcp-odoo` library gives us a solid base (~50% of the work), and we add intelligence, UI, and safety on top.

## 📋 Core Requirements

### 1. Agent Always Running - Waiting for Requests

**The microservice MUST**:
- Run as a background service (daemon)
- Listen for incoming requests via multiple channels:
  - Web Chat UI (Chainlit)
  - REST API endpoints
  - WebSocket connections
  - MCP protocol endpoint
  - A2A protocol endpoint
- Process requests asynchronously (non-blocking)
- Maintain conversation context/memory
- Support multiple concurrent users

### 2. Dynamic Odoo Model Discovery & Action Mapping

**The system MUST**:
- Connect to Odoo and fetch ALL available models using `ir.model`
- For each model, fetch ALL fields AND available methods using `fields_get()`
- **Discover available actions**: button actions, workflow transitions, automation rules
- Create dynamic tool definitions for:
  - **Read operations**: search, read, count
  - **Write operations**: create, update, delete
  - **Action operations**: approve, send email, change state, attach files
- Store model + action metadata in memory for fast access
- Support periodic refresh of model list (when Odoo modules change)

**Example queries + actions this enables**:

**QUERIES (Read)**:
- "What's our total spent on purchases this month?" → searches `purchase.order` model
- "Show me pending RFQs from supplier X" → searches `purchase.order` with state filter
- "How many products are below minimum stock?" → searches `stock.warehouse.orderpoint`

**ACTIONS (Write)**:
- "Approve purchase order PO-1234" → calls action_approve() method
- "Send RFQ to all suppliers for Product XYZ" → creates purchase.order records
- "Change status of PO-1234 to done" → updates state field
- "Add comment to PO-1234: Delivery delayed" → posts message to chatter
- "Attach invoice.pdf to PO-1234" → creates ir.attachment record

### 3. LLM-Powered Intent Router

**The system MUST include an intelligent router that**:
- Receives user request in natural language (any language)
- Uses LLM to determine:
  - **Intent**: Is this a query (read) or action (write)?
  - **Target model(s)**: Which Odoo models to work with?
  - **Parameters**: What filters, values, or files are needed?
  - **Safety check**: Is this action allowed/safe?
- Generates appropriate:
  - **Domain filters** for queries (Odoo search syntax)
  - **Method calls** for actions (with correct parameters)
  - **Validation** before executing write operations
- Handles follow-up questions with context
- Explains what it's doing (transparency)

**Example**:
```
User: "Approve all purchase orders from last week that are under $5000"

Router determines:
  Intent: ACTION (approve)
  Model: purchase.order
  Filters: [['create_date', '>=', '2026-01-12'], 
           ['create_date', '<=', '2026-01-18'],
           ['amount_total', '<', 5000],
           ['state', '=', 'to approve']]
  Method: action_approve()
  Safety: Check user permissions, confirm count before executing
  
Response: "Found 12 purchase orders matching your criteria. 
           Shall I approve all 12? (yes/no)"
```

### 4. Procurement Department Automation (Priority Use Cases)

**Core Procurement Workflows to Support**:

**A. Purchase Order Management**:
- ✅ View pending POs
- ✅ Approve/Reject POs
- ✅ Change PO status
- ✅ Add comments/notes to POs
- ✅ Attach documents (quotes, invoices)
- ✅ Send PO to supplier via email

**B. RFQ (Request for Quotation) Management**:
- ✅ Create RFQs for products
- ✅ Send RFQs to multiple suppliers
- ✅ Track RFQ responses
- ✅ Compare supplier quotes

**C. Supplier Management**:
- ✅ View supplier information
- ✅ Check supplier performance
- ✅ Update supplier details
- ✅ Send messages to suppliers

**D. Inventory Monitoring**:
- ✅ Check stock levels
- ✅ View products below minimum stock
- ✅ Check incoming shipments
- ✅ Trigger reorder points

**E. Reporting & Analytics**:
- ✅ Monthly spend by category
- ✅ Top suppliers by volume
- ✅ Pending approvals summary
- ✅ Delivery performance metrics

### 5. Multi-Protocol Support

**The service MUST expose**:
- **Web Chat UI** (Chainlit) - Primary interface for Procurement Manager
- **REST API** (`/api/query` and `/api/action`) for external integrations
- **WebSocket** for real-time streaming responses
- **MCP endpoint** (`/mcp`) for Claude Desktop, Cursor, etc.
- **A2A endpoint** (`/agent`) for agent-to-agent communication
- **Health check** (`/health`) for monitoring

### 6. Safety & Permission System

**Critical for write operations**:
- **User authentication** via API key or Odoo session
- **Permission checking** before any write operation
- **Confirmation prompts** for destructive actions
- **Audit logging** of all actions performed
- **Rollback capability** for failed operations
- **Rate limiting** to prevent abuse

## 🛠️ Technical Stack (Built on mcp-odoo Foundation)

### 🏗️ **FOUNDATION: mcp-odoo (Fork & Extend)**

```bash
# Our fork of the excellent mcp-odoo library
git clone https://github.com/YOUR_USERNAME/mcp-odoo.git
cd mcp-odoo
pip install -e .  # Install as editable for development
```

**What mcp-odoo Gives Us (Out of Box)**:
- ✅ MCP Server implementation (saves 1 week)
- ✅ XML-RPC Odoo connection (proven, stable)
- ✅ Resource system: `odoo://models`, `odoo://model/{name}`, etc.
- ✅ `execute_method()` tool (can call any Odoo method)
- ✅ Configuration via env vars or JSON file
- ✅ Docker support
- ✅ Error handling for common Odoo issues
- ✅ MIT License (free to modify)

### ⭐ **PRIMARY ADDITIONS: Our Extensions**

```bash
# On top of mcp-odoo, we add:
pip install chainlit>=1.0.0              # AI chat UI
pip install langchain>=0.1.0             # LLM orchestration
pip install langchain-openai             # OpenAI integration
pip install langchain-anthropic          # Claude integration
pip install python-a2a>=0.5.10           # A2A protocol (optional)
pip install fastapi>=0.109.0             # REST API layer
pip install uvicorn>=0.27.0              # ASGI server
pip install redis>=5.0.0                 # Caching & sessions
pip install loguru                       # Better logging
pip install python-dotenv                # Environment variables
```

### 📦 **Complete Dependency Tree**

```python
# pyproject.toml or requirements.txt

# ========================================
# FOUNDATION (mcp-odoo - fork & extend)
# ========================================
# Install from our fork:
git+https://github.com/YOUR_USERNAME/mcp-odoo.git@main

# mcp-odoo's dependencies (auto-installed):
# - mcp>=0.9.0
# - xmlrpc (built-in Python)
# - python-dotenv

# ========================================
# WEB UI LAYER
# ========================================
chainlit>=1.0.0              # AI chat interface (PRIMARY UI)

# ========================================
# INTELLIGENCE LAYER
# ========================================
langchain>=0.1.0             # LLM orchestration
langchain-community          # Community integrations
langchain-openai             # OpenAI/GPT support
langchain-anthropic          # Claude support
# langchain-ollama           # Local LLMs (optional)

# ========================================
# API & PROTOCOL LAYER
# ========================================
fastapi>=0.109.0             # REST API framework
uvicorn[standard]>=0.27.0    # ASGI server with websockets
python-a2a>=0.5.10           # A2A protocol (optional)
pydantic>=2.5.0              # Data validation

# ========================================
# INFRASTRUCTURE
# ========================================
redis>=5.0.0                 # Caching & session storage
loguru>=0.7.0                # Advanced logging
python-dotenv>=1.0.0         # Environment management

# ========================================
# LLM PROVIDERS (choose one or more)
# ========================================
anthropic>=0.18.0            # Claude API (RECOMMENDED)
openai>=1.12.0               # GPT API (alternative)

# ========================================
# UTILITIES
# ========================================
pydantic-settings>=2.1.0     # Settings management
asyncio                      # Async operations (built-in)
```

### 🎨 **Why This Stack Works**

| Component | What It Does | Why This Choice |
|-----------|--------------|-----------------|
| **mcp-odoo** (base) | MCP server + Odoo connection | ✅ Already works, battle-tested, saves weeks |
| **Chainlit** | Web chat UI | ✅ Purpose-built for AI chat, beautiful |
| **LangChain** | LLM orchestration | ✅ Industry standard, huge ecosystem |
| **FastAPI** | REST API | ✅ Fast, modern, auto-docs |
| **Claude** | LLM provider | ✅ Best for intent understanding & safety |
| **Redis** | Caching/sessions | ✅ Industry standard, fast |

### 🔄 **Data Flow with mcp-odoo**

```
User Input (Chainlit)
    ↓
LangChain Agent
    ↓
Decides: Query or Action?
    ↓
[Query Path]                     [Action Path]
    ↓                                ↓
Use mcp-odoo resources          Call our extended tools
(odoo://search/...)             (create_record, call_action)
    ↓                                ↓
mcp-odoo's XML-RPC ←────────────→ Our Safety Layer
    ↓                                ↓
Odoo ERP                        Confirm → Execute
    ↓                                ↓
Format & Return ←────────────────┘
```

### 🆕 **What We're Building (Not Using Libraries)**

1. **Dynamic Model Discovery Engine** - Odoo-specific logic
2. **Intent Router** - Natural language → Odoo operation mapping
3. **Action Executor** - Safe write operations with confirmations
4. **Procurement Workflows** - Domain-specific business logic
5. **Safety Layer** - Permission checks, audit logs, confirmations

## 📁 Project Structure (Extending mcp-odoo)

```
odoo-ai-agent/
├── mcp-odoo/                   # Forked submodule from tuanle96/mcp-odoo
│   ├── src/odoo_mcp/          # Original mcp-odoo code
│   │   ├── server.py          # ✅ MCP server (use as-is)
│   │   ├── resources.py       # ✅ Resources (use as-is)
│   │   └── tools.py           # ✅ Base tools (use as-is)
│   ├── pyproject.toml         # ✅ Original config
│   └── README.md              # ✅ Original docs
│
├── src/
│   ├── main.py                # Main entry point (orchestrates everything)
│   ├── config.py              # Configuration management
│   │
│   ├── extensions/            # 🆕 OUR EXTENSIONS TO mcp-odoo
│   │   ├── __init__.py
│   │   ├── write_tools.py     # 🆕 create_record, update_record, etc.
│   │   ├── action_tools.py    # 🆕 call_action, post_message, attach_file
│   │   ├── discovery.py       # 🆕 Dynamic model/action discovery
│   │   └── safety.py          # 🆕 Permission checks, confirmations
│   │
│   ├── ui/
│   │   └── chainlit_app.py    # 🆕 Chainlit web chat UI
│   │
│   ├── agent/
│   │   ├── router.py          # 🆕 LLM-powered intent router
│   │   ├── prompts.py         # 🆕 System prompts
│   │   ├── memory.py          # 🆕 Conversation memory
│   │   └── langchain_agent.py # 🆕 LangChain agent setup
│   │
│   ├── api/
│   │   ├── rest.py            # 🆕 FastAPI REST endpoints
│   │   ├── a2a.py             # 🆕 A2A protocol server (optional)
│   │   └── websocket.py       # 🆕 WebSocket handler
│   │
│   └── utils/
│       ├── logging.py         # Logging configuration
│       ├── cache.py           # Redis caching
│       ├── audit.py           # 🆕 Audit logging
│       └── security.py        # 🆕 Auth & permissions
│
├── procurement/               # 🆕 PROCUREMENT-SPECIFIC FEATURES
│   ├── __init__.py
│   ├── workflows.py           # Purchase order, RFQ workflows
│   ├── prompts.py             # Procurement domain prompts
│   └── tools.py               # Specialized procurement tools
│
├── tests/
│   ├── test_mcp_integration.py  # Test integration with base mcp-odoo
│   ├── test_extensions.py       # Test our extensions
│   ├── test_write_operations.py # Test write operations
│   ├── test_router.py           # Test intent router
│   └── test_procurement.py      # Test procurement workflows
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── .env.example
├── requirements.txt          # Our additional dependencies
├── pyproject.toml           # Our project config
└── README.md                # Our documentation

# Key Principles:
# 1. DON'T modify mcp-odoo/* - keep it as git submodule
# 2. All extensions go in src/extensions/
# 3. Use mcp-odoo's server as base, extend with our tools
# 4. Keep procurement logic separate for clarity
```

## 🔑 Key Implementation Details

### 1. Model Discovery System

```python
class OdooModelDiscovery:
    """
    Discovers all models and fields from Odoo instance
    """
    
    async def discover_all_models(self) -> Dict[str, ModelMetadata]:
        """
        Fetch all models from ir.model
        Returns: {
            'res.partner': ModelMetadata(...),
            'sale.order': ModelMetadata(...),
            ...
        }
        """
        
    async def get_model_fields(self, model_name: str) -> Dict[str, FieldMetadata]:
        """
        Get all fields for a specific model using fields_get()
        """
        
    async def refresh_models(self):
        """
        Periodic refresh of model list (every 5 minutes)
        """
```

### 2. Dynamic MCP Tool Generator

```python
class DynamicMCPToolGenerator:
    """
    Generates MCP tools for every Odoo model
    """
    
    def generate_search_tool(self, model_name: str, model_meta: ModelMetadata):
        """
        Creates a search tool like: search_res_partner, search_sale_order
        """
        
    def generate_create_tool(self, model_name: str, model_meta: ModelMetadata):
        """
        Creates a create tool like: create_crm_lead, create_sale_order
        """
        
    def generate_update_tool(self, model_name: str, model_meta: ModelMetadata):
        """
        Creates an update tool
        """
```

### 3. LLM Query Router

```python
class QueryRouter:
    """
    Routes natural language queries to appropriate Odoo models
    """
    
    async def route_query(self, user_query: str, context: dict) -> QueryPlan:
        """
        Input: "Show me unpaid invoices from last month"
        Output: QueryPlan(
            models=['account.move'],
            domains=[[['state', '=', 'posted'], ['payment_state', '!=', 'paid']]],
            fields=['name', 'partner_id', 'amount_total'],
            explanation="Searching for invoices..."
        )
        """
        
    async def execute_plan(self, plan: QueryPlan) -> QueryResult:
        """
        Executes the query plan and returns results
        """
```

## 🚀 Implementation Plan (Building on mcp-odoo Foundation)

### Phase 0: Fork & Setup mcp-odoo (Day 1)
**Goal**: Get the base MCP server running

- [ ] Fork `tuanle96/mcp-odoo` to your GitHub
- [ ] Clone your fork as git submodule
- [ ] Install and test base mcp-odoo:
  ```bash
  cd mcp-odoo
  pip install -e .
  python run_server.py
  ```
- [ ] Test with Claude Desktop (verify MCP works)
- [ ] Read and understand the codebase (~500 lines)
- [ ] Test existing resources: `odoo://models`, `odoo://search/...`
- [ ] Test `execute_method()` tool

**Deliverable**: Base mcp-odoo running, connected to your Odoo instance

---

### Phase 1: Extend with Write Operations (Days 2-3)
**Goal**: Add create, update, delete capabilities

- [ ] Create `src/extensions/write_tools.py`
- [ ] Implement tools extending mcp-odoo:
  ```python
  @mcp_server.tool()
  def create_record(model: str, values: dict)
  
  @mcp_server.tool()
  def update_record(model: str, record_id: int, values: dict)
  
  @mcp_server.tool()
  def delete_record(model: str, record_id: int)
  ```
- [ ] Reuse mcp-odoo's XML-RPC connection
- [ ] Add basic validation
- [ ] Test: create a purchase.order record

**Deliverable**: Can perform write operations via MCP tools

---

### Phase 2: Dynamic Discovery Engine (Days 4-5)
**Goal**: Auto-discover all Odoo models and actions

- [ ] Create `src/extensions/discovery.py`
- [ ] Implement dynamic model discovery:
  - Query `ir.model` for all models
  - Get fields via `fields_get()`
  - Discover action methods (buttons)
- [ ] Cache discovered models in Redis
- [ ] Generate tool descriptions dynamically
- [ ] Test: discover purchase.order model + actions

**Deliverable**: System knows about all Odoo models automatically

---

### Phase 3: Action Methods & Safety (Days 6-7)
**Goal**: Execute Odoo actions with safety checks

- [ ] Create `src/extensions/action_tools.py`
- [ ] Implement action tools:
  ```python
  @mcp_server.tool()
  def call_action(model, record_id, method_name)
  
  @mcp_server.tool()
  def post_message(model, record_id, body)
  
  @mcp_server.tool()
  def attach_file(model, record_id, filename, content)
  ```
- [ ] Create `src/extensions/safety.py`
- [ ] Add confirmation prompts for write operations
- [ ] Add permission checking (respect Odoo ACLs)
- [ ] Add audit logging to file
- [ ] Test: approve a PO with confirmation

**Deliverable**: Safe action execution with audit trail

---

### Phase 4: LangChain Agent + Intent Router (Days 8-9)
**Goal**: Understand natural language and route to correct tools

- [ ] Create `src/agent/router.py`
- [ ] Set up LangChain with Claude/GPT
- [ ] Create system prompts in `src/agent/prompts.py`
- [ ] Implement intent classification:
  - Query (read) vs Action (write)
  - Which model(s) to use
  - Generate domain filters or action parameters
- [ ] Add conversation memory
- [ ] Connect all MCP tools (base + extensions) to LangChain
- [ ] Test: "Show me pending POs" → routes to search
- [ ] Test: "Approve PO-1234" → routes to call_action

**Deliverable**: NL queries work end-to-end

---

### Phase 5: Chainlit Web UI (Days 10-11)
**Goal**: Beautiful chat interface for users

- [ ] Install Chainlit
- [ ] Create `src/ui/chainlit_app.py`
- [ ] Integrate LangChain agent
- [ ] Add streaming responses
- [ ] Add file upload support
- [ ] Add interactive buttons (Approve, Reject)
- [ ] Add conversation history
- [ ] Customize branding (logo, colors)
- [ ] Test full flow: user asks → agent responds → action executes

**Deliverable**: Working web chat interface at `localhost:8080`

---

### Phase 6: Procurement Workflows (Days 12-13)
**Goal**: Specific Procurement Manager use cases

- [ ] Create `procurement/workflows.py`
- [ ] Implement workflows:
  - View/filter pending POs
  - Approve/reject POs with one click
  - Create RFQs for multiple suppliers
  - Send emails to suppliers
  - Check stock levels
  - Generate spend reports
- [ ] Create `procurement/prompts.py` with domain knowledge
- [ ] Add procurement-specific tools
- [ ] Test with real procurement scenarios
- [ ] Add file handling (attach invoices, specs)

**Deliverable**: Fully functional Procurement automation

---

### Phase 7: REST API & Additional Protocols (Days 14-15)
**Goal**: External integrations

- [ ] Create `src/api/rest.py` with FastAPI
- [ ] Add endpoints:
  - POST /api/query - for read operations
  - POST /api/action - for write operations
  - GET /health - health check
  - GET /models - list available models
- [ ] Add API key authentication
- [ ] (Optional) Add A2A protocol support
- [ ] Write OpenAPI documentation
- [ ] Test via curl and Postman

**Deliverable**: Service accessible via REST API

---

### Phase 8: Production Ready (Days 16-17)
**Goal**: Deploy and monitor

- [ ] Create Docker setup
- [ ] Configure Redis for production
- [ ] Add comprehensive error handling
- [ ] Add rate limiting (per user/API key)
- [ ] Set up monitoring (health checks, metrics)
- [ ] Write deployment guide
- [ ] Write user documentation
- [ ] Performance testing (load test)
- [ ] Security audit
- [ ] Create backup/restore procedures

**Deliverable**: Production-ready microservice

---

### Optional Phase 9: Advanced Features
- [ ] Voice interface (speech-to-text)
- [ ] Slack bot integration
- [ ] Email notifications
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Mobile app support

---

## 📊 Time Savings from Using mcp-odoo

| Task | From Scratch | With mcp-odoo | Saved |
|------|-------------|---------------|-------|
| MCP Protocol Implementation | 5 days | 0 days | **5 days** |
| XML-RPC Connection | 2 days | 0 days | **2 days** |
| Resource System | 3 days | 0 days | **3 days** |
| Configuration | 1 day | 0 days | **1 day** |
| Error Handling | 2 days | 0 days | **2 days** |
| Docker Setup | 1 day | 0 days | **1 day** |
| **TOTAL** | **~4 weeks** | **~2.5 weeks** | **~1.5 weeks** |

## 🤔 Why Use mcp-odoo as Foundation?

### Evaluation of Available Odoo MCP Servers

| Library | Stars | Status | Pros | Cons | Verdict |
|---------|-------|--------|------|------|---------|
| **tuanle96/mcp-odoo** | 235⭐ | ✅ Active | • Working MCP server<br>• XML-RPC connection<br>• Resource system<br>• Docker support<br>• MIT License<br>• ~500 lines (readable) | • No write operations<br>• Limited tools<br>• No dynamic discovery | ✅ **CHOOSE THIS** |
| ivnvxd/mcp-server-odoo | 180⭐ | ✅ Active | • Similar features | • More complex<br>• Less documentation | ⚠️ Alternative |
| hachecito/odoo-mcp-improved | 45⭐ | ⚠️ Unclear | • Claims improvements | • Less proven | ❌ Too risky |
| Build from scratch | - | - | • Full control | • 4+ weeks work<br>• Need to learn MCP spec<br>• Reinventing wheel | ❌ Waste of time |

### Time Investment Analysis

```
Option 1: Build Everything from Scratch
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MCP Protocol Implementation    [████████] 5 days
XML-RPC Connection             [███] 2 days
Resource System                [█████] 3 days
Error Handling                 [███] 2 days
Configuration Management       [█] 1 day
Docker Setup                   [█] 1 day
Testing                        [███] 2 days
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL: ~16 days (~2.5 weeks)

Option 2: Fork & Extend mcp-odoo ⭐
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fork & Understand Codebase     [█] 1 day
Add Write Operations           [███] 2 days
Add Dynamic Discovery          [███] 2 days
Add Safety Layer               [███] 2 days
Testing Extensions             [██] 1.5 days
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL: ~8.5 days (~1.5 weeks)

TIME SAVED: 7.5 days (~1 week)
```

### What mcp-odoo Gives Us Out of the Box

```python
# ✅ Already Working in mcp-odoo:

# 1. MCP Server
from mcp import Server
server = Server("odoo-mcp")  # Done ✅

# 2. Resources (read operations)
odoo://models                          # List all models ✅
odoo://model/purchase.order           # Model info ✅
odoo://record/purchase.order/123      # Get record ✅
odoo://search/purchase.order/[...]   # Search ✅

# 3. Tools
execute_method(model, method, args)   # Execute any Odoo method ✅

# 4. Configuration
ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD  # ✅

# 5. XML-RPC Connection
# Proven, stable, handles auth, errors, timeouts ✅
```

### What We Need to Add

```python
# 🆕 Our Extensions on Top:

# 1. Write Operations Tools
@server.tool()
def create_record(model: str, values: dict)  # NEW

@server.tool()
def update_record(model: str, id: int, values: dict)  # NEW

@server.tool()
def call_action(model: str, id: int, method: str)  # NEW

# 2. Dynamic Discovery
def discover_all_models()  # NEW
def generate_tools_dynamically()  # NEW

# 3. Safety & Audit
def confirm_action(action_plan)  # NEW
def log_audit(user, action, details)  # NEW

# 4. Intelligence Layer (separate from MCP)
- Chainlit UI
- LangChain Agent
- Intent Router
```

### Decision Matrix

| Factor | Build from Scratch | Use mcp-odoo |
|--------|-------------------|--------------|
| **Time to MVP** | 3-4 weeks | 1.5-2 weeks |
| **Code Maturity** | Untested | Battle-tested (235⭐) |
| **MCP Compliance** | Risk of bugs | Proven working |
| **Maintenance** | All on us | Share with community |
| **Learning Curve** | High (MCP spec) | Low (extend existing) |
| **Flexibility** | 100% | 95% (MIT license) |
| **Risk** | High | Low |

### Conclusion: Fork & Extend mcp-odoo ✅

**Reasoning**:
1. ✅ Saves 1+ week of development
2. ✅ Battle-tested codebase (235 stars)
3. ✅ MIT License (can modify freely)
4. ✅ Clean, readable code (~500 lines)
5. ✅ Active maintenance
6. ✅ MCP compliance guaranteed
7. ✅ We can focus on business logic, not plumbing

**Strategy**:
- Fork mcp-odoo as **foundation**
- Add our **extensions** on top
- Add **intelligence layer** (Chainlit + LangChain)
- Add **safety layer** (confirmations + audit)
- Keep base mcp-odoo as **git submodule** (easy to pull updates)

## 🏛️ Architecture Decisions (Build on mcp-odoo Foundation)

### 🏗️ **FOUNDATION: mcp-odoo (Don't Reinvent)**

| What mcp-odoo Gives Us | Status | Time Saved |
|------------------------|--------|------------|
| **MCP Protocol** | ✅ Working | ~5 days |
| **XML-RPC Connection** | ✅ Working | ~2 days |
| **Resource System** | ✅ Working | ~3 days |
| **execute_method() tool** | ✅ Working | ~2 days |
| **Configuration** | ✅ Working | ~1 day |
| **Docker Setup** | ✅ Working | ~1 day |
| **Error Handling** | ✅ Working | ~2 days |
| **TOTAL** | | **~2.5 weeks saved** |

### ✅ What We're ADDING (Ready-Made Solutions)

| Component | Solution | Why |
|-----------|----------|-----|
| **Base MCP Server** | **mcp-odoo (fork)** | ✅ Already works, 235⭐, proven, saves 2+ weeks |
| **Web Chat UI** | **Chainlit** | Purpose-built for AI chat, beautiful UI, LangChain native |
| **LLM Orchestration** | **LangChain** | Industry standard, massive ecosystem, tool calling built-in |
| **A2A Protocol** | **Python A2A** | Official implementation (optional) |
| **REST API** | **FastAPI** | Fast, modern, auto-documentation |
| **Caching** | **Redis** | Industry standard for session & cache |
| **LLM Provider** | **Claude (Anthropic)** | Best for intent understanding & safety |

### ❌ What We're NOT Building from Scratch

- ❌ MCP Protocol Implementation (using mcp-odoo)
- ❌ XML-RPC Odoo Client (using mcp-odoo's connection)
- ❌ Resource System (using mcp-odoo's resources)
- ❌ Custom chat UI (using Chainlit)
- ❌ Custom LLM orchestration (using LangChain)
- ❌ Custom websocket server (Chainlit has it)
- ❌ Custom authentication (FastAPI + API keys)

### 🎯 What We ARE Building (Custom Logic)

1. **Write Operations Extensions** (on top of mcp-odoo)
   - create_record() tool
   - update_record() tool
   - delete_record() tool
   - call_action() tool

2. **Dynamic Model Discovery Engine**
   - Odoo-specific: fetch ALL models & fields
   - Generate tools dynamically
   - Cache & refresh mechanism

3. **Intent Router**
   - Natural language → Odoo operation
   - Query vs Action classification
   - Safety validation

4. **Action Executor with Safety**
   - Safe write operations to Odoo
   - Confirmation flows
   - Permission checking
   - Audit logging

5. **Procurement Workflows**
   - Domain-specific prompts
   - Specialized tools for Procurement
   - Business logic

### 🔄 Data Flow (Extending mcp-odoo)

```
User Input (Chainlit)
    ↓
LangChain Agent (with all tools)
    ↓
Intent Router (our custom logic)
    ↓ 
[Query Path]                    [Action Path]
    ↓                               ↓
mcp-odoo Resources             Our Extended Tools
(odoo://search/...)           (create_record, call_action)
    ↓                               ↓
mcp-odoo XML-RPC Connection    Our Safety Validator
    ↓                               ↓
Odoo ERP ←─────────────────────→ Confirm with User
    ↓                               ↓
Format Response                 Audit Log
    ↓                               ↓
Return to User (Chainlit)
```

### 🔐 Security Layers

1. **Authentication**: API key for each user/service
2. **Authorization**: Check Odoo user permissions before actions
3. **Validation**: Validate all inputs before Odoo calls
4. **Confirmation**: Require confirmation for write operations
5. **Audit**: Log every action with user + timestamp
6. **Rate Limiting**: Prevent abuse (100 req/min per user)



## 🚀 Quick Start Guide

### Prerequisites
```bash
# System requirements
- Python 3.11+
- Git
- Redis (for caching)
- Access to an Odoo instance (v14+)
```

### Step 1: Fork & Clone mcp-odoo
```bash
# 1. Fork https://github.com/tuanle96/mcp-odoo on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/odoo-ai-agent.git
cd odoo-ai-agent

# 3. Add mcp-odoo as submodule
git submodule add https://github.com/YOUR_USERNAME/mcp-odoo.git
git submodule update --init --recursive
```

### Step 2: Install Base mcp-odoo
```bash
# Install mcp-odoo as editable
cd mcp-odoo
pip install -e .
cd ..

# Test base MCP server works
cd mcp-odoo
python run_server.py
# Press Ctrl+C after verifying it starts without errors
cd ..
```

### Step 3: Install Our Extensions
```bash
# Install additional dependencies
pip install chainlit langchain langchain-anthropic fastapi uvicorn redis loguru

# Or use requirements.txt
pip install -r requirements.txt
```

### Step 4: Configure
```bash
# Copy example config
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Add your Odoo and API credentials:
```bash
ODOO_URL=https://your-odoo.com
ODOO_DB=your_database
ODOO_USERNAME=admin
ODOO_PASSWORD=your_password

ANTHROPIC_API_KEY=sk-ant-...
```

### Step 5: Run the Application
```bash
# Start Redis (in separate terminal)
redis-server

# Run Chainlit UI
chainlit run src/ui/chainlit_app.py --port 8080

# Open browser: http://localhost:8080
```

### Step 6: First Test
In the Chainlit UI, try:
```
"Show me all models available in Odoo"
"List purchase orders from last month"
"What fields does purchase.order have?"
```

### Docker Quick Start (Alternative)
```bash
# Build and run with Docker Compose
docker-compose up -d

# Access at http://localhost:8080
```

## 📝 Configuration

### Environment Variables

```bash
# ===================================
# Odoo Configuration
# ===================================
ODOO_URL=https://your-odoo-instance.com
ODOO_DB=your_database_name
ODOO_USERNAME=admin  # or service account
ODOO_PASSWORD=your_password_or_api_key

# ===================================
# LLM Provider
# ===================================
ANTHROPIC_API_KEY=sk-ant-...  # RECOMMENDED
# OPENAI_API_KEY=sk-...       # Alternative

# ===================================
# Service Configuration
# ===================================
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8000
CHAINLIT_PORT=8080

# Caching & Performance
REDIS_URL=redis://localhost:6379/0
MODEL_CACHE_TTL=300  # seconds (5 minutes)

# ===================================
# Security
# ===================================
API_KEY_ENABLED=true
ADMIN_API_KEY=your-secure-random-key-here

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=1000

# ===================================
# Features
# ===================================
ENABLE_MCP=true
ENABLE_A2A=true
ENABLE_FILE_UPLOADS=true
MAX_FILE_SIZE_MB=10

# ===================================
# Logging
# ===================================
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
LOG_FILE=logs/odoo_agent.log
AUDIT_LOG=logs/actions_audit.log
```

### Chainlit Configuration

```toml
# .chainlit/config.toml

[project]
name = "Odoo Procurement Assistant"
enable_telemetry = false

[UI]
name = "Odoo AI Agent"
github = "https://github.com/your-repo/odoo-ai-agent"
show_readme_as_default = true
default_collapse_content = true

[features]
spontaneous_file_upload = true
edit_message = false
latex = false
unsafe_allow_html = true
```

## 🧪 Testing Strategy

### Unit Tests
- Odoo connection and authentication
- Model discovery logic
- Domain filter generation
- Tool creation

### Integration Tests
- Full query flow end-to-end
- MCP protocol compliance
- A2A protocol compliance
- LangChain integration

### Manual Tests
- Claude Desktop integration
- Web UI functionality
- Performance with large datasets
- Error handling scenarios

## 🔒 Security Considerations

1. **API Key Authentication**: All endpoints require valid API key
2. **Odoo Permissions**: Respect Odoo's record rules and access rights
3. **Rate Limiting**: Prevent abuse of API
4. **Input Validation**: Sanitize all user inputs
5. **SQL Injection**: Never construct raw SQL, use Odoo ORM
6. **Secrets Management**: Use environment variables, never hardcode

## 📊 Performance Requirements

- **Model Discovery**: Cache models, refresh every 5 minutes
- **Query Response Time**: < 2 seconds for simple queries
- **Concurrent Users**: Support 50+ simultaneous users
- **Memory Usage**: < 512MB under normal load
- **Startup Time**: < 10 seconds

## 🎨 Example User Interactions (Procurement Focus)

### Example 1: Query - View Pending Purchase Orders
```
User: "Show me all pending purchase orders"

Agent thinks:
  - Intent: QUERY (read)
  - Model: purchase.order
  - Filter: state in ['draft', 'sent', 'to approve']
  - Fields: name, partner_id, amount_total, state, date_order

Agent responds: "You have 15 pending purchase orders:
1. PO-1234 - ABC Supplier - $12,450.00 - Draft
2. PO-1235 - XYZ Corp - $8,900.00 - Waiting Approval
3. PO-1236 - DEF Ltd - $15,200.00 - Sent
..."

[Shows interactive table with buttons: "Approve", "View Details"]
```

### Example 2: Action - Approve Purchase Order
```
User: "Approve PO-1235"

Agent thinks:
  - Intent: ACTION (write)
  - Model: purchase.order
  - Record ID: find by name="PO-1235"
  - Method: button_approve()
  - Safety: Check user has approval rights

Agent confirms: "⚠️ Approval Request:
PO-1235 - XYZ Corp - $8,900.00
Do you want to approve this purchase order? (yes/no)"

User: "yes"

Agent executes & responds: "✅ PO-1235 has been approved. 
Email sent to XYZ Corp automatically."
```

### Example 3: Action - Create RFQ with File Attachment
```
User: "Create RFQ for 100 units of Product X, send to suppliers A, B, and C. 
      Attach the spec sheet I uploaded."

Agent thinks:
  - Intent: ACTION (create multiple records)
  - Product: search product.product for "Product X"
  - Suppliers: search res.partner for companies A, B, C
  - Quantity: 100
  - Attachment: use uploaded file
  
Agent confirms: "📝 Creating RFQ:
Product: Product X (ID: 42)
Quantity: 100 units
Suppliers: 3 found (Supplier A, Supplier B, Supplier C)
Attachment: spec_sheet.pdf (2.3 MB)
Proceed? (yes/no)"

User: "yes"

Agent executes:
  1. Creates purchase.order records (3x)
  2. Attaches spec_sheet.pdf to each
  3. Calls action_rfq_send() to email suppliers

Agent responds: "✅ Created 3 RFQs:
- RFQ-001 → Supplier A
- RFQ-002 → Supplier B  
- RFQ-003 → Supplier C
All sent via email with spec sheet attached."
```

### Example 4: Action - Update PO & Add Comment
```
User: "Change PO-1234 delivery date to Feb 15, and add comment: 
      Supplier confirmed new timeline"

Agent thinks:
  - Intent: ACTION (update + message)
  - Model: purchase.order
  - Update fields: date_planned = '2026-02-15'
  - Action: post message to chatter

Agent executes & responds: "✅ Updated PO-1234:
- Delivery date: Feb 15, 2026
- Comment added to discussion thread
Would you like to notify the supplier? (yes/no)"
```

### Example 5: Complex Query - Analytics
```
User: "What's our total procurement spend this month by category?"

Agent thinks:
  - Intent: QUERY (aggregation)
  - Model: purchase.order
  - Filter: date_order in current month, state = 'purchase'
  - Group by: order_line.product_id.categ_id
  - Aggregate: sum(amount_total)

Agent responds: "📊 Procurement Spend - January 2026:

Category          | Amount     | Orders
------------------|------------|--------
Raw Materials     | $125,400   | 23
Electronics       | $89,200    | 15
Office Supplies   | $12,300    | 8
Services          | $45,600    | 11

Total: $272,500 across 57 purchase orders"

[Shows interactive chart]
```

### Example 6: Proactive Monitoring
```
System (automated check): "⚠️ Low Stock Alert:

5 products below minimum stock level:
1. Product A - Current: 15, Min: 50
2. Product B - Current: 8, Min: 25
3. ...

Would you like me to create purchase orders? (yes/no)"

User: "yes, for all products below 10 units"

Agent: "✅ Creating purchase orders for 2 products...
- PO-1240 created for Product B (Qty: 50, Supplier: Default)
Done. Orders sent for approval."
```

### Example 7: File Operations
```
User: "Attach the invoice I'm sending to PO-1234"
[User uploads invoice.pdf]

Agent thinks:
  - Intent: ACTION (attach file)
  - Model: ir.attachment
  - Create attachment linked to purchase.order

Agent: "✅ invoice.pdf (1.2 MB) attached to PO-1234
Added to document section."
```

### Example 8: Supplier Communication
```
User: "Send message to supplier of PO-1234: When can we expect delivery?"

Agent thinks:
  - Intent: ACTION (send message)
  - Find supplier from purchase.order
  - Use mail.compose.message wizard

Agent: "✉️ Message prepared for ABC Supplier:
Subject: Delivery Update - PO-1234
Body: When can we expect delivery?

Send now? (yes/no)"

User: "yes"

Agent: "✅ Email sent to ABC Supplier (contact@abc.com)
Logged in PO-1234 chatter."
```

## 🎁 Bonus Features (Optional)

1. **Voice Interface**: Add speech-to-text and text-to-speech
2. **Slack Bot**: Deploy as Slack app
3. **Email Notifications**: Send daily summaries
4. **Analytics Dashboard**: Visualize common queries
5. **Multi-language Support**: Answer in user's language
6. **Export Results**: Download as CSV/Excel
7. **Scheduled Reports**: Automated periodic queries

## 🚦 Success Criteria

The service is successful when:

✅ Can answer ANY question about data in Odoo
✅ Works with Claude Desktop, LangChain, and web UI
✅ Response time < 2 seconds for 90% of queries
✅ Discovers new models automatically when Odoo changes
✅ Handles 50+ concurrent users
✅ Zero hallucinations (always uses real Odoo data)
✅ Complete documentation and deployment guide

## 📚 Additional Context

### Odoo Model Examples

Common models you'll find in Odoo:
- `res.partner` - Customers, suppliers, contacts
- `sale.order` - Sales orders
- `product.product` - Products
- `stock.quant` - Inventory quantities
- `account.move` - Invoices, bills
- `hr.employee` - Employees
- `crm.lead` - CRM leads/opportunities
- `project.task` - Project tasks
- `mrp.production` - Manufacturing orders

### Odoo Domain Filter Syntax

```python
# Examples of Odoo domains:
[['customer_rank', '>', 0]]  # All customers
[['country_id.code', '=', 'ES']]  # From Spain
['|', ['email', '!=', False], ['phone', '!=', False]]  # Has email OR phone
[['create_date', '>=', '2026-01-01']]  # Created this year
```

### MCP Tool Definition Example

```python
@mcp_server.tool()
async def search_sale_order(
    partner_id: Optional[int] = None,
    state: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50
) -> List[Dict]:
    """
    Search for sales orders in Odoo
    
    Args:
        partner_id: Filter by customer ID
        state: Order state (draft/sent/sale/done/cancel)
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        limit: Maximum results
    
    Returns:
        List of sales orders with details
    """
    # Implementation...
```

## 🎯 Final Notes

**This service should be:**
- **Universal**: Works with ANY Odoo instance, any modules
- **Intelligent**: Understands natural language, routes to correct models
- **Fast**: Responses in seconds, not minutes
- **Reliable**: Handles errors gracefully, never crashes
- **Extensible**: Easy to add new features, new protocols
- **Production-ready**: Proper logging, monitoring, security

**The key innovation**: Traditional integrations require hardcoding each model. This service **discovers models dynamically**, so it works with vanilla Odoo OR Odoo with 100+ custom modules installed.

---

## 🎬 Quick Start Commands

### Development Setup

```bash
# 1. Clone and setup
git clone <repo-url>
cd odoo-ai-agent

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your Odoo & LLM credentials

# 5. Start Redis (if using caching)
docker run -d -p 6379:6379 redis:alpine

# 6. Run the Chainlit UI
chainlit run src/ui/chainlit_app.py --port 8080

# 7. (Optional) Run REST API separately
uvicorn src.api.rest:app --host 0.0.0.0 --port 8000 --reload
```

### Production Deployment

```bash
# Docker Compose (recommended)
docker-compose up -d

# Check logs
docker-compose logs -f

# Health check
curl http://localhost:8000/health
```

### Quick Test

```bash
# Test Odoo connection
python -m src.odoo.connection

# Test model discovery
python -m src.odoo.discovery

# Test via curl
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me pending purchase orders"}'
```

### Example Usage via Python

```python
import requests

# Query example
response = requests.post(
    "http://localhost:8000/api/query",
    headers={"Authorization": "Bearer your-api-key"},
    json={"message": "What's our procurement spend this month?"}
)
print(response.json())

# Action example  
response = requests.post(
    "http://localhost:8000/api/action",
    headers={"Authorization": "Bearer your-api-key"},
    json={
        "message": "Approve purchase order PO-1234",
        "confirm": True
    }
)
print(response.json())
```

---

## 🎯 Success Criteria

The microservice is **successful** when:

✅ **Can query ANY Odoo data** via natural language  
✅ **Can perform write actions** safely with confirmations  
✅ **Procurement Manager can work through chat UI** for daily tasks  
✅ **Response time < 3 seconds** for 90% of queries  
✅ **Supports 20+ concurrent users** without degradation  
✅ **Zero hallucinations** - all data is real from Odoo  
✅ **Complete audit trail** of all actions performed  
✅ **Works with Claude, LangChain, and custom agents** via protocols  
✅ **Documentation complete** for users and developers  
✅ **Can be deployed in 30 minutes** with Docker  

---

## 📚 Additional Notes

### Why This Approach Works

1. **Chainlit** - Battle-tested for AI chat UIs, saves weeks of frontend work
2. **LangChain** - Handles LLM orchestration, tool calling, memory - don't rebuild this
3. **OdooRPC** - Simple, stable Odoo connector - no need for complex client
4. **Dynamic Discovery** - Works with ANY Odoo instance, any modules installed
5. **Procurement First** - Start with real use case, expand later
6. **Safety by Design** - Confirmations + audit log = can't break production
7. **Multi-Protocol** - One service, multiple access methods = maximum flexibility

### Scaling Considerations

- **Horizontal scaling**: Run multiple instances behind load balancer
- **Redis for state**: Share sessions across instances
- **Odoo connection pool**: Reuse connections, don't create per-request
- **Caching**: Cache model metadata, common queries
- **Async operations**: Use async/await for I/O operations

### Common Pitfalls to Avoid

- ❌ Don't hardcode Odoo models - discover dynamically
- ❌ Don't skip confirmation for write operations - always ask first
- ❌ Don't ignore Odoo permissions - respect access rules
- ❌ Don't cache user-specific data - security issue
- ❌ Don't forget audit logs - compliance requirement
- ❌ Don't over-engineer - use ready-made solutions

---

## 🏁 Final Checklist Before Starting

- [ ] Odoo instance accessible with admin credentials
- [ ] Claude or GPT API key obtained
- [ ] Redis installed (or Docker available)
- [ ] Python 3.11+ installed
- [ ] Test Procurement user account in Odoo
- [ ] Sample purchase orders in Odoo for testing
- [ ] Git repository created
- [ ] Team alignment on Procurement workflows
- [ ] Security requirements documented
- [ ] Deployment environment identified (local/cloud)

**Ready to build!** This specification provides everything needed to create a production-ready Odoo AI Agent microservice using battle-tested tools and frameworks. 🚀
