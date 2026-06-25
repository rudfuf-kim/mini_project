"""
Tool 5 — 교통수단별 경로 탐색 (get_transit_routes)
사용 API : Tmap API (SK텔레콤)
  - 자동차 경로   : /tmap/routes
  - 대중교통 경로  : /tmap/routes/transit
발급처   : https://openapi.sk.com
비용     : 무료 (월 호출량 제한 있음)

[변경 이력]
기존 한국도로공사 API(data.ex.co.kr) 기반 고속도로 전용 조회에서
Tmap API 기반 자동차/대중교통 경로 비교로 전면 교체.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TMAP_API_KEY = os.getenv("EX_API_KEY")   # .env 변수명 기존 유지

TMAP_BASE = "https://apis.openapi.sk.com/tmap"

# 주요 도시 좌표 (위도, 경도)
CITY_COORDS = {
    "서울":  (37.5665, 126.9780),
    "부산":  (35.1796, 129.0756),
    "대구":  (35.8714, 128.6014),
    "광주":  (35.1595, 126.8526),
    "대전":  (36.3504, 127.3845),
    "인천":  (37.4563, 126.7052),
    "수원":  (37.2636, 127.0286),
    "강릉":  (37.7519, 128.8761),
    "춘천":  (37.8813, 127.7298),
    "전주":  (35.8242, 127.1480),
    "여수":  (34.7604, 127.6622),
    "청주":  (36.6424, 127.4890),
    "천안":  (36.8151, 127.1139),
    "울산":  (35.5384, 129.3114),
    "경주":  (35.8562, 129.2247),
    "포항":  (36.0190, 129.3435),
    "통영":  (34.8544, 128.4335),
    "속초":  (38.2070, 128.5918),
    "제주":  (33.4996, 126.5312),
    "서귀포": (33.2541, 126.5600),
}


def _get_coords(city: str):
    """도시명 → (위도, 경도) 반환. 없으면 None."""
    return CITY_COORDS.get(city)


def _car_route(start_lat, start_lon, end_lat, end_lon) -> dict:
    """Tmap 자동차 경로 탐색"""
    try:
        resp = requests.post(
            f"{TMAP_BASE}/routes",
            headers={
                "appKey": TMAP_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "startX": str(start_lon),
                "startY": str(start_lat),
                "endX":   str(end_lon),
                "endY":   str(end_lat),
                "reqCoordType":  "WGS84GEO",
                "resCoordType":  "WGS84GEO",
                "searchOption":  "0",   # 0=최적, 1=최단거리, 2=무료도로
                "trafficInfo":   "Y",
            },
            timeout=10,
        )
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if not features:
            return {"error": "자동차 경로 데이터를 받지 못했습니다."}

        props = features[0].get("properties", {})
        total_dist_km = round(props.get("totalDistance", 0) / 1000, 1)
        total_time_min = round(props.get("totalTime", 0) / 60)
        fare = props.get("totalFare", 0)           # 통행요금(원)
        taxi_fare = props.get("taxiFare", 0)       # 택시 예상요금(원)

        return {
            "수단":        "🚗 자동차",
            "거리":        f"{total_dist_km} km",
            "소요시간":    f"{total_time_min}분",
            "통행요금":    f"{fare:,}원" if fare else "없음 (무료도로)",
            "택시예상요금": f"{taxi_fare:,}원" if taxi_fare else "-",
        }
    except requests.RequestException as e:
        return {"error": f"자동차 경로 API 오류: {str(e)}"}


def _transit_route(start_lat, start_lon, end_lat, end_lon) -> dict:
    """Tmap 대중교통 경로 탐색"""
    try:
        resp = requests.get(
            f"{TMAP_BASE}/routes/transit",
            headers={"appKey": TMAP_API_KEY},
            params={
                "startX":      str(start_lon),
                "startY":      str(start_lat),
                "endX":        str(end_lon),
                "endY":        str(end_lat),
                "count":       1,
                "searchDttm":  "",   # 빈 값 = 현재 시각 기준
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        # 대중교통 응답 파싱
        metaData = data.get("metaData", {})
        plan = metaData.get("plan", {})
        itineraries = plan.get("itineraries", [])

        if not itineraries:
            return {"error": "대중교통 경로 데이터를 받지 못했습니다."}

        best = itineraries[0]
        duration_min = round(best.get("duration", 0) / 60)
        fare_won = best.get("fare", {}).get("regular", {}).get("totalFare", 0)
        transfer_count = best.get("transferCount", 0)

        # 이용 수단 요약
        legs = best.get("legs", [])
        modes = []
        for leg in legs:
            mode = leg.get("mode", "")
            if mode == "WALK":
                modes.append("🚶도보")
            elif mode == "BUS":
                modes.append(f"🚌버스({leg.get('route', '')})")
            elif mode in ("SUBWAY", "RAIL"):
                modes.append(f"🚇지하철/기차({leg.get('route', '')})")
            elif mode == "EXPRESSBUS":
                modes.append(f"🚍고속버스({leg.get('route', '')})")
        route_summary = " → ".join(modes) if modes else "-"

        return {
            "수단":        "🚌 대중교통",
            "소요시간":    f"{duration_min}분",
            "환승횟수":    f"{transfer_count}회",
            "요금":        f"{fare_won:,}원" if fare_won else "정보 없음",
            "이용수단요약": route_summary,
        }
    except requests.RequestException as e:
        return {"error": f"대중교통 경로 API 오류: {str(e)}"}


# ── 메인 함수 ─────────────────────────────────
def get_transit_routes(start_city: str, end_city: str) -> dict:
    """
    출발지와 도착지 간 자동차·대중교통 경로를 Tmap API로 탐색하고
    소요시간·요금·이동수단을 비교해서 반환합니다.

    Parameters
    ----------
    start_city : str  출발 도시명 (예: 서울, 부산)
    end_city   : str  도착 도시명 (예: 강릉, 경주)

    Returns
    -------
    dict  자동차/대중교통 비교 결과 or 에러
    """
    if not TMAP_API_KEY:
        return {"error": "EX_API_KEY(Tmap)가 .env에 설정되지 않았습니다."}

    # 제주도 안내
    if "제주" in start_city or "제주" in end_city:
        jeju_note = (
            "제주도는 육로 연결이 없습니다.\n"
            "✈️ 항공: 김포/김해/인천 → 제주공항 (약 1시간)\n"
            "🚢 배편: 목포/완도/녹동 → 제주항 (약 5~12시간)"
        )
        return {"안내": jeju_note}

    start_coords = _get_coords(start_city)
    end_coords   = _get_coords(end_city)

    if not start_coords:
        return {"error": f"'{start_city}'의 좌표 정보가 없습니다. 지원 도시: {', '.join(CITY_COORDS.keys())}"}
    if not end_coords:
        return {"error": f"'{end_city}'의 좌표 정보가 없습니다. 지원 도시: {', '.join(CITY_COORDS.keys())}"}

    s_lat, s_lon = start_coords
    e_lat, e_lon = end_coords

    car     = _car_route(s_lat, s_lon, e_lat, e_lon)
    transit = _transit_route(s_lat, s_lon, e_lat, e_lon)

    return {
        "출발지":   start_city,
        "도착지":   end_city,
        "자동차":   car,
        "대중교통": transit,
    }


# ── OpenAI Function Calling 스키마 ──────────────
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_transit_routes",
            "description": (
                "출발지에서 도착지까지 자동차와 대중교통 경로를 각각 탐색하여 "
                "소요시간, 요금, 이동수단을 비교합니다. "
                "예: '서울에서 강릉 가는 방법', '부산까지 얼마나 걸려?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_city": {
                        "type": "string",
                        "description": "출발 도시명 (예: 서울, 대전)",
                    },
                    "end_city": {
                        "type": "string",
                        "description": "도착 도시명 (예: 부산, 강릉, 경주)",
                    },
                },
                "required": ["start_city", "end_city"],
            },
        },
    },
]
