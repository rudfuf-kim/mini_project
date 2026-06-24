"""
Tool 4 — 여행 일정 생성 (generate_itinerary)
사용 모델 : OpenAI GPT-4o mini
비용      : 소액 유료 (데모 수준 $1 미만)
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

STYLE_DESC = {
    "힐링":   "조용하고 여유로운 자연·카페 위주 일정",
    "액티브": "등산·서핑·레포츠 등 활동적인 일정",
    "문화":   "역사유적·박물관·전통시장 위주 일정",
    "미식":   "지역 특산 맛집·시장·음식 투어 위주 일정",
    "가족":   "어린이 동반 가족 친화적인 체험 위주 일정",
}

SYSTEM_PROMPT = """당신은 대한민국 국내 여행 전문 플래너입니다.
사용자의 목적지, 기간, 여행 스타일을 바탕으로 현실적이고 구체적인 국내 여행 일정을 만들어 주세요.

규칙:
- 실제 존재하는 장소와 명소만 추천하세요.
- 이동 동선을 고려해 가까운 곳끼리 묶어주세요.
- 오전/오후/저녁 시간대로 구분하여 작성하세요.
- 예상 비용(입장료, 식비 등)을 간략히 포함하세요.
- 제주도의 경우 렌터카 이동을 권장하세요.
- 비현실적인 일정(당일치기 제주 등)은 정중히 수정 제안하세요.
"""


def generate_itinerary(destination: str, duration: int, style: str = "힐링") -> dict:
    """
    LLM을 활용해 국내 맞춤 여행 일정을 생성합니다.

    Parameters
    ----------
    destination : str  여행 목적지 (예: 제주도, 부산, 경주)
    duration    : int  여행 기간 (일수, 1~7)
    style       : str  여행 스타일 (힐링/액티브/문화/미식/가족)

    Returns
    -------
    dict  생성된 일정 텍스트 or 에러 메시지
    """
    style_desc = STYLE_DESC.get(style, style)
    duration = max(1, min(duration, 7))

    user_prompt = (
        f"목적지: {destination}\n"
        f"기간: {duration}박 {duration + 1}일\n"
        f"여행 스타일: {style} ({style_desc})\n\n"
        f"위 조건에 맞는 상세 여행 일정을 Day별로 작성해 주세요."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=1200,
            temperature=0.7,
        )
        itinerary_text = response.choices[0].message.content

        return {
            "목적지":   destination,
            "기간":     f"{duration}박 {duration + 1}일",
            "스타일":   style,
            "일정":     itinerary_text,
        }

    except Exception as e:
        return {"error": f"일정 생성 실패: {str(e)}"}


# ── OpenAI Function Calling 스키마 ──────────────
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_itinerary",
        "description": (
            "목적지, 여행 기간, 여행 스타일을 입력받아 국내 맞춤 여행 일정을 생성합니다. "
            "오전·오후·저녁 시간대별로 구체적인 코스와 예상 비용을 포함합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "description": "여행 목적지 (예: 제주도, 부산, 경주, 강릉)",
                },
                "duration": {
                    "type": "integer",
                    "description": "여행 일수 (1~7일). 예: 2박 3일이면 2",
                },
                "style": {
                    "type": "string",
                    "enum": ["힐링", "액티브", "문화", "미식", "가족"],
                    "description": "여행 스타일 (기본값: 힐링)",
                },
            },
            "required": ["destination", "duration"],
        },
    },
}
