import os
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def classify_item(image_url: str, controlled_lists: dict):
    """
    Classify a product from an image using GPT-4o-mini (vision).
    Returns a tuple: (ai_result: dict, needs_review: bool)
    """
    # Build prompt
    prompt = (
        "You are a product classification AI.\n"
        "Look at the photo and suggest:\n"
        "- Title\n"
        "- Description\n"
        "- Type (must match one of: {types})\n"
        "- Category (must match one of: {categories})\n"
        "- Color (must match one of: {colors})\n"
        "- Brand (must match one of: {brands}) if you are confident, else leave empty.\n\n"
        "If you are not confident about Type/Category/Color, leave them empty."
    ).format(
        types=", ".join(controlled_lists.get("type", [])),
        categories=", ".join(controlled_lists.get("category", [])),
        colors=", ".join(controlled_lists.get("color", [])),
        brands=", ".join(controlled_lists.get("brand", [])),
    )

    # Send request to OpenAI Vision API
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert product classifier."},
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_url}  # Correct type: string
                ],
            },
        ],
    )

    text = response.choices[0].message.content.strip()

    # Initialize result dictionary
    ai_result = {
        "title": "",
        "description": "",
        "type": "",
        "category": "",
        "color": "",
        "brand": ""
    }

    # Simple line-by-line parsing
    for line in text.split("\n"):
        line = line.strip()
        if line.lower().startswith("title"):
            ai_result["title"] = line.split(":", 1)[-1].strip()
        elif line.lower().startswith("description"):
            ai_result["description"] = line.split(":", 1)[-1].strip()
        elif line.lower().startswith("type"):
            value = line.split(":", 1)[-1].strip()
            ai_result["type"] = value if value in controlled_lists.get("type", []) else ""
        elif line.lower().startswith("category"):
            value = line.split(":", 1)[-1].strip()
            ai_result["category"] = value if value in controlled_lists.get("category", []) else ""
        elif line.lower().startswith("color"):
            value = line.split(":", 1)[-1].strip()
            ai_result["color"] = value if value in controlled_lists.get("color", []) else ""
        elif line.lower().startswith("brand"):
            value = line.split(":", 1)[-1].strip()
            ai_result["brand"] = value if value in controlled_lists.get("brand", []) else ""

    # Needs review if any key fields are missing
    needs_review = any([
        not ai_result["type"],
        not ai_result["category"],
        not ai_result["color"],
    ])

    return ai_result, needs_review
