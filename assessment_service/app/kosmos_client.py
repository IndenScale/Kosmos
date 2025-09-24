"""
Client for interacting with the Kosmos Core backend service.

This module encapsulates all the logic for making API calls to the main
Kosmos application, handling authentication and error responses.
"""
import os
import requests
from typing import Dict, Any, Optional, List
import uuid

# --- Configuration ---

# Get the base URL for the Kosmos API from environment variables
KOSMOS_API_URL = os.getenv("KOSMOS_API_URL", "http://127.0.0.1:8011/api/v1")

# For service-to-service communication, we might use a pre-shared secret key.
# In a real production environment, this should be a more robust mechanism like OAuth.
INTERNAL_AUTH_TOKEN = os.getenv("KOSMOS_INTERNAL_TOKEN")

# --- Client Functions ---

def _get_auth_headers(token: Optional[str] = None) -> Dict[str, str]:
    """
    Constructs the authorization headers.
    Priority: Passed-in token > Environment variable token.
    """
    if token:
        # Ensure the token includes "Bearer " prefix if it's missing
        if token.lower().startswith("bearer "):
            return {"Authorization": token}
        else:
            return {"Authorization": f"Bearer {token}"}
            
    if INTERNAL_AUTH_TOKEN:
        return {"Authorization": f"Bearer {INTERNAL_AUTH_TOKEN}"}
        
    return {}

def search_in_kosmos(
    ks_id: uuid.UUID, 
    query: str, 
    top_k: int, 
    token: Optional[str] = None,
    doc_ids_include: Optional[List[str]] = None,
    doc_ids_exclude: Optional[List[str]] = None,
    filename_contains: Optional[str] = None,
    filename_does_not_contain: Optional[str] = None,
    extensions_include: Optional[List[str]] = None,
    extensions_exclude: Optional[List[str]] = None,
    keywords_include_all: Optional[List[str]] = None,
    keywords_exclude_any: Optional[List[str]] = None,
    boosters: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Performs a search query in a specific Kosmos knowledge space.
    """
    headers = _get_auth_headers(token)
    base_url = KOSMOS_API_URL.rstrip('/')
    endpoint = f"{base_url}/search/"
    
    filters = {
        "document_ids_include": doc_ids_include,
        "document_ids_exclude": doc_ids_exclude,
        "filename_contains": filename_contains,
        "filename_does_not_contain": filename_does_not_contain,
        "extensions_include": extensions_include,
        "extensions_exclude": extensions_exclude,
        "keywords_include_all": keywords_include_all,
        "keywords_exclude_any": keywords_exclude_any,
    }
    # Remove None values so they are not sent in the payload
    filters = {k: v for k, v in filters.items() if v is not None}

    payload = {
        "knowledge_space_id": str(ks_id),
        "query": query,
        "top_k": top_k,
        "filters": filters,
        "boosters": boosters or [],
        "max_content_length": 500,
        "detailed": True
    }
    
    response = requests.post(endpoint, json=payload, headers=headers)
    response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
    return response.json()

def read_from_kosmos(
    doc_ref: str, 
    ks_id: uuid.UUID, 
    start: int = 1, 
    end: Optional[int] = None,
    token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Reads content from a document or bookmark within a Kosmos knowledge space.
    """
    headers = _get_auth_headers(token)
    base_url = KOSMOS_API_URL.rstrip('/')
    endpoint = f"{base_url}/read/{doc_ref}"
    params = {
        "knowledge_space_id": str(ks_id),
        "start": start,
    }
    if end is not None:
        params["end"] = end
        
    response = requests.get(endpoint, params=params, headers=headers)
    response.raise_for_status()
    return response.json()

def get_page_image_from_kosmos(
    doc_id: str,
    page_number: int,
    token: Optional[str] = None
) -> bytes:
    """
    Retrieves a single page of a document rendered as a PNG image.
    """
    headers = _get_auth_headers(token)
    base_url = KOSMOS_API_URL.rstrip('/')
    endpoint = f"{base_url}/contents/{doc_id}/pages/{page_number}"
    
    response = requests.get(endpoint, headers=headers)
    response.raise_for_status()
    return response.content # Return the raw image bytes

def multi_document_grep_in_kosmos(
    token: Optional[str] = None,
    payload: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Executes a multi-document grep (regex search) API call using the new endpoint.
    The payload is expected to be the complete request body for the POST /api/v1/grep endpoint.
    """
    headers = _get_auth_headers(token)
    base_url = KOSMOS_API_URL.rstrip('/')
    endpoint = f"{base_url}/grep/"
    
    # The payload is now constructed by the service layer and passed in directly.
    # We just need to ensure UUIDs are converted to strings for JSON serialization.
    scope = payload.get("scope", {})
    if "knowledge_space_id" in scope and isinstance(scope["knowledge_space_id"], uuid.UUID):
        scope["knowledge_space_id"] = str(scope["knowledge_space_id"])
    if "document_ids" in scope and scope["document_ids"]:
        scope["document_ids"] = [str(doc_id) for doc_id in scope["document_ids"]]

    response = requests.post(endpoint, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()
