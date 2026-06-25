"""
Tool 6 — 렌트카 & 편의시설 검색 (search_rentcar / search_facilities)
사용 API : 네이버 지역검색 API
엔드포인트: https://openapi.naver.com/v1/search/local.json
비용      : 완전 무료
발급처    : https://developers.naver.com
"""

import os
import re
import urllib.parse
import requests
from dotenv import load_dotenv

load_dotenv()


def _remove_html_tags(text: str) -> str:
    """네이버 API 응답의 <b> 태그 등 HTML 제거"""
    return re.sub(re.compile("<.*?>"), "", text)


def _naver_local_search(query: str, limit: int) -> list:
    """네이버 지역검색 API 공통 호출 함수"""
    client_id     = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")

    if not client_id or not client_secret:
        return []

    resp = requests.get(
        "https://openapi.naver.com/v1/search/local.json",
        headers={
            "X-Naver-Client-Id":     client_id,
            "X-Naver-Client-Secret": client_secret,
        },
        params={"query": query, "display": limit, "sort": "comment"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def _build_item(location: str, item: dict) -> dict:
    """API 응답 item → 공통 딕셔너리 변환"""
    title    = _remove_html_tags(item.get("title", "이름 없음"))
    category = item.get("category", "").split(">")[-1].strip()
    address  = item.get("roadAddress") or item.get("address", "주소 정보 없음")
    tel      = item.get("telephone", "전화번호 없음")
    map_link = f"https://map.naver.com/v5/search/{urllib.parse.quote(f'{location} {title}')}"
    return {
        "이름":     title,
        "카테고리": category,
        "주소":     address,
        "전화번호": tel,
        "지도링크": map_link,
    }


# ── Tool 1: 렌트카 검색 ───────────────────────────
def search_rentcar(location: str, limit: int = 5) -> dict:
    """
    여행지 주변 렌트카 업체를 네이버 지역검색으로 조회합니다.

    Parameters
    ----------
    location : str  여행지 (예: 제주도, 부산)
    limit    : int  결과 수 (기본값 5)

    Returns
    -------
    dict  렌트카 업체 목록 or 에러
    """
    if not os.getenv("NAVER_CLIENT_ID"):
        return {"error": "네이버 API 키가 설정되지 않았습니다."}

    query = f"{location} 렌트카"
    try:
        items = _naver_local_search(query, limit)
    except requests.RequestException as e:
        return {"error": f"네트워크 오류: {e}"}

    if not items:
        return {"message": f"'{query}' 검색 결과가 없습니다."}

    return {
        "검색어":       query,
        "결과수":       len(items),
        "렌트카업체목록": [_build_item(location, item) for item in items],
    }


# ── Tool 2: 편의시설 검색 ─────────────────────────
FACILITY_KEYWORDS = {
    "편의점":  "편의점",
    "마트":    "마트 슈퍼마켓",
    "병원":    "병원 의원",
    "약국":    "약국",
    "주유소":  "주유소",
    "은행":    "은행 ATM",
    "카페":    "카페 커피",
    "숙박":    "호텔 펜션 게스트하우스",
}

def search_facilities(location: str, facility_type: str = "편의점", limit: int = 5) -> dict:
    """
    여행지 주변 편의시설을 네이버 지역검색으로 조회합니다.

    Parameters
    ----------
    location      : str  여행지 (예: 제주도, 강릉)
    facility_type : str  시설 종류 — 편의점 / 마트 / 병원 / 약국 /
                         주유소 / 은행 / 카페 / 숙박 (기본값: 편의점)
    limit         : int  결과 수 (기본값 5)

    Returns
    -------
    dict  편의시설 목록 or 에러
    """
    if not os.getenv("NAVER_CLIENT_ID"):
        return {"error": "네이버 API 키가 설정되지 않았습니다."}

    keyword = FACILITY_KEYWORDS.get(facility_type, facility_type)
    query   = f"{location} {keyword}"

    try:
        items = _naver_local_search(query, limit)
    except requests.RequestException as e:
        return {"error": f"네트워크 오류: {e}"}

    if not items:
        return {"message": f"'{query}' 검색 결과가 없습니다."}

    return {
        "검색어":       query,
        "시설종류":     facility_type,
        "결과수":       len(items),
        "편의시설목록": [_build_item(location, item) for item in items],
    }


# ── OpenAI Function Calling 스키마 2개 ──────────
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_rentcar",
            "description": (
                "여행지 주변 렌트카 업체를 검색합니다. "
                "업체명, 주소, 전화번호, 네이버 지도 링크를 제공합니다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "렌트카를 찾을 여행지 (예: 제주도, 부산, 강릉)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "결과 수 (기본값 5)",
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_facilities",
            "description": (
                "여행지 주변 편의시설(편의점, 마트, 병원, 약국, 주유소, 은행, 카페, 숙박)을 검색합니다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "편의시설을 찾을 여행지 (예: 제주도, 경주)",
                    },
                    "facility_type": {
                        "type": "string",
                        "enum": ["편의점", "마트", "병원", "약국", "주유소", "은행", "카페", "숙박"],
                        "description": "찾을 시설 종류 (기본값: 편의점)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "결과 수 (기본값 5)",
                    },
                },
                "required": ["location"],
            },
        },
    },
]
