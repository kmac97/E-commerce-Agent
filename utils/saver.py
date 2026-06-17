# utils/saver.py
# Saves assistant responses to files in the data/ folder

import json
import os
from datetime import datetime


def save_response(topic: str, question: str, response: str, category: str = "products") -> str:
    """
    Save an assistant response to the appropriate data folder.

    Args:
        topic: Short name for the file (e.g., "posture-corrector")
        question: What the user asked
        response: The assistant's full response
        category: Subfolder — products, competitors, brands, decisions, templates

    Returns:
        Path to the saved file
    """
    valid_categories = ["products", "competitors", "brands", "decisions", "templates"]
    if category not in valid_categories:
        category = "products"

    # Build the file path
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    safe_topic = topic.lower().replace(" ", "-").replace("/", "-")[:40]
    filename = f"{timestamp}_{safe_topic}.json"

    # Get the directory of this script, go up one level to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder = os.path.join(project_root, "data", category)
    os.makedirs(folder, exist_ok=True)

    filepath = os.path.join(folder, filename)

    # Save as JSON for easy reading later
    data = {
        "saved_at": datetime.now().isoformat(),
        "category": category,
        "topic": topic,
        "question": question,
        "response": response,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return filepath


def list_saved(category: str = None) -> list:
    """
    List all saved research files, optionally filtered by category.

    Returns:
        List of dicts with filename, category, topic, saved_at
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_root = os.path.join(project_root, "data")

    results = []
    categories = ["products", "competitors", "brands", "decisions", "templates"]

    for cat in categories:
        if category and cat != category:
            continue
        folder = os.path.join(data_root, cat)
        if not os.path.exists(folder):
            continue
        for fname in sorted(os.listdir(folder)):
            if fname.endswith(".json"):
                fpath = os.path.join(folder, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    results.append({
                        "category": cat,
                        "topic": data.get("topic", fname),
                        "saved_at": data.get("saved_at", ""),
                        "filepath": fpath,
                    })
                except Exception:
                    pass

    return results
