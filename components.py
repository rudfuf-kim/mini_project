"""
components.py — UI HTML 조각 함수 모음
app.py에서 import해서 사용합니다.
"""

def sidebar_header() -> str:
    return """
    <div style="display:flex; align-items:center; gap:10px; padding:4px 4px 20px;">
        <div style="width:34px; height:34px; border-radius:11px; background:#FDCB6E;
                    display:flex; align-items:center; justify-content:center; font-size:18px;">🗺️</div>
        <span style="font-size:19px; font-weight:800; color:#322E29; letter-spacing:-.01em;">
            여키어때
        </span>
    </div>
    """


def sidebar_recent_label() -> str:
    return """
    <div style="font-size:11.5px; font-weight:700; color:#B6AD99;
                letter-spacing:.05em; padding:22px 4px 10px;">최근 대화</div>
    """


def sidebar_recent_item(text: str) -> str:
    return f"""
    <div style="padding:10px 12px; border-radius:11px; color:#6B655A;
                font-size:13.5px; cursor:pointer;">🕐 {text}</div>
    """


def sidebar_api_label() -> str:
    return """
    <div style="font-size:11.5px; font-weight:700; color:#B6AD99;
                letter-spacing:.05em; padding:0 4px 10px;">API 연결 상태</div>
    """


def sidebar_api_status(icon: str, label: str) -> str:
    return f"""
    <div style="font-size:13px; color:#6B655A; padding:3px 4px;">{icon} {label}</div>
    """


def sidebar_footer() -> str:
    return """
    <div style="font-size:11px; color:#C5BCA8; padding:20px 4px 0;">
        TravelMate KR v1.1
    </div>
    """


def home_hero() -> str:
    return """
    <div style="text-align:center; padding: 2.5rem 0 1.5rem;">
        <div style="width:72px; height:72px; border-radius:24px; background:#FDCB6E;
                    display:flex; align-items:center; justify-content:center;
                    font-size:38px; margin: 0 auto 22px;
                    box-shadow:0 16px 36px -14px rgba(253,203,110,.85);">🗺️</div>
        <h1 style="font-size:32px; font-weight:800; color:#2B2722;
                   letter-spacing:-.02em; margin:0 0 10px;">
            어디로 떠나볼까요?
        </h1>
        <p style="font-size:15px; color:#8A8170; margin:0;">
            날씨, 맛집, 관광지, 일정, 교통까지 한번에 알려드릴게요.
        </p>
    </div>
    """


def pill_section_divider(label: str = "빠른 질문") -> str:
    return f"""
    <div class="pill-section-divider">
        <span>{label}</span>
    </div>
    """


def suggestion_card(icon: str, bg: str, text: str) -> str:
    return f"""
    <div class="suggestion-card">
        <div class="icon-box" style="background:{bg};">{icon}</div>
        <div class="card-title">{text}</div>
    </div>
    """
