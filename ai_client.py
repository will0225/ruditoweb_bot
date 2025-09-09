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
    for key in ["type"]:
        if key in ["type"]:
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


def  getDescriptionByAI(title: str, brand: str, type: str, color: str, material: str, gender: str):
    
    prompt = f"""
        Role: e-commerce copywriter.

        Goal: From product photo(s) + a few fields, generate short, sales-ready copy in English and Russian.
        Tone: concise, premium, factual. No emojis. No hype. Don’t invent facts.
        Use simple color names (black, white, beige, navy, ivory, light-blue, etc.).

        Input:
        brand={brand};
        item={title};
        color={color};
        material={material};
        gender={gender};
        purchased in Italy.

        Task:
        1) EN: 1–2 concise sentences including item, color, brand, and the phrase “purchased in Italy”.
        2) Pairings EN: 2–3 bullets. Each bullet MUST include colors of pieces (e.g., beige trench, white tee, light-blue jeans).
        3) RU: 1–2 коротких предложения с типом, цветом, брендом и «куплено в Италии».
        4) Сочетания RU: 2–3 пункта. В КАЖДОМ пункте явно указать цвета вещей.

        Rules: no emojis, no hype, no invented facts; simple color names; max ~300 chars per language.

        Return EXACTLY in this layout (no extra headings or text):

        EN:
        <sentence(s)>
        Pairings:
        - <bullet 1>
        - <bullet 2>
        - <bullet 3 (opt)>

        RU:
        <предложение(я)>
        Сочетания:
        - <пункт 1>
        - <пункт 2>
        - <пункт 3 (опц.)>
    """

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert fashion e-commerce copywriter."},
            {"role": "user", "content": prompt}
        ]
    )

    description_text = resp.choices[0].message.content
    
    return description_text