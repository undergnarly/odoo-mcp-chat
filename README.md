# Odoo AI Agent Microservice

Intelligent AI agent for automating Odoo ERP workflows, with primary focus on Procurement Department operations.

## 🎯 Features

- 🔍 **Natural Language Queries**: Ask questions about your Odoo data in plain language
- ✏️ **Safe Write Operations**: Create, update, and delete records with confirmations
- 🤖 **Intelligent Routing**: LLM-powered intent understanding and action routing
- 🎨 **Web Chat Interface**: Beautiful Chainlit-based UI for daily operations
- 🔒 **Safety & Audit**: Permission checks, confirmation prompts, full audit trail
- 📦 **Procurement Workflows**: Specialized tools for PO approval, RFQ creation, etc.
- 🔄 **Dynamic Discovery**: Automatically discovers all Odoo models and fields

## 🏗️ Architecture

Built on top of [mcp-odoo](https://github.com/tuanle96/mcp-odoo) - a battle-tested MCP server for Odoo.

```
┌─────────────────────┐
│   Chainlit Web UI   │
├─────────────────────┤
│  LangChain Agent    │
├─────────────────────┤
│ Extended MCP Server │  ← Our extensions
├─────────────────────┤
│   mcp-odoo Base     │  ← Forked library
├─────────────────────┤
│   Odoo ERP (XML-RPC)│
└─────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

```bash
# System requirements
- Python 3.11+
- Redis (optional, for caching)
- Odoo instance (v14+)
- Anthropic or OpenAI API key
```

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/undergnarly/odoo-ai-agent.git
cd odoo-ai-agent

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install mcp-odoo base (from local fork)
pip install -e ./mcp-odoo

# 4. Install our dependencies
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 6. Run the web UI
chainlit run src/ui/chainlit_app.py --port 8080
```

### Configuration

Edit `.env` file:

```bash
# Odoo connection
ODOO_URL=https://your-odoo.com
ODOO_DB=your_database
ODOO_USERNAME=admin
ODOO_PASSWORD=your_password

# LLM Provider
ANTHROPIC_API_KEY=sk-ant-...
```

## 📖 Usage Examples

### Query Examples

```
User: "Show me all pending purchase orders"
Agent: [Displays list of POs with state='draft' or 'sent']

User: "What's our total spend this month?"
Agent: [Calculates and displays total spend]
```

### Action Examples

```
User: "Approve PO-1234"
Agent: "⚠️ Confirmation: Approve PO-1234 for $5,000? (yes/no)"
User: "yes"
Agent: "✅ PO-1234 approved successfully"

User: "Create RFQ for Product X, send to suppliers A and B"
Agent: "📝 Creating RFQ for Product X to 2 suppliers. Proceed? (yes/no)"
```

## 🛠️ Development

```bash
# Run tests
pytest tests/

# Start Redis (for caching)
docker run -d -p 6379:6379 redis:alpine

# Run REST API
uvicorn src.api.rest:app --reload

# Run Chainlit UI
chainlit run src/ui/chainlit_app.py --port 8080
```

## 📁 Project Structure

```
odoo-ai-agent/
├── mcp-odoo/              # Forked base library (don't modify)
├── src/
│   ├── extensions/        # Our MCP extensions
│   ├── agent/             # LangChain integration
│   ├── api/               # REST API endpoints
│   ├── ui/                # Chainlit web interface
│   └── utils/             # Utilities (logging, cache, etc.)
├── procurement/           # Procurement workflows
├── tests/                 # Unit and integration tests
└── docs/                  # Documentation
```

## 🔒 Security

- ✅ API key authentication
- ✅ Odoo permission checks
- ✅ Confirmation prompts for write operations
- ✅ Full audit logging
- ✅ Rate limiting
- ✅ Input validation

## 📝 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please read our contributing guidelines.

## 📚 Additional Resources

- [mcp-odoo Documentation](https://github.com/tuanle96/mcp-odoo)
- [Chainlit Documentation](https://docs.chainlit.io)
- [LangChain Documentation](https://python.langchain.com)
- [Odoo Documentation](https://www.odoo.com/documentation)
