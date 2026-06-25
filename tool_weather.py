import os
import requests
from dotenv import load_dotenv

load_dotenv()

OWM_API_KEY = os.getenv("WEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5"
GEO_URL = "http://api.openweathermap.org/geo/1.0/direct" # Geocoding API

WEATHER_EMOJI = {
    "Clear": "☀️", "Clouds": "⛅", "Rain": "🌧️",
    "Snow": "❄️", "Thunderstorm": "⛈️", "Drizzle": "🌦️",
    "Mist": "🌫️", "Fog": "🌁", "Haze": "🌫️",
}

def get_weather(city: str, days: int = 3) -> dict:
    if not OWM_API_KEY:
        return {"error": "OPENWEATHER_API_KEY가 .env에 설정되지 않았습니다."}

    # 1. Geocoding API를 통해 좌표 획득 (가장 확실한 방법)
    try:
        # 도시, 국가코드(KR)로 검색, limit을 5로 설정하여 정확도 확보
        geo_resp = requests.get(
            GEO_URL,
            params={"q": f"{city}, KR", "limit": 5, "appid": OWM_API_KEY},
            timeout=10
        )
        geo_data = geo_resp.json()
        
        # 한국(KR) 지역인 것 중 첫 번째 항목 선택
        target = next((item for item in geo_data if item.get("country") == "KR"), None)
        
        if not target:
            return {"error": f"'{city}'라는 도시를 대한민국에서 찾을 수 없습니다."}
        
        lat = target["lat"]
        lon = target["lon"]
    except Exception as e:
        return {"error": f"도시 검색 실패: {str(e)}"}

    # 2. 공통 매개변수 설정
    common_params = {"lat": lat, "lon": lon, "appid": OWM_API_KEY, "units": "metric", "lang": "kr"}

    # 3. 현재 날씨 조회
    try:
        curr_resp = requests.get(f"{BASE_URL}/weather", params=common_params, timeout=10)
        curr_resp.raise_for_status()
        curr = curr_resp.json()
    except requests.RequestException as e:
        return {"error": f"현재 날씨 조회 실패: {str(e)}"}

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

    # 4. 예보 조회 (좌표 기반)
    try:
        forecast_params = common_params.copy()
        forecast_params["cnt"] = max(1, min(days, 5)) * 8
        
        forecast_resp = requests.get(f"{BASE_URL}/forecast", params=forecast_params, timeout=10)
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
    except:
        pass # 예보 실패 시 현재 날씨 정보만 반환

    return result

def _recommend_clothes(temp: float) -> str:
    if temp >= 28: return "민소매·반팔·반바지, 선크림 필수"
    elif temp >= 23: return "반팔·얇은 긴팔, 자외선 차단 권장"
    elif temp >= 17: return "얇은 가디건·청재킷, 레이어링 추천"
    elif temp >= 11: return "자켓·가디건·트렌치코트"
    elif temp >= 5: return "코트·히트텍·두꺼운 니트"
    else: return "패딩·두꺼운 코트·목도리·장갑"

# OpenAI Function Calling 스키마
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "국내 여행지의 현재 날씨와 날짜별 예보를 조회합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "여행 목적지 도시명"},
                "days": {"type": "integer", "description": "예보 기간 (1~5일)"},
            },
            "required": ["city"],
        },
    },
}
