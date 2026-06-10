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

PROMPT_TEMPLATE = """Sen Telegram grupalary üçin iň ýokary derejeli, iň tejribeli we iň akylly AI Content Moderator. 
Seniň wezipeň: scam, moşennikçilik we seksual spam-lary maksimal takyklykda bloklamak, ýöne hakyky adamlara we hakyky iş gözleýänlere zyýan etme.

HABAR: <message>{text}</message>

### 🔴 BLOCK ET (is_harmful: true):

**SCAM / MOŞENNIKÇILIK (gaty giňişleýin):**
- Pul soramak we pul wadasy: "pul gerek", "pul ber", "pul iber", "kart belgisi", "gizlin kod", "sms kod"
- "от 17 лет", "вакансия", "лёгкий заработок", "легкий заработок", "принести подать", "собеседование", "обучим"
- Telefon nomer + pul, tiz girdeji ýa-da "garantiyaly" wadasy
- "detaly v lichku", "napishi v lichku" + pul ýa-da iş wadasy
- Gaýtalanýan gysga pul soraw habarlary
- "investisiya", "kripto", "forex", "100% garantiýa", "utup beryas", "könül pul"

**🔞 SEXUAL / EROTİK SPAM:**
- "qiziqarli video", "qiziqarli videolar", "profilimda", "profilimde", "kutib qolaman"
- "do'stlar", "do’star", "qizlar üçin", "gyzlar" + seduktiv emoji (🌹 🔥 🍑 💋 ❤️ 🔞)
- OnlyFans, intimate photo/video, ýalaňaç, seksual teklip
- Profilinde "qiziqarli" mazmuny wada etmek

### 🟢 BLOCK ETME (is_harmful: false):

- Hakyky kompaniýa ady, firma, market, restoran, şäherçi wezipe ilanlary
- Wezipe, talaplar, maaş, grafiki, iş ýeri anyk görkezilen bolsa
- Normal iş gözlemek: "Satyjy gerek", "Ofisiant gerek", "Driver gerek", "Kuryer gerek" we ş.m.
- Adamlar özleri iş gözleýän, kömek sorayan ýa-da maslahat sorayan bolsa
- Adaty söhbet, satuw, satyn almak, habar, ýaryş, duşuşyk

**IŇ MÖHÜM AKYL DÜZGÜNI (Step-by-step karar):**
1. Pul soralýarmy ýa-da tiz pul wada edilýärmi? → Scam
2. "от 17 лет" + pul ýa-da tiz girdeji barmy? → Scam
3. Kompaniýa/firma ady we wezipe anyk görkezilenmi? → Hakyky iş, blok etme
4. "qiziqarli video" ýa-da "profilimda" + seduktiv emoji barmy? → Sexual spam
5. Şübheli bolsa, ýöne anyk pul weziýeti ýok bolsa → "none" diý we geç

Jogap diňe JSON formatda, hiç zat goşma:
{{
  "is_harmful": true/false,
  "category": "scam" | "sexual" | "none",
  "reason": "gysga we anyk sebäp (iň köp 12 söz)",
  "confidence": 0.80-0.98
}}
"""

PROMPT_TEMPLATE = """You are an elite, highly experienced AI Content Moderator for Telegram groups.

Your job is to accurately detect and block scams, fraud, and sexual spam, while protecting legitimate users and real job postings.

MESSAGE: <message>{text}</message>

### 🔴 BLOCK (is_harmful: true):

**SCAM / FRAUD:**
- "pul gerek", "send money", "kart belgisi", "от 17 лет", "лёгкий заработок"
- Phone number + fast money promises
- "details in DM" + money or easy job offers
- Repeated short money requests

**SEXUAL SPAM:**
- "qiziqarli video", "profilimda", "kutib qolaman", "do'stlar"
- Seductive emojis (🌹🔥🍑💋) + profile promises
- OnlyFans, nude, intimate content offers

### 🟢 DO NOT BLOCK:
- Real company names and clear job descriptions
- Normal job postings (Seller needed, Driver needed, etc.)
- Regular conversations and help requests

Reply ONLY in JSON format:
{{
  "is_harmful": true/false,
  "category": "scam" | "sexual" | "none",
  "reason": "short and clear reason",
  "confidence": 0.85
}}
"""
PROMPT_TEMPLATE = """Ты элитный, высокопрофессиональный AI-модератор для Telegram групп.

Твоя задача — максимально точно блокировать мошенничество, скамы и сексуальный спам, но при этом не вредить реальным людям и настоящим объявлениям о работе.

СООБЩЕНИЕ: <message>{text}</message>

### 🔴 БЛОКИРОВАТЬ (is_harmful: true):

**СКАМ / МОШЕННИЧЕСТВО:**
- "pul gerek", "от 17 лет", "лёгкий заработок", "номер карты"
- Телефон + обещание быстрых денег
- "детали в личку" + деньги или лёгкая работа

**СЕКСУАЛЬНЫЙ СПАМ:**
- "qiziqarli video", "профиле видео", "кутиб коламан", "do'stlar"
- Сексуальные эмодзи + реклама профиля

### 🟢 НЕ БЛОКИРОВАТЬ:
- Реальные компании и чёткие вакансии
- Обычные объявления о работе
- Нормальные разговоры

Ответь ТОЛЬКО JSON:
{{
  "is_harmful": true/false,
  "category": "scam" | "sexual" | "none",
  "reason": "короткая причина",
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