"""
Tool 3 — 관광지 검색 (search_attractions)
사용 API : 네이버 오픈 API — 블로그 검색 (/v1/search/blog.json)
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
NAVER_BLOG_URL      = "https://openapi.naver.com/v1/search/blog.json"


def search_attractions(city: str, category: str = "") -> dict:
    """
    네이버 블로그 검색으로 여행지의 관광지·명소 정보를 가져옵니다.

    Parameters
    ----------
    city     : str  지역명 (예: 제주도, 경주, 통영)
    category : str  관광 유형 (예: 해수욕장, 역사, 자연, 테마파크, 야경)

    Returns
    -------
    dict  관광지 목록 or 에러 메시지
    """
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return {"error": "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET이 .env에 설정되지 않았습니다."}

    query = f"{city} {category} 관광지 추천".strip()

    headers = {
        "X-Naver-Client-Id":     NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query":   query,
        "display": 5,
        "sort":    "sim",   # 정확도 순
    }

    try:
        resp = requests.get(NAVER_BLOG_URL, headers=headers,
                            params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return {"error": f"관광지 검색 API 요청 실패: {str(e)}"}

    items = data.get("items", [])
    if not items:
        return {
            "message": f"'{query}' 검색 결과가 없습니다.",
            "fallback": f"https://korean.visitkorea.or.kr 에서 '{city}' 검색을 추천합니다.",
        }

    attractions = []
    for item in items[:5]:
        desc = _strip_tags(item.get("description", ""))
        attractions.append({
            "제목":       _strip_tags(item.get("title", "")),
            "요약":       desc[:120] + "..." if len(desc) > 120 else desc,
            "블로그링크": item.get("link", ""),
            "작성일":     item.get("postdate", ""),
        })

    return {
        "검색어":   query,
        "결과수":   len(attractions),
        "관광지목록": attractions,
        "관광공사": f"https://korean.visitkorea.or.kr/kfes/search/searchMain.do?keyword={city}",
    }


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


# ── OpenAI Function Calling 스키마 ──────────────
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_attractions",
        "description": (
            "여행지의 주요 관광지, 명소, 액티비티 정보를 네이버 블로그 기반으로 검색합니다. "
            "카테고리(해수욕장, 역사, 자연, 야경 등)를 지정하면 더 구체적인 결과를 얻습니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "여행 목적지 (예: 제주도, 경주, 통영, 강릉)",
                },
                "category": {
                    "type": "string",
                    "description": "관광 유형 (예: 해수욕장, 역사유적, 자연경관, 테마파크, 야경). 생략 가능.",
                },
            },
            "required": ["city"],
        },
    },
}
