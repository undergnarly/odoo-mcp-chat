# Odoo AI Agent - Architecture Documentation

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interfaces                          │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Chainlit    │  │  REST API    │  │  MCP Client  │     │
│  │  Web Chat    │  │  (FastAPI)   │  │  (Claude)    │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │              │
└─────────┼─────────────────┼─────────────────┼──────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                  Intelligence Layer                         │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │         LangChain Agent (OdooAgent)                │    │
│  │                                                     │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  │    │
│  │  │ Intent     │  │ LLM        │  │ Memory     │  │    │
│  │  │ Router     │  │ (Claude)   │  │ Management │  │    │
│  │  └────────────┘  └────────────┘  └────────────┘  │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                  Extended MCP Server                        │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │        Extended MCP Server (extended_mcp)          │    │
│  │                                                     │    │
│  │  ┌──────────────┐  ┌──────────────────────────┐   │    │
│  │  │ Base mcp-odoo│  │ Our Extensions           │   │    │
│  │  │              │  │                          │   │    │
│  │  │ - Resources  │  │ - write_tools.py         │   │    │
│  │  │ - execute_   │  │ - action_tools.py        │   │    │
│  │  │   method()   │  │ - discovery.py           │   │    │
│  │  │              │  │ - safety.py              │   │    │
│  │  │              │  │                          │   │    │
│  │  │              │  │ - Procurement workflows  │   │    │
│  │  └──────────────┘  └──────────────────────────┘   │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                  Odoo ERP (XML-RPC)                        │
│                                                              │
│  • purchase.order    • res.partner      • product.product  │
│  • sale.order        • account.move      • stock.picking    │
│  • 125+ other models                                         │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. User Interface Layer

#### Chainlit Web Chat (`src/ui/chainlit_app.py`)
- Beautiful web-based chat interface
- Real-time streaming responses
- File upload support
- Interactive action buttons
- Multi-user session support

#### REST API (`src/api/rest.py`)
- FastAPI-based REST endpoints
- JSON request/response
- API key authentication
- Rate limiting
- OpenAPI documentation at `/docs`

#### MCP Protocol (via mcp-odoo)
- Standard Model Context Protocol
- Works with Claude Desktop, Cursor, etc.
- stdio transport for local usage

### 2. Intelligence Layer

#### Intent Router (`src/agent/`)
- Classifies user requests into intents
- Maps natural language to Odoo operations
- Uses Claude LLM for understanding

#### LangChain Agent (`src/agent/langchain_agent.py`)
- Orchestrates conversation flow
- Maintains conversation history
- Handles multi-turn interactions
- Integrates with safety layer

#### Prompts (`src/agent/prompts.py`)
- System prompts for different use cases
- Intent classification prompts
- Query generation prompts
- Domain-specific prompts (procurement)

### 3. Extended MCP Server

#### Base mcp-odoo (`mcp-odoo/`)
- Original forked library
- Provides XML-RPC connection
- Resources for read operations
- `execute_method()` tool

#### Write Tools (`src/extensions/write_tools.py`)
- `create_record()` - Create new records
- `update_record()` - Update existing records
- `delete_record()` - Delete records
- Full audit logging

#### Action Tools (`src/extensions/action_tools.py`)
- `call_action()` - Execute workflow methods
- `post_message()` - Post to chatter
- `attach_file()` - Attach files to records

#### Discovery (`src/extensions/discovery.py`)
- Dynamic model discovery
- Field metadata extraction
- Method discovery
- Caching with TTL

#### Safety (`src/extensions/safety.py`)
- Permission checking
- Confirmation flows
- Danger level assessment
- Audit logging

### 4. Domain Layer

#### Procurement Workflows (`procurement/workflows.py`)
- Purchase order management
- RFQ creation and sending
- Supplier performance
- Low stock alerts

#### Procurement Prompts (`procurement/prompts.py`)
- Domain-specific system prompt
- Intent patterns
- Terminology guide
- Best practices

### 5. Infrastructure

#### Configuration (`src/config.py`)
- Environment variable management
- Pydantic settings
- Type-safe configuration

#### Logging (`src/utils/logging.py`)
- Loguru-based structured logging
- Console output (colored)
- File output (with rotation)
- Separate audit log

#### Caching (Future - Redis)
- Model metadata caching
- Session storage
- Response caching

## Data Flow

### Query Flow

```
User: "Show me pending POs"
    ↓
Chainlit receives message
    ↓
LangChain Agent.process_message()
    ↓
Intent Router.classify()
    → Intent: QUERY
    → Model: purchase.order
    ↓
Agent._handle_query()
    ↓
OdooClient.search_read()
    ↓
Format results
    ↓
Display in Chainlit UI
```

### Action Flow (with Confirmation)

```
User: "Approve PO-1234"
    ↓
Chainlit receives message
    ↓
LangChain Agent.process_message()
    ↓
Intent Router.classify()
    → Intent: ACTION
    → Method: button_approve
    ↓
SafetyValidator.check_operation()
    → Danger Level: MEDIUM
    → Requires confirmation
    ↓
Return confirmation request
    ↓
User clicks "Confirm"
    ↓
Execute call_action()
    ↓
OdooClient.execute_method("purchase.order", "button_approve", [1234])
    ↓
Audit log success
    ↓
Display result in UI
```

## Security Model

1. **Authentication**
   - API key for REST API
   - Odoo session for direct access
   - User context tracking

2. **Authorization**
   - Odoo ACLs respected
   - Permission checks before actions
   - Role-based access

3. **Safety**
   - Confirmation for write operations
   - Danger level classification
   - Audit trail for all actions

4. **Rate Limiting**
   - Per-user rate limits
   - Configurable thresholds
   - Automatic blocking

## Scalability

### Horizontal Scaling
- Stateless design
- Redis for shared session
- Multiple instances behind load balancer

### Performance Optimization
- Model metadata caching
- Connection pooling
- Async operations
- Lazy loading

### Monitoring
- Health check endpoints
- Audit logging
- Error tracking
- Performance metrics

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Base MCP** | mcp-odoo (forked) | Odoo integration |
| **LLM** | Claude (Anthropic) | Intent understanding |
| **Agent Framework** | LangChain | Agent orchestration |
| **Web UI** | Chainlit | Chat interface |
| **REST API** | FastAPI | HTTP endpoints |
| **Configuration** | Pydantic Settings | Settings management |
| **Logging** | Loguru | Structured logging |
| **Caching** | Redis (future) | Performance |

## Future Enhancements

1. **Multi-language Support**
   - Detect user language
   - Localize responses
   - Multi-language prompts

2. **Voice Interface**
   - Speech-to-text input
   - Text-to-speech responses

3. **Advanced Analytics**
   - Usage analytics
   - Performance metrics
   - Custom dashboards

4. **Integration Hub**
   - Slack bot
   - Email notifications
   - Webhook support

5. **Mobile Apps**
   - iOS app
   - Android app
   - Responsive PWA
