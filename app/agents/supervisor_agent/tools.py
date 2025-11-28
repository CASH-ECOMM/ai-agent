import logging
from langchain.tools import tool
from langchain.messages import SystemMessage, HumanMessage
from app.agents.sql_agent.sql_agent import agent as sql_agent
from app.agents.api_agent.api_agent import agent as api_agent

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@tool
def query_database(request: str) -> str:
    """Query the database using natural language.

    Use this when the user wants to:
    - Search or analyze data across databases (catalogue_db, auction_db, payment_db)
    - Get statistics, counts, aggregations, or reports
    - Filter, sort, or retrieve specific records
    - Analyze historical data or trends
    - Get information about items, auctions, bids, payments, or receipts

    This tool will:
    1. Generate appropriate SQL queries from natural language
    2. Validate queries for syntax and security
    3. Execute queries safely against the correct database
    4. Return formatted results

    Input: Natural language query (e.g., 'Show me all active items' or 'How many bids were placed today?')
    User ID: Optional user ID for filtering personal data
    """
    logger.info(f"SQL Agent invoked with request: {request}")
    return sql_agent.invoke({"messages": [HumanMessage(content=request)]})  # type: ignore


@tool
def manage_api_operations(request: str) -> str:
    """Perform API operations on the e-commerce system.

    Use this when the user wants to:
    - Create items in the catalogue
    - Place bids on auctions
    - Search for items or auctions
    - Manage auction operations
    - Perform any action that modifies system state
    - Get real-time data from the system APIs

    This tool will:
    1. Determine which API endpoint(s) to call
    2. Extract parameters from natural language
    3. Execute API calls with proper authentication
    4. Return formatted results

    Input: Natural language request (e.g., 'Create a new item called Laptop for $500' or 'Place a bid of $150 on auction 5')
    """
    logger.info(f"API Agent invoked with request: {request}")
    return api_agent.invoke({"messages": [HumanMessage(content=request)]})  # type: ignore


tools = [query_database, manage_api_operations]
