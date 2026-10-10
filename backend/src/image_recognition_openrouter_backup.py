
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
# Supports cardamom and black pepper image analysis.
# Uses OpenRouter-compatible vision models.
# Does not diagnose diseases or prescribe chemical treatments.
# ---------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

API_URL = "https://openrouter.ai/api/v1/chat/completions"
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
    "user safety: safe",
    "user safety safe",
    "safe",
    "safety: safe",
    "image is safe",
    "the image is safe",
    "no analysis available",
    "unable to analyze",
}


def _extract_answer(result):
    """Extract text from a chat-completions response safely."""

    if not isinstance(result, dict):
        raise RuntimeError(
            "OpenRouter returned an invalid response."
        )

    choices = result.get("choices")

    if not isinstance(choices, list) or not choices:
        raise RuntimeError(
            "The vision model returned no result. "
            "Check the selected model and try again."
        )

    choice = choices[0]

    if not isinstance(choice, dict):
        raise RuntimeError(
            "The vision model returned an invalid result."
        )

    message = choice.get("message", {})

    if not isinstance(message, dict):
        raise RuntimeError(
            "The vision model returned an invalid message."
        )

    content = message.get("content")

    if isinstance(content, str):
        answer = content.strip()

    elif isinstance(content, list):
        parts = []

        for item in content:
            if not isinstance(item, dict):
                continue

            text = item.get("text")

            if isinstance(text, str) and text.strip():
                parts.append(text.strip())

        answer = "\n".join(parts).strip()

    else:
        answer = ""

    if not answer:
        raise RuntimeError(
            "The vision model returned an empty response. "
            "The selected model may not support image input."
        )

    return answer, choice.get("finish_reason")


def _validate_analysis(answer):
    """Reject empty, generic, or obviously irrelevant responses."""

    cleaned = re.sub(r"\s+", " ", answer).strip()
    normalized = cleaned.casefold().strip(" .!\"'")

    if normalized in GENERIC_RESPONSES:
        raise RuntimeError(
            "The AI returned a generic safety message instead of "
            "crop observations. The selected model may not support "
            "vision correctly. Check QFARM_VISION_MODEL in "
            "backend\\.env."
        )

    # Catch safety-only responses even when the provider adds
    # a few words around the generic message.
    if (
        "user safety" in normalized
        and len(cleaned) < 180
        and not any(
            term in normalized
            for term in (
                "leaf",
                "plant",
                "stem",
                "root",
                "symptom",
                "observation",
                "വളർച്ച",
                "ഇല",
                "ചെടി",
            )
        )
    ):
        raise RuntimeError(
            "The AI did not provide meaningful crop observations. "
            "Check that the configured model supports image input."
        )

    if len(cleaned) < 120:
        raise RuntimeError(
            "The AI response is too short to provide useful crop "
            "observations. Please try again or check the vision model."
        )

    return answer.strip()


def _provider_error_message(exc):
    """Read a provider error without exposing credentials."""

    try:
        body = exc.read().decode("utf-8", errors="replace")
        data = json.loads(body)
        info = data.get("error", {})

        if isinstance(info, dict):
            message = info.get("message")
            code = info.get("code")
        else:
            message = None
            code = None

        # Keep provider text short and avoid returning arbitrary
        # response data to the browser.
        if isinstance(message, str):
            message = re.sub(r"\s+", " ", message).strip()[:250]
        else:
            message = ""

        return message, code

    except (ValueError, TypeError, AttributeError):
        return "", None


