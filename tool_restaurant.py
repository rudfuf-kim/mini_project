import os
import requests
import urllib.parse
import re
import logging
from functools import lru_cache
from dotenv import load_dotenv

# 1. 환경 변수 로드 (보안 유지)
# API 키가 코드에 하드코딩되는 것을 방지하기 위해 dotenv 라이브러리를 사용했습니다.
load_dotenv()

def remove_html_tags(text: str) -> str:
    """
    [발표 포인트 1: 데이터 정제(전처리)]
    네이버 지역 검색 API는 검색어와 일치하는 키워드를 <b> 태그로 감싸서 반환합니다.
    LLM과 사용자에게 깔끔한 텍스트를 제공하기 위해 정규식을 사용하여 HTML 태그를 제거하는 헬퍼 함수를 구현했습니다.
    """
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

@lru_cache(maxsize=100)
def search_restaurants(location: str, category: str = "맛집", limit: int = 5) -> str:
    """
    네이버 지역 검색 API를 사용하여 여행지 주변의 맛집/카페를 검색합니다.
    
    [발표 포인트 2: LLM Tool Calling을 위한 상세한 Docstring]
    이 함수는 LLM(GPT-4o mini)이 직접 읽고 실행할 Tool입니다.
    따라서 Args와 Returns를 명확히 정의하여 LLM이 파라미터를 정확히 넘길 수 있도록 유도했습니다.
    
    Args:
        location (str): 검색할 지역명 (예: "제주 서귀포", "강릉")
        category (str): 음식 종류 또는 키워드 (예: "해산물", "카페", "한식"). 기본값은 "맛집"
        limit (int): 반환할 결과의 개수. 기본값은 5
        
    Returns:
        str: 포맷팅된 맛집 검색 결과 문자열
    """
    
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")
    
    # API 키 누락 예외 처리
    if not client_id or not client_secret:
        return {"error": "네이버 API 키가 설정되지 않았습니다."}

    # 2. 검색 쿼리 동적 생성 로직
    # 사용자가 '해산물'만 입력해도 자연스럽게 '제주 서귀포 해산물 맛집'으로 검색되도록 보정합니다.
    if "맛집" not in category and "카페" not in category:
        query = f"{location} {category} 맛집"
    else:
        query = f"{location} {category}"

    url = "https://openapi.naver.com/v1/search/local.json"
    
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    
    params = {
        "query": query,
        "display": limit,
        "sort": "comment" # [발표 포인트 3: 정렬 기준] 리뷰(코멘트) 순 정렬을 통해 실제 인기 있는 장소 우선 노출
    }

    try:
        # 3. API 요청 및 응답 처리
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status() # HTTP 200번대 응답이 아닐 경우 예외 발생
        data = response.json()
        
        items = data.get("items", [])
        
        # PRD 예외 처리 요구사항 반영: 검색 결과가 없을 때의 가이드라인 제공
        if not items:
            return {"message": f"'{query}' 검색 결과가 없습니다. 다른 키워드로 시도해 주세요."}

        # 4. 결과 문자열 포맷팅 (LLM이 읽기 좋고, Streamlit UI에 띄우기 좋은 형태)
        restaurants = []

        for item in items:
            title = remove_html_tags(item.get("title", "이름 없음"))
            item_category = item.get("category", "카테고리 없음").split(">")[-1]
            address = item.get("roadAddress") or item.get("address", "주소 정보 없음")
            telephone = item.get("telephone", "전화번호 없음")
            encoded_title = urllib.parse.quote(f"{location} {title}")
            map_link = f"https://map.naver.com/v5/search/{encoded_title}"
        
            restaurants.append({
                "이름":       title,
                "카테고리":   item_category,
                "주소":       address,
                "전화번호":   telephone,
                "지도링크":   map_link,
            })
        
        return {
            "검색어":   query,
            "결과수":   len(restaurants),
            "맛집목록": restaurants,
        }

    except requests.exceptions.RequestException as e:
        # 네트워크 관련 오류 처리
        return {"error": f"네트워크 오류: {e}"}
    except Exception as e:
        # 기타 예상치 못한 오류 처리
        return {"error": f"알 수 없는 오류: {e}"}

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
                    "description": "음식 종류 (예: 해산물, 한식, 카페, 흑돼지). 생략 가능.",
                },
                "limit": {
                    "type": "integer",
                    "description": "결과 수 (기본값 5)",
                },
            },
            "required": ["location"],
        },
    },
}
