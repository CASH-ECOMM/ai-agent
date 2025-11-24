# Supervisor Agent V2 - Sequential Flow Documentation

## Overview

The `supervisor_agent_v2.py` has been modified to implement a sequential agent flow where the **API Agent** is always tried first, and the **SQL Agent** is used as a fallback when the API Agent cannot fulfill the request.

## Flow Architecture

```
┌─────────┐
│  START  │
└────┬────┘
     │
     ▼
┌─────────────┐
│  API Agent  │ (Always executed first)
└─────┬───────┘
      │
      ▼
  ┌───────────────────┐
  │ Can fulfill?      │
  │ (Check response)  │
  └─────┬─────────────┘
        │
    ┌───┴───┐
    │       │
   Yes      No
    │       │
    │   ┌───▼──────────┐
    │   │  SQL Agent   │ (Fallback)
    │   └───┬──────────┘
    │       │
    └───┬───┘
        │
        ▼
    ┌───────┐
    │  END  │
    └───────┘
```

## Key Changes

### 1. Sequential Routing
- **Before**: Router node decided which agent to call based on LLM decision
- **After**: API agent always runs first, SQL agent only runs if needed

### 2. State Management
New fields added to `ConversationContext`:
- `api_agent_attempted`: Tracks if API agent has been tried
- `needs_sql_fallback`: Flag indicating if SQL agent should be invoked

### 3. Fallback Detection
The system detects when API agent cannot fulfill a request by analyzing response content for these indicators:
- "i don't have"
- "i cannot"
- "i'm unable to"
- "not available"
- "cannot provide"
- "don't have access"
- "analytics"
- "statistics"
- "query the database"
- "historical data"
- "aggregate"
- "report"

### 4. Error Handling
If API agent encounters an error, the system automatically routes to SQL agent as a fallback.

## Usage

### Running the Agent

```python
from app.agents.supervisor_agent.supervisor_agent_v2 import meta_agent, create_initial_context
from langchain.messages import HumanMessage

# Create context for user
context = create_initial_context(user_id=1)

# Add user message
context["messages"].append(HumanMessage(content="Show me all items"))

# Invoke the agent
result = meta_agent.invoke(context)

# Check which agent handled the request
print(f"Handled by: {result['last_agent_used']}")
print(f"Response: {result['messages'][-1].content}")
```

### Interactive Mode

Run the agent in interactive mode:

```bash
cd /home/runner/work/ai-agent/ai-agent
source venv/bin/activate
python -m app.agents.supervisor_agent.supervisor_agent_v2
```

This starts an interactive chat where you can test the sequential flow:
- Requests for API operations (create item, place bid) → API Agent
- Requests for analytics, statistics, database queries → API Agent first, then SQL Agent as fallback

## Example Scenarios

### Scenario 1: API Agent Handles Request
```
User: "Get all catalogue items"
→ API Agent: Calls get_all_catalogue_items API
→ Returns results directly
→ No SQL fallback needed
```

### Scenario 2: SQL Fallback Triggered
```
User: "Show me statistics on all auctions"
→ API Agent: Attempts to handle request
→ Recognizes need for database aggregation
→ Indicates it cannot provide analytics
→ SQL Agent: Generates and executes SQL query
→ Returns aggregated results
```

### Scenario 3: Error Triggers Fallback
```
User: "Complex query about bid patterns"
→ API Agent: Encounters error with API tools
→ Automatically routes to SQL Agent
→ SQL Agent: Handles the database query
→ Returns results
```

## Testing

Run the unit tests to verify the implementation:

```bash
cd /home/runner/work/ai-agent/ai-agent
source venv/bin/activate
python tests/test_supervisor_v2_unit.py
```

The tests verify:
- ✓ Graph structure is correct (START → API → SQL? → END)
- ✓ Initial context is properly created
- ✓ Fallback routing logic works correctly
- ✓ Fallback indicators are properly detected
- ✓ Sequential flow pattern is implemented

## Benefits

1. **Efficiency**: Try API operations first (faster, more direct)
2. **Comprehensive**: Fall back to SQL for complex queries
3. **Resilient**: Automatic error recovery through fallback
4. **User-Friendly**: Seamless experience regardless of which agent handles the request
5. **Maintainable**: Clear, linear flow that's easy to understand and debug

## Configuration

The agent uses these environment variables:
- `OPENAI_API_KEY`: OpenAI API key for LLM calls
- `LLM_MODEL`: Model to use (default: "gpt-4.1-mini-2025-04-14")
- `API_BASE`: Base URL for the auction system API (default: "http://localhost:8080")
- `POSTGRES_*`: Database connection parameters for SQL agent

## Future Enhancements

Possible improvements:
1. Add more sophisticated fallback detection using LLM classification
2. Implement retry logic for API operations
3. Add caching for frequently accessed data
4. Enable hybrid responses (API + SQL data combined)
5. Add metrics/logging for monitoring agent usage patterns

## Related Files

- `app/agents/supervisor_agent/supervisor_agent_v2.py` - Main implementation
- `app/agents/api_agent/api_agent.py` - API agent with tools
- `app/agents/sql_agent/sql_agent.py` - SQL agent for database queries
- `tests/test_supervisor_v2_unit.py` - Unit tests
