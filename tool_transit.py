"""
Tool 5 — 고속도로 교통정보 (get_highway_traffic / get_highway_fare)
사용 API : 한국도로공사 고속도로 공공데이터 포털 (data.ex.co.kr)
  - 실시간 소통 정보  : /openapi/trafficapilist/trafficSectionListM
  - 영업소간 통행요금  : /openapi/trafficapilist/getFare
발급처   : https://data.ex.co.kr
비용     : 완전 무료
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

EX_API_KEY = os.getenv("EX_API_KEY")

IC_CODE_MAP = {
    "서울": "1000", "부산": "5100", "대구": "3800",
    "광주": "5700", "대전": "2900", "인천": "1200",
    "수원": "1500", "강릉": "4200", "춘천": "4000",
    "전주": "5500", "여수": "5800", "청주": "2700",
    "천안": "2300", "울산": "5000", "경주": "4900",
    "포항": "5000", "통영": "5600", "속초": "4300",
}

CAR_TYPE_MAP = {"소형": "1", "중형": "2", "대형": "3", "특대형": "4", "경차": "5"}


def get_highway_traffic(start_city: str, end_city: str) -> dict:
    """출발지 ~ 도착지 고속도로 실시간 소통 상태 조회"""
    if not EX_API_KEY:
        return {"error": "EX_API_KEY가 .env에 설정되지 않았습니다."}

    if "제주" in (start_city, end_city):
        return {
            "notice":      "제주도는 고속도로가 없습니다.",
            "recommended": "항공편 이용: 김포/김해 공항 → 제주 공항 (약 1시간)",
        }

    start_code = IC_CODE_MAP.get(start_city)
    end_code   = IC_CODE_MAP.get(end_city)
    if not start_code or not end_code:
        return {
            "error":     f"'{start_city}' 또는 '{end_city}'의 영업소 코드를 찾을 수 없습니다.",
            "available": list(IC_CODE_MAP.keys()),
        }

    try:
        resp = requests.get(
            "https://data.ex.co.kr/openapi/trafficapilist/trafficSectionListM",
            params={"key": EX_API_KEY, "type": "json",
                    "startCode": start_code, "endCode": end_code},
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("list", [])
    except requests.RequestException as e:
        return {"error": f"소통 정보 API 요청 실패: {str(e)}"}

    if not items:
        return {"message": "해당 구간 실시간 소통 데이터가 없습니다."}

    return {
        "route":    f"{start_city} → {end_city}",
        "sections": [
            {
                "구간":     item.get("conzone_nmae", ""),
                "혼잡도":   item.get("traffic_statue", ""),
                "평균속도":  f"{item.get('max_speed', '-')} km/h",
                "소요시간":  f"{item.get('travel_time', '-')} 분",
            }
            for item in items[:5]
        ],
    }


def get_highway_fare(start_city: str, end_city: str, car_type: str = "소형") -> dict:
    """출발 영업소 ~ 도착 영업소 간 통행요금 조회"""
    if not EX_API_KEY:
        return {"error": "EX_API_KEY가 .env에 설정되지 않았습니다."}

    if "제주" in (start_city, end_city):
        return {"notice": "제주도는 고속도로 구간이 없어 통행료 조회가 불가합니다."}

    start_code = IC_CODE_MAP.get(start_city)
    end_code   = IC_CODE_MAP.get(end_city)
    if not start_code or not end_code:
        return {
            "error":     f"영업소 코드를 찾을 수 없습니다: {start_city}, {end_city}",
            "available": list(IC_CODE_MAP.keys()),
        }

    try:
        resp = requests.get(
            "https://data.ex.co.kr/openapi/trafficapilist/getFare",
            params={"key": EX_API_KEY, "type": "json",
                    "startCode": start_code, "endCode": end_code,
                    "vehicleType": CAR_TYPE_MAP.get(car_type, "1")},
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("list", [])
    except requests.RequestException as e:
        return {"error": f"통행요금 API 요청 실패: {str(e)}"}

    if not items:
        return {"message": "통행요금 정보가 없습니다."}

    item = items[0]
    return {
        "route":       f"{start_city} → {end_city}",
        "차종":        car_type,
        "정상요금":    f"{item.get('fare', '-')} 원",
        "하이패스요금": f"{item.get('discountFare', '-')} 원",
        "거리":        f"{item.get('distance', '-')} km",
        "예상소요시간": f"{item.get('travelTime', '-')} 분",
    }


# ── OpenAI Function Calling 스키마 2개 ──────────
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_highway_traffic",
            "description": (
                "출발지와 도착지 사이의 고속도로 실시간 소통 상태(혼잡도, 평균 속도, "
                "소요 시간)를 조회합니다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_city": {"type": "string", "description": "출발 도시명 (예: 서울)"},
                    "end_city":   {"type": "string", "description": "도착 도시명 (예: 부산)"},
                },
                "required": ["start_city", "end_city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_highway_fare",
            "description": "출발지에서 도착지까지의 고속도로 통행요금과 예상 소요 시간을 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_city": {"type": "string", "description": "출발 도시명"},
                    "end_city":   {"type": "string", "description": "도착 도시명"},
                    "car_type": {
                        "type": "string",
                        "enum": ["소형", "중형", "대형", "특대형", "경차"],
                        "description": "차종 (기본값: 소형)",
                    },
                },
                "required": ["start_city", "end_city"],
            },
        },
    },
]
