"""
Tool — 숙박시설 추천 (recommend_stay_place / search_accommodations)
사용 API : 한국관광공사 TourAPI(KorService2) + 네이버 블로그 검색 API

역할
----
- 여행지와 여행 날짜, 가격대 조건을 기반으로 숙박시설 후보를 추천합니다.
- TourAPI의 areaCode2/sigunguCode2/searchStay2/detailCommon2/detailIntro2를 활용합니다.
- 네이버 블로그 검색으로 지역/숙소별 후기 링크를 함께 제공합니다.
- 네이버지도/카카오맵 검색 링크를 생성합니다.

.env 예시
----------
NAVER_CLIENT_ID=발급받은_네이버_CLIENT_ID
NAVER_CLIENT_SECRET=발급받은_네이버_CLIENT_SECRET
TOUR_API_KEY=발급받은_한국관광공사_TourAPI_KEY
"""

from __future__ import annotations

import os
import re
import html
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

# ── 환경 변수 ─────────────────────────────────────
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
TOUR_API_KEY = os.getenv("TOUR_API_KEY")

NAVER_BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"

# 한국관광공사 국문 관광정보 서비스_GW, KorService2 기준
TOUR_API_BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
TOUR_AREA_CODE_URL = f"{TOUR_API_BASE_URL}/areaCode2"
TOUR_SEARCH_STAY_URL = f"{TOUR_API_BASE_URL}/searchStay2"
TOUR_DETAIL_COMMON_URL = f"{TOUR_API_BASE_URL}/detailCommon2"
TOUR_DETAIL_INTRO_URL = f"{TOUR_API_BASE_URL}/detailIntro2"

# TourAPI 지역 코드 기본 매핑. API 조회 실패 시 fallback으로 사용합니다.
AREA_CODE_FALLBACK = {
    "서울": "1", "서울특별시": "1",
    "인천": "2", "인천광역시": "2",
    "대전": "3", "대전광역시": "3",
    "대구": "4", "대구광역시": "4",
    "광주": "5", "광주광역시": "5",
    "부산": "6", "부산광역시": "6",
    "울산": "7", "울산광역시": "7",
    "세종": "8", "세종특별자치시": "8",
    "경기": "31", "경기도": "31",
    "강원": "32", "강원도": "32", "강원특별자치도": "32",
    "충북": "33", "충청북도": "33",
    "충남": "34", "충청남도": "34",
    "경북": "35", "경상북도": "35",
    "경남": "36", "경상남도": "36",
    "전북": "37", "전라북도": "37", "전북특별자치도": "37",
    "전남": "38", "전라남도": "38",
    "제주": "39", "제주도": "39", "제주특별자치도": "39",
}

PRICE_LABELS = {
    "UNDER_100K": "10만원 미만",
    "UNDER_200K": "20만원 미만",
    "UNDER_300K": "30만원 미만",
    "OVER_300K": "30만원 이상",
    "ANY": "가격대 무관",
}

PRICE_NOTE = "실시간 요금은 예약일, 객실 유형, 성수기 여부에 따라 달라질 수 있습니다."


# ── 공통 유틸 ─────────────────────────────────────
def clean_text(text: Optional[str]) -> str:
    """HTML 태그/엔티티 제거."""
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
    timeout: int = 8,
) -> Optional[dict]:
    """API 호출 실패 시 None 반환."""
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _extract_tour_items(data: Optional[dict]) -> List[Dict[str, Any]]:
    """TourAPI 응답에서 item 리스트를 안전하게 추출."""
    if not data:
        return []
    try:
        items_obj = data.get("response", {}).get("body", {}).get("items", {})
        if not items_obj:
            return []
        item = items_obj.get("item", [])
        if isinstance(item, dict):
            return [item]
        if isinstance(item, list):
            return item
        return []
    except Exception:
        return []


