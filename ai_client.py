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
        "_ 'category' must choose from the below list. \n"
        " Women:"
            'All'
            'Bags / Backpacks Women / Bags Women / Suitcases'
            'Accessories / Belts Women / Scarves Women / Gloves Women / Hats Women / Sunglasses Women / Glasses Women'
            'Shoes / Boots Women / Sneakers Women / Shoes Women / Shoes Heels Women / Slippers and Sandals Women'
            'Clothing / Coats Women / Jackets Women / Gilets Women / Dresses / Skirts / Jeans / Pants Women / Leggings Women / Shorts Women / Shirts Women / Bluse / Polo / Tops Women / T-Shirts Women / Sweatshirts Women / Sport Suits Women / Body Women / Underwear Women'

        "Men:"
            'All'
            'Bags / Backpacks Men / Bags Men / Suitcases'
            'Accessories / Belts Men / Scarves Men / Gloves Men / Hats Men / Sunglasses Men'
            'Shoes / Boots Men / Sneakers Men / Shoes Men / Slippers and Sandals Men'
            'Clothing / Coats Men / Jackets Men / Classic Clothes Men / Gilets Men / Jeans Men / Pants Men / Shorts Men / Shirts Men / Polo Shirts Men / T-Shirts Men / Sweatshirts Men / Sport Suits Men'
        
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
    for key in ["type", "color", "brand"]:
        if key in ["type", "color", "brand"]:
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
