import base64
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


# ---------------------------------------------------------
# Q-FARM | Crop Image Recognition
# ---------------------------------------------------------
# Gemini-powered agricultural visual observation.
# Supports cardamom and black pepper.
# Does not diagnose diseases or prescribe chemicals.
# ---------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

MAX_IMAGE_BYTES = 5 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 90
MAX_OUTPUT_TOKENS = 1200

MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

CROP_NAMES = {
    "cardamom": "cardamom",
    "black_pepper": "black pepper",
}

GENERIC_RESPONSES = {
    "safe",
    "user safety: safe",
    "user safety safe",
    "image is safe",
    "the image is safe",
    "no analysis available",
    "unable to analyze",
}


def _extract_answer(result):
    """Extract text safely from Gemini generateContent response."""

    if not isinstance(result, dict):
        raise RuntimeError("Gemini returned an invalid response.")

    candidates = result.get("candidates")

    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError(
            "Gemini returned no result. "
            "Check the model and API configuration."
        )

    candidate = candidates[0]

    if not isinstance(candidate, dict):
        raise RuntimeError("Gemini returned an invalid candidate.")

    content = candidate.get("content", {})

    if not isinstance(content, dict):
        raise RuntimeError("Gemini returned an invalid content object.")

    parts = content.get("parts", [])

    if not isinstance(parts, list):
        raise RuntimeError("Gemini returned an invalid parts list.")

    text_parts = []

    for part in parts:
        if not isinstance(part, dict):
            continue

        text = part.get("text")

        if isinstance(text, str) and text.strip():
            text_parts.append(text.strip())

    answer = "\n".join(text_parts).strip()

    if not answer:
        raise RuntimeError(
            "Gemini returned an empty response. "
            "The model may not have been able to analyze the image."
        )

    return answer


def _validate_analysis(answer):
    """Reject empty, generic, or obviously irrelevant responses."""

    cleaned = re.sub(r"\s+", " ", answer).strip()
    normalized = cleaned.casefold().strip(" .!\"'")

    if normalized in GENERIC_RESPONSES:
        raise RuntimeError(
            "Gemini returned a generic response instead of crop "
            "observations. Please try another image."
        )

    if len(cleaned) < 120:
        raise RuntimeError(
            "The AI response is too short to provide useful crop "
            "observations. Please try again."
        )

    return answer.strip()


def _provider_error_message(exc):
    """Read Gemini error information without exposing credentials."""

    try:
        body = exc.read().decode("utf-8", errors="replace")
        data = json.loads(body)

        error = data.get("error", {})

        if isinstance(error, dict):
            message = error.get("message")
        else:
            message = None

        if isinstance(message, str):
            return re.sub(r"\s+", " ", message).strip()[:300]

    except (ValueError, TypeError, AttributeError):
        pass

    return ""


