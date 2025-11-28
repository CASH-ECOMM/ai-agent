import os
from langchain.tools import tool
from langchain_openai import ChatOpenAI
import requests
from contextvars import ContextVar
import functools
import requests
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit

load_dotenv()

# --- Database Setup ---
db_host = os.getenv("POSTGRES_HOST", "localhost")
db_port = os.getenv("POSTGRES_PORT", "5555")
db_user = os.getenv("POSTGRES_USER", "dev")
db_password = os.getenv("POSTGRES_PASSWORD", "dev")
db_url = os.getenv(
    "POSTGRES_URL", "postgresql://{db_user}:{db_password}@{db_host}:{db_port}"
)

catalogue_db = SQLDatabase.from_uri(f"{db_url}/catalogue_db")
auction_db = SQLDatabase.from_uri(f"{db_url}/auction_db")

model = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-5-nano-2025-08-07"))

cat_toolkit = SQLDatabaseToolkit(db=catalogue_db, llm=model)
auc_toolkit = SQLDatabaseToolkit(db=auction_db, llm=model)

catalogue_tools = cat_toolkit.get_tools()
for sql_tool in catalogue_tools:  # Renamed to avoid shadowing @tool
    sql_tool.name = f"catalogue_{sql_tool.name}"
    sql_tool.description = (
        f"Use this to query the CATALOGUE database. {sql_tool.description}"
    )

auction_tools = auc_toolkit.get_tools()
for sql_tool in auction_tools:  # Renamed to avoid shadowing @tool
    sql_tool.name = f"auction_{sql_tool.name}"
    sql_tool.description = (
        f"Use this to query the AUCTION database. {sql_tool.description}"
    )


API_BASE = os.getenv("API_BASE", "http://localhost:8080")

jwt_token_context: ContextVar[str] = ContextVar("jwt_token", default="")


def get_headers():
    """Get headers with JWT token from context."""
    token = jwt_token_context.get()
    print("Using JWT token in headers: ", token)
    return {"Authorization": f"Bearer {token}"}


