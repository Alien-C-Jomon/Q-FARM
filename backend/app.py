from backend.src.task_store import (
    record_task,
    get_task_history,
    get_today_task_history,
)
from flask import Flask, jsonify, request, send_from_directory
from pathlib import Path

from backend.src.farm_data import get_crop_data, get_source_registry
from backend.src.farm_economics import (
    estimate_plant_count,
    estimate_reported_yield,
)
from backend.src.seasonal_planner import get_seasonal_plan
from backend.src.soil_support import get_soil_reference


app = Flask(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"



@app.get("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.get("/farm")
def farm_dashboard():
    return send_from_directory(FRONTEND_DIR, "farm.html")


@app.get("/ui/<path:filename>")
def frontend_assets(filename):
    return send_from_directory(FRONTEND_DIR, filename)
       

@app.get("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "Q-FARM",
        "version": "0.1.0",
        "diagnostic": False,
        "cloud_ai": False,
        "quantum_optimizer": False,
    })


@app.get("/api/crops")
def list_crops():
    crops = []

    for crop_id in ("cardamom", "black_pepper"):
        data = get_crop_data(crop_id)
        crops.append({
            "crop_id": data["crop_id"],
            "crop_name": data["crop_name"],
            "data_type": data.get("data_type"),
            "source": data.get("source"),
        })

    return jsonify({"crops": crops})


@app.get("/api/crops/<crop_id>")
def crop_details(crop_id):
    try:
        return jsonify(get_crop_data(crop_id))
    except ValueError as error:
        return jsonify({"error": str(error)}), 404


@app.get("/api/soil/<crop_id>")
def soil_details(crop_id):
    try:
        return jsonify(get_soil_reference(crop_id))
    except ValueError as error:
        return jsonify({"error": str(error)}), 404


@app.get("/api/seasons/<crop_id>")
def season_details(crop_id):
    try:
        return jsonify(get_seasonal_plan(crop_id))
    except ValueError as error:
        return jsonify({"error": str(error)}), 404


@app.get("/api/sources")
def sources():
    return jsonify(get_source_registry())


@app.post("/api/estimate/plants")
def plant_estimate():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"error": "Send a JSON object."}), 400

    try:
        result = estimate_plant_count(
            float(payload["area_acres"]),
            float(payload["plants_per_acre"]),
        )
        return jsonify(result)
    except (KeyError, TypeError, ValueError) as error:
        return jsonify({"error": f"Invalid plant estimate input: {error}"}), 400


@app.post("/api/estimate/yield")
def yield_estimate():
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"error": "Send a JSON object."}), 400

    try:
        crop_id = payload["crop_id"]
        plant_count = payload["plant_count"]

        if isinstance(plant_count, bool):
            raise ValueError("Plant count must be a positive whole number.")

        numeric_count = float(plant_count)
        if not numeric_count.is_integer() or numeric_count <= 0:
            raise ValueError("Plant count must be a positive whole number.")

        result = estimate_reported_yield(crop_id, int(numeric_count))
        return jsonify(result)
    except (KeyError, TypeError, ValueError) as error:
        return jsonify({"error": f"Invalid yield estimate input: {error}"}), 400


@app.errorhandler(500)
def internal_error(error):
    app.logger.exception("Unexpected Q-FARM server error")
    return jsonify({
        "error": "An internal server error occurred."
    }), 500


@app.get("/api/tasks/history")
def task_history():
    try:
        history = get_task_history()
        return jsonify({
            "status": "success",
            "count": len(history),
            "history": history,
        })
    except Exception:
        app.logger.exception("Could not retrieve task history")
        return jsonify({
            "error": "Could not retrieve task history."
        }), 500

@app.get("/api/tasks/today")
def today_task_history():
    try:
        history = get_today_task_history()
        return jsonify({
            "status": "success",
            "count": len(history),
            "history": history,
        })
    except Exception:
        app.logger.exception("Could not retrieve today's task history")
        return jsonify({
            "error": "Could not retrieve today's task history."
        }), 500


@app.post("/api/tasks")
def save_task():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object."}), 400

    task_key = data.get("task_key")
    status = data.get("status")

    if not isinstance(task_key, str) or not isinstance(status, str):
        return jsonify({
            "error": "task_key and status must be strings."
        }), 400

    try:
        saved_task = record_task(task_key, status)
        return jsonify({
            "status": "success",
            "task": saved_task,
        }), 201
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception:
        app.logger.exception("Could not save farm task")
        return jsonify({"error": "Could not save farm task."}), 500




from backend.src.ai_assistant import ask_farm_assistant
from backend.src.image_recognition import recognize_crop_image


@app.post("/api/assistant")
def farm_assistant():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Send a JSON request."}), 400

    question = data.get("question")
    language = data.get("language", "en")

    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Please enter a farming question."}), 400

    if language not in ("en", "ml"):
        return jsonify({"error": "Language must be en or ml."}), 400

    try:
        answer = ask_farm_assistant(question, language)
        return jsonify({
            "status": "success",
            "answer": answer,
            "language": language,
        }), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502

    except Exception:
        app.logger.exception("Farm assistant request failed")
        return jsonify({
            "error": "The farm assistant is temporarily unavailable."
        }), 500



@app.post("/api/recognize-image")
def recognize_image():
    if "image" not in request.files:
        return jsonify({
            "error": "Please upload a crop image."
        }), 400

    image = request.files["image"]

    if not image.filename:
        return jsonify({
            "error": "Please choose an image."
        }), 400

    crop_id = request.form.get("crop_id", "cardamom")
    language = request.form.get("language", "en")

    try:
        # Read at most 5 MB plus one byte to detect oversized uploads.
        image_bytes = image.stream.read(5 * 1024 * 1024 + 1)

        answer = recognize_crop_image(
            image_bytes=image_bytes,
            filename=image.filename,
            crop_id=crop_id,
            language=language,
        )

        return jsonify({
            "status": "success",
            "answer": answer,
            "crop_id": crop_id,
            "language": language,
        }), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502

    except Exception:
        app.logger.exception("Crop image recognition failed")
        return jsonify({
            "error": "Image analysis is temporarily unavailable."
        }), 500



if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)