def recognize_crop_image(
    image_bytes,
    filename,
    crop_id,
    language="en",
):
    """
    Analyze a cardamom or black pepper image using a vision model.

    Returns useful textual observations or raises RuntimeError
    when the provider cannot provide a meaningful analysis.
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

    # 2. Load provider configuration.
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "OpenRouter API key is not configured. "
            "Check backend\\.env."
        )

    model = os.getenv(
        "QFARM_VISION_MODEL",
        "openrouter/free",
    ).strip()

    if not model:
        raise RuntimeError(
            "QFARM_VISION_MODEL is empty. "
            "Configure a vision-capable model in backend\\.env."
        )

    crop_name = CROP_NAMES[crop_id]

    # 3. Build language-specific instructions.
    if language == "ml":
        language_instruction = (
            "Write the entire final answer in clear, natural "
            "Malayalam using Malayalam script. Avoid Manglish. "
            "Keep necessary scientific terms understandable."
        )

        section_names = (
            "കാണുന്ന ലക്ഷണങ്ങൾ",
            "സാധ്യമായ കാരണങ്ങൾ",
            "അടുത്തതായി പരിശോധിക്കേണ്ടത്",
            "എപ്പോൾ സഹായം തേടണം",
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
- If image input is unavailable to you, say so explicitly.
- Describe only visual details that can reasonably be observed.
- If the photo is unclear, explain the limitation.
- Do not invent leaf spots, pests, discoloration, or symptoms.
- Do not assume a disease from the crop name alone.
- Separate visible observations from possible explanations.
- Explain that possible causes are not confirmed diagnoses.
- Suggest practical, low-risk inspection steps.
- Do not prescribe pesticides, chemical doses, or mixtures.
- Do not invent laboratory results, weather data, or sources.
- Recommend a qualified agricultural officer or Krishi Bhavan
  when symptoms are serious, spreading, or uncertain.

{language_instruction}

Use these four sections, with useful details under each:
1. {section_names[0]}
2. {section_names[1]}
3. {section_names[2]}
4. {section_names[3]}

Aim for a concise but useful response based on the photograph.
If the image does not clearly show the selected crop, state that.
""".strip()

    # 4. Encode the image for the vision API.
    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    image_data_url = f"data:{mime_type};base64,{encoded_image}"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Please visually examine this "
                            f"{crop_name} photograph. Describe the "
                            "actual visible plant features and "
                            "provide the four requested sections. "
                            "If you cannot inspect the image, "
                            "say so instead of guessing."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url,
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
        "temperature": 0.2,
        "max_tokens": MAX_OUTPUT_TOKENS,
    }

    request = Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-OpenRouter-Title": "Q-FARM Image Recognition",
        },
        method="POST",
    )

    # 5. Send the request and handle provider errors.
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
                "OpenRouter returned invalid JSON. Please try again."
            ) from None

        answer, finish_reason = _extract_answer(result)

        # Reject generic responses rather than reporting success.
        answer = _validate_analysis(answer)

        if finish_reason == "length":
            answer += (
                "\n\nNote: The response reached its output limit "
                "and may be incomplete."
            )

        return answer

    except HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError(
                "OpenRouter rejected the API key. Check the key "
                "configured in backend\\.env."
            ) from None

        if exc.code == 402:
            raise RuntimeError(
                "The selected model or account requires credits. "
                "Check the model's pricing and account limits."
            ) from None

        if exc.code == 413:
            raise RuntimeError(
                "The image request was too large. Try a smaller image."
            ) from None

        if exc.code == 429:
            provider_message, _ = _provider_error_message(exc)

            raise RuntimeError(
                "OpenRouter rate limit reached. Wait before trying "
                "again. Free models may have usage limits."
                + (
                    f" Provider detail: {provider_message}"
                    if provider_message
                    else ""
                )
            ) from None

        provider_message, _ = _provider_error_message(exc)

        if exc.code == 400:
            raise RuntimeError(
                "OpenRouter rejected the request. The selected model "
                "may not support image input, or the request format "
                "may be unsupported."
                + (
                    f" Provider detail: {provider_message}"
                    if provider_message
                    else ""
                )
            ) from None

        if exc.code == 404:
            raise RuntimeError(
                "The configured vision model was not found or is "
                "unavailable. Check QFARM_VISION_MODEL in backend\\.env."
            ) from None

        raise RuntimeError(
            f"OpenRouter request failed with HTTP {exc.code}."
            + (
                f" Provider detail: {provider_message}"
                if provider_message
                else ""
            )
        ) from None

    except (URLError, TimeoutError):
        raise RuntimeError(
            "Could not reach OpenRouter. Check your internet "
            "connection and try again."
        ) from None