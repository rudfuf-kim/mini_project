"""
TravelMate KR — 국내 여행 플래너 챗봇
Streamlit + OpenAI Function Calling + 7가지 Tool
[변경] tool_stay 연결 + 일정 생성 파이프라인 숙박 추천 반영
"""

import json
import os
import re
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

from tool_weather    import get_weather,                           TOOL_SCHEMA  as WEATHER_SCHEMA
from tool_restaurant import search_restaurants,                    TOOL_SCHEMA  as RESTAURANT_SCHEMA
from tool_attraction import search_attractions,                    TOOL_SCHEMA  as ATTRACTION_SCHEMA
from tool_stay       import recommend_stay_place,                  TOOL_SCHEMA  as STAY_SCHEMA
from tool_itinerary  import generate_itinerary,                    TOOL_SCHEMA  as ITINERARY_SCHEMA
from tool_transit    import get_highway_traffic, get_highway_fare, TOOL_SCHEMAS as TRANSIT_SCHEMAS
from tool_facilities import search_rentcar, search_facilities,     TOOL_SCHEMAS as FACILITY_SCHEMAS
import components as C

load_dotenv()

# ── 상수 ──────────────────────────────────────────
ALL_TOOLS = [
    WEATHER_SCHEMA, RESTAURANT_SCHEMA, ATTRACTION_SCHEMA, STAY_SCHEMA,
    ITINERARY_SCHEMA, *TRANSIT_SCHEMAS, *FACILITY_SCHEMAS,
]

TOOL_FUNC_MAP = {
    "get_weather":          get_weather,
    "search_restaurants":   search_restaurants,
    "search_attractions":   search_attractions,
    "recommend_stay_place": recommend_stay_place,
    "search_accommodations": recommend_stay_place,
    "generate_itinerary":   generate_itinerary,
    "get_highway_traffic":  get_highway_traffic,
    "get_highway_fare":     get_highway_fare,
    "search_rentcar":       search_rentcar,
    "search_facilities":    search_facilities,
}

TOOL_STATUS_MSG = {
    "get_weather":         "🌤️ 날씨 정보 조회 중...",
    "search_restaurants":  "🍽️ 맛집 검색 중...",
    "search_attractions":  "📍 관광지 검색 중...",
    "recommend_stay_place": "🏨 숙박시설 검색 중...",
    "search_accommodations": "🏨 숙박시설 검색 중...",
    "generate_itinerary":  "📅 여행 일정 생성 중...",
    "get_highway_traffic": "🚗 고속도로 소통 정보 조회 중...",
    "get_highway_fare":    "🪙 통행요금 조회 중...",
    "search_rentcar":      "🚙 렌트카 업체 검색 중...",
    "search_facilities":   "🏪 편의시설 검색 중...",
}

