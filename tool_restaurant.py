"""
Tool 2 — 맛집 검색 (search_restaurants)
사용 API : 네이버 오픈 API — 지역 검색 (/v1/search/local.json)
비용     : 완전 무료 (일 25,000건)
발급처   : https://developers.naver.com
"""

import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

NAVER_CLIENT_ID     = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
NAVER_LOCAL_URL     = "https://openapi.naver.com/v1/search/local.json"


def search_restaurants(location: str, category: str = "", limit: int = 5) -> dict:
    """
    네이버 지역 검색 API로 여행지 맛집·카페를 검색합니다.

    Parameters
    ----------
    location : str  지역명 (예: 제주 서귀포, 부산 해운대)
    category : str  음식 종류 (예: 해산물, 한식, 카페, 흑돼지)
    limit    : int  결과 수 (기본값 5, 최대 5)

    Returns
    -------
    dict  맛집 목록 or 에러 메시지
    """
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return {"error": "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET이 .env에 설정되지 않았습니다."}

    query = f"{location} {category} 맛집".strip()
    limit = max(1, min(limit, 5))

    headers = {
        "X-Naver-Client-Id":     NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query":   query,
        "display": limit,
        "sort":    "comment",   # 리뷰 많은 순
    }

    try:
        resp = requests.get(NAVER_LOCAL_URL, headers=headers,
                            params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return {"error": f"맛집 검색 API 요청 실패: {str(e)}"}

    items = data.get("items", [])
    if not items:
        return {
            "message": f"'{query}' 검색 결과가 없습니다. 키워드를 바꿔 보세요.",
            "suggestion": f"예: '{location} 식당' 또는 '{location} 음식점'",
        }

    restaurants = []
    for item in items:
        restaurants.append({
            "이름":       _strip_tags(item.get("title", "")),
            "카테고리":   item.get("category", ""),
            "주소":       item.get("roadAddress") or item.get("address", ""),
            "전화번호":   item.get("telephone", "정보 없음"),
            "네이버지도": item.get("link", ""),
        })

    return {
        "검색어":    query,
        "결과수":    len(restaurants),
        "맛집목록":  restaurants,
    }


def _strip_tags(text: str) -> str:
    """HTML 태그 제거"""
    return re.sub(r"<[^>]+>", "", text)


# ── OpenAI Function Calling 스키마 ──────────────
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_restaurants",
        "description": (
            "여행지 근처 맛집, 식당, 카페를 네이버 기반으로 검색합니다. "
            "음식 종류(한식, 해산물, 카페 등)를 함께 지정하면 더 정확한 결과를 얻습니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "검색할 지역명 (예: 제주 서귀포, 강릉 경포대)",
                },
                "category": {
                    "type": "string",
                    "description": "음식 종류 (예: 해산물, 한식, 카페, 흑돼지, 막국수). 생략 가능.",
                },
                "limit": {
                    "type": "integer",
                    "description": "결과 수 (1~5, 기본값 5)",
                },
            },
            "required": ["location"],
        },
    },
}
