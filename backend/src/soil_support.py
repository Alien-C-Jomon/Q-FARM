
from typing import Any

from backend.src.farm_data import get_crop_data


def get_soil_reference(crop_id: str) -> dict[str, Any]:
    """Return recorded soil references without claiming farm measurements."""
    crop = get_crop_data(crop_id)
    soil = crop.get("values", {}).get("soil")

    if not isinstance(soil, dict):
        return {
            "crop_id": crop_id,
            "soil_reference_available": False,
            "message": "No structured soil reference is currently recorded.",
        }

    return {
        "crop_id": crop_id,
        "soil_reference_available": True,
        "local_soil_term": soil.get("reported_local_term"),
        "reported_characteristic": soil.get("reported_characteristic"),
        "external_ph_reference": soil.get("pH_reference"),
        "external_ph_source_type": soil.get("pH_source_type"),
        "farm_ph_measured": soil.get("farm_pH_measured", False),
        "warning": (
            "Reference values are not measurements of your farm. "
            "Use a soil test for farm-specific pH and nutrient information."
        ),
    }


def record_farm_ph(ph_value: float) -> dict[str, Any]:
    """Validate a user-entered pH value without treating it as verified."""
    if not isinstance(ph_value, (int, float)) or isinstance(ph_value, bool):
        raise ValueError("pH must be a numeric value.")

    if not 0 <= ph_value <= 14:
        raise ValueError("pH must be between 0 and 14.")

    return {
        "reported_ph_value": float(ph_value),
        "measurement_status": "user_entered_unverified",
        "warning": (
            "This value is user-entered, not independently verified. "
            "Record the soil test date and source separately."
        ),
    }