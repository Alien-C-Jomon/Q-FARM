
from typing import Any

from backend.src.farm_data import get_crop_data


def get_seasonal_plan(crop_id: str) -> dict[str, Any]:
    """Return seasonal reference information without inventing farm dates."""
    crop = get_crop_data(crop_id)
    values = crop.get("values", {})

    if crop_id == "cardamom":
        harvest = values.get("harvest_season", {})

        return {
            "crop_id": crop_id,
            "crop_name": crop.get("crop_name", {}),
            "reported_harvest_months": harvest.get("reported", []),
            "source": crop.get("source"),
            "schedule_type": "local_reference",
            "farm_specific_calendar_available": False,
            "message": (
                "These are approximate reported harvest months, "
                "not a confirmed schedule for an individual farm."
            ),
        }

    if crop_id == "black_pepper":
        harvest = values.get("harvest_season", {})

        return {
            "crop_id": crop_id,
            "crop_name": crop.get("crop_name", {}),
            "reported_harvest_months": harvest.get("reported", []),
            "possible_extension_months": harvest.get(
                "reported_possible_extension", []
            ),
            "source": crop.get("source"),
            "schedule_type": "local_reference",
            "farm_specific_calendar_available": False,
            "message": (
                "These are approximate reported harvest months, "
                "not a confirmed schedule for an individual farm."
            ),
        }

    raise ValueError(f"Unsupported crop: {crop_id}")