"""
components.py — UI HTML 조각 함수 모음
app.py에서 import해서 사용합니다.
"""

def sidebar_header() -> str:
    return """
    <div style="padding:6px 2px 18px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
            <div style="width:34px; height:34px; border-radius:11px;
                        background:linear-gradient(135deg, #EC0B8C, #C80670);
                        display:flex; align-items:center; justify-content:center;
                        color:#ffffff; font-size:18px; font-weight:900;
                        box-shadow:0 8px 20px -10px rgba(236,11,140,.55);">✈</div>
            <span style="font-size:20px; font-weight:900; color:#ffffff; letter-spacing:-.02em;">
                여<span style="color:#EC0B8C;">키</span>어때
            </span>
        </div>
        <div style="display:flex; align-items:flex-end; gap:4px; padding-left:2px;">
            <span style="font-size:19px; font-weight:900; color:#ffffff; letter-spacing:-.03em;">K</span>
            <span style="font-size:19px; font-weight:900; color:#ffffff; letter-spacing:-.03em;">D</span>
            <span style="font-size:19px; font-weight:900; color:#EC0B8C; letter-spacing:-.03em;">A</span>
        </div>
    </div>
    """


def sidebar_recent_label() -> str:
    return """
    <div style="font-size:11.5px; font-weight:800; color:#AFC2E8;
                letter-spacing:.06em; padding:20px 4px 10px;">최근 대화</div>
    """


def sidebar_recent_item(text: str) -> str:
    return f"""
    <div style="padding:10px 12px; border-radius:11px; color:#E6EEFF;
                font-size:13.5px; cursor:pointer; background:rgba(255,255,255,.04);
                border:1px solid rgba(255,255,255,.05); margin-bottom:6px;">🕐 {text}</div>
    """


def sidebar_api_label() -> str:
    return """
    <div style="font-size:11.5px; font-weight:800; color:#AFC2E8;
                letter-spacing:.06em; padding:2px 4px 10px;">API 연결 상태</div>
    """


def sidebar_api_status(icon: str, label: str) -> str:
    return f"""
    <div style="font-size:13px; color:#E6EEFF; padding:4px 4px;">{icon} {label}</div>
    """


def sidebar_footer() -> str:
    return """
    <div style="font-size:11px; color:#8EA8DA; padding:20px 4px 0;">
        여키어때 · KDA Edition
    </div>
    """


def home_hero() -> str:
    return """
    <div style="text-align:center; padding: 2.3rem 0 1.7rem;">
        <div style="display:inline-flex; flex-direction:column; align-items:center; gap:16px;">
            <div style="display:flex; align-items:flex-end; gap:14px;">
                <div style="font-size:76px; line-height:1; font-weight:900; color:#062A73; letter-spacing:-.06em;">
                    여<span style="color:#EC0B8C;">키</span>어때
                </div>
                <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; transform: translateY(-10px);">
                    <div style="font-size:54px; color:#EC0B8C; line-height:1;">✈</div>
                    <div style="width:72px; height:10px; border-radius:999px;
                                background:linear-gradient(90deg, rgba(236,11,140,.0), rgba(236,11,140,.9)); transform:rotate(-48deg) translateY(-6px);"></div>
                </div>
            </div>
            <div style="display:flex; align-items:flex-end; gap:6px; margin-top:-10px;">
                <span style="font-size:54px; font-weight:900; color:#062A73; letter-spacing:-.04em;">K</span>
                <span style="font-size:54px; font-weight:900; color:#062A73; letter-spacing:-.04em;">D</span>
                <span style="font-size:54px; font-weight:900; color:#EC0B8C; letter-spacing:-.04em;">A</span>
            </div>
        </div>
        <h1 style="font-size:30px; font-weight:850; color:#102A57;
                   letter-spacing:-.02em; margin:22px 0 10px;">
            국내 여행을 더 똑똑하고 편하게
        </h1>
        <p style="font-size:15px; color:#49627E; margin:0;">
            날씨, 맛집, 관광지, 숙박, 일정, 교통까지 한 번에 추천해드릴게요.
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
