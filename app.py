"""
TravelMate KR — 국내 여행 플래너 챗봇
Streamlit + OpenAI Function Calling + 5가지 Tool
"""

import json
import os
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

from tool_weather    import get_weather,                           TOOL_SCHEMA  as WEATHER_SCHEMA
from tool_restaurant import search_restaurants,                    TOOL_SCHEMA  as RESTAURANT_SCHEMA
from tool_attraction import search_attractions,                    TOOL_SCHEMA  as ATTRACTION_SCHEMA
from tool_itinerary  import generate_itinerary,                    TOOL_SCHEMA  as ITINERARY_SCHEMA
from tool_transit    import get_highway_traffic, get_highway_fare, TOOL_SCHEMAS as TRANSIT_SCHEMAS
import components as C

load_dotenv()

# ── 상수 ──────────────────────────────────────────
ALL_TOOLS = [
    WEATHER_SCHEMA, RESTAURANT_SCHEMA, ATTRACTION_SCHEMA,
    ITINERARY_SCHEMA, *TRANSIT_SCHEMAS,
]

TOOL_FUNC_MAP = {
    "get_weather":          get_weather,
    "search_restaurants":   search_restaurants,
    "search_attractions":   search_attractions,
    "generate_itinerary":   generate_itinerary,
    "get_highway_traffic":  get_highway_traffic,
    "get_highway_fare":     get_highway_fare,
}

TOOL_STATUS_MSG = {
    "get_weather":         "🌤️ 날씨 정보 조회 중...",
    "search_restaurants":  "🍽️ 맛집 검색 중...",
    "search_attractions":  "📍 관광지 검색 중...",
    "generate_itinerary":  "📅 여행 일정 생성 중...",
    "get_highway_traffic": "🚗 고속도로 소통 정보 조회 중...",
    "get_highway_fare":    "🪙 통행요금 조회 중...",
}

SYSTEM_PROMPT = """당신은 대한민국 국내 여행 전문 플래너 챗봇 'TravelMate KR'입니다.

사용자가 국내 여행과 관련된 질문을 하면 제공된 도구(tool)를 적절히 활용해 답변하세요.

도구 사용 원칙:
- 날씨 질문 → get_weather
- 맛집·식당·카페 질문 → search_restaurants
- 관광지·명소·볼거리 질문 → search_attractions
- 여행 일정·코스·계획 질문 → generate_itinerary (날씨·맛집·관광지 tool도 함께 사용)
- 고속도로 소통·혼잡 질문 → get_highway_traffic
- 통행요금·고속도로 비용 질문 → get_highway_fare

답변 규칙:
- 한국어로 친근하게 답변하세요.
- tool 결과를 그대로 나열하지 말고, 자연스러운 문장으로 요약·정리하세요.
- 여행 팁이나 추천 이유를 함께 제공하면 좋습니다.
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
        ("OPENAI_API_KEY",      "OpenAI API"),
        ("OPENWEATHER_API_KEY", "OpenWeatherMap"),
        ("NAVER_CLIENT_ID",     "네이버 오픈 API"),
        ("EX_API_KEY",          "한국도로공사 API"),
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
    st.markdown(C.pill_section_divider(), unsafe_allow_html=True)
    st.markdown('<div class="pill-row">', unsafe_allow_html=True)
    cols2 = st.columns(len(EXAMPLE_PILLS))
    for i, ex in enumerate(EXAMPLE_PILLS):
        with cols2[i]:
            if st.button(ex, key=f"pill_{i}", use_container_width=True):
                st.session_state["pending_input"] = ex
    st.markdown('</div>', unsafe_allow_html=True)

else:
    for msg in st.session_state.messages:
        if msg["role"] in ("user", "assistant"):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])


# ── 입력 & LLM 처리 ──────────────────────────────
user_input = st.chat_input("여행지와 기간을 입력하세요… (예: 제주도 2박 3일 여행 계획 짜줘)")

if "pending_input" in st.session_state:
    user_input = st.session_state.pop("pending_input")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        status_ph = st.empty()
        answer_ph = st.empty()

        api_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in st.session_state.messages:
            if msg["role"] in ("user", "assistant") and msg.get("content"):
                api_messages.append({"role": msg["role"], "content": msg["content"]})

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
            final_answer = msg_obj.content or ""
            answer_ph.markdown(final_answer)
            st.session_state.messages.append({"role": "assistant", "content": final_answer})

        else:
            api_messages.append(msg_obj)

            for tool_call in msg_obj.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                status_ph.info(TOOL_STATUS_MSG.get(func_name, f"⚙️ {func_name} 실행 중..."))

                func = TOOL_FUNC_MAP.get(func_name)
                result = func(**func_args) if func else {"error": f"알 수 없는 tool: {func_name}"}

                api_messages.append({
                    "role":         "tool",
                    "tool_call_id": tool_call.id,
                    "content":      json.dumps(result, ensure_ascii=False),
                })

            status_ph.info("✍️ 답변 생성 중...")

            try:
                final_response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=api_messages,
                )
                final_answer = final_response.choices[0].message.content or ""
            except Exception as e:
                final_answer = f"답변 생성 중 오류가 발생했습니다: {e}"

            status_ph.empty()
            answer_ph.markdown(final_answer)
            st.session_state.messages.append({"role": "assistant", "content": final_answer})
