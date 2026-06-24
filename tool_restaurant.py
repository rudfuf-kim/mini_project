import os
import requests
import urllib.parse
import re
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
        return "오류: 네이버 API 키가 설정되지 않았습니다. .env 파일을 확인해 주세요."

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
            return f"'{query}'에 대한 검색 결과가 없습니다. 다른 음식 종류나 더 넓은 지역명으로 다시 시도해 주세요."

        # 4. 결과 문자열 포맷팅 (LLM이 읽기 좋고, Streamlit UI에 띄우기 좋은 형태)
        result_str = f"🍽 {location} '{category}' 추천 장소 TOP {len(items)}\n"
        result_str += "-" * 30 + "\n"
        
        for idx, item in enumerate(items, 1):
            title = remove_html_tags(item.get("title", "이름 없음"))
            item_category = item.get("category", "카테고리 없음").split(">")[-1] # 대분류>소분류 중 마지막 소분류만 추출
            address = item.get("roadAddress") or item.get("address", "주소 정보 없음")
            telephone = item.get("telephone", "전화번호 없음")
            
            # [발표 포인트 4: 지도 링크 동적 생성]
            # 네이버 API는 상세 지도 링크를 주지 않으므로, 지역명+가게이름을 URL 인코딩하여 네이버 지도 검색 링크를 직접 생성했습니다.
            encoded_title = urllib.parse.quote(f"{location} {title}")
            map_link = f"https://map.naver.com/v5/search/{encoded_title}"
            
            result_str += f"{idx}. {title} | {item_category}\n"
            result_str += f"   📍 주소: {address}\n"
            if telephone:
                result_str += f"   📞 전화: {telephone}\n"
            result_str += f"   🔗 지도: {map_link}\n\n"
            
        return result_str.strip()

    except requests.exceptions.RequestException as e:
        # 네트워크 관련 오류 처리
        return f"맛집 검색 중 네트워크 오류가 발생했습니다. (상세: {e})"
    except Exception as e:
        # 기타 예상치 못한 오류 처리
        return f"맛집 검색 중 알 수 없는 오류가 발생했습니다. (상세: {e})"

if __name__ == "__main__":
    # 이 스크립트를 단독 실행했을 때 동작하는 자체 테스트 코드 (발표 시연용으로 활용 가능)
    print("--- 🟢 맛집 검색 테스트 1: 제주 서귀포 해산물 ---")
    print(search_restaurants(location="제주 서귀포", category="해산물", limit=3))
    
    print("\n--- 🟢 맛집 검색 테스트 2: 강릉 오션뷰 카페 ---")
    print(search_restaurants(location="강릉", category="오션뷰 카페", limit=2))