def _tour_params(extra: Optional[dict] = None) -> dict:
    params = {
        "serviceKey": TOUR_API_KEY,
        "MobileOS": "ETC",
        "MobileApp": "TravelMateKR",
        "_type": "json",
    }
    if extra:
        params.update(extra)
    return params


def _naver_headers() -> dict:
    return {
        "X-Naver-Client-Id": NAVER_CLIENT_ID or "",
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET or "",
    }


def build_stay_map_links(destination: str, stay_name: str) -> Dict[str, str]:
    """숙소명 기반 네이버지도/카카오맵 검색 링크 생성."""
    query = f"{destination} {stay_name}".strip()
    encoded = quote(query)
    return {
        "naver_map_url": f"https://map.naver.com/v5/search/{encoded}",
        "kakao_map_url": f"https://map.kakao.com/link/search/{encoded}",
    }


# ── 가격대 처리 ───────────────────────────────────
def normalize_price_range(price_range: Optional[str] = None) -> str:
    """사용자 가격대 입력을 내부 코드로 정규화."""
    if not price_range:
        return "ANY"

    text = str(price_range).replace(" ", "").lower()

    if any(k in text for k in ["10만원미만", "10만미만", "저렴", "가성비", "저예산"]):
        return "UNDER_100K"
    if any(k in text for k in ["20만원미만", "20만미만", "중간", "무난"]):
        return "UNDER_200K"
    if any(k in text for k in ["30만원미만", "30만미만", "중상급", "감성"]):
        return "UNDER_300K"
    if any(k in text for k in ["30만원이상", "30만이상", "고급", "럭셔리", "프리미엄", "풀빌라", "5성급"]):
        return "OVER_300K"

    return "ANY"


def build_price_keywords(destination: str, price_range_code: str, stay_type: Optional[str] = None) -> List[str]:
    """가격대별 네이버 블로그 검색 키워드 생성."""
    by_price = {
        "UNDER_100K": [
            f"{destination} 10만원 미만 숙소",
            f"{destination} 가성비 숙소 추천",
            f"{destination} 저렴한 호텔",
            f"{destination} 게스트하우스 추천",
        ],
        "UNDER_200K": [
            f"{destination} 20만원 미만 숙소",
            f"{destination} 20만원대 호텔",
            f"{destination} 깔끔한 호텔 추천",
            f"{destination} 가족 숙소 추천",
        ],
        "UNDER_300K": [
            f"{destination} 30만원 미만 숙소",
            f"{destination} 감성 숙소 추천",
            f"{destination} 오션뷰 호텔 추천",
            f"{destination} 리조트 추천",
        ],
        "OVER_300K": [
            f"{destination} 30만원 이상 호텔",
            f"{destination} 고급호텔 추천",
            f"{destination} 럭셔리 리조트 추천",
            f"{destination} 풀빌라 추천",
        ],
        "ANY": [
            f"{destination} 숙소 추천",
            f"{destination} 호텔 추천",
            f"{destination} 감성 숙소",
            f"{destination} 가성비 숙소",
        ],
    }
    keywords = by_price.get(price_range_code, by_price["ANY"])
    if stay_type:
        keywords.insert(0, f"{destination} {stay_type} 추천")
    return keywords


def estimate_price_range(
    stay_name: str,
    stay_type: Optional[str] = None,
    blog_items: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, str]:
    """
    숙소명·숙소 유형·블로그 문맥 기반 예상 가격대 추정.
    TourAPI는 실시간 가격을 주지 않으므로 추정값임을 함께 반환한다.
    """
    text = f"{stay_name} {stay_type or ''} "
    if blog_items:
        text += " ".join(
            f"{b.get('title', '')} {b.get('description', '')}" for b in blog_items
        )
    text = text.lower()

    if any(k in text for k in ["풀빌라", "럭셔리", "프리미엄", "5성", "5성급", "스위트", "고급", "특급"]):
        return "30만원 이상", "고급호텔"
    if any(k in text for k in ["리조트", "오션뷰", "감성", "부티크", "스파"]):
        return "30만원 미만", "중상급 숙소"
    if any(k in text for k in ["비즈니스", "호텔", "펜션", "가족"]):
        return "20만원 미만", "중간 가격대 숙소"
    if any(k in text for k in ["게스트하우스", "호스텔", "모텔", "저렴", "가성비"]):
        return "10만원 미만", "저예산 숙소"

    return "가격 확인 필요", stay_type or "숙박"


