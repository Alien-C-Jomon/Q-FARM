
from typing import Any

from backend.src.farm_data import get_crop_data


def estimate_plant_count(
    area_acres: float,
    plants_per_acre: float,
) -> dict[str, Any]:
    """Estimate plant count using a user-provided density."""
    if area_acres <= 0:
        raise ValueError("Area must be greater than zero.")

    if plants_per_acre <= 0:
        raise ValueError("Plant density must be greater than zero.")

    estimated_count = round(area_acres * plants_per_acre)

    return {
        "area_acres": area_acres,
        "plants_per_acre": plants_per_acre,
        "estimated_plant_count": estimated_count,
        "estimate_only": True,
    }


def estimate_reported_yield(
    crop_id: str,
    plant_count: int,
) -> dict[str, Any]:
    """
    Calculate a reported yield scenario from local reference data.
    This is not a forecast or a guaranteed harvest.
    """
    if plant_count <= 0:
        raise ValueError("Plant count must be greater than zero.")

    crop = get_crop_data(crop_id)
    values = crop.get("values", {})

    if crop_id == "cardamom":
        yield_info = values.get("yield_per_plant", {})
        reported_yield = yield_info.get("reported")

        if reported_yield is None:
            raise ValueError("Cardamom yield reference is unavailable.")

        return {
            "crop_id": crop_id,
            "plant_count": plant_count,
            "reported_yield_per_plant_kg": reported_yield,
            "calculated_yield_kg": plant_count * reported_yield,
            "yield_basis": "local reported reference",
            "estimate_only": True,
            "warning": "Not a guaranteed or farm-measured yield.",
        }

    if crop_id == "black_pepper":
        yield_info = values.get("yield_per_vine", {})
        reported_range = yield_info.get("reported_typical_range")

        if not isinstance(reported_range, list) or len(reported_range) != 2:
            raise ValueError("Black pepper yield reference is unavailable.")

        return {
            "crop_id": crop_id,
            "plant_count": plant_count,
            "reported_yield_per_vine_kg_range": reported_range,
            "calculated_yield_kg_range": [
                plant_count * reported_range[0],
                plant_count * reported_range[1],
            ],
            "yield_basis": "local reported reference",
            "estimate_only": True,
            "warning": "Not a guaranteed or farm-measured yield.",
        }

    raise ValueError(f"Unsupported crop: {crop_id}")