def handle_api_errors(func):
    """Decorator to catch API errors and return the ACTUAL backend error message."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            try:
                error_body = e.response.json()
                server_msg = error_body.get("message", e.response.text)
            except ValueError:
                server_msg = e.response.text or "No error details provided."
            return f"API_ERROR: {status_code} - {server_msg}"
        except Exception as e:
            return f"SYSTEM_ERROR: Internal tool execution failed. {str(e)}"

    return wrapper


@tool
@handle_api_errors
def get_all_catalogue_items() -> dict:
    """Fetch all items in the catalogue.

    Returns:
        All catalogue items as a dictionary.
    """
    resp = requests.get(f"{API_BASE}/api/catalogue/items", headers=get_headers())
    resp.raise_for_status()
    return resp.json()


@tool
@handle_api_errors
def create_catalogue_item(
    title: str, description: str, startingPrice: int, durationHours: int
) -> dict:
    """Create a new item in the catalogue.

    Args:
        title: Title of the item
        description: Description of the item
        startingPrice: Starting price for the auction
        durationHours: Duration of the auction in hours
    Returns:
        The created item as a dictionary with an 'id' field.
        IMPORTANT: Use the 'id' from this response to start the auction by calling start_auction(catalogue_id=id).
    """
    data = {
        "title": title,
        "description": description,
        "startingPrice": startingPrice,
        "durationHours": durationHours,
    }
    resp = requests.post(
        f"{API_BASE}/api/catalogue/items", json=data, headers=get_headers()
    )
    resp.raise_for_status()
    return resp.json()


@tool
@handle_api_errors
def search_catalogue_items(keyword: str) -> dict:
    """Search catalogue items by keyword in title.

    Args:
        keyword: Search keyword to filter items by title
    Returns:
        Matching catalogue items as a dictionary.
    """
    params = {"keyword": keyword}
    resp = requests.get(
        f"{API_BASE}/api/catalogue/search", params=params, headers=get_headers()
    )
    resp.raise_for_status()
    return resp.json()


@tool
@handle_api_errors
def get_catalogue_item_by_id(item_id: int) -> dict:
    """Fetch a single catalogue item by ID.

    Args:
        item_id: The ID of the catalogue item
    Returns:
        The catalogue item as a dictionary.
    """
    resp = requests.get(
        f"{API_BASE}/api/catalogue/items/{item_id}", headers=get_headers()
    )
    resp.raise_for_status()
    return resp.json()


@tool
@handle_api_errors
def start_auction(catalogue_id: int) -> dict:
    """Start an auction for a catalogue item.

    Args:
        catalogue_id: The ID of the catalogue item to start the auction for
    Returns:
        Auction start response as a dictionary.
    """
    resp = requests.post(
        f"{API_BASE}/api/auctions/{catalogue_id}/start", headers=get_headers()
    )
    resp.raise_for_status()
    return resp.json()


@tool
@handle_api_errors
def place_bid(catalogue_id: int, bidAmount: int) -> dict:
    """Place a bid on an auction for a catalogue item.

    Args:
        catalogue_id: The ID of the catalogue item
        bidAmount: The amount to bid
    Returns:
        Bid response as a dictionary.
    """
    data = {"bidAmount": bidAmount}
    resp = requests.post(
        f"{API_BASE}/api/auctions/{catalogue_id}/bid", json=data, headers=get_headers()
    )
    resp.raise_for_status()
    return resp.json()


@tool
@handle_api_errors
def get_auction_winner(catalogue_id: int) -> dict:
    """Get the winner of a completed auction.

    Args:
        catalogue_id: The ID of the catalogue item
    Returns:
        Winner information as a dictionary.
    """
    resp = requests.get(
        f"{API_BASE}/api/auctions/{catalogue_id}/winner", headers=get_headers()
    )
    resp.raise_for_status()
    return resp.json()


@tool
@handle_api_errors
def get_auction_status(catalogue_id: int) -> dict:
    """Get the status of an auction for a catalogue item.

    Args:
        catalogue_id: The ID of the catalogue item
    Returns:
        Auction status as a dictionary.
    """
    resp = requests.get(
        f"{API_BASE}/api/auctions/{catalogue_id}/status", headers=get_headers()
    )
    resp.raise_for_status()
    return resp.json()


@tool
@handle_api_errors
def get_auction_end_time(catalogue_id: int) -> dict:
    """Get the end time of an auction for a catalogue item.

    Args:
        catalogue_id: The ID of the catalogue item
    Returns:
        Auction end time as a dictionary.
    """
    resp = requests.get(
        f"{API_BASE}/api/auctions/{catalogue_id}/end", headers=get_headers()
    )
    resp.raise_for_status()
    return resp.json()


@tool
@handle_api_errors
def get_payment_receipt(payment_id: str) -> dict:
    """Retrieve payment details and receipt information by payment ID.

    Args:
        payment_id: The ID of the payment
    Returns:
        Payment receipt as a dictionary.
    """
    resp = requests.get(f"{API_BASE}/api/payments/{payment_id}", headers=get_headers())
    resp.raise_for_status()
    return resp.json()


@tool
@handle_api_errors
def get_my_payment_history() -> dict:
    """Returns payment history for the authenticated user.

    Returns:
        Payment history as a dictionary.
    """
    print("headers: ", get_headers())
    resp = requests.get(f"{API_BASE}/api/payments/history", headers=get_headers())
    resp.raise_for_status()
    return resp.json()


# Augment the LLM with tools
tools = (
    catalogue_tools
    + auction_tools
    + [
        get_all_catalogue_items,
        create_catalogue_item,
        search_catalogue_items,
        get_catalogue_item_by_id,
        start_auction,
        place_bid,
        get_auction_winner,
        get_auction_status,
        get_auction_end_time,
        get_payment_receipt,
        get_my_payment_history,
    ]
)
