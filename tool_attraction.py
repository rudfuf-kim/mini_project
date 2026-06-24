"""
TravelMate KR - 개인화 관광지 추천 Tool + 한국관광공사 TourAPI 상세조회 포함 버전
파일명 예시: travelmate/tools/attraction_tool.py

팀장님 통합용 핵심 함수:
    recommend_travel_place(...)
    search_attractions(...)  # recommend_travel_place의 alias

필요 환경 변수:
    NAVER_CLIENT_ID
    NAVER_CLIENT_SECRET
    TOUR_API_KEY  # 선택이지만, 상세조회까지 쓰려면 필요
"""

from __future__ import annotations

import os
import re
import html
import json
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()


# =========================
# 1. 환경 변수
# =========================

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

# 한국관광공사 TourAPI 서비스키
# data.go.kr에서 받은 Decoding 키 사용 권장
TOUR_API_KEY = os.getenv("TOUR_API_KEY")

NAVER_LOCAL_URL = "https://openapi.naver.com/v1/search/local.json"
NAVER_BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"

# 2025년 이후 국문 관광정보 서비스 URL은 KorService2 사용
TOUR_API_BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
TOUR_API_SEARCH_KEYWORD_URL = f"{TOUR_API_BASE_URL}/searchKeyword2"
TOUR_API_DETAIL_COMMON_URL = f"{TOUR_API_BASE_URL}/detailCommon2"
TOUR_API_DETAIL_INTRO_URL = f"{TOUR_API_BASE_URL}/detailIntro2"


# =========================
# 2. 공통 유틸 함수
# =========================

def _require_naver_keys() -> None:
    """네이버 API 키가 없으면 명확한 오류를 발생시킨다."""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise EnvironmentError(
            "NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET이 설정되지 않았습니다. "
            ".env 파일을 확인하세요."
        )


def _naver_headers() -> Dict[str, str]:
    return {
        "X-Naver-Client-Id": NAVER_CLIENT_ID or "",
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET or "",
    }


def clean_html(text: Optional[str]) -> str:
    """네이버/TourAPI 응답의 HTML 태그와 엔티티를 제거한다."""
    if not text:
        return ""
    text = html.unescape(str(text))
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def safe_get(
    url: str,
    *,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: int = 7,
) -> Optional[dict]:
    """API 호출 실패 시 None을 반환하여 Tool 전체가 죽지 않도록 처리한다."""
    try:
        res = requests.get(url, headers=headers, params=params, timeout=timeout)
        res.raise_for_status()
        return res.json()
    except Exception:
        return None


def get_age_group(age: Optional[int]) -> str:
    if age is None:
        return "연령 미상"
    if age < 20:
        return "10대"
    if age < 30:
        return "20대"
    if age < 40:
        return "30대"
    if age < 50:
        return "40대"
    if age < 60:
        return "50대"
    return "60대 이상"


def build_map_links(destination: str, place_name: str) -> Dict[str, str]:
    """네이버지도와 카카오맵 검색 링크 생성."""
    query = f"{destination} {place_name}".strip()
    encoded = quote(query)
    return {
        "naver_map_url": f"https://map.naver.com/v5/search/{encoded}",
        "kakao_map_url": f"https://map.kakao.com/link/search/{encoded}",
    }


def build_visitkorea_fallback_link(place_name: str) -> str:
    """한국관광공사 페이지 검색 링크 생성."""
    return f"https://korean.visitkorea.or.kr/search/search_list.do?keyword={quote(place_name)}"


def _extract_items_from_tour_response(data: Optional[dict]) -> List[Dict[str, Any]]:
    """
    TourAPI 응답에서 item 리스트만 안전하게 추출.
    응답 구조가 item=dict 또는 item=list 둘 다 가능해서 보정한다.
    """
    if not data:
        return []

    try:
        body = data.get("response", {}).get("body", {})
        items = body.get("items", {})
        if not items:
            return []
        item = items.get("item", [])
        if isinstance(item, dict):
            return [item]
        if isinstance(item, list):
            return item
        return []
    except Exception:
        return []