def _price_code_from_estimated(label: str) -> str:
    if label == "10만원 미만":
        return "UNDER_100K"
    if label == "20만원 미만":
        return "UNDER_200K"
    if label == "30만원 미만":
        return "UNDER_300K"
    if label == "30만원 이상":
        return "OVER_300K"
    return "ANY"


def _is_price_match(estimated_label: str, requested_code: str) -> bool:
    """가격대 필터. ANY는 전체 허용."""
    if requested_code == "ANY":
        return True
    estimated_code = _price_code_from_estimated(estimated_label)
    if estimated_code == "ANY":
        return False
    return estimated_code == requested_code


# ── TourAPI 지역/숙박 조회 ─────────────────────────
def get_area_code(destination: str) -> Dict[str, Optional[str]]:
    """여행지명에서 TourAPI areaCode를 찾는다."""
    if not TOUR_API_KEY:
        return {"area_code": AREA_CODE_FALLBACK.get(destination), "area_name": destination, "source": "fallback"}

    data = safe_get(TOUR_AREA_CODE_URL, params=_tour_params({"numOfRows": 50, "pageNo": 1}))
    items = _extract_tour_items(data)

    normalized_destination = destination.replace(" ", "")
    for item in items:
        name = clean_text(item.get("name"))
        code = str(item.get("code") or "")
        if not name or not code:
            continue
        normalized_name = name.replace(" ", "")
        if normalized_name in normalized_destination or normalized_destination in normalized_name:
            return {"area_code": code, "area_name": name, "source": "tour_api"}

    # fallback: 대표 행정구역명 일부 포함 처리
    for key, code in AREA_CODE_FALLBACK.items():
        if key in destination:
            return {"area_code": code, "area_name": key, "source": "fallback"}

    return {"area_code": None, "area_name": None, "source": "none"}


def get_sigungu_code(area_code: str, destination: str) -> Dict[str, Optional[str]]:
    """areaCode 내부에서 destination에 맞는 sigunguCode를 찾는다. 없으면 None."""
    if not TOUR_API_KEY or not area_code:
        return {"sigungu_code": None, "sigungu_name": None, "source": "none"}

    data = safe_get(
        TOUR_AREA_CODE_URL,
        params=_tour_params({"areaCode": area_code, "numOfRows": 100, "pageNo": 1}),
    )
    items = _extract_tour_items(data)

    normalized_destination = destination.replace(" ", "")
    for item in items:
        name = clean_text(item.get("name"))
        code = str(item.get("code") or "")
        if not name or not code:
            continue
        normalized_name = name.replace(" ", "")
        if normalized_name in normalized_destination or normalized_destination in normalized_name:
            return {"sigungu_code": code, "sigungu_name": name, "source": "tour_api"}

    return {"sigungu_code": None, "sigungu_name": None, "source": "none"}