SYSTEM_PROMPT = """당신은 대한민국 국내 여행 전문 플래너 챗봇 'TravelMate KR'입니다.

【여행 일정 요청 시 필수 수집 절차】
사용자가 여행 일정·계획을 요청하면, 아래 두 정보가 모두 확보될 때까지 tool을 호출하지 말고 대화로 먼저 수집하세요.
  1) 여행지 (예: 제주도, 부산, 강릉) — 없으면 "어디로 여행을 계획 중이신가요?" 라고 질문
  2) 여행 기간 (예: 2박 3일, 당일치기) — 없으면 "여행 기간은 얼마나 생각하고 계세요?" 라고 질문
두 정보가 모두 확보된 뒤에만 generate_itinerary tool을 호출하세요.

단, 날씨·맛집·관광지·숙박·교통·렌트카·편의시설 등 일정 외 단순 질문은 즉시 해당 tool을 사용해 답변하세요.

【도구 사용 원칙】
- 날씨 질문 → get_weather
- 맛집·식당·카페 질문 → search_restaurants
- 관광지·명소·볼거리 질문 → search_attractions
- 숙소·숙박시설·호텔·펜션·게스트하우스 질문 → recommend_stay_place
- 여행 일정·코스·계획 질문 → generate_itinerary (위 수집 절차 선행 필수)
  · 일정 생성 파이프라인에서는 관광지, 맛집, 숙박시설, 날씨 정보를 자동으로 함께 조회합니다.
- 고속도로 소통·혼잡 질문 → get_highway_traffic
- 통행요금·고속도로 비용 질문 → get_highway_fare
- 렌트카·차량 대여 질문 → search_rentcar
- 편의점·마트·병원·약국·주유소·은행 등 편의시설 질문 → search_facilities

【generate_itinerary 출발지 처리】
- 사용자가 출발지를 언급했다면 origin 파라미터로 전달하세요.
- tool 결과에 "안내" 필드가 있으면 답변 끝에 "어디서 출발하시나요?"라고 물어보고,
  출발지를 받으면 generate_itinerary를 origin과 함께 다시 호출해 일정을 갱신하세요.

【답변 규칙】
- 한국어로 친근하게 답변하세요.
- tool 결과를 그대로 나열하지 말고, 자연스러운 문장으로 요약·정리하세요.
- 렌트카·편의시설 결과는 UI 카드로 표시되므로 텍스트 답변에서는 간단히 요약만 하세요.
- 여행 팁이나 추천 이유를 함께 제공하면 좋습니다.
- 숙박시설 결과를 답변할 때는 가능하면 네이버지도 링크와 공식 홈페이지 링크를 함께 안내하세요.
"""

EXAMPLE_CARDS = [
    ("🧳", "#D8F0E4", "제주도 2박 3일 힐링 여행 계획 짜줘"),
    ("🍽️", "#FFE2D1", "강릉 해산물 맛집 추천해줘"),
    ("🏯", "#E7E1F6", "경주 역사 관광지 알려줘"),
    ("🚗", "#FEF0D0", "서울에서 부산 고속도로 지금 막혀?"),
]

EXAMPLE_PILLS = [
    "부산 날씨 어때?",
    "서울 → 광주 통행료",
    "속초 카페 추천",
    "전주 한옥마을 볼거리",
]

RECENT_CHATS = [
    "제주도 2박 3일 여행 계획",
    "부산 해운대 맛집 추천",
    "서울 → 강릉 교통 정보",
    "경주 역사 관광지",
]


