# llm.py
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from typing import Optional, Literal, Union, List, Dict
import json
import os

import firebase_admin
from firebase_admin import credentials, firestore

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=API_KEY)

if not firebase_admin._apps:
    cred = credentials.Certificate("Gwallet/firebase_key/gwallet-180a9-firebase-adminsdk-fbsvc-c1fbf88538.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

class Item(BaseModel):
    name: str
    price: float
    quantity: int


class Receipt(BaseModel):
    type_of_purchase: Literal["Restaurant", "Retail", "Other"]
    date: str
    establishment_name: str
    items: List[Item]
    total: float


parser = PydanticOutputParser(pydantic_object=Receipt)

def build_extraction_prompt(image_path, format_instruction: str) -> str:
    return f"""
You are a receipt text extractor assistant. 
You are given a user-uploaded receipt image. 
Your job is to extract all important information and return it strictly following this format:

{format_instruction}

IMPORTANT:
- Return raw JSON only (no markdown, no ```json blocks).
- Start directly with '{{' and end with '}}'.
- Do NOT include any explanations or text outside the JSON.
"""


def build_chat_prompt(user_prompt: str, firebase_data: List[Dict]) -> str:
    """
    Create a chat prompt for Gemini that gives the LLM context
    about stored receipts in Firebase.
    """
    receipts_json = json.dumps(firebase_data, indent=2)
    return f"""
You are an intelligent financial assistant. You have access to the user's past receipts stored in Firebase.

User prompt:
{user_prompt}

Here is the list of receipts from Firebase:
{receipts_json}

Your job:
- Understand the user's request.
- Analyze the receipts to provide insights or summaries.
- Keep your response clear and factual.
- Do NOT output any JSON unless explicitly asked.
"""

def fetch_all_receipts_from_firebase() -> List[Dict]:
    """Retrieve all receipts and their items from Firestore."""
    receipts_ref = db.collection("receipts")
    snapshot = receipts_ref.stream()

    all_receipts = []
    for doc in snapshot:
        data = doc.to_dict()
        items_ref = receipts_ref.document(doc.id).collection("items").stream()
        items = [it.to_dict() for it in items_ref]
        data["id"] = doc.id
        data["items"] = items
        for k, v in data.items():
            if hasattr(v, "isoformat"):
                data[k] = v.isoformat()
        all_receipts.append(data)
    return all_receipts

def llm_model(*args, **kwargs):
    """
    Universal model handler.
    - If passed an image path -> extract structured data.
    - If passed a prompt and receipts -> chat reasoning.
    - If no receipts passed -> automatically fetch from Firebase.
    """
    if len(args) == 1 and isinstance(args[0], str) and args[0].lower().endswith((".jpg", ".jpeg", ".png")):
        image_path = args[0]
        uploaded_file = client.files.upload(file=image_path)
        prompt = build_extraction_prompt(image_path, format_instruction=parser.get_format_instructions())

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[prompt, uploaded_file],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=100)
            ),
        )

        raw_text = response.candidates[0].content.parts[0].text
        structured_response = parser.parse(raw_text)
        return structured_response

    elif len(args) >= 1 and isinstance(args[0], str):
        prompt = args[0]
        receipts = []
        if len(args) > 1 and isinstance(args[1], list):
            receipts = args[1]
        else:
            receipts = fetch_all_receipts_from_firebase()

        chat_prompt = build_chat_prompt(prompt, receipts)
        response = client.models.generate_content(
            model="gemini-2.0-flash-thinking-exp",
            contents=[chat_prompt],
            config=types.GenerateContentConfig(
                temperature=0.5,
                thinking_config=types.ThinkingConfig(thinking_budget=100),
            ),
        )
        return response.candidates[0].content.parts[0].text.strip()

    else:
        raise ValueError("Invalid llm_model call — must pass image_path or (prompt, [receipts])")

# if __name__ == "__main__":
#     print("Fetching receipts and asking Gemini...")
#     reply = llm_model("Summarize my last 5 purchases.")
#     print("LLM reply:", reply)



# from google import genai
# from google.genai import types
# from dotenv import load_dotenv
# from pydantic import BaseModel,Field
# from langchain_core.output_parsers import PydanticOutputParser
# from typing import Optional,Union,Literal
# import json
# import os

# load_dotenv()
# API_KEY = os.getenv("GOOGLE_API_KEY")

# client = genai.Client(api_key=API_KEY)

# class Item(BaseModel):
#     name :str
#     price:float
#     quantity:int
 

# class receipts(BaseModel):
#     type_of_purchase:Literal["Restaurant", "Retail", "Other"]
#     date:str
#     establishment_name:str
#     items:list[Item]
#     total :float

    

# parser = PydanticOutputParser(pydantic_object=receipts)


# def build_prompt(user_uloaded_image,format_instruction):
#     return f"""
#         You are a receipt text extractor assistant .You are given a user uploaded receipt .your job is to provided extracted text and return them in a following format {format_instruction}

#         IMPORTANT: Return raw JSON without any formatting, code blocks, or markdown. 
#         Start directly with  and end with .
#         Do NOT include ```json or ``` anywhere in your response.

# """


# def llm_model(image_path):
#     # client = genai.Client()
#     uploaded_file = client.files.upload(file=image_path)

#     prompt =build_prompt(image_path,format_instruction=parser.get_format_instructions())

#     response = client.models.generate_content(
#         model="gemini-2.5-flash-lite",
#         contents=[prompt, uploaded_file],
#         config=types.GenerateContentConfig(
#             thinking_config=types.ThinkingConfig(thinking_budget=0)
#         ))
    

#     # print(f"raw response  \n {response.candidates[0].content.parts[0].text}")
#     structured_response = parser.parse(response.candidates[0].content.parts[0].text)
#     return structured_response

