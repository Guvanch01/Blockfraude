"""
AI Filter — Güýçli Scam + Sexual Content Detector
Only xAI Grok (grok-4.3)
"""

import os
import json
import logging
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GROK_API_KEY = os.getenv("GROK_API_KEY")

PROMPT_TEMPLATE = """Sen Telegram grupalary üçin gaty berk moderatoryň. Habary seljer we zyýanlylygyny kesgit et.

HABAR: <message>{text}</message>

**BLOCK ET (is_harmful: true):**

**SCAM / MOŞENNIKÇILIK:**
- "pul gerek", "pul ber", "pul iber", "kart belgisi"
- "от 17 лет", "вакансия", "лёгкий заработок", "легкий заработок"
- Telefon nomer + pul/iş wada etmek (+7, +996, +993)
- "Информация у +7...", "собеседование", "принести подать", "обучим"
- "pul gerek" ýaly gysga we gaýtalanýan habarlar

**SEXUAL / EROTİK SPAM:**
- "qiziqarli video", "qiziqarli videolar", "profilimda", "profilimde"
- "kutib qolaman", "do'stlar", "do’star", "do'star"
- "qizlar", "gyzlar" + emoji (🌹, 🔥, 🍑, ❤️, 💋)
- Profilinde video/foto wada etmek
- Any sexual or seductive content

**BLOCK ETME (is_harmful: false):**
- Adaty söhbet, sorag, satuw, satyn almak, habarlaşma

**JOGAP diňe JSON formatda bolmaly, başga hiç zat ýazma:**
{{
  "is_harmful": true/false,
  "category": "scam" | "sexual" | "none",
  "reason": "gysga we aňsat düşünikli sebäp (iň köp 8 söz)",
  "confidence": 0.85
}}
"""

def _parse_result(raw: str) -> dict:
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        result = json.loads(raw)
        return {
            "is_harmful": bool(result.get("is_harmful", False)),
            "category": result.get("category", "none"),
            "reason": result.get("reason", "AI detected harmful content"),
            "confidence": float(result.get("confidence", 0.8))
        }
    except Exception as e:
        logger.error(f"JSON parse error: {e}")
        return {"is_harmful": False, "category": "none", "reason": "parse error", "confidence": 0.4}


class AIFilter:
    def __init__(self):
        # Quick keywords (çalt blok)
        self.quick_scam_keywords = [
            "pul gerek", "pul ber", "pul iber", "kart belgisi", "от 17 лет",
            "вакансия", "лёгкий заработок", "легкий заработок", "+7967", "+7 967"
        ]

        self.quick_sexual_keywords = [
            "qiziqarli video", "qiziqarli videolar", "profilimda", "profilimde",
            "kutib qolaman", "do'stlar", "do’star", "do'star", "qizlar", "gyzlar",
            "🌹", "🍑", "🔥", "💋", "🔞"
        ]

    def quick_check(self, text: str) -> dict | None:
        if not text:
            return None
        text_lower = text.lower()

        for kw in self.quick_sexual_keywords:
            if kw in text_lower:
                return {"is_harmful": True, "reason": "Sexual spam keyword", "category": "sexual", "confidence": 0.94}

        for kw in self.quick_scam_keywords:
            if kw in text_lower:
                return {"is_harmful": True, "reason": "Scam keyword", "category": "scam", "confidence": 0.93}

        return None

    async def analyze(self, text: str) -> dict:
        if len(text) < 5:
            return {"is_harmful": False, "reason": "", "confidence": 1.0}

        # 1. Çalt barlag
        quick = self.quick_check(text)
        if quick:
            return quick

        # 2. Esasy AI seljermesi (Grok)
        result = await self._xai_grok(text)
        if result:
            return result

        return {"is_harmful": False, "reason": "AI unavailable", "category": "none", "confidence": 0.4}

    async def _xai_grok(self, text: str) -> dict | None:
        if not GROK_API_KEY:
            logger.error("GROK_API_KEY .env faýlynda tapylmady!")
            return None

        prompt = PROMPT_TEMPLATE.format(text=text[:950])

        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROK_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "grok-4.3",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 350,
                        "temperature": 0.0
                    },
                    timeout=30
                )

                data = await resp.json()

                if resp.status != 200:
                    logger.error(f"xAI API Error: {resp.status} - {data}")
                    return None

                raw = data["choices"][0]["message"]["content"]
                result = _parse_result(raw)
                logger.info(f"🤖 Grok: {result}")
                return result

        except Exception as e:
            logger.error(f"xAI Grok error: {e}")
            return None