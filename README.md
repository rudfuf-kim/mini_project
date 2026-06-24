# 🗺️ TravelMate KR — 국내 여행 플래너 챗봇

Streamlit + OpenAI Function Calling 기반 국내 여행 올인원 챗봇

## 📁 프로젝트 구조

```
travelmate/
├── app.py                # Streamlit 메인 앱 (UI + Tool Calling 통합)
├── tool_weather.py       # Tool 1 — 날씨 조회 (OpenWeatherMap)
├── tool_restaurant.py    # Tool 2 — 맛집 검색 (네이버 지역검색)
├── tool_attraction.py    # Tool 3 — 관광지 검색 (네이버 블로그검색)
├── tool_itinerary.py     # Tool 4 — 여행 일정 생성 (GPT-4o mini)
├── tool_transit.py       # Tool 5 — 교통정보 (한국도로공사 API)
├── requirements.txt
├── .env.example
└── README.md
```

## 🚀 실행 방법

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. API 키 설정
```bash
cp .env.example .env
# .env 파일을 열어 각 API 키 입력
```

### 3. 앱 실행
```bash
streamlit run app.py
```

## 🔑 API 키 발급

| API | 발급처 | 비용 |
|-----|--------|------|
| OpenAI | https://platform.openai.com | 소액 유료 |
| OpenWeatherMap | https://openweathermap.org/api | 무료 |
| 네이버 오픈 API | https://developers.naver.com | 무료 |
| 한국도로공사 | https://data.ex.co.kr | 무료 |

## 💬 사용 예시

- `"제주도 2박 3일 힐링 여행 계획 짜줘"`
- `"부산 날씨 어때? 이번 주말에 가려고"`
- `"강릉 해산물 맛집 추천해줘"`
- `"경주 역사 관광지 알려줘"`
- `"서울에서 부산 고속도로 지금 막혀?"`
- `"서울에서 광주 소형차 통행료 얼마야?"`
