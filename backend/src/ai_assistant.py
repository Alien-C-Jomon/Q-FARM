import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

MODEL = os.getenv("QFARM_CHAT_MODEL", "gemini-3.1-flash-lite")
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent"
)


def ask_farm_assistant(question, language="en"):
    """Ask Gemini a farming question and return a readable answer."""

    if not isinstance(question, str) or not question.strip():
        raise ValueError("Please enter a farming question.")

    if language not in ("en", "ml"):
        raise ValueError("Language must be en or ml.")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Gemini API key is not configured.")

    if language == "ml":
        language_instructions = (
            "Write your entire answer in natural, clear Malayalam using "
            "the Malayalam script. Do not use Manglish or transliterated "
            "Malayalam. Avoid unnecessary English words and do not mix "
            "languages mid-sentence. Keep scientific crop names and "
            "essential technical terms in English only when helpful. "
            "Use short, readable Malayalam sentences and simple words."
        )
    else:
        language_instructions = (
            "Write your entire answer in clear, natural English. "
            "Do not switch languages. Use short, readable sentences."
        )

    system_prompt = (
        "You are Q-FARM, an agricultural information assistant for "
        "cardamom and black pepper farmers in Kerala, India.\n\n"
        + language_instructions
        + "\n\n"
        "Answer the farmer's actual question directly. Never return "
        "moderation labels, internal safety messages, debug text, or "
        "phrases such as 'User Safety: safe'.\n\n"
        "For normal questions, provide a useful, complete answer with "
        "these parts when relevant:\n"
        "1. Possible explanations.\n"
        "2. Practical next steps the farmer can safely take.\n"
        "3. What additional information or observations could help.\n"
        "4. When to consult a qualified agricultural officer or "
        "local Krishi Bhavan.\n\n"
        "Do not pretend that you inspected a farm or identified a "
        "disease with certainty from a text description alone. "
        "For yellow spots on leaves, for example, explain that several "
        "causes are possible and suggest checking both sides of leaves, "
        "the spread of symptoms, and growing conditions.\n\n"
        "Never invent soil test results, weather data, measurements, "
        "sources, or observations. Do not recommend unverified pesticide "
        "products, doses, or chemical mixtures. For serious crop damage, "
        "recommend guidance from a qualified agricultural officer.\n\n"
        "Keep the answer focused, practical, and complete. Use plain "
        "text with simple headings or numbered steps when helpful. "
        "Do not stop in the middle of a sentence."
    )

    prompt = (
        system_prompt
        + "\n\nFarmer's question:\n"
        + question.strip()
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1000
        }
    }

    request = Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))

        candidates = result.get("candidates")

        if not isinstance(candidates, list) or not candidates:
            raise RuntimeError(
                "The AI model returned no answer. Please try again."
            )

        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])

        answer = "\n".join(
            part.get("text", "")
            for part in parts
            if isinstance(part, dict)
            and isinstance(part.get("text"), str)
        ).strip()

        if not answer:
            raise RuntimeError(
                "The AI returned an empty answer. Please try again."
            )

        normalized = answer.lower().strip()

        if normalized in (
            "user safety: safe",
            "safety: safe",
            "safe",
        ):
            raise RuntimeError(
                "The AI returned an unusable response. Please try again."
            )

        finish_reason = candidate.get("finishReason")

        if finish_reason == "MAX_TOKENS":
            if language == "ml":
                answer += (
                    "\n\nകുറിപ്പ്: ഉത്തരം പരിമിതമായതിനാൽ അപൂർണ്ണമായിരിക്കാം. "
                    "കൂടുതൽ വിശദാംശങ്ങൾ ആവശ്യമെങ്കിൽ ഒരു തുടർചോദ്യം ചോദിക്കാം."
                )
            else:
                answer += (
                    "\n\nNote: The response reached its output limit and "
                    "may be incomplete. Please ask a follow-up question "
                    "if you need more detail."
                )

        return answer

    except HTTPError as exc:
        if exc.code in (401, 403):
            raise RuntimeError(
                "Gemini rejected the API key. Check the Gemini API key "
                "configured in Q-FARM."
            ) from None

        if exc.code == 404:
            raise RuntimeError(
                f"Gemini model '{MODEL}' was not found or is unavailable."
            ) from None

        if exc.code == 429:
            raise RuntimeError(
                "Gemini rate limit reached. Try again later."
            ) from None

        if exc.code == 400:
            raise RuntimeError(
                "Gemini rejected the request. Please try again."
            ) from None

        raise RuntimeError(
            f"Gemini request failed with HTTP {exc.code}."
        ) from None

    except (URLError, TimeoutError):
        raise RuntimeError(
            "Could not reach Gemini. Check your internet connection."
        ) from None

    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise RuntimeError(
            "Gemini returned an unexpected response."
        ) from None