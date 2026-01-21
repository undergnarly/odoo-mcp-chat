# Quick Start Guide - Odoo AI Agent

This guide will get you up and running with the Odoo AI Agent microservice in **under 30 minutes**.

## Prerequisites

Before you start, make sure you have:

- ✅ Python 3.11 or higher
- ✅ Access to an Odoo instance (v14+)
- ✅ Anthropic API key (or OpenAI API key)
- ✅ Git installed

## Step 1: Clone and Setup (5 minutes)

```bash
# Clone your fork
git clone https://github.com/undergnarly/mcp-odoo.git
cd mcp-odoo

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install mcp-odoo base (from your fork)
pip install -e .

# Test that mcp-odoo works
python -c "from odoo_mcp.odoo_client import get_odoo_client; print('✅ mcp-odoo installed successfully')"
```

## Step 2: Configure Environment (2 minutes)

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your favorite editor
```

Add your credentials to `.env`:

```bash
# Odoo Configuration
ODOO_URL=https://your-odoo-instance.com
ODOO_DB=your_database_name
ODOO_USERNAME=admin
ODOO_PASSWORD=your_password

# LLM Provider (Anthropic recommended)
ANTHROPIC_API_KEY=sk-ant-...
```

## Step 3: Install Dependencies (5 minutes)

```bash
# Install all dependencies
pip install -r requirements.txt

# Verify installation
python -c "import chainlit; print('✅ Chainlit installed')"
python -c "import langchain; print('✅ LangChain installed')"
python -c "import anthropic; print('✅ Anthropic installed')"
```

## Step 4: Test Odoo Connection (2 minutes)

```bash
# Test the connection
python << 'EOF'
import os
from dotenv import load_dotenv
load_dotenv()

from odoo_mcp.odoo_client import get_odoo_client

try:
    client = get_odoo_client()
    models = client.get_models()
    print(f"✅ Successfully connected to Odoo!")
    print(f"✅ Found {len(models['model_names'])} models")
except Exception as e:
    print(f"❌ Connection failed: {e}")
EOF
```

## Step 5: Start the Web UI (1 minute)

```bash
# Start Chainlit web interface
chainlit run src/ui/chainlit_app.py --port 8080
```

Open your browser to: **http://localhost:8080**

You should see the welcome message!

## Step 6: Try Your First Query (2 minutes)

In the Chainlit UI, try these example queries:

### Query Examples

```
1. "Show me all purchase orders"

2. "List all suppliers"

3. "What products do we have?"

4. "Show me pending purchase orders"
```

## Step 7: (Optional) Start the REST API

If you want to use the REST API:

```bash
# In a new terminal
uvicorn src.api.rest:app --reload --port 8000
```

API is available at: **http://localhost:8000**

Interactive API docs: **http://localhost:8000/docs**

## Testing the API

```bash
# Health check
curl http://localhost:8000/health

# List models (requires API key)
curl -H "X-API-Key: your-key" http://localhost:8000/models
```

## Troubleshooting

### Issue: "No Odoo configuration found"

**Solution:** Make sure you created `.env` file with proper credentials

### Issue: "Authentication failed"

**Solution:** Check your ODOO_USERNAME and ODOO_PASSWORD in `.env`

### Issue: "ANTHROPIC_API_KEY not found"

**Solution:** Get your API key from https://console.anthropic.com/

### Issue: "Module not found"

**Solution:** Make sure you ran `pip install -r requirements.txt`

### Issue: Chainlit not starting

**Solution:** Try `chainlit run -h` to see help, check port 8080 is not in use

## Next Steps

1. **Read the full documentation** in the main README.md
2. **Explore procurement workflows** - Check out the `procurement/` module
3. **Customize prompts** - Edit `src/agent/prompts.py` for your domain
4. **Add your own workflows** - Extend the system for your specific needs

## Getting Help

- 📖 Check the documentation in `docs/`
- 🐛 Report issues on GitHub
- 💬 Join our community discussions

## What You Can Do Now

✅ **Query Odoo data** using natural language
✅ **View purchase orders**, suppliers, products
✅ **Use the web UI** at http://localhost:8080
✅ **Make REST API calls** to http://localhost:8000

## What's Next (Coming Soon)

- ⏳ Execute write operations (create, update, delete)
- ⏳ Approve purchase orders
- ⏳ Create and send RFQs
- ⏳ Attach files to records
- ⏳ Advanced procurement workflows

---

**Congratulations!** 🎉 You now have a working Odoo AI Agent running locally!

For more advanced features and production deployment, see the full documentation.
