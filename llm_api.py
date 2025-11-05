from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from llm import llm_model
from fbase import insert_data, get_all_receipts
import tempfile, shutil, logging, inspect, json
from typing import Any
from main import create_wallet_object
from firebase_admin import firestore
app = FastAPI()
logging.basicConfig(level=logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def safe_json(obj: Any):
    """Safely serialize Firestore and custom Python objects."""
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return str(obj)


async def call_llm_model(*args, **kwargs):
    """Handle async/sync llm_model calls gracefully."""
    if inspect.iscoroutinefunction(llm_model):
        return await llm_model(*args, **kwargs)
    result = llm_model(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


@app.post("/extract-receipt")
async def extract_receipt(file: UploadFile = File(...)):
    """Handle image upload and receipt extraction."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_path = tmp.name

        result = await call_llm_model(temp_path)
        payload = (
            safe_json(result.model_dump())
            if hasattr(result, "model_dump")
            else safe_json(result)
        )
        return {"status": "success", "data": payload}
    except Exception as e:
        logging.exception("extract_receipt failed")
        return {"status": "error", "message": str(e)}


@app.post("/save-receipt")
async def save_receipt(request: Request):
    """Save receipt data to Firebase."""
    try:
        data = await request.json()
        receipt_id = insert_data(data)
        if receipt_id:
            return {"status": "success", "receipt_id": receipt_id}
        return {"status": "error", "message": "Failed to save"}
    except Exception as e:
        logging.exception("save_receipt failed")
        return {"status": "error", "message": str(e)}


@app.get("/receipts")
async def list_receipts():
    """Return all receipts stored in Firestore."""
    try:
        receipts = get_all_receipts()
        return {"status": "success", "data": safe_json(receipts)}
    except Exception as e:
        logging.exception("list_receipts failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/save-to-wallet/{receipt_id}")
async def save_to_wallet(receipt_id:str):
    try :
        db = firestore.client()
        doc_ref = db.collection("receipts").document(receipt_id)
        doc= doc_ref.get()
        if not doc.exists:
            return {"status":"error","message":"Receipt not found"}
        receipt_data= doc.to_dict()
        item_ref = doc_ref.collection("items")
        items =[
            {
                "name":i.to_dict().get("item_name","unknown"),
                "price":i.to_dict().get("price",0),
                "quantity":i.to_dict().get("quantity",1),

            }
            for i  in item_ref.stream()
        ]
        receipt_data["items"]=items
        save_url = create_wallet_object(receipt_data)
        if save_url:
            # return {"status":'success',"saveurl":save_url}
            return {"status": "success", "saveUrl": save_url}

        else:
            return {"status":"error","message":"Failed to create wallet object"}
        
    except Exception as e:
        return {"status": "error","message":str(e)}





@app.post("/llm-receipt")
async def llm_receipt(req: Request):
    """
    Chat endpoint — LLM always accesses live Firebase receipts
    and responds to the user’s prompt.
    """
    try:
        body = await req.json()
        prompt = body.get("prompt", "")

        result = await call_llm_model(prompt)

        if isinstance(result, dict):
            reply = result.get("reply") or json.dumps(result)
        else:
            reply = str(result)

        return {"reply": reply}
    except Exception as e:
        logging.exception("llm_receipt failed")
        return {"reply": f"Error: {str(e)}"}
