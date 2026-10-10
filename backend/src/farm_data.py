
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "backend" / "data"


CROP_FILES = {
    "cardamom": "cardamom.json",
    "black_pepper": "black_pepper.json",
}


def load_json_file(filename: str) -> dict[str, Any]:
    """Load a JSON file from the Q-FARM data directory."""
    file_path = DATA_DIR / filename

    if not file_path.is_file():
        raise FileNotFoundError(f"Q-FARM data file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {filename}")

    return data


def get_crop_data(crop_id: str) -> dict[str, Any]:
    """Return stored reference data for a supported crop."""
    if crop_id not in CROP_FILES:
        supported = ", ".join(sorted(CROP_FILES))
        raise ValueError(
            f"Unsupported crop '{crop_id}'. Supported crops: {supported}"
        )

    data = load_json_file(CROP_FILES[crop_id])

    if data.get("crop_id") != crop_id:
        raise ValueError(
            f"Crop ID inside {CROP_FILES[crop_id]} does not match its filename."
        )

    return data


def get_source_registry() -> dict[str, Any]:
    """Return the source registry without treating entries as verified evidence."""
    return load_json_file("sources.json")