# ── CSS 로드 ──────────────────────────────────────
def load_css(path: str):
    with open(path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ── 페이지 설정 ───────────────────────────────────
st.set_page_config(page_title="TravelMate KR", page_icon="🗺️", layout="wide")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_css(os.path.join(BASE_DIR, "style.css"))

# ── 세션 초기화 ───────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

if "openai_client" not in st.session_state:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OPENAI_API_KEY가 .env에 설정되지 않았습니다.")
        st.stop()
    st.session_state.openai_client = OpenAI(api_key=api_key)

client: OpenAI = st.session_state.openai_client


# ── 지도링크 카드 렌더링 ──────────────────────────
def render_place_cards(items: list, name_key: str, category_key: str,
                       address_key: str, tel_key: str, link_key: str):
    for item in items:
        name     = item.get(name_key, "")
        category = item.get(category_key, "")
        address  = item.get(address_key, "")
        tel      = item.get(tel_key, "")
        link     = item.get(link_key, "")
        map_btn  = (
            f'<a href="{link}" target="_blank" style="display:inline-block;margin-top:10px;'
            f'padding:6px 14px;background:#FDCB6E;color:#3A2E12;border-radius:8px;'
            f'font-size:12px;font-weight:700;text-decoration:none;">🗺️ 지도보기</a>'
            if link else ""
        )
        st.markdown(
            f"""
            <div style="border:1px solid #F0EBE0;border-radius:14px;
                        padding:14px 16px;margin-bottom:10px;background:#FFFFFF;
                        box-shadow:0 4px 12px -8px rgba(120,100,50,.2);">
                <div style="font-size:15px;font-weight:700;color:#2B2722;">
                    {name}
                    <span style="font-size:12px;font-weight:400;color:#B6AD99;
                                 margin-left:8px;">{category}</span>
                </div>
                <div style="font-size:13px;color:#6B655A;margin-top:5px;">📍 {address}</div>
                <div style="font-size:13px;color:#6B655A;margin-top:3px;">📞 {tel}</div>
                {map_btn}
            </div>
            """,
            unsafe_allow_html=True,
        )


# ── 렌트카/편의시설 결과 렌더링 ───────────────────
def render_facility_result(func_name: str, result: dict):
    with st.chat_message("assistant"):
        if func_name == "search_rentcar":
            items = result.get("렌트카업체목록", [])
            if items:
                st.markdown(f"**🚙 렌트카 업체 검색 결과** ({result.get('검색어', '')})")
                render_place_cards(items, "이름", "카테고리", "주소", "전화번호", "지도링크")
            else:
                st.markdown(result.get("message") or result.get("error") or "검색 결과가 없습니다.")

        elif func_name == "search_facilities":
            items = result.get("편의시설목록", [])
            facility_type = result.get("시설종류", "편의시설")
            if items:
                st.markdown(f"**🏪 {facility_type} 검색 결과** ({result.get('검색어', '')})")
                render_place_cards(items, "이름", "카테고리", "주소", "전화번호", "지도링크")
            else:
                st.markdown(result.get("message") or result.get("error") or "검색 결과가 없습니다.")


# ── 숙박시설 결과 렌더링 ──────────────────────────
def render_stay_result(result: dict, destination: str | None = None):
    """recommend_stay_place 결과를 간단한 카드형 목록으로 렌더링."""
    with st.chat_message("assistant"):
        title_destination = destination or result.get("destination", "")
        st.markdown(f"**🏨 {title_destination} 추천 숙박시설**")

        items = result.get("results", []) if isinstance(result, dict) else []
        if not items:
            st.markdown(
                result.get("message")
                or result.get("error")
                or "숙박시설 정보를 가져오지 못했습니다."
            )
            return

        for s in items:
            name = s.get("name", "숙소명 정보 없음")
            stay_type = s.get("stay_type", "숙박")
            price = s.get("estimated_price_range", "가격 확인 필요")
            address = s.get("address", "주소 정보 확인 필요")
            check_in = s.get("check_in", "정보 확인 필요")
            check_out = s.get("check_out", "정보 확인 필요")
            parking = s.get("parking", "정보 확인 필요")
            naver_link = s.get("naver_map_url") or ""
            kakao_link = s.get("kakao_map_url") or ""
            homepage_link = s.get("official_homepage_url") or s.get("homepage") or ""
            blog_summary = s.get("blog_review_summary", "")

            line = f"- **{name}** ({stay_type}, {price}) — {address}"
            links = []
            if naver_link:
                links.append(f"[🗺️ 네이버지도]({naver_link})")
            if kakao_link:
                links.append(f"[📍 카카오맵]({kakao_link})")
            if homepage_link and homepage_link.startswith(("http://", "https://")):
                links.append(f"[🏠 공식홈페이지]({homepage_link})")
            blog_links = s.get("blog_links") or []
            if blog_links:
                links.append(f"[📝 블로그후기]({blog_links[0]})")
            if links:
                line += "  " + " · ".join(links)
            st.markdown(line)
            st.caption(f"체크인 {check_in} · 체크아웃 {check_out} · 주차 {parking}")
            if blog_summary and blog_summary != "후기 정보 부족":
                st.caption(f"후기 요약: {blog_summary}")

        notice = result.get("notice")
        if notice:
            st.caption(f"참고: {notice}")


# ── 사이드바 ──────────────────────────────────────
with st.sidebar:
    st.markdown(C.sidebar_header(), unsafe_allow_html=True)

    if st.button("＋  새 대화 시작하기", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown(C.sidebar_recent_label(), unsafe_allow_html=True)
    for r in RECENT_CHATS:
        st.markdown(C.sidebar_recent_item(r), unsafe_allow_html=True)

    st.markdown("<hr style='margin:16px 0;'>", unsafe_allow_html=True)
    st.markdown(C.sidebar_api_label(), unsafe_allow_html=True)

    for key, label in [
        ("OPENAI_API_KEY",  "OpenAI API"),
        ("WEATHER_API_KEY", "OpenWeatherMap"),
        ("NAVER_CLIENT_ID", "네이버 오픈 API"),
        ("TOUR_API_KEY",    "한국관광공사 TourAPI"),
        ("EX_API_KEY",      "한국도로공사 API"),
    ]:
        icon = "✅" if os.getenv(key) else "❌"
        st.markdown(C.sidebar_api_status(icon, label), unsafe_allow_html=True)

    st.markdown(C.sidebar_footer(), unsafe_allow_html=True)


# ── 메인 영역 ─────────────────────────────────────
if not st.session_state.messages:
    st.markdown(C.home_hero(), unsafe_allow_html=True)

    cols = st.columns(4)
    for i, (icon, bg, text) in enumerate(EXAMPLE_CARDS):
        with cols[i]:
            st.markdown(C.suggestion_card(icon, bg, text), unsafe_allow_html=True)
            if st.button(text, key=f"card_{i}", use_container_width=True):
                st.session_state["pending_input"] = text

    cols2 = st.columns(len(EXAMPLE_PILLS))
    for i, ex in enumerate(EXAMPLE_PILLS):
        with cols2[i]:
            if st.button(ex, key=f"pill_{i}", use_container_width=True):
                st.session_state["pending_input"] = ex

else:
    for msg in st.session_state.messages:
        if msg["role"] in ("user", "assistant"):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])