# =========================
# 3. 네이버 API 호출 함수
# =========================

def search_naver_local(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    네이버 지역 검색 API로 장소 후보를 가져온다.
    """
    _require_naver_keys()

    params = {
        "query": query,
        "display": min(max(limit, 1), 5),
        "start": 1,
        "sort": "random",
    }

    data = safe_get(NAVER_LOCAL_URL, headers=_naver_headers(), params=params)
    if not data:
        return []

    items = []
    for item in data.get("items", []):
        items.append({
            "title": clean_html(item.get("title")),
            "category": clean_html(item.get("category")),
            "address": clean_html(item.get("address")),
            "road_address": clean_html(item.get("roadAddress")),
            "telephone": clean_html(item.get("telephone")),
            "link": item.get("link") or "",
        })

    return items


def search_naver_blogs(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    네이버 블로그 검색 API로 후기 후보를 가져온다.
    """
    _require_naver_keys()

    params = {
        "query": query,
        "display": min(max(limit, 1), 10),
        "start": 1,
        "sort": "sim",
    }

    data = safe_get(NAVER_BLOG_URL, headers=_naver_headers(), params=params)
    if not data:
        return []

    items = []
    for item in data.get("items", []):
        items.append({
            "title": clean_html(item.get("title")),
            "link": item.get("link") or "",
            "description": clean_html(item.get("description")),
            "postdate": item.get("postdate") or "",
            "bloggername": clean_html(item.get("bloggername")),
        })

    return items


# =========================
# 4. 한국관광공사 TourAPI 상세조회 함수
# =========================

def search_tour_api_keyword(place_name: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    TourAPI 키워드 검색(searchKeyword2)으로 contentId/contentTypeId를 찾는다.

    주요 반환 필드:
    - contentid
    - contenttypeid
    - title
    - addr1
    - firstimage
    - mapx, mapy
    """
    if not TOUR_API_KEY:
        return []

    params = {
        "serviceKey": TOUR_API_KEY,
        "MobileOS": "ETC",
        "MobileApp": "TravelMateKR",
        "_type": "json",
        "keyword": place_name,
        "numOfRows": limit,
        "pageNo": 1,
        "arrange": "A",
    }

    data = safe_get(TOUR_API_SEARCH_KEYWORD_URL, params=params, timeout=7)
    return _extract_items_from_tour_response(data)


def get_tour_detail_common(content_id: str, content_type_id: Optional[str] = None) -> Dict[str, Any]:
    """
    TourAPI 공통정보 조회(detailCommon2).

    가져오려는 정보:
    - overview: 관광지 개요
    - homepage: 공식 홈페이지 HTML
    - tel: 문의처
    - firstimage: 대표 이미지
    - addr1: 주소
    - mapx/mapy: 좌표
    """
    if not TOUR_API_KEY or not content_id:
        return {}

    params = {
        "serviceKey": TOUR_API_KEY,
        "MobileOS": "ETC",
        "MobileApp": "TravelMateKR",
        "_type": "json",
        "contentId": content_id,
        "defaultYN": "Y",
        "firstImageYN": "Y",
        "areacodeYN": "Y",
        "catcodeYN": "Y",
        "addrinfoYN": "Y",
        "mapinfoYN": "Y",
        "overviewYN": "Y",
    }

    # 일부 환경에서는 contentTypeId를 함께 넣어도 정상 동작
    if content_type_id:
        params["contentTypeId"] = content_type_id

    data = safe_get(TOUR_API_DETAIL_COMMON_URL, params=params, timeout=7)
    items = _extract_items_from_tour_response(data)
    if not items:
        return {}

    item = items[0]
    return {
        "content_id": str(item.get("contentid") or content_id),
        "content_type_id": str(item.get("contenttypeid") or content_type_id or ""),
        "title": clean_html(item.get("title")),
        "overview": clean_html(item.get("overview")),
        "homepage": clean_html(item.get("homepage")),
        "tel": clean_html(item.get("tel")),
        "address": clean_html(item.get("addr1")),
        "address_detail": clean_html(item.get("addr2")),
        "zipcode": clean_html(item.get("zipcode")),
        "first_image": item.get("firstimage") or "",
        "first_image2": item.get("firstimage2") or "",
        "mapx": item.get("mapx") or "",
        "mapy": item.get("mapy") or "",
    }


def get_tour_detail_intro(content_id: str, content_type_id: str) -> Dict[str, Any]:
    """
    TourAPI 소개정보 조회(detailIntro2).

    contentTypeId별로 필드명이 달라서 원본 intro_raw도 같이 반환하고,
    운영시간/쉬는날/입장료/주차 등은 normalize_tour_intro_fields()에서 공통 필드로 정리한다.

    대표 contentTypeId:
    - 12: 관광지
    - 14: 문화시설
    - 15: 행사/공연/축제
    - 25: 여행코스
    - 28: 레포츠
    - 32: 숙박
    - 38: 쇼핑
    - 39: 음식점
    """
    if not TOUR_API_KEY or not content_id or not content_type_id:
        return {}

    params = {
        "serviceKey": TOUR_API_KEY,
        "MobileOS": "ETC",
        "MobileApp": "TravelMateKR",
        "_type": "json",
        "contentId": content_id,
        "contentTypeId": content_type_id,
    }

    data = safe_get(TOUR_API_DETAIL_INTRO_URL, params=params, timeout=7)
    items = _extract_items_from_tour_response(data)
    if not items:
        return {}

    raw = items[0]
    return {
        key: clean_html(value) if isinstance(value, str) else value
        for key, value in raw.items()
    }


def normalize_tour_intro_fields(intro: Dict[str, Any], content_type_id: Optional[str]) -> Dict[str, str]:
    """
    TourAPI detailIntro2의 contentTypeId별 상이한 필드를
    프로젝트 공통 필드로 통일한다.

    반환:
    - opening_hours
    - rest_date
    - admission_fee
    - parking
    - info_center
    - use_time_note
    """
    if not intro:
        return {
            "opening_hours": "정보 확인 필요",
            "rest_date": "정보 확인 필요",
            "admission_fee": "정보 확인 필요",
            "parking": "정보 확인 필요",
            "info_center": "정보 확인 필요",
            "use_time_note": "",
        }

    ctype = str(content_type_id or intro.get("contenttypeid") or "")

    def first_non_empty(*keys: str) -> str:
        for key in keys:
            value = clean_html(intro.get(key))
            if value:
                return value
        return ""

    # 공통적으로 자주 쓰이는 필드 후보들을 contentTypeId별로 흡수
    opening_hours = first_non_empty(
        "usetime",             # 관광지
        "usetimeculture",      # 문화시설
        "playtime",            # 행사
        "usetimefestival",     # 행사 일부
        "usetimeleports",      # 레포츠
        "checkintime",         # 숙박
        "opentime",            # 쇼핑
        "opentimefood",        # 음식점
        "taketime",            # 여행코스
    )

    rest_date = first_non_empty(
        "restdate",            # 관광지
        "restdateculture",     # 문화시설
        "restdateleports",     # 레포츠
        "restdateshopping",    # 쇼핑
        "restdatefood",        # 음식점
        "restdateaccommodation",
    )

    admission_fee = first_non_empty(
        "usefee",              # 문화시설 등
        "usetimefestival",     # 축제 이용요금이 섞여 오는 경우
        "expagerange",         # 직접 요금은 아니지만 보조
        "eventstartdate",      # 축제는 입장료 대신 기간이 중요할 수 있음
    )

    parking = first_non_empty(
        "parking",
        "parkingculture",
        "parkingleports",
        "parkingshopping",
        "parkingfood",
    )

    info_center = first_non_empty(
        "infocenter",
        "infocenterculture",
        "sponsor1tel",
        "eventinquiry",
        "infocenterleports",
        "infocentershopping",
        "infocenterfood",
    )

    # 축제/행사 기간 보완
    event_start = first_non_empty("eventstartdate")
    event_end = first_non_empty("eventenddate")
    event_period = ""
    if event_start or event_end:
        event_period = f"{event_start} ~ {event_end}".strip(" ~")

    if ctype == "15" and event_period:
        opening_hours = opening_hours or event_period

    return {
        "opening_hours": opening_hours or "정보 확인 필요",
        "rest_date": rest_date or "정보 확인 필요",
        "admission_fee": admission_fee or "정보 확인 필요",
        "parking": parking or "정보 확인 필요",
        "info_center": info_center or "정보 확인 필요",
        "use_time_note": event_period,
    }


def get_tour_api_detail_by_place(place_name: str) -> Dict[str, Any]:
    """
    장소명으로 TourAPI 검색 → contentId 추출 → 공통정보/소개정보 상세조회까지 수행.

    반환 예시:
    {
        "matched": True,
        "content_id": "...",
        "content_type_id": "12",
        "title": "...",
        "overview": "...",
        "homepage": "...",
        "address": "...",
        "opening_hours": "...",
        "rest_date": "...",
        "admission_fee": "...",
        "parking": "...",
        "info_center": "...",
        "first_image": "...",
        "mapx": "...",
        "mapy": "...",
        "raw": {...}
    }
    """
    if not TOUR_API_KEY:
        return {
            "matched": False,
            "reason": "TOUR_API_KEY가 설정되지 않았습니다.",
        }

    candidates = search_tour_api_keyword(place_name, limit=3)
    if not candidates:
        return {
            "matched": False,
            "reason": "TourAPI 키워드 검색 결과 없음",
        }

    # 가장 첫 번째 결과를 사용. 고도화하려면 주소/지역명으로 유사도 비교 가능.
    selected = candidates[0]
    content_id = str(selected.get("contentid") or "")
    content_type_id = str(selected.get("contenttypeid") or "")

    if not content_id:
        return {
            "matched": False,
            "reason": "contentId 없음",
        }

    common = get_tour_detail_common(content_id, content_type_id)
    intro = get_tour_detail_intro(content_id, content_type_id)
    normalized_intro = normalize_tour_intro_fields(intro, content_type_id)

    return {
        "matched": True,
        "content_id": content_id,
        "content_type_id": content_type_id,
        "title": common.get("title") or clean_html(selected.get("title")),
        "overview": common.get("overview") or "",
        "homepage": common.get("homepage") or "",
        "tel": common.get("tel") or "",
        "address": common.get("address") or clean_html(selected.get("addr1")),
        "address_detail": common.get("address_detail") or clean_html(selected.get("addr2")),
        "zipcode": common.get("zipcode") or "",
        "first_image": common.get("first_image") or selected.get("firstimage") or "",
        "first_image2": common.get("first_image2") or selected.get("firstimage2") or "",
        "mapx": common.get("mapx") or selected.get("mapx") or "",
        "mapy": common.get("mapy") or selected.get("mapy") or "",
        "opening_hours": normalized_intro["opening_hours"],
        "rest_date": normalized_intro["rest_date"],
        "admission_fee": normalized_intro["admission_fee"],
        "parking": normalized_intro["parking"],
        "info_center": normalized_intro["info_center"],
        "use_time_note": normalized_intro["use_time_note"],
        "raw": {
            "keyword_candidate": selected,
            "detail_common": common,
            "detail_intro": intro,
        },
    }


# 이전 버전 호환용 함수명
def search_tour_api(place_name: str, limit: int = 1) -> List[Dict[str, Any]]:
    """
    이전 코드와의 호환을 위한 함수.
    키워드 검색 결과만 반환한다.
    """
    return search_tour_api_keyword(place_name, limit=limit)


# =========================
# 5. 요약/추천 로직
# =========================

def summarize_blog_reviews(blog_items: List[Dict[str, Any]]) -> str:
    """
    LLM 없이 블로그 제목/요약을 기반으로 짧은 후기 요약을 만든다.
    팀장님이 LLM을 통합하면 이 부분만 LLM 요약으로 바꿔도 된다.
    """
    if not blog_items:
        return "후기 정보 부족"

    text_blob = " ".join(
        f"{item.get('title', '')} {item.get('description', '')}"
        for item in blog_items
    )

    positive_points = []
    rules = [
        ("데이트", "데이트 코스로 언급됩니다"),
        ("가족", "가족 단위 방문에 적합하다는 후기가 있습니다"),
        ("아이", "아이와 함께 방문하기 좋다는 평가가 있습니다"),
        ("실내", "실내에서 즐기기 좋아 날씨 영향을 덜 받는다는 장점이 있습니다"),
        ("사진", "사진 찍기 좋은 장소로 언급됩니다"),
        ("산책", "산책하기 좋다는 후기가 있습니다"),
        ("체험", "체험 요소가 있다는 후기가 있습니다"),
        ("주차", "주차 관련 정보를 미리 확인하는 것이 좋습니다"),
        ("웨이팅", "주말이나 성수기에는 대기 시간이 있을 수 있습니다"),
        ("운영시간", "방문 전 운영시간 확인이 필요합니다"),
        ("입장료", "입장료 또는 이용요금을 미리 확인하는 것이 좋습니다"),
    ]

    for keyword, sentence in rules:
        if keyword in text_blob and sentence not in positive_points:
            positive_points.append(sentence)

    if positive_points:
        return "블로그 후기 기준으로 " + ", ".join(positive_points[:3]) + "."

    first = blog_items[0]
    desc = first.get("description") or first.get("title") or ""
    return f"블로그 후기에서는 '{desc[:80]}' 등의 내용이 확인됩니다."


def infer_travel_style(category: Optional[str], travel_style: Optional[str], age: Optional[int]) -> str:
    """입력값이 부족할 때 나이대 기반 기본 여행 스타일을 추론한다."""
    if travel_style:
        return travel_style
    if category:
        return category

    age_group = get_age_group(age)
    if age_group in ["10대", "20대"]:
        return "이색/체험"
    if age_group == "30대":
        return "데이트/힐링"
    if age_group in ["40대", "50대"]:
        return "가족/자연"
    if age_group == "60대 이상":
        return "휴식/문화"
    return "일반"


def make_personalized_reason(
    place_name: str,
    category: str,
    age: Optional[int],
    gender: Optional[str],
    travel_date: Optional[str],
    travel_style: Optional[str],
    blog_summary: str,
    tour_overview: Optional[str] = None,
) -> str:
    """
    사용자 특성 기반 추천 이유 생성.
    성별은 고정관념적 판단 기준이 아니라 보조 정보로만 표현한다.
    """
    age_group = get_age_group(age)
    style = travel_style or "여행 스타일"

    reasons = []

    if age_group in ["10대", "20대"]:
        reasons.append("젊은 여행자에게 이색 체험이나 사진 기록용 장소로 활용하기 좋습니다")
    elif age_group == "30대":
        reasons.append("주말 나들이나 데이트 코스로 무난하게 추천할 수 있습니다")
    elif age_group in ["40대", "50대"]:
        reasons.append("가족 여행이나 여유로운 산책 코스로 연결하기 좋습니다")
    elif age_group == "60대 이상":
        reasons.append("비교적 부담 없는 문화·휴식형 일정으로 구성하기 좋습니다")
    else:
        reasons.append("여행 일정에 포함하기 좋은 대표 관광지입니다")

    combined_text = f"{category} {blog_summary} {tour_overview or ''}"

    if "실내" in combined_text or "전시" in combined_text or "과학관" in place_name:
        reasons.append("실내 관광지 성격이 있어 날씨 영향을 비교적 덜 받습니다")

    if "테마" in combined_text or "체험" in combined_text or "체험" in style:
        reasons.append("체험형 콘텐츠와 함께 일정에 넣기 좋습니다")

    if "데이트" in combined_text or style in ["데이트", "감성"]:
        reasons.append("데이트나 감성 여행 코스로도 활용할 수 있습니다")

    if travel_date:
        reasons.append(f"{travel_date} 일정에 맞춰 운영 여부만 확인하면 방문 후보로 적합합니다")

    return " ".join(reasons[:3])


def calculate_confidence(
    local_item: Dict[str, Any],
    blog_items: List[Dict[str, Any]],
    tour_detail: Dict[str, Any],
) -> str:
    """정보 신뢰도 간단 계산."""
    score = 0
    if local_item.get("address") or local_item.get("road_address"):
        score += 1
    if blog_items:
        score += 1
    if tour_detail.get("matched"):
        score += 2
    if tour_detail.get("opening_hours") and tour_detail.get("opening_hours") != "정보 확인 필요":
        score += 1

    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def build_quick_actions() -> List[str]:
    return [
        "더 많은 관광지 추천 받기",
        "MBTI별 여행지 추천 받기",
        "액티비티한 여행지 추천 받기",
        "감성 여행지 추천 받기",
        "사진 찍기 좋은 여행지 추천",
        "비 오는 날 가기 좋은 관광지 추천",
    ]


# =========================
# 6. 팀장님께 넘길 메인 Tool 함수
# =========================

def recommend_travel_place(
    destination: str,
    travel_date: Optional[str] = None,
    gender: Optional[str] = None,
    age: Optional[int] = None,
    category: Optional[str] = None,
    travel_style: Optional[str] = None,
    mbti: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    개인화 관광지 추천 Tool.

    Args:
        destination: 여행 지역. 예: "과천", "부산 해운대"
        travel_date: 여행 날짜. 예: "2026-07-20", "이번 주말"
        gender: 사용자 성별. 예: "여성", "남성", "선택 안 함"
        age: 사용자 나이. 예: 25
        category: 관광지 유형. 예: "실내", "데이트", "자연"
        travel_style: 여행 스타일. 예: "액티비티", "감성", "가족"
        mbti: 선택 입력. 예: "ENFP"
        limit: 추천 개수

    Returns:
        dict: 최종 일정 생성 Tool이 바로 사용할 수 있는 JSON 호환 dict
    """
    if not destination:
        raise ValueError("destination은 필수 입력값입니다.")

    user_style = infer_travel_style(category, travel_style, age)

    # 1) 네이버 지역 검색으로 관광지 후보 조회
    queries = []
    if category:
        queries.append(f"{destination} {category} 관광지")
    if travel_style:
        queries.append(f"{destination} {travel_style} 가볼만한곳")
    queries.extend([
        f"{destination} 관광지",
        f"{destination} 가볼만한곳",
        f"{destination} 명소",
    ])

    local_candidates: List[Dict[str, Any]] = []
    seen_names = set()

    for query in queries:
        for item in search_naver_local(query, limit=limit):
            name = item.get("title", "").strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            local_candidates.append(item)
            if len(local_candidates) >= limit:
                break
        if len(local_candidates) >= limit:
            break

    # 검색 결과가 전혀 없을 때도 에러 대신 빈 결과 반환
    if not local_candidates:
        return {
            "destination": destination,
            "travel_date": travel_date,
            "user_profile": {
                "gender": gender or "선택 안 함",
                "age": age,
                "age_group": get_age_group(age),
                "travel_style": user_style,
                "mbti": mbti,
            },
            "results": [],
            "quick_actions": build_quick_actions(),
            "message": "관광지 검색 결과가 부족합니다. 지역명을 더 구체적으로 입력해 주세요.",
        }

    # 2) 각 후보별 블로그 후기 + TourAPI 상세정보 + 지도 링크 구성
    results = []

    for item in local_candidates[:limit]:
        place_name = item.get("title", "")
        place_category = item.get("category") or category or "관광지"

        blog_query = f"{destination} {place_name} 후기 운영시간 입장료"
        blog_items = search_naver_blogs(blog_query, limit=3)

        blog_summary = summarize_blog_reviews(blog_items)
        blog_links = [b["link"] for b in blog_items if b.get("link")]

        # TourAPI 상세정보 조회
        tour_detail = get_tour_api_detail_by_place(place_name)

        # 주소 우선순위: 네이버 도로명주소 > 네이버 지번주소 > TourAPI 주소
        address = (
            item.get("road_address")
            or item.get("address")
            or tour_detail.get("address")
            or "주소 정보 확인 필요"
        )

        # 운영시간/입장료는 TourAPI 상세조회 결과를 우선 사용
        opening_hours = tour_detail.get("opening_hours") or "정보 확인 필요"
        admission_fee = tour_detail.get("admission_fee") or "정보 확인 필요"
        rest_date = tour_detail.get("rest_date") or "정보 확인 필요"

        # 공식 설명이 있으면 summary에 반영
        tour_overview = tour_detail.get("overview") or ""
        summary = (
            tour_overview[:120] + "..."
            if len(tour_overview) > 120
            else tour_overview
        )
        if not summary:
            summary = f"{destination} 지역에서 방문 후보로 추천할 수 있는 장소입니다."

        map_links = build_map_links(destination, place_name)

        personalized_reason = make_personalized_reason(
            place_name=place_name,
            category=place_category,
            age=age,
            gender=gender,
            travel_date=travel_date,
            travel_style=user_style,
            blog_summary=blog_summary,
            tour_overview=tour_overview,
        )

        fallback_url = (
            tour_detail.get("homepage")
            or build_visitkorea_fallback_link(place_name)
        )

        result = {
            "name": place_name,
            "category": place_category,
            "summary": summary,
            "personalized_reason": personalized_reason,
            "blog_review_summary": blog_summary,
            "address": address,
            "opening_hours": opening_hours,
            "rest_date": rest_date,
            "admission_fee": admission_fee,
            "parking": tour_detail.get("parking") or "정보 확인 필요",
            "info_center": tour_detail.get("info_center") or tour_detail.get("tel") or "정보 확인 필요",
            "naver_map_url": map_links["naver_map_url"],
            "kakao_map_url": map_links["kakao_map_url"],
            "blog_links": blog_links,
            "official_or_fallback_url": fallback_url,
            "tour_api": {
                "matched": tour_detail.get("matched", False),
                "content_id": tour_detail.get("content_id"),
                "content_type_id": tour_detail.get("content_type_id"),
                "first_image": tour_detail.get("first_image"),
                "mapx": tour_detail.get("mapx"),
                "mapy": tour_detail.get("mapy"),
            },
            "confidence": calculate_confidence(item, blog_items, tour_detail),
        }
        results.append(result)

    return {
        "destination": destination,
        "travel_date": travel_date,
        "user_profile": {
            "gender": gender or "선택 안 함",
            "age": age,
            "age_group": get_age_group(age),
            "travel_style": user_style,
            "mbti": mbti,
        },
        "results": results,
        "quick_actions": build_quick_actions(),
    }


# 팀장님이 기획서 이름(search_attractions)으로 쓰고 싶을 때를 위한 alias
def search_attractions(
    destination: str,
    travel_date: Optional[str] = None,
    gender: Optional[str] = None,
    age: Optional[int] = None,
    category: Optional[str] = None,
    travel_style: Optional[str] = None,
    mbti: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    return recommend_travel_place(
        destination=destination,
        travel_date=travel_date,
        gender=gender,
        age=age,
        category=category,
        travel_style=travel_style,
        mbti=mbti,
        limit=limit,
    )


# =========================
# 7. 로컬 테스트
# =========================

if __name__ == "__main__":
    # 전체 관광지 추천 테스트
    sample = recommend_travel_place(
        destination="과천",
        travel_date="2026-07-20",
        gender="여성",
        age=25,
        travel_style="이색/체험",
        limit=3,
    )
    print(json.dumps(sample, ensure_ascii=False, indent=2))

    # TourAPI 상세조회만 따로 테스트하고 싶을 때
    # detail = get_tour_api_detail_by_place("국립과천과학관")
    # print(json.dumps(detail, ensure_ascii=False, indent=2))