def search_stay_by_area(area_code: str, sigungu_code: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """TourAPI searchStay2로 숙박시설 목록 조회."""
    if not TOUR_API_KEY:
        return []
    if not area_code:
        return []

    params = {
        "areaCode": area_code,
        "numOfRows": min(max(limit, 1), 30),
        "pageNo": 1,
        "arrange": "A",
    }
    if sigungu_code:
        params["sigunguCode"] = sigungu_code

    data = safe_get(TOUR_SEARCH_STAY_URL, params=_tour_params(params), timeout=10)
    return _extract_tour_items(data)


def get_stay_detail_common(content_id: str, content_type_id: str = "32") -> Dict[str, Any]:
    """TourAPI detailCommon2로 숙소 공통 정보 조회."""
    if not TOUR_API_KEY or not content_id:
        return {}

    params = {
        "contentId": content_id,
        "contentTypeId": content_type_id or "32",
        "defaultYN": "Y",
        "firstImageYN": "Y",
        "areacodeYN": "Y",
        "catcodeYN": "Y",
        "addrinfoYN": "Y",
        "mapinfoYN": "Y",
        "overviewYN": "Y",
    }
    data = safe_get(TOUR_DETAIL_COMMON_URL, params=_tour_params(params), timeout=10)
    items = _extract_tour_items(data)
    if not items:
        return {}
    item = items[0]
    return {
        "title": clean_text(item.get("title")),
        "overview": clean_text(item.get("overview")),
        "homepage": clean_text(item.get("homepage")),
        "tel": clean_text(item.get("tel")),
        "address": clean_text(item.get("addr1")),
        "address_detail": clean_text(item.get("addr2")),
        "zipcode": clean_text(item.get("zipcode")),
        "first_image": item.get("firstimage") or "",
        "first_image2": item.get("firstimage2") or "",
        "mapx": item.get("mapx") or "",
        "mapy": item.get("mapy") or "",
    }


def get_stay_detail_intro(content_id: str, content_type_id: str = "32") -> Dict[str, str]:
    """TourAPI detailIntro2로 숙소 상세 정보 조회."""
    if not TOUR_API_KEY or not content_id:
        return {}

    params = {
        "contentId": content_id,
        "contentTypeId": content_type_id or "32",
    }
    data = safe_get(TOUR_DETAIL_INTRO_URL, params=_tour_params(params), timeout=10)
    items = _extract_tour_items(data)
    if not items:
        return {}
    raw = items[0]

    return {
        "check_in": clean_text(raw.get("checkintime")) or "정보 확인 필요",
        "check_out": clean_text(raw.get("checkouttime")) or "정보 확인 필요",
        "room_count": clean_text(raw.get("roomcount")) or "정보 확인 필요",
        "room_type": clean_text(raw.get("roomtype")) or "정보 확인 필요",
        "parking": clean_text(raw.get("parkinglodging")) or "정보 확인 필요",
        "reservation": clean_text(raw.get("reservationlodging")) or "정보 확인 필요",
        "reservation_url": clean_text(raw.get("reservationurl")) or "",
        "info_center": clean_text(raw.get("infocenterlodging")) or "정보 확인 필요",
        "food_place": clean_text(raw.get("foodplace")) or "정보 확인 필요",
        "subfacility": clean_text(raw.get("subfacility")) or "정보 확인 필요",
        "cooking": clean_text(raw.get("chkcooking")) or "정보 확인 필요",
        "raw": raw,
    }


# ── 네이버 블로그 후기 ─────────────────────────────
def search_naver_stay_blogs(
    destination: str,
    stay_name: Optional[str] = None,
    price_range: Optional[str] = None,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """네이버 블로그 검색으로 지역/숙소 후기 링크 수집."""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []

    price_code = normalize_price_range(price_range)
    queries = []
    if stay_name:
        queries.extend([
            f"{destination} {stay_name} 후기",
            f"{stay_name} 체크인 후기",
            f"{stay_name} 조식 후기",
        ])
    queries.extend(build_price_keywords(destination, price_code))

    seen_links = set()
    results: List[Dict[str, Any]] = []

    for query in queries:
        params = {
            "query": query,
            "display": min(max(limit, 1), 10),
            "start": 1,
            "sort": "sim",
        }
        data = safe_get(NAVER_BLOG_URL, headers=_naver_headers(), params=params, timeout=8)
        if not data:
            continue
        for item in data.get("items", []):
            link = item.get("link") or ""
            if not link or link in seen_links:
                continue
            seen_links.add(link)
            results.append({
                "title": clean_text(item.get("title")),
                "link": link,
                "description": clean_text(item.get("description")),
                "postdate": item.get("postdate") or "",
                "bloggername": clean_text(item.get("bloggername")),
                "query": query,
            })
            if len(results) >= limit:
                return results
    return results


def summarize_stay_blog_reviews(blog_items: List[Dict[str, Any]], price_range: Optional[str] = None) -> str:
    """블로그 제목/요약 기반 간단 후기 요약."""
    if not blog_items:
        return "후기 정보 부족"

    text = " ".join(f"{b.get('title', '')} {b.get('description', '')}" for b in blog_items)
    points = []
    rules = [
        ("가성비", "가성비를 중시하는 후기에서 자주 언급됩니다"),
        ("저렴", "비교적 저렴한 숙소를 찾는 글에서 언급됩니다"),
        ("오션뷰", "오션뷰나 전망 관련 만족 후기가 있습니다"),
        ("조식", "조식 만족도 관련 언급이 있습니다"),
        ("수영장", "수영장이나 부대시설 관련 언급이 있습니다"),
        ("위치", "위치가 좋다는 후기가 있습니다"),
        ("깨끗", "객실 청결도 관련 긍정적 언급이 있습니다"),
        ("가족", "가족 여행 숙소로 언급됩니다"),
        ("커플", "커플 여행 숙소로 언급됩니다"),
        ("감성", "감성 숙소로 언급됩니다"),
        ("고급", "고급 숙소 추천 글에서 언급됩니다"),
    ]
    for keyword, sentence in rules:
        if keyword in text and sentence not in points:
            points.append(sentence)

    if points:
        prefix = f"{price_range} 조건 기준으로 " if price_range else "블로그 후기 기준으로 "
        return prefix + ", ".join(points[:3]) + "."

    first = blog_items[0]
    desc = first.get("description") or first.get("title") or ""
    return f"블로그 후기에서는 '{desc[:80]}' 등의 내용이 확인됩니다."


# ── 추천 메인 함수 ────────────────────────────────
def recommend_stay_place(
    destination: str,
    travel_date: Optional[str] = None,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    price_range: Optional[str] = None,
    stay_type: Optional[str] = None,
    limit: int = 5,
) -> dict:
    """
    여행지, 여행 날짜, 가격대 조건을 기반으로 숙박시설을 추천합니다.

    Parameters
    ----------
    destination : str  여행지. 예: 제주도, 부산 해운대, 강릉
    travel_date : str, optional  여행 날짜/기간. 예: 2026-07-20, 2박 3일
    check_in : str, optional  체크인 날짜
    check_out : str, optional  체크아웃 날짜
    price_range : str, optional  10만원 미만/20만원 미만/30만원 미만/30만원 이상/고급호텔
    stay_type : str, optional  호텔/리조트/펜션/게스트하우스/감성숙소
    limit : int  추천 개수

    Returns
    -------
    dict  숙박 추천 결과 JSON 호환 dict
    """
    if not destination:
        return {"error": "destination은 필수 입력값입니다."}
    if not TOUR_API_KEY:
        return {"error": "TOUR_API_KEY가 .env에 설정되지 않았습니다."}

    price_code = normalize_price_range(price_range)
    price_label = PRICE_LABELS.get(price_code, "가격대 무관")

    # 1) 지역 코드 조회
    area = get_area_code(destination)
    area_code = area.get("area_code")
    if not area_code:
        return {
            "destination": destination,
            "travel_date": travel_date,
            "check_in": check_in,
            "check_out": check_out,
            "price_range": price_range,
            "price_range_code": price_code,
            "results": [],
            "message": "지역 코드를 찾지 못했습니다. 예: 제주도, 부산, 강릉처럼 더 넓은 지역명으로 다시 입력해 주세요.",
        }

    sigungu = get_sigungu_code(area_code, destination)
    sigungu_code = sigungu.get("sigungu_code")

    # 2) 숙박시설 목록 조회. 필터링 여유를 위해 limit보다 넉넉히 조회
    raw_stays = search_stay_by_area(area_code, sigungu_code, limit=max(limit * 3, 10))
    if not raw_stays:
        return {
            "destination": destination,
            "travel_date": travel_date,
            "check_in": check_in,
            "check_out": check_out,
            "price_range": price_range,
            "price_range_code": price_code,
            "results": [],
            "message": "숙박시설 검색 결과가 없습니다. 네이버에서 지역 숙소 추천 키워드로 확인해 주세요.",
            "fallback_blog_query": f"{destination} 숙소 추천",
        }

    # 3) 각 숙소 상세조회 + 블로그 후기 + 가격대 추정
    all_results: List[Dict[str, Any]] = []
    filtered_results: List[Dict[str, Any]] = []

    for raw in raw_stays:
        content_id = str(raw.get("contentid") or "")
        content_type_id = str(raw.get("contenttypeid") or "32")
        raw_title = clean_text(raw.get("title")) or "숙소명 정보 없음"

        common = get_stay_detail_common(content_id, content_type_id)
        intro = get_stay_detail_intro(content_id, content_type_id)

        name = common.get("title") or raw_title
        address = common.get("address") or clean_text(raw.get("addr1")) or "주소 정보 확인 필요"
        image_url = common.get("first_image") or raw.get("firstimage") or ""
        homepage = common.get("homepage") or intro.get("reservation_url") or ""

        blog_items = search_naver_stay_blogs(
            destination=destination,
            stay_name=name,
            price_range=price_range,
            limit=3,
        )
        blog_summary = summarize_stay_blog_reviews(blog_items, price_range=price_label)
        estimated_price, estimated_stay_type = estimate_price_range(name, stay_type, blog_items)
        final_stay_type = stay_type or estimated_stay_type

        maps = build_stay_map_links(destination, name)

        result = {
            "name": name,
            "category": "숙박",
            "stay_type": final_stay_type,
            "estimated_price_range": estimated_price,
            "price_note": PRICE_NOTE,
            "summary": common.get("overview") or f"{destination} 여행 시 이용 가능한 숙박시설입니다.",
            "address": address,
            "check_in": intro.get("check_in") or "정보 확인 필요",
            "check_out": intro.get("check_out") or "정보 확인 필요",
            "room_count": intro.get("room_count") or "정보 확인 필요",
            "room_type": intro.get("room_type") or "정보 확인 필요",
            "parking": intro.get("parking") or "정보 확인 필요",
            "reservation": intro.get("reservation") or "정보 확인 필요",
            "info_center": intro.get("info_center") or common.get("tel") or "정보 확인 필요",
            "homepage": homepage,
            "image_url": image_url,
            "naver_map_url": maps["naver_map_url"],
            "kakao_map_url": maps["kakao_map_url"],
            "blog_review_summary": blog_summary,
            "blog_links": [b.get("link") for b in blog_items if b.get("link")],
            "tour_api": {
                "content_id": content_id,
                "content_type_id": content_type_id,
                "matched": bool(content_id),
                "area_code": area_code,
                "sigungu_code": sigungu_code,
                "mapx": common.get("mapx") or raw.get("mapx") or "",
                "mapy": common.get("mapy") or raw.get("mapy") or "",
            },
            "confidence": _calculate_confidence(common, intro, blog_items),
        }

        all_results.append(result)
        if _is_price_match(estimated_price, price_code):
            filtered_results.append(result)
        if len(filtered_results) >= limit:
            break

    # 가격대 조건에 맞는 결과가 너무 적으면 전체 결과를 보완 제공
    used_relaxed_filter = False
    results = filtered_results[:limit]
    if len(results) < limit:
        used_relaxed_filter = True
        existing = {r["name"] for r in results}
        for r in all_results:
            if r["name"] not in existing:
                results.append(r)
                existing.add(r["name"])
            if len(results) >= limit:
                break

    return {
        "destination": destination,
        "travel_date": travel_date,
        "check_in": check_in,
        "check_out": check_out,
        "price_range": price_range or "가격대 무관",
        "price_range_code": price_code,
        "area": area,
        "sigungu": sigungu,
        "results": results,
        "notice": (
            "가격대 조건과 정확히 일치하는 결과가 부족해 일부 숙소는 조건을 완화해 함께 제공합니다. "
            + PRICE_NOTE
            if used_relaxed_filter and price_code != "ANY"
            else PRICE_NOTE
        ),
    }


def search_accommodations(
    destination: str,
    travel_date: Optional[str] = None,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    price_range: Optional[str] = None,
    stay_type: Optional[str] = None,
    limit: int = 5,
) -> dict:
    """recommend_stay_place의 alias. 팀장님 통합용 보조 함수명."""
    return recommend_stay_place(
        destination=destination,
        travel_date=travel_date,
        check_in=check_in,
        check_out=check_out,
        price_range=price_range,
        stay_type=stay_type,
        limit=limit,
    )


def _calculate_confidence(common: Dict[str, Any], intro: Dict[str, Any], blog_items: List[Dict[str, Any]]) -> str:
    score = 0
    if common.get("address"):
        score += 1
    if common.get("overview") or common.get("homepage"):
        score += 1
    if intro.get("check_in") and intro.get("check_in") != "정보 확인 필요":
        score += 1
    if blog_items:
        score += 1

    if score >= 3:
        return "high"
    if score == 2:
        return "medium"
    return "low"


# ── OpenAI Function Calling 스키마 ──────────────
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "recommend_stay_place",
        "description": (
            "여행지, 여행 날짜, 가격대 조건을 기반으로 주변 숙박시설을 추천합니다. "
            "한국관광공사 TourAPI로 숙소 정보(주소, 이미지, 체크인/체크아웃, 주차, 문의처)를 조회하고, "
            "네이버 블로그 후기 링크와 네이버지도/카카오맵 링크를 함께 제공합니다. "
            "가격대는 10만원 미만, 20만원 미만, 30만원 미만, 30만원 이상, 고급호텔 등으로 받을 수 있습니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "description": "여행 목적지 또는 숙박 지역 (예: 제주도, 부산 해운대, 강릉)",
                },
                "travel_date": {
                    "type": "string",
                    "description": "여행 날짜 또는 기간 (예: 2026-07-20, 이번 주말, 2박 3일). 생략 가능.",
                },
                "check_in": {
                    "type": "string",
                    "description": "체크인 날짜 (예: 2026-07-20). 생략 가능.",
                },
                "check_out": {
                    "type": "string",
                    "description": "체크아웃 날짜 (예: 2026-07-22). 생략 가능.",
                },
                "price_range": {
                    "type": "string",
                    "enum": ["10만원 미만", "20만원 미만", "30만원 미만", "30만원 이상", "고급호텔"],
                    "description": "원하는 숙박 가격대 또는 등급. 생략 가능.",
                },
                "stay_type": {
                    "type": "string",
                    "description": "숙소 유형 (예: 호텔, 리조트, 펜션, 게스트하우스, 감성숙소). 생략 가능.",
                },
                "limit": {
                    "type": "integer",
                    "description": "추천 숙박시설 개수 (기본값 5)",
                },
            },
            "required": ["destination"],
        },
    },
}


if __name__ == "__main__":
    # 로컬 테스트 예시
    import json

    result = recommend_stay_place(
        destination="제주도",
        travel_date="2박 3일",
        price_range="30만원 이상",
        stay_type="고급호텔",
        limit=3,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
