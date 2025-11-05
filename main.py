import firebase_admin
from firebase_admin import credentials, firestore
import requests
from google.oauth2 import service_account
import google.auth.transport.requests
import json
import time
import jwt

# --- FIREBASE SETUP ---
if not firebase_admin._apps:
    cred = credentials.Certificate("Gwallet/firebase_key/gwallet-180a9-firebase-adminsdk-fbsvc-c1fbf88538.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- GOOGLE WALLET SETUP ---
SERVICE_ACCOUNT_FILE = "Gwallet/wallet-service-key.json"
ISSUER_ID = "3388000000023012969"
SCOPES = ["https://www.googleapis.com/auth/wallet_object.issuer"]

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
request = google.auth.transport.requests.Request()
credentials.refresh(request)
BASE_URL = "https://walletobjects.googleapis.com/walletobjects/v1"

# --- Helper Functions ---
def create_jwt_save_url(object_payload):
    with open(SERVICE_ACCOUNT_FILE, "r") as f:
        service_account_info = json.load(f)

    claims = {
        "iss": service_account_info["client_email"],
        "aud": "google",
        "typ": "savetowallet",
        "payload": {"genericObjects": [object_payload]},
    }

    token = jwt.encode(
        claims,
        service_account_info["private_key"],
        algorithm="RS256",
    )
    return f"https://pay.google.com/gp/v/save/{token}"


def create_wallet_object(receipt_data):
    """Create a Google Wallet object for a receipt."""

    items_text = "\n".join(
    [
        f"{i.get('name', 'Unknown')}: ₹{i.get('price', 0)} x {i.get('quantity', 1)}"
        for i in receipt_data.get("items", [])
    ]
)


    object_id = f"{ISSUER_ID}.receiptObject{int(time.time())}"

    object_payload = {
        "id": object_id,
        "classId": f"{ISSUER_ID}.receiptClass123",
        "state": "ACTIVE",
        "cardTitle": {"defaultValue": {"language": "en-US", "value": receipt_data["establishment_name"]}},
        "header": {"defaultValue": {"language": "en-US", "value": f"{receipt_data['type_of_purchase']} Receipt"}},
        "subheader": {"defaultValue": {"language": "en-US", "value": receipt_data["date"]}},
        "hexBackgroundColor": "#4285f4",
        "logo": {
            "sourceUri": {
                "uri": "https://storage.googleapis.com/wallet-lab-tools-codelab-artifacts-public/pass_google_logo.jpg"
            },
            "contentDescription": {
                "defaultValue": {"language": "en-US", "value": "Project Raseed Logo"}
            },
        },
        "textModulesData": [
            {"header": "Items Purchased", "body": items_text, "id": "items"},
            {"header": "Total Amount", "body": f"₹{receipt_data['total']}", "id": "total"},
        ],
        "barcode": {
            "type": "QR_CODE",
            "value": json.dumps({
                "establishment": receipt_data["establishment_name"],
                "date": receipt_data["date"],
                "type": receipt_data["type_of_purchase"],
                "total": receipt_data["total"],
                "items": receipt_data["items"],
            }),
        },
    }

    response = requests.post(
        f"{BASE_URL}/genericObject",
        headers={"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"},
        data=json.dumps(object_payload),
    )

    if response.status_code in [200, 409]:
        print(f"✅ Wallet object created for {receipt_data['establishment_name']}")
        save_url = create_jwt_save_url(object_payload)
        print(f"🔗 Save to Google Wallet: {save_url}\n")
        return save_url
    else:
        print("❌ Failed:", response.text)
        return None



# def get_all_receipts():
#     """Fetch all receipts + their items from Firestore."""
#     receipts_ref = db.collection("receipts").order_by("created_at", direction=firestore.Query.DESCENDING)
#     docs = receipts_ref.stream()
#     receipts = []

#     for doc in docs:
#         data = doc.to_dict()
#         items_ref = db.collection("receipts").document(doc.id).collection("items")
        
#         # Map item_name to name for consistency
#         items = []
#         for i in items_ref.stream():
#             item_data = i.to_dict()
#             items.append({
#                 "name": item_data.get("item_name", item_data.get("name", "Unknown")),
#                 "price": item_data.get("price", 0),
#                 "quantity": item_data.get("quantity", 1)
#             })
        
#         data["items"] = items
#         data["id"] = doc.id
#         receipts.append(data)

#     return receipts

# # --- MAIN FLOW ---
# if __name__ == "__main__":
#     print("📦 Fetching receipts from Firestore...\n")
#     receipts = get_all_receipts()

#     print(f"Found {len(receipts)} receipts.\n")
#     for receipt in receipts:
#         create_wallet_object(receipt)
