# NoteSlide

PDF/이미지 슬라이드를 **편집 가능한 PowerPoint(PPTX)**로 변환하는 AI 기반 웹 도구입니다.

## ✨ 주요 기능

- **픽셀 퍼펙트 변환** — 원본 레이아웃, 폰트, 스타일을 정확히 재현
- **AI 기반 인식** — Gemini Vision으로 텍스트, 그래픽, 슬라이드 구조 인식
- **3단계 폴백** — 직접 추출 → AI Vision → 이미지 배경

## 🚀 실행 방법

```bash
# 의존성 설치
pip install -r requirements.txt

# 서버 실행
python app.py
```

브라우저에서 `http://localhost:5000` 접속

## 🔑 AI Vision 활성화 (선택)

`.env` 파일을 생성하고 Gemini API 키를 설정:

```
GEMINI_API_KEY=your_api_key_here
```

## 🛠 기술 스택

- **Backend**: Python, Flask, PyMuPDF, python-pptx
- **Frontend**: HTML, CSS (다크 테마), JavaScript
- **AI**: Google Gemini Vision API

## 📁 프로젝트 구조

```
noteslide/
├── app.py                  # Flask 서버
├── modules/
│   ├── pdf_processor.py    # PDF 텍스트/이미지 추출
│   ├── ai_analyzer.py      # Gemini Vision 분석
│   └── pptx_builder.py     # PPTX 생성
├── templates/index.html    # 메인 페이지
├── static/
│   ├── css/style.css       # 스타일시트
│   └── js/main.js          # 프론트엔드 로직
└── requirements.txt
```

## License

MIT
