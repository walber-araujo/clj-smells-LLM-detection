import json
from pathlib import Path


def load_catalog(path: str = "smells_catalog.json") -> dict:
    """
    Load smells_catalog.json and return a flat index:
        smell_id -> { id, name, summary, category }
    """
    catalog_path = Path(path)
    if not catalog_path.exists():
        raise FileNotFoundError(f"Catalog not found at: {catalog_path.resolve()}")

    with catalog_path.open(encoding="utf-8") as f:
        data = json.load(f)

    index: dict[str, dict] = {}
    for category in data["categories"]:
        for smell in category["smells"]:
            index[smell["id"]] = {
                "id": smell["id"],
                "name": smell["name"],
                "summary": smell["summary"],
                "category": category["label"],
            }
    return index


def format_catalog_for_prompt(catalog: dict) -> str:
    """
    Render the catalog as a compact bullet list for the Detection Agent prompt.
    One line per smell: [id] summary
    """
    lines = []
    for entry in catalog.values():
        lines.append(f"- [{entry['id']}] {entry['summary']}")
    return "\n".join(lines)
