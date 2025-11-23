import os
from langchain.tools import tool
import requests

# --- API Tools generated from OpenAPI spec (excluding forbidden endpoints) ---

API_BASE = os.getenv("API_BASE", "http://localhost:8080")
BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjo0LCJ1c2VybmFtZSI6ImFnZW50Iiwicm9sZSI6InVzZXIiLCJpYXQiOjE3NjM5MzA5MjQsImV4cCI6MTc2MzkzNDUyNCwianRpIjoiNDY2ZTU0NGEtNDZiMS00MTY5LTkyZmQtNmRiY2I5YmEyN2RjIn0.gRdJmxbu5-sM1ui2HYR1cBvEUnaE6fhUyGNVY-Ny1I4"
HEADERS = {"Authorization": f"Bearer {BEARER_TOKEN}"}


@tool
def get_all_catalogue_items() -> dict:
    """Fetch all items in the catalogue.

    Returns:
        All catalogue items as a dictionary.
    """
    resp = requests.get(f"{API_BASE}/api/catalogue/items", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


@tool
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
        The created item as a dictionary.
    """
    data = {
        "title": title,
        "description": description,
        "startingPrice": startingPrice,
        "durationHours": durationHours,
    }
    resp = requests.post(f"{API_BASE}/api/catalogue/items", json=data, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


@tool
def search_catalogue_items(keyword: str) -> dict:
    """Search catalogue items by keyword in title.

    Args:
        keyword: Search keyword to filter items by title
    Returns:
        Matching catalogue items as a dictionary.
    """
    params = {"keyword": keyword}
    resp = requests.get(
        f"{API_BASE}/api/catalogue/search", params=params, headers=HEADERS
    )
    resp.raise_for_status()
    return resp.json()


@tool
def get_catalogue_item_by_id(item_id: int) -> dict:
    """Fetch a single catalogue item by ID.

    Args:
        item_id: The ID of the catalogue item
    Returns:
        The catalogue item as a dictionary.
    """
    resp = requests.get(f"{API_BASE}/api/catalogue/items/{item_id}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


@tool
def start_auction(catalogue_id: int) -> dict:
    """Start an auction for a catalogue item.

    Args:
        catalogue_id: The ID of the catalogue item to start the auction for
    Returns:
        Auction start response as a dictionary.
    """
    resp = requests.post(
        f"{API_BASE}/api/auctions/{catalogue_id}/start", headers=HEADERS
    )
    resp.raise_for_status()
    return resp.json()


@tool
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
        f"{API_BASE}/api/auctions/{catalogue_id}/bid", json=data, headers=HEADERS
    )
    resp.raise_for_status()
    return resp.json()


@tool
def get_auction_winner(catalogue_id: int) -> dict:
    """Get the winner of a completed auction.

    Args:
        catalogue_id: The ID of the catalogue item
    Returns:
        Winner information as a dictionary.
    """
    resp = requests.get(
        f"{API_BASE}/api/auctions/{catalogue_id}/winner", headers=HEADERS
    )
    resp.raise_for_status()
    return resp.json()


@tool
def get_auction_status(catalogue_id: int) -> dict:
    """Get the status of an auction for a catalogue item.

    Args:
        catalogue_id: The ID of the catalogue item
    Returns:
        Auction status as a dictionary.
    """
    resp = requests.get(
        f"{API_BASE}/api/auctions/{catalogue_id}/status", headers=HEADERS
    )
    resp.raise_for_status()
    return resp.json()


@tool
def get_auction_end_time(catalogue_id: int) -> dict:
    """Get the end time of an auction for a catalogue item.

    Args:
        catalogue_id: The ID of the catalogue item
    Returns:
        Auction end time as a dictionary.
    """
    resp = requests.get(f"{API_BASE}/api/auctions/{catalogue_id}/end", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


@tool
def get_payment_receipt(payment_id: str) -> dict:
    """Retrieve payment details and receipt information by payment ID.

    Args:
        payment_id: The ID of the payment
    Returns:
        Payment receipt as a dictionary.
    """
    resp = requests.get(f"{API_BASE}/api/payments/{payment_id}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


@tool
def get_my_payment_history() -> dict:
    """Returns payment history for the authenticated user.

    Returns:
        Payment history as a dictionary.
    """
    resp = requests.get(f"{API_BASE}/api/payments/history", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


# Augment the LLM with tools
tools = [
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
