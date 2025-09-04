import os
from openai import OpenAI
import json

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def classify_item(image_url: str, controlled_lists: dict):
    """
    Classify a product from an image using GPT-4o-mini (vision).
    Returns a tuple: (ai_result: dict, needs_review: bool)
    """

    # Structured prompt requesting JSON
    prompt = (
        "You are a product classification AI.\n"
        "Analyze the product photo at the given URL and respond **ONLY** in JSON with the keys:\n"
        "- title\n"
        "- description\n"
        "- type (must match one of: {types})\n"
        "- category (must match one of: {categories})\n"
        "- color (must match one of: {colors})\n"
        "- brand (must match one of: {brands}) or empty string if unsure\n"
        "If Type/Category/Color does not match controlled lists, leave them empty.\n"
        "Example output:\n"
        '{{"title": "...", "description": "...", "type": "...", "category": "...", "color": "...", "brand": "..."}}'
    ).format(
        types=", ".join(controlled_lists.get("type", [])),
        categories=", ".join(controlled_lists.get("category", [])),
        colors=", ".join(controlled_lists.get("color", [])),
        brands=", ".join(controlled_lists.get("brand", [])),
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert product classifier."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": { "url": image_url }
                     }  # Correct type: string
                ],
            },
        ]
    )

    # Parse JSON safely
    try:
        text = response.choices[0].message.content.strip()
        print(text)
        ai_result = json.loads(text)
    except Exception as e:
        print("AI classification error:", e)
        ai_result = {
            "title": "",
            "description": "",
            "type": "",
            "category": "",
            "color": "",
            "brand": ""
        }

    # Ensure only valid values from controlled lists
    for key in ["type", "category", "color", "brand"]:
        if key in controlled_lists and ai_result.get(key) not in controlled_lists.get(key, []):
            ai_result[key] = ""

    needs_review = any([
        not ai_result.get("type"),
        not ai_result.get("category"),
        not ai_result.get("color")
    ])

    return ai_result, needs_review
