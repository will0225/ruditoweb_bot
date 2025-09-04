import os
from typing import Dict, Tuple
import base64
from openai import OpenAI

# Initialize OpenAI client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

def classify_item(image_path: str, controlled_lists: Dict[str, list] = None) -> Tuple[dict, bool]:
    """
    Classify a product image using AI and normalize results to controlled lists.

    Args:
        image_path (str): Path to the main image
        controlled_lists (dict): {"type": [...], "category": [...], "color": [...], "brand": [...]}

    Returns:
        dict: {
            "title": str,
            "description": str,
            "type": str,
            "category": str,
            "color": str,
            "brand": str | None
        }
        bool: needs_review (True if AI output is uncertain or not in controlled lists)
    """
    controlled_lists = controlled_lists or {}
    needs_review = False

    # Call OpenAI Vision / Image Classification
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Extract title, description, type, category, color, brand."},
                        {"type": "image_url", 
                         "image_url": 
                            {
                                "url": image_path
                            }
                        }
                    ]
                }
            ]
        )
        # Extract text output
        text_output = response.output_text.strip()
        # Here, implement your parsing logic
        # Example: assume output is JSON string
        import json
        try:
            result = json.loads(text_output)
        except:
            result = {}

    except Exception as e:
        print("AI classification error:", e)
        result = {}

    # Normalize to controlled lists
    def normalize(field: str, controlled: list) -> str:
        val = result.get(field, "").strip()
        if controlled and val not in controlled:
            nonlocal needs_review
            needs_review = True
            return ""
        return val

    return {
        "title": result.get("title", ""),
        "description": result.get("description", ""),
        "type": normalize("type", controlled_lists.get("type", [])),
        "category": normalize("category", controlled_lists.get("category", [])),
        "color": normalize("color", controlled_lists.get("color", [])),
        "brand": normalize("brand", controlled_lists.get("brand", [])) or None
    }, needs_review