def recognize_crop_image(
    image_bytes,
    filename,
    crop_id,
    language="en",
):
    """
    Analyze a cardamom or black pepper image using Gemini.

    Returns textual observations or raises RuntimeError.
    """

    # 1. Validate user input.
    if crop_id not in CROP_NAMES:
        raise ValueError("Choose cardamom or black pepper.")

    if language not in ("en", "ml"):
        raise ValueError("Language must be en or ml.")

    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise ValueError("The uploaded image is empty or invalid.")

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("Image must be 5 MB or smaller.")

    extension = Path(filename or "").suffix.lower()
    mime_type = MIME_TYPES.get(extension)

    if not mime_type:
        raise ValueError("Use a JPG, JPEG, PNG, or WEBP image.")

    # 2. Load Gemini configuration.
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "Gemini API key is not configured. "
            "Check backend\\.env."
        )

    model = os.getenv(
        "QFARM_VISION_MODEL",
        "gemini-3.1-flash-lite",
    ).strip()

    if not model:
        raise RuntimeError(
            "QFARM_VISION_MODEL is empty. "
            "Configure a Gemini model in backend\\.env."
        )

    crop_name = CROP_NAMES[crop_id]

    # 3. Language instructions.
    if language == "ml":
        language_instruction = (
            "Write the entire final answer in clear, natural "
            "Malayalam using Malayalam script. Avoid Manglish. "
            "Keep necessary scientific terms understandable."
        )

        section_names = (
            "കാണാൻ കഴിയുന്ന നിരീക്ഷണങ്ങൾ",
            "സാധ്യമായ കാരണങ്ങൾ",
            "അടുത്തതായി പരിശോധിക്കേണ്ട കാര്യങ്ങൾ",
            "സഹായം തേടേണ്ട സാഹചര്യം",
        )

    else:
        language_instruction = (
            "Write the entire final answer in clear English."
        )

        section_names = (
            "Visible observations",
            "Possible causes",
            "What to check next",
            "When to seek help",
        )

    system_prompt = f"""
You are Q-FARM, an agricultural visual-observation assistant
helping farmers in Kerala, India.

The farmer selected: {crop_name}.

IMPORTANT IMAGE-ANALYSIS REQUIREMENTS:

- Examine the actual image attached to the user message.
- Do not answer with a content-safety classification.
- Do not output "User Safety: safe" or similar generic messages.
- Do not claim to have analyzed the image if you cannot see it.
- If image input is unavailable, say so explicitly.
- Describe only visual details that can reasonably be observed.
- If the photo is unclear, explain the limitation.
- Do not invent leaf spots, pests, discoloration, or symptoms.
- Do not assume a disease from the crop name alone.
- Separate visible observations from possible explanations.
- Possible causes are not confirmed diagnoses.
- Suggest practical, low-risk inspection steps.
- Do not prescribe pesticides, chemical doses, or mixtures.
- Do not invent laboratory results, weather data, or sources.
- Recommend a qualified agricultural officer or Krishi Bhavan
  when symptoms are serious, spreading, or uncertain.

{language_instruction}

Use these four sections:

1. {section_names[0]}
2. {section_names[1]}
3. {section_names[2]}
4. {section_names[3]}

Aim for a concise but useful response based on the photograph.

If the image does not clearly show the selected crop,
state that clearly.
""".strip()

    # 4. Encode image.
    encoded_image = base64.b64encode(image_bytes).decode("ascii")

    # 5. Gemini generateContent request.
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            system_prompt
                            + "\n\n"
                            + f"Please visually examine this "
                            f"{crop_name} photograph. "
                            "Describe the actual visible plant "
                            "features and provide the four "
                            "requested sections. "
                            "If you cannot inspect the image, "
                            "say so instead of guessing."
                        )
                    },
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": encoded_image,
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
        },
    }

    request_url = API_URL.format(model=model)

    request = Request(
        request_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    # 6. Send request.
    try:
        with urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            raw_response = response.read().decode("utf-8")

        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError:
            raise RuntimeError(
                "Gemini returned invalid JSON. Please try again."
            ) from None

        answer = _extract_answer(result)

        answer = _validate_analysis(answer)

        return answer

    except HTTPError as exc:

        provider_message = _provider_error_message(exc)

        if exc.code == 400:
            raise RuntimeError(
                "Gemini rejected the image request. "
                "Check the image format, model name, and request."
                + (
                    f" Provider detail: {provider_message}"
                    if provider_message
                    else ""
                )
            ) from None

        if exc.code == 401 or exc.code == 403:
            raise RuntimeError(
                "Gemini rejected the API key. "
                "Check GEMINI_API_KEY in backend\\.env."
            ) from None

        if exc.code == 404:
            raise RuntimeError(
                "The configured Gemini model was not found or "
                "is unavailable. Check QFARM_VISION_MODEL."
            ) from None

        if exc.code == 429:
            raise RuntimeError(
                "Gemini rate limit reached. "
                "Please wait before trying again."
                + (
                    f" Provider detail: {provider_message}"
                    if provider_message
                    else ""
                )
            ) from None

        if exc.code == 413:
            raise RuntimeError(
                "The image request was too large. "
                "Try a smaller image."
            ) from None

        raise RuntimeError(
            f"Gemini request failed with HTTP {exc.code}."
            + (
                f" Provider detail: {provider_message}"
                if provider_message
                else ""
            )
        ) from None

    except (URLError, TimeoutError):
        raise RuntimeError(
            "Could not reach Gemini. "
            "Check your internet connection and try again."
        ) from None