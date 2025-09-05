import os
import json
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def classify_item(image_url: str, controlled_lists: dict):
    """
    Classify a product from an image using GPT-4o-mini (vision).
    Returns a tuple: (ai_result: dict, needs_review: bool)
    """
    # Prompt for structured JSON output
    prompt = (
        "You are an expert product classifier. Look at the product image and respond ONLY with a valid JSON object.\n\n"
        "The JSON must have the following keys:\n"
        "- title\n"
        "- description\n"
        "- type\n"
        "- category\n"
        "- color\n"
        "- brand\n\n"
        "Rules:\n"
        "- Respond ONLY with JSON (no markdown, no code fences, no explanations).\n"
        "- 'title' and 'description' must always be filled.\n"
        "- If unsure about 'brand', leave it empty.\n"
        "- For 'type', 'category', and 'color', provide your best guess (normalization will be applied later)."
    )

    # Call OpenAI Vision API
    response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a product classification AI."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": { "url": image_url }}
            ]
        }
    ]
)

    # Extract text
    text = response.choices[0].message.content.strip()
    print(text)
    # Try parsing JSON
    try:
        ai_result = json.loads(text)
    except Exception:
        ai_result = {
            "title": "",
            "description": "",
            "type": "",
            "category": "",
            "color": "",
            "brand": ""
        }

    # Normalize type/category/color according to controlled lists
    for key in ["type", "category", "color", "brand"]:
        if key in ["type", "category", "color", "brand"]:
            value = ai_result.get(key, "").strip()
            if key in controlled_lists:
                ai_result[key] = value if value in controlled_lists[key] else ""
            else:
                ai_result[key] = value
    print(ai_result)
    # Determine if review is needed
    needs_review = any([
        not ai_result["type"],
        not ai_result["category"],
        not ai_result["color"],
    ])

    return ai_result, needs_review
