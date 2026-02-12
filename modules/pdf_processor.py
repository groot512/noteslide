"""
PDF 처리 모듈
- PDF에서 텍스트 블록, 이미지, 도형 정보 추출
- PDF 페이지를 고해상도 이미지로 변환
"""

import fitz  # PyMuPDF
from PIL import Image
import io
import os
import gc
from dataclasses import dataclass, field

# 이미지 최대 크기 (메모리 절약)
MAX_IMAGE_DIM = 1200


@dataclass
class TextBlock:
    """추출된 텍스트 블록"""
    text: str
    x: float  # 좌측 상단 X (pt)
    y: float  # 좌측 상단 Y (pt)
    width: float  # 너비 (pt)
    height: float  # 높이 (pt)
    font_size: float = 12.0
    font_name: str = ""
    color: str = "#000000"  # hex
    bold: bool = False
    italic: bool = False


@dataclass
class ImageBlock:
    """추출된 이미지 블록"""
    image: Image.Image
    x: float
    y: float
    width: float
    height: float


@dataclass
class SlideData:
    """한 슬라이드(페이지)의 추출 데이터"""
    page_number: int
    width: float  # 페이지 너비 (pt)
    height: float  # 페이지 높이 (pt)
    text_blocks: list = field(default_factory=list)
    image_blocks: list = field(default_factory=list)
    background_color: str = "#FFFFFF"
    page_image: Image.Image = None  # 전체 페이지 이미지 (AI 분석용)

    @property
    def has_sufficient_text(self):
        """텍스트가 충분히 추출되었는지 판단"""
        total_chars = sum(len(tb.text.strip()) for tb in self.text_blocks)
        return total_chars > 20  # 최소 20자 이상이면 충분


def _hex_color(color_int):
    """PyMuPDF 색상값을 hex로 변환"""
    if isinstance(color_int, int):
        r = (color_int >> 16) & 0xFF
        g = (color_int >> 8) & 0xFF
        b = color_int & 0xFF
        return f"#{r:02x}{g:02x}{b:02x}"
    return "#000000"


def extract_from_pdf(pdf_path: str) -> list:
    """
    PDF에서 각 페이지의 텍스트/이미지를 추출합니다.

    Args:
        pdf_path: PDF 파일 경로

    Returns:
        list[SlideData]: 각 페이지의 추출 데이터
    """
    doc = fitz.open(pdf_path)
    slides = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        rect = page.rect
        slide = SlideData(
            page_number=page_num + 1,
            width=rect.width,
            height=rect.height,
        )

        # --- 텍스트 블록 추출 ---
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # 텍스트 블록
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue

                        bbox = span.get("bbox", (0, 0, 0, 0))
                        font_flags = span.get("flags", 0)
                        color_int = span.get("color", 0)

                        tb = TextBlock(
                            text=text,
                            x=bbox[0],
                            y=bbox[1],
                            width=bbox[2] - bbox[0],
                            height=bbox[3] - bbox[1],
                            font_size=span.get("size", 12),
                            font_name=span.get("font", ""),
                            color=_hex_color(color_int),
                            bold=bool(font_flags & 2**4),
                            italic=bool(font_flags & 2**1),
                        )
                        slide.text_blocks.append(tb)

        # --- 이미지 추출 (메모리 최적화) ---
        image_list = page.get_images(full=True)
        for img_index, img_info in enumerate(image_list[:5]):  # 페이지당 최대 5개
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                pil_image = Image.open(io.BytesIO(image_bytes))

                # 이미지 크기 제한
                if max(pil_image.size) > MAX_IMAGE_DIM:
                    ratio = MAX_IMAGE_DIM / max(pil_image.size)
                    new_size = (int(pil_image.width * ratio), int(pil_image.height * ratio))
                    pil_image = pil_image.resize(new_size, Image.LANCZOS)

                img_rects = page.get_image_rects(xref)
                if img_rects:
                    r = img_rects[0]
                    ib = ImageBlock(
                        image=pil_image,
                        x=r.x0,
                        y=r.y0,
                        width=r.width,
                        height=r.height,
                    )
                    slide.image_blocks.append(ib)
            except Exception:
                continue

        # --- 배경색 추출 (간단한 방법) ---
        # 페이지를 작은 이미지로 렌더링하여 모서리 색상 확인
        try:
            small_pix = page.get_pixmap(matrix=fitz.Matrix(0.1, 0.1))
            small_img = Image.frombytes("RGB", [small_pix.width, small_pix.height], small_pix.samples)
            corner_color = small_img.getpixel((0, 0))
            slide.background_color = f"#{corner_color[0]:02x}{corner_color[1]:02x}{corner_color[2]:02x}"
        except Exception:
            pass

        slides.append(slide)

    doc.close()
    return slides


def pdf_pages_to_images(pdf_path: str, dpi: int = 150) -> list:
    """
    PDF의 각 페이지를 PIL Image로 변환합니다.
    메모리 절약을 위해 DPI를 150으로 제한합니다.
    """
    doc = fitz.open(pdf_path)
    images = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=matrix)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        # pixmap 메모리 즉시 해제
        pix = None
        images.append(img)

    doc.close()
    gc.collect()
    return images


def images_to_slide_data(image_paths: list) -> list:
    """
    이미지 파일 목록을 SlideData로 변환합니다.
    (이미지 업로드의 경우, 텍스트 추출 없이 AI 분석 필요)

    Args:
        image_paths: 이미지 파일 경로 목록

    Returns:
        list[SlideData]: 각 이미지의 SlideData (텍스트 없음, page_image만 포함)
    """
    slides = []
    for i, path in enumerate(image_paths):
        img = Image.open(path).convert("RGB")
        slide = SlideData(
            page_number=i + 1,
            width=img.width * 72 / 96,  # px → pt (96dpi 기준)
            height=img.height * 72 / 96,
            page_image=img,
        )
        slides.append(slide)
    return slides
