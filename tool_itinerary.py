"""
Tool 4 — 여행 일정 생성 (generate_itinerary)
사용 모델 : OpenAI GPT-4o mini
비용      : 소액 유료 (데모 수준 $1 미만)

[변경 사항]
이 함수는 더 이상 다른 tool을 직접 호출하지 않습니다.
대신 이미 검색된 관광지(attractions_data), 맛집(restaurants_data),
날씨(weather_data), 교통(transit_data) 정보를 파라미터로 전달받아서
그 데이터를 바탕으로 일정을 생성합니다.

실제 검색(tool 호출)과 중간 결과 출력은 app.py에서 단계별로 진행합니다.
"""

import os
from typing import Optional

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
아래 제공되는 [실제 데이터]를 최대한 활용해서 현실적이고 구체적인 국내 여행 일정을 만들어 주세요.

규칙:
- [실제 데이터]에 있는 관광지, 맛집, 날씨, 교통 정보를 일정에 적극 반영하세요.
  (예: 비 예보가 있으면 실내 관광지 위주로 조정, 제공된 맛집/관광지 이름과 주소를 실제로 일정에 배치)
- [실제 데이터]에 없는 내용이 필요하면, 알고 있는 실제 장소로 보완하되 지어내지 마세요.
- 이동 동선을 고려해 가까운 곳끼리 묶어주세요. (관광지/맛집의 주소를 참고하세요)
- 오전/오후/저녁 시간대로 구분하여 작성하세요.
- 예상 비용(입장료, 식비 등)을 간략히 포함하세요.
- 제주도의 경우 렌터카 이동을 권장하세요.
- 비현실적인 일정(당일치기 제주 등)은 정중히 수정 제안하세요.
- 교통 정보가 없다면 일정에서 이동 수단을 언급하지 말고, 다른 정보만으로 일정을 구성하세요.
"""


def _summarize_weather(weather: Optional[dict]) -> str:
    if not weather or weather.get("error"):
        return "- 날씨 정보: 없음 (참고 없이 진행)"
    lines = [f"- 현재 날씨: {weather.get('날씨', '-')}, {weather.get('현재기온', '-')}"]
    forecast = weather.get("예보", [])
    if forecast:
        lines.append("- 일별 예보:")
        for f in forecast:
            lines.append(
                f"  · {f.get('날짜')}: {f.get('날씨')} "
                f"(최고 {f.get('최고기온')} / 최저 {f.get('최저기온')}, 강수확률 {f.get('강수확률')})"
            )
    if weather.get("옷차림추천"):
        lines.append(f"- 옷차림 추천: {weather['옷차림추천']}")
    return "\n".join(lines)


def _summarize_restaurants(restaurants: Optional[dict]) -> str:
    if not restaurants or not restaurants.get("맛집목록"):
        return "- 맛집 정보: 없음 (참고 없이 진행)"
    lines = ["- 추천 맛집 목록:"]
    for r in restaurants["맛집목록"]:
        lines.append(f"  · {r.get('이름')} ({r.get('카테고리')}) - {r.get('주소')}")
    return "\n".join(lines)


def _summarize_attractions(attractions: Optional[dict]) -> str:
    if not attractions or not attractions.get("results"):
        return "- 관광지 정보: 없음 (참고 없이 진행)"
    lines = ["- 추천 관광지 목록:"]
    for a in attractions["results"]:
        lines.append(
            f"  · {a.get('name')} ({a.get('category')}) - "
            f"주소: {a.get('address')}, 운영시간: {a.get('opening_hours')}, 입장료: {a.get('admission_fee')}"
        )
    return "\n".join(lines)


def _summarize_transit(transit: Optional[dict], origin: Optional[str]) -> str:
    if not origin:
        return "- 교통 정보: 출발지가 입력되지 않아 조회하지 않았습니다."
    if not transit or transit.get("error"):
        return "- 교통 정보: 없음 (참고 없이 진행)"
    if transit.get("notice"):
        return f"- 교통 정보: {transit['notice']} / {transit.get('recommended', '')}"
    sections = transit.get("sections")
    if sections:
        lines = [f"- {transit.get('route', '')} 실시간 소통 정보:"]
        for s in sections:
            lines.append(f"  · {s.get('구간')}: 혼잡도 {s.get('혼잡도')}, 평균속도 {s.get('평균속도')}")
        return "\n".join(lines)
    return "- 교통 정보: 데이터 없음"


def generate_itinerary(
    destination: str,
    duration: int,
    style: str = "힐링",
    origin: Optional[str] = None,
    attractions_data: Optional[dict] = None,
    restaurants_data: Optional[dict] = None,
    weather_data: Optional[dict] = None,
    transit_data: Optional[dict] = None,
) -> dict:
    """
    이미 검색된 관광지·맛집·날씨·교통 데이터를 바탕으로 국내 맞춤 여행 일정을 생성합니다.

    Parameters
    ----------
    destination      : str   여행 목적지 (예: 제주도, 부산, 경주)
    duration          : int   여행 기간 (일수, 1~7)
    style             : str   여행 스타일 (힐링/액티브/문화/미식/가족)
    origin            : str, optional  출발지 (교통 정보 표시용)
    attractions_data  : dict, optional  search_attractions()의 반환값
    restaurants_data  : dict, optional  search_restaurants()의 반환값
    weather_data      : dict, optional  get_weather()의 반환값
    transit_data      : dict, optional  get_highway_traffic()의 반환값

    Returns
    -------
    dict  생성된 일정 텍스트 or 에러 메시지
    """
    style_desc = STYLE_DESC.get(style, style)
    duration = max(1, min(duration, 7))

    data_summary = "\n\n".join([
        "[실제 데이터]",
        _summarize_attractions(attractions_data),
        _summarize_restaurants(restaurants_data),
        _summarize_weather(weather_data),
        _summarize_transit(transit_data, origin),
    ])

    user_prompt = (
        f"목적지: {destination}\n"
        f"기간: {duration}박 {duration + 1}일\n"
        f"여행 스타일: {style} ({style_desc})\n"
        f"출발지: {origin or '미입력'}\n\n"
        f"{data_summary}\n\n"
        f"위 조건과 실제 데이터를 반영해 상세 여행 일정을 Day별로 작성해 주세요."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=1500,
            temperature=0.7,
        )
        itinerary_text = response.choices[0].message.content

        result = {
            "목적지":   destination,
            "기간":     f"{duration}박 {duration + 1}일",
            "스타일":   style,
            "일정":     itinerary_text,
        }

        if not origin:
            result["안내"] = (
                "출발지가 입력되지 않아 교통 정보는 이번 일정에 포함되지 않았습니다. "
                "출발지를 알려주시면 교통 정보를 추가해 드릴 수 있습니다."
            )

        return result

    except Exception as e:
        return {"error": f"일정 생성 실패: {str(e)}"}


# ── OpenAI Function Calling 스키마 ──────────────
# 참고: attractions_data/restaurants_data/weather_data/transit_data는
# app.py에서 내부적으로 채워주는 값이라 LLM이 직접 채울 필요가 없으므로
# 스키마의 parameters에는 포함하지 않습니다 (LLM에게는 노출 안 함).
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_itinerary",
        "description": (
            "목적지, 여행 기간, 여행 스타일을 입력받아 국내 맞춤 여행 일정을 생성합니다. "
            "호출되면 사전에 관광지·맛집·날씨·교통 정보가 단계적으로 조회된 뒤 "
            "그 데이터를 반영한 일정이 만들어집니다. "
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
                "origin": {
                    "type": "string",
                    "description": (
                        "출발지 (예: 서울, 부산). 교통 정보를 일정에 포함하려면 필요합니다. "
                        "사용자가 출발지를 말하지 않았다면 생략하세요."
                    ),
                },
            },
            "required": ["destination", "duration"],
        },
    },
}
