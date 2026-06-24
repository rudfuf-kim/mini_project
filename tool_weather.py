"""
Tool 1 — 날씨 조회 (get_weather)
사용 API : OpenWeatherMap Free Access API
엔드포인트: /data/2.5/weather (현재), /data/2.5/forecast (예보)
비용      : 완전 무료 (카드 등록 불필요, 월 100만 건)
발급처    : https://openweathermap.org/api

.env 예시
----------
OPENWEATHER_API_KEY=발급받은_날씨_키
OPENAI_API_KEY=발급받은_오픈AI_키
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

OWM_API_KEY = os.getenv("WEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5"

# ── 한글 도시명 → 영문 변환 매핑 ─────────────────────
# 검색은 영문 + ",KR" 로 보내야 OpenWeatherMap 이 정확히 찾습니다.
CITY_MAP = {
    # 특별시·광역시
    "서울": "Seoul", "부산": "Busan", "대구": "Daegu",
    "인천": "Incheon", "광주": "Gwangju", "대전": "Daejeon",
    "울산": "Ulsan", "세종": "Sejong",
    # 도청 소재지·주요 도시
    "수원": "Suwon", "성남": "Seongnam", "용인": "Yongin",
    "고양": "Goyang", "안양": "Anyang", "부천": "Bucheon",
    "춘천": "Chuncheon", "원주": "Wonju", "강릉": "Gangneung",
    "속초": "Sokcho", "청주": "Cheongju", "충주": "Chungju",
    "천안": "Cheonan", "아산": "Asan", "전주": "Jeonju",
    "군산": "Gunsan", "익산": "Iksan", "목포": "Mokpo",
    "여수": "Yeosu", "순천": "Suncheon", "포항": "Pohang",
    "경주": "Gyeongju", "구미": "Gumi", "안동": "Andong",
    "창원": "Changwon", "진주": "Jinju", "통영": "Tongyeong",
    "거제": "Geoje", "김해": "Gimhae", "양산": "Yangsan",
    # 관광지·제주·평창 등
    "제주": "Jeju", "제주도": "Jeju", "서귀포": "Seogwipo",
    "평창": "Pyeongchang", "가평": "Gapyeong", "남원": "Namwon",
    "보령": "Boryeong", "태안": "Taean", "단양": "Danyang",
}

WEATHER_EMOJI = {
    "Clear": "☀️", "Clouds": "⛅", "Rain": "🌧️",
    "Snow": "❄️", "Thunderstorm": "⛈️", "Drizzle": "🌦️",
    "Mist": "🌫️", "Fog": "🌁", "Haze": "🌫️",
}


def _to_english_city(city: str) -> str:
    """한글 도시명을 영문으로 변환. 매핑에 없으면 입력값을 그대로 사용."""
    key = city.strip().replace("특별시", "").replace("광역시", "") \
              .replace("시", "").replace("도", "")
    # 원본 → 정리한 키 순으로 매핑 조회, 둘 다 없으면 입력 그대로(영문 입력 대비)
    return CITY_MAP.get(city.strip()) or CITY_MAP.get(key) or city.strip()


def get_weather(city: str, days: int = 3) -> dict:
    """
    국내 여행지의 현재 날씨 및 예보를 조회합니다.

    Parameters
    ----------
    city : str  여행 목적지 (한글 or 영문)
    days : int  예보 기간 1~5일 (기본값 3)

    Returns
    -------
    dict  날씨 정보 or 에러 메시지
    """
    if not OWM_API_KEY:
        return {"error": "OPENWEATHER_API_KEY가 .env에 설정되지 않았습니다."}

    en_city = _to_english_city(city)

    # ── 현재 날씨 ──────────────────────────────────
    try:
        current_resp = requests.get(
            f"{BASE_URL}/weather",
            params={"q": f"{en_city},KR", "appid": OWM_API_KEY,
                    "units": "metric", "lang": "kr"},
            timeout=10,
        )
        if current_resp.status_code == 401:
            return {"error": "API 키가 거부되었습니다(401). 키 값/활성화 상태를 확인하세요."}
        if current_resp.status_code == 404:
            return {
                "error": f"'{city}'({en_city}) 도시 정보를 찾을 수 없습니다.",
                "available_cities": list(CITY_MAP.keys()),
            }
        current_resp.raise_for_status()
        curr = current_resp.json()
    except requests.RequestException as e:
        return {"error": f"날씨 API 요청 실패: {str(e)}"}

    weather_main = curr["weather"][0]["main"]
    emoji = WEATHER_EMOJI.get(weather_main, "🌡️")

    result = {
        "도시":     city,
        "현재기온":  f"{curr['main']['temp']:.1f}°C",
        "체감기온":  f"{curr['main']['feels_like']:.1f}°C",
        "날씨":     f"{emoji} {curr['weather'][0]['description']}",
        "습도":     f"{curr['main']['humidity']}%",
        "풍속":     f"{curr['wind']['speed']} m/s",
        "예보":     [],
        "옷차림추천": _recommend_clothes(curr['main']['temp']),
    }

    # ── 예보 (3시간 단위 → 일별 대표값 추출) ──────
    try:
        days = max(1, min(days, 5))
        forecast_resp = requests.get(
            f"{BASE_URL}/forecast",
            params={"q": f"{en_city},KR", "appid": OWM_API_KEY,
                    "units": "metric", "lang": "kr", "cnt": days * 8},
            timeout=10,
        )
        forecast_resp.raise_for_status()
        forecasts = forecast_resp.json().get("list", [])

        seen_dates = {}
        for item in forecasts:
            date = item["dt_txt"][:10]
            if date not in seen_dates:
                w = item["weather"][0]
                seen_dates[date] = {
                    "날짜":   date,
                    "날씨":   f"{WEATHER_EMOJI.get(w['main'], '🌡️')} {w['description']}",
                    "최고기온": f"{item['main']['temp_max']:.1f}°C",
                    "최저기온": f"{item['main']['temp_min']:.1f}°C",
                    "강수확률": f"{int(item.get('pop', 0) * 100)}%",
                }

        result["예보"] = list(seen_dates.values())[:days]

    except requests.RequestException:
        pass  # 예보 실패해도 현재 날씨는 반환

    return result


def _recommend_clothes(temp: float) -> str:
    if temp >= 28:
        return "민소매·반팔·반바지, 선크림 필수"
    elif temp >= 23:
        return "반팔·얇은 긴팔, 자외선 차단 권장"
    elif temp >= 17:
        return "얇은 가디건·청재킷, 레이어링 추천"
    elif temp >= 11:
        return "자켓·가디건·트렌치코트"
    elif temp >= 5:
        return "코트·히트텍·두꺼운 니트"
    else:
        return "패딩·두꺼운 코트·목도리·장갑"


# ── OpenAI Function Calling 스키마 ──────────────
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": (
            "국내 여행지의 현재 날씨와 날짜별 예보(기온, 날씨 상태, 강수 확률)를 조회합니다. "
            "여행지 날씨가 궁금하거나 여행 준비물을 추천할 때 사용합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "여행 목적지 도시명 (예: 제주, 부산, 강릉). 한글로 받아도 됩니다.",
                },
                "days": {
                    "type": "integer",
                    "description": "예보 기간 (1~5일, 기본값 3)",
                },
            },
            "required": ["city"],
        },
    },
}