# ── 일정 파이프라인 입력값 보정 유틸 ───────────────────
def normalize_trip_destination(destination: str | None, raw_user_input: str = "") -> str:
    """
    LLM이 destination에 "강릉 2박 3일 여행 일정 추천해줘"처럼 전체 문장을 넣는 경우를 방지한다.
    """
    text = (destination or raw_user_input or "").strip()
    if not text:
        return ""

    # "서울에서 강릉 2박 3일"처럼 출발지가 섞인 경우 목적지 쪽만 남긴다.
    text = re.sub(r".*에서\s+", "", text)
    text = re.sub(r".*→\s*", "", text)

    # 기간/요청 표현 제거
    text = re.sub(r"\d+\s*박\s*\d+\s*일", "", text)
    text = re.sub(r"당일치기|여행|일정|계획|코스|추천|짜줘|해줘|알려줘|부탁해|찾아줘", "", text)

    # LLM이 destination에 "강릉 추천 숙박시설"처럼 숙박 관련 단어까지 넣는 경우 방어
    text = re.sub(
        r"숙박시설|숙박|숙소|호텔|펜션|게스트하우스|리조트|풀빌라|고급호텔|감성숙소|가성비",
        "",
        text,
    )

    text = re.sub(r"[,.!?~]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def parse_trip_period(raw_user_input: str = "", duration_value=None) -> tuple[int, str]:
    """
    '2박 3일' → (2, '2박 3일')
    '당일치기' → (0, '당일치기')
    명시 기간이 없으면 generate_itinerary가 쓰던 duration 값을 유지한다.
    """
    text = str(raw_user_input or "")

    match = re.search(r"(\d+)\s*박\s*(\d+)\s*일", text)
    if match:
        nights = int(match.group(1))
        days = int(match.group(2))
        return nights, f"{nights}박 {days}일"

    if "당일치기" in text:
        return 0, "당일치기"

    try:
        nights = int(duration_value)
    except Exception:
        nights = 1

    if nights <= 0:
        return 0, "당일치기"
    return nights, f"{nights}박 {nights + 1}일"


def infer_stay_type_from_style(style: str | None) -> str | None:
    """일정 스타일을 숙소 검색용 stay_type으로 느슨하게 변환한다."""
    text = str(style or "")
    if any(k in text for k in ["감성", "힐링", "휴식"]):
        return "감성숙소"
    if any(k in text for k in ["가족", "아이"]):
        return "가족 숙소"
    if any(k in text for k in ["럭셔리", "프리미엄", "고급"]):
        return "고급호텔"
    if any(k in text for k in ["가성비", "실속", "저렴"]):
        return "가성비 숙소"
    return None


def infer_price_range_from_text(text: str = "") -> str | None:
    """사용자 문장 안에 가격대 힌트가 있으면 숙박 Tool에 전달한다."""
    compact = str(text or "").replace(" ", "")
    if any(k in compact for k in ["10만원미만", "10만미만", "가성비", "저렴"]):
        return "10만원 미만"
    if any(k in compact for k in ["20만원미만", "20만미만"]):
        return "20만원 미만"
    if any(k in compact for k in ["30만원미만", "30만미만"]):
        return "30만원 미만"
    if any(k in compact for k in ["30만원이상", "30만이상", "고급호텔", "럭셔리"]):
        return "30만원 이상"
    return None


def call_generate_itinerary_with_optional_stay(
    *,
    destination: str,
    duration: int,
    style: str,
    origin: str | None,
    attractions_data: dict,
    restaurants_data: dict,
    stay_data: dict,
    weather_data: dict,
    transit_data: dict | None,
) -> dict:
    """
    tool_itinerary.generate_itinerary가 stay_data 파라미터를 아직 지원하지 않아도
    앱이 죽지 않도록 TypeError 시 기존 인자만으로 재호출한다.
    """
    common_kwargs = {
        "destination": destination,
        "duration": duration,
        "style": style,
        "origin": origin,
        "attractions_data": attractions_data,
        "restaurants_data": restaurants_data,
        "weather_data": weather_data,
        "transit_data": transit_data,
    }

    try:
        result = generate_itinerary(**common_kwargs, stay_data=stay_data)
    except TypeError:
        result = generate_itinerary(**common_kwargs)

    if isinstance(result, dict):
        result.setdefault("stay_data", stay_data)
        result.setdefault("pipeline_data", {})
        result["pipeline_data"].update({
            "attractions_data": attractions_data,
            "restaurants_data": restaurants_data,
            "stay_data": stay_data,
            "weather_data": weather_data,
            "transit_data": transit_data,
        })
        return result

    return {
        "itinerary_result": result,
        "stay_data": stay_data,
        "pipeline_data": {
            "attractions_data": attractions_data,
            "restaurants_data": restaurants_data,
            "stay_data": stay_data,
            "weather_data": weather_data,
            "transit_data": transit_data,
        },
    }


# ── 일정 생성 단계별 파이프라인 ───────────────────
def run_itinerary_pipeline(itin_args: dict, raw_user_input: str = "") -> dict:
    raw_destination = itin_args.get("destination")
    destination = normalize_trip_destination(raw_destination, raw_user_input)
    if not destination:
        destination = raw_destination or ""

    duration, travel_period_text = parse_trip_period(raw_user_input, itin_args.get("duration", 1))
    style = itin_args.get("style", "힐링")
    origin = itin_args.get("origin")

    status_ph = st.empty()

    # 1) 관광지
    status_ph.info("📍 관광지 검색 중...")
    try:
        attractions_data = search_attractions(destination, travel_style=style)
    except Exception as e:
        attractions_data = {"error": str(e)}

    # 2) 맛집
    status_ph.info("🍽️ 맛집 검색 중...")
    try:
        restaurants_data = search_restaurants(destination)
    except Exception as e:
        restaurants_data = {"error": str(e)}

    # 3) 숙박시설
    if duration <= 0:
        stay_data = {
            "destination": destination,
            "travel_date": travel_period_text,
            "results": [],
            "message": "당일치기 일정이라 숙박시설 검색을 생략했습니다.",
        }
    else:
        status_ph.info("🏨 숙박시설 검색 중...")
        try:
            stay_data = recommend_stay_place(
                destination=destination,
                travel_date=travel_period_text,
                price_range=infer_price_range_from_text(raw_user_input),
                stay_type=infer_stay_type_from_style(style),
                limit=3,
            )
        except Exception as e:
            stay_data = {"error": str(e), "results": []}

    # 4) 날씨
    status_ph.info("🌤️ 날씨 정보 조회 중...")
    try:
        weather_data = get_weather(destination, min(duration + 1, 5))
    except Exception as e:
        weather_data = {"error": str(e)}

    # 5) 교통
    transit_data = None
    if origin:
        status_ph.info("🚗 교통 정보 조회 중...")
        try:
            transit_data = get_highway_traffic(origin, destination)
        except Exception as e:
            transit_data = {"error": str(e)}

    # 6) 일정 생성
    status_ph.info("📅 여행 일정 생성 중...")
    result = call_generate_itinerary_with_optional_stay(
        destination=destination,
        duration=duration,
        style=style,
        origin=origin,
        attractions_data=attractions_data,
        restaurants_data=restaurants_data,
        stay_data=stay_data,
        weather_data=weather_data,
        transit_data=transit_data,
    )
    status_ph.empty()

    # 7) 결과 순서대로 출력
    with st.chat_message("assistant"):
        st.markdown(f"**📍 {destination} 추천 관광지**")
        if attractions_data and attractions_data.get("results"):
            for a in attractions_data["results"]:
                link = a.get("naver_map_url", "")
                line = f"- **{a.get('name')}** ({a.get('category')}) — {a.get('address')}"
                if link:
                    line += f"  [🗺️ 지도]({link})"
                st.markdown(line)
        else:
            st.markdown("관광지 정보를 가져오지 못했습니다.")

    with st.chat_message("assistant"):
        st.markdown(f"**🍽️ {destination} 추천 맛집**")
        if restaurants_data and restaurants_data.get("맛집목록"):
            for r in restaurants_data["맛집목록"]:
                link = r.get("지도링크", "")
                line = f"- **{r.get('이름')}** ({r.get('카테고리')}) — {r.get('주소')}"
                if link:
                    line += f"  [🗺️ 지도]({link})"
                st.markdown(line)
        else:
            st.markdown("맛집 정보를 가져오지 못했습니다.")

    with st.chat_message("assistant"):
        st.markdown(f"**🏨 {destination} 추천 숙박시설**")
        if stay_data and stay_data.get("results"):
            for s in stay_data["results"]:
                naver_link = s.get("naver_map_url") or ""
                kakao_link = s.get("kakao_map_url") or ""
                homepage_link = s.get("official_homepage_url") or s.get("homepage") or ""
                line = (
                    f"- **{s.get('name')}** "
                    f"({s.get('stay_type', '숙박')}, {s.get('estimated_price_range', '가격 확인 필요')}) "
                    f"— {s.get('address', '주소 정보 확인 필요')}"
                )
                links = []
                if naver_link:
                    links.append(f"[🗺️ 네이버지도]({naver_link})")
                if kakao_link:
                    links.append(f"[📍 카카오맵]({kakao_link})")
                if homepage_link and homepage_link.startswith(("http://", "https://")):
                    links.append(f"[🏠 공식홈페이지]({homepage_link})")
                blog_links = s.get("blog_links") or []
                if blog_links:
                    links.append(f"[📝 블로그후기]({blog_links[0]})")
                if links:
                    line += "  " + " · ".join(links)
                st.markdown(line)
                st.caption(
                    f"체크인 {s.get('check_in', '정보 확인 필요')} · "
                    f"체크아웃 {s.get('check_out', '정보 확인 필요')} · "
                    f"주차 {s.get('parking', '정보 확인 필요')}"
                )
        else:
            st.markdown(stay_data.get("message") or stay_data.get("error") or "숙박시설 정보를 가져오지 못했습니다.")

    with st.chat_message("assistant"):
        st.markdown(f"**🌤️ {destination} 날씨**")
        if weather_data and not weather_data.get("error"):
            st.markdown(
                f"- 현재: {weather_data.get('날씨')}, {weather_data.get('현재기온')} "
                f"(체감 {weather_data.get('체감기온')})"
            )
            st.markdown(f"- 옷차림: {weather_data.get('옷차림추천')}")
        else:
            st.markdown("날씨 정보를 가져오지 못했습니다.")

    if origin:
        with st.chat_message("assistant"):
            st.markdown(f"**🚗 {origin} → {destination} 교통 정보**")
            if transit_data and not transit_data.get("error"):
                st.markdown(f"- {transit_data.get('route', '')} 관련 정보 확인 완료")
            else:
                st.markdown("교통 정보를 가져오지 못했습니다.")

    return result


# ── 입력 & LLM 처리 ──────────────────────────────
user_input = st.chat_input("여행지와 기간을 입력하세요… (예: 제주도 2박 3일 여행 계획 짜줘)")

if "pending_input" in st.session_state:
    user_input = st.session_state.pop("pending_input")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    status_ph = st.empty()

    api_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in st.session_state.messages:
        if msg["role"] in ("user", "assistant") and msg.get("content"):
            api_messages.append({"role": msg["role"], "content": msg["content"]})

    status_ph.info("🤔 생각 중...")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=api_messages,
            tools=ALL_TOOLS,
            tool_choice="auto",
        )
    except Exception as e:
        st.error(f"LLM 호출 오류: {e}")
        st.stop()

    msg_obj = response.choices[0].message

    if not msg_obj.tool_calls:
        status_ph.empty()
        final_answer = msg_obj.content or ""
        with st.chat_message("assistant"):
            st.markdown(final_answer)
        st.session_state.messages.append({"role": "assistant", "content": final_answer})

    else:
        api_messages.append(msg_obj)
        status_ph.empty()

        for tool_call in msg_obj.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            if func_name == "generate_itinerary":
                result = run_itinerary_pipeline(func_args, raw_user_input=user_input)

            elif func_name in ("search_rentcar", "search_facilities"):
                status_ph.info(TOOL_STATUS_MSG.get(func_name, f"⚙️ {func_name} 실행 중..."))
                func   = TOOL_FUNC_MAP.get(func_name)
                result = func(**func_args) if func else {"error": f"알 수 없는 tool: {func_name}"}
                status_ph.empty()
                render_facility_result(func_name, result)

            elif func_name in ("recommend_stay_place", "search_accommodations"):
                status_ph.info(TOOL_STATUS_MSG.get(func_name, f"⚙️ {func_name} 실행 중..."))
                func   = TOOL_FUNC_MAP.get(func_name)
                result = func(**func_args) if func else {"error": f"알 수 없는 tool: {func_name}"}
                status_ph.empty()
                render_stay_result(result, destination=func_args.get("destination"))

            else:
                status_ph.info(TOOL_STATUS_MSG.get(func_name, f"⚙️ {func_name} 실행 중..."))
                func   = TOOL_FUNC_MAP.get(func_name)
                result = func(**func_args) if func else {"error": f"알 수 없는 tool: {func_name}"}
                status_ph.empty()

            api_messages.append({
                "role":         "tool",
                "tool_call_id": tool_call.id,
                "content":      json.dumps(result, ensure_ascii=False),
            })

        status_ph.info("✍️ 최종 답변 정리 중...")
        try:
            final_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=api_messages,
            )
            final_answer = final_response.choices[0].message.content or ""
        except Exception as e:
            final_answer = f"답변 생성 중 오류가 발생했습니다: {e}"

        status_ph.empty()
        with st.chat_message("assistant"):
            st.markdown(final_answer)
        st.session_state.messages.append({"role": "assistant", "content": final_answer})