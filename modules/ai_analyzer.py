"""
AI 분석 모듈
- Gemini Vision API를 사용하여 슬라이드 이미지의 구조를 분석
- 텍스트 블록, 도형, 색상, 레이아웃 정보를 JSON으로 반환
"""

import google.generativeai as genai
from PIL import Image
import json
import os
import re
import sys
from dataclasses import dataclass, field


@dataclass
class SlideElement:
    """AI가 인식한 슬라이드 요소"""
    type: str  # "text", "image", "shape"
    content: str = ""
    x: float = 0  # 백분율 (0-100)
    y: float = 0
    width: float = 0
    height: float = 0
    font_size: int = 14
    font_color: str = "#000000"
    background_color: str = ""
    bold: bool = False
    italic: bool = False
    alignment: str = "left"  # left, center, right


@dataclass
class SlideLayout:
    """AI가 분석한 슬라이드 레이아웃"""
    elements: list = field(default_factory=list)
    background_color: str = "#FFFFFF"
    slide_width: float = 960
    slide_height: float = 540


def _log(msg):
    """로그 출력"""
    print(f"  [AI] {msg}", flush=True)


# Gemini에 보낼 분석 프롬프트
ANALYSIS_PROMPT = """You are an expert presentation slide analyzer. Analyze this slide image and extract ALL visual elements into a structured JSON format.

For each element, identify:
1. **Text blocks**: All text content with approximate position, font size, color, and styling
2. **Images/Graphics**: Areas containing images or graphics (NOT background)
3. **Shapes**: Background shapes, colored boxes, dividers, decorative elements

Return a JSON object with this exact structure:
{
    "background_color": "#hex_color",
    "elements": [
        {
            "type": "text",
            "content": "the actual text content here",
            "x": 5,
            "y": 10,
            "width": 40,
            "height": 8,
            "font_size": 24,
            "font_color": "#333333",
            "bold": true,
            "italic": false,
            "alignment": "left"
        },
        {
            "type": "shape",
            "x": 0,
            "y": 0,
            "width": 100,
            "height": 15,
            "background_color": "#2c3e50"
        },
        {
            "type": "image",
            "x": 60,
            "y": 20,
            "width": 35,
            "height": 60
        }
    ]
}

CRITICAL RULES:
- All positions (x, y, width, height) are PERCENTAGES (0-100) relative to the full slide
- Extract EVERY piece of text visible on the slide
- Keep multi-line text together in one element using newline characters
- Title text is usually 24-44pt, subtitle 18-24pt, body text 14-18pt, small text 10-12pt
- Detect colors as precisely as possible in #RRGGBB hex format
- For text alignment: use "center" for centered text, "left" for left-aligned, "right" for right-aligned
- Include ALL shapes/boxes/containers as "shape" elements with their background colors
- Order elements: shapes first (background layer), then text (foreground), then images
- Return ONLY valid JSON, nothing else - no markdown, no explanation"""


def _configure_api():
    """Gemini API 설정"""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY 환경변수가 설정되지 않았습니다. "
            ".env 파일에 API 키를 설정해주세요."
        )
    genai.configure(api_key=api_key)
    return api_key


def analyze_slide(image: Image.Image, slide_num: int = 0) -> SlideLayout:
    """
    슬라이드 이미지를 AI Vision으로 분석하여 구조화된 레이아웃을 반환합니다.
    """
    api_key = _configure_api()
    _log(f"슬라이드 {slide_num} 분석 시작 (이미지 크기: {image.size})")

    model = genai.GenerativeModel("gemini-2.0-flash")

    # 이미지 크기 제한 (API 비용 절약 + 빠른 응답)
    max_dim = 1920
    if max(image.size) > max_dim:
        ratio = max_dim / max(image.size)
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image = image.resize(new_size, Image.LANCZOS)
        _log(f"  이미지 리사이즈: {new_size}")

    response = model.generate_content(
        [ANALYSIS_PROMPT, image],
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
            max_output_tokens=8192,
        ),
    )

    # 응답 확인
    if not response or not response.text:
        _log(f"  경고: 빈 응답 수신")
        return SlideLayout()

    response_text = response.text.strip()
    _log(f"  응답 길이: {len(response_text)} 글자")

    # JSON 파싱
    # 코드 블록 마커 제거
    if response_text.startswith("```"):
        response_text = re.sub(r"^```(?:json)?\s*\n?", "", response_text)
        response_text = re.sub(r"\n?\s*```$", "", response_text)

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as e:
        _log(f"  JSON 파싱 실패 (1차): {e}")
        # JSON 부분만 추출 시도
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            try:
                data = json.loads(json_match.group())
                _log(f"  JSON 추출 성공 (2차)")
            except json.JSONDecodeError:
                _log(f"  JSON 파싱 완전 실패. 응답 앞부분: {response_text[:200]}")
                return SlideLayout()
        else:
            _log(f"  JSON 패턴 없음. 응답 앞부분: {response_text[:200]}")
            return SlideLayout()

    # SlideLayout 구성
    layout = SlideLayout(
        background_color=data.get("background_color", "#FFFFFF"),
    )

    elements_data = data.get("elements", [])
    _log(f"  인식된 요소 수: {len(elements_data)}")

    for elem_data in elements_data:
        elem_type = elem_data.get("type", "text")
        elem = SlideElement(
            type=elem_type,
            content=elem_data.get("content", ""),
            x=float(elem_data.get("x", 0)),
            y=float(elem_data.get("y", 0)),
            width=float(elem_data.get("width", 10)),
            height=float(elem_data.get("height", 5)),
            font_size=int(elem_data.get("font_size", 14)),
            font_color=elem_data.get("font_color", "#000000"),
            background_color=elem_data.get("background_color", ""),
            bold=elem_data.get("bold", False),
            italic=elem_data.get("italic", False),
            alignment=elem_data.get("alignment", "left"),
        )
        layout.elements.append(elem)

        if elem_type == "text":
            preview = elem.content[:50].replace('\n', ' ')
            _log(f"    [TEXT] \"{preview}\" pos=({elem.x:.0f},{elem.y:.0f}) size={elem.font_size}pt")
        elif elem_type == "shape":
            _log(f"    [SHAPE] pos=({elem.x:.0f},{elem.y:.0f}) size=({elem.width:.0f}x{elem.height:.0f}) color={elem.background_color}")
        elif elem_type == "image":
            _log(f"    [IMAGE] pos=({elem.x:.0f},{elem.y:.0f}) size=({elem.width:.0f}x{elem.height:.0f})")

    return layout


def analyze_slides_batch(images: list) -> list:
    """
    여러 슬라이드 이미지를 배치로 분석합니다.
    """
    _log(f"배치 분석 시작: {len(images)}개 슬라이드")
    layouts = []
    for i, img in enumerate(images):
        try:
            layout = analyze_slide(img, slide_num=i + 1)
            layouts.append(layout)
            _log(f"슬라이드 {i+1}/{len(images)} 완료 ({len(layout.elements)}개 요소)")
        except Exception as e:
            _log(f"슬라이드 {i+1} 분석 실패: {e}")
            import traceback
            traceback.print_exc()
            layouts.append(SlideLayout())
    
    total = sum(len(l.elements) for l in layouts)
    _log(f"배치 분석 완료: 총 {total}개 요소 인식")
    return layouts
