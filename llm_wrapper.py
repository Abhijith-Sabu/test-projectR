from typing import Any, Dict

def extract_from_image(path: str) -> Dict:
    """Return dict with parsed receipt fields (merchant, total, items, etc.)."""
    return {"merchant": "Example Store", "total": 12.34, "items": [{"name":"Milk","price":12.34}]}

def chat_with_receipts(prompt: str, receipts: list) -> str:
    """Return a single string reply suitable for frontend display."""
    return "I processed your prompt with the provided receipts."

def llm_model(*args, **kwargs):
    if len(args) == 1 and isinstance(args[0], str) and args[0].lower().endswith((".jpg", ".png", ".jpeg")):
        return extract_from_image(args[0])
    if len(args) >= 1 and isinstance(args[0], str):
        prompt = args[0]
        receipts = args[1] if len(args) > 1 else kwargs.get("receipts", [])
        return chat_with_receipts(prompt, receipts)
    raise ValueError("Invalid llm_model call")
