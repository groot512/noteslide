"""
NoteSlide — Flask 웹 서버
PDF/이미지를 편집 가능한 PPTX로 변환하는 API 서버
"""

import os
import sys
import uuid
import shutil
import traceback
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

from modules.pdf_processor import (
    extract_from_pdf,
    pdf_pages_to_images,
    images_to_slide_data,
)
from modules.ai_analyzer import analyze_slides_batch
from modules.pptx_builder import (
    build_pptx_from_pdf_data,
    build_pptx_from_ai_data,
    build_pptx_with_background_images,
)

# 환경변수 로드
load_dotenv()

# stdout 인코딩 설정 (Windows CP949 대응)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB 제한
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")

# 허용 확장자
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}


def log(msg):
    """서버 로그 출력"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def ensure_upload_dir():
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/convert", methods=["POST"])
def convert():
    """
    파일 업로드 및 변환 API
    전략: AI Vision을 항상 우선 사용 → 실패 시 PDF 직접 추출 → 최종 이미지 폴백
    """
    ensure_upload_dir()

    if "files" not in request.files:
        return jsonify({"error": "파일이 업로드되지 않았습니다."}), 400

    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "파일을 선택해주세요."}), 400

    # 고유 작업 ID 생성
    job_id = str(uuid.uuid4())[:8]
    job_dir = os.path.join(app.config["UPLOAD_FOLDER"], job_id)
    os.makedirs(job_dir, exist_ok=True)
    log(f"[{job_id}] 새 변환 작업 시작")

    try:
        saved_files = []
        file_type = None  # "pdf" or "images"

        for f in files:
            if not allowed_file(f.filename):
                return jsonify({
                    "error": f"지원하지 않는 파일 형식입니다: {f.filename}"
                }), 400

            filename = secure_filename(f.filename)
            if not filename or filename == "":
                ext = f.filename.rsplit(".", 1)[1].lower() if "." in f.filename else "bin"
                filename = f"{job_id}_{len(saved_files)}.{ext}"

            filepath = os.path.join(job_dir, filename)
            f.save(filepath)
            saved_files.append(filepath)

            ext = filename.rsplit(".", 1)[1].lower()
            if ext == "pdf":
                file_type = "pdf"
            elif file_type != "pdf":
                file_type = "images"

        log(f"[{job_id}] 파일 타입: {file_type}, 파일 수: {len(saved_files)}")

        # --- 변환 처리 ---
        output_filename = f"NoteSlide_{job_id}.pptx"
        output_path = os.path.join(job_dir, output_filename)

        use_ai = os.environ.get("GEMINI_API_KEY", "").strip() != ""
        method_used = "unknown"

        if file_type == "pdf":
            pdf_path = saved_files[0]

            # PDF를 이미지로 변환 (AI 분석 및 폴백 공용)
            log(f"[{job_id}] PDF 페이지를 이미지로 변환 중...")
            page_images = pdf_pages_to_images(pdf_path, dpi=200)
            log(f"[{job_id}] {len(page_images)}개 페이지 이미지 생성 완료")

            if use_ai:
                # 전략 1: AI Vision으로 분석 (최우선)
                log(f"[{job_id}] AI Vision 분석 시작...")
                try:
                    layouts = analyze_slides_batch(page_images)
                    # AI가 실제로 요소를 인식했는지 확인
                    total_elements = sum(len(l.elements) for l in layouts)
                    log(f"[{job_id}] AI Vision 결과: {total_elements}개 요소 인식")

                    if total_elements > 0:
                        build_pptx_from_ai_data(layouts, page_images, output_path)
                        method_used = "ai_vision"
                        log(f"[{job_id}] AI Vision으로 PPTX 생성 완료")
                    else:
                        raise ValueError("AI Vision이 요소를 인식하지 못했습니다")
                except Exception as ai_err:
                    log(f"[{job_id}] AI Vision 실패: {ai_err}")
                    log(f"[{job_id}] PDF 직접 추출로 폴백...")
                    # 전략 2: PDF 직접 추출로 폴백
                    slides_data = extract_from_pdf(pdf_path)
                    has_text = any(s.has_sufficient_text for s in slides_data)
                    if has_text:
                        build_pptx_from_pdf_data(slides_data, output_path)
                        method_used = "direct_extraction"
                        log(f"[{job_id}] PDF 직접 추출로 PPTX 생성 완료")
                    else:
                        # 전략 3: 이미지 폴백
                        build_pptx_with_background_images(page_images, output_path)
                        method_used = "image_fallback"
                        log(f"[{job_id}] 이미지 폴백으로 PPTX 생성 완료")
            else:
                # API 키 없음: PDF 직접 추출 시도
                log(f"[{job_id}] API 키 없음, PDF 직접 추출 시도...")
                slides_data = extract_from_pdf(pdf_path)
                has_text = any(s.has_sufficient_text for s in slides_data)
                if has_text:
                    build_pptx_from_pdf_data(slides_data, output_path)
                    method_used = "direct_extraction"
                else:
                    build_pptx_with_background_images(page_images, output_path)
                    method_used = "image_fallback"
                log(f"[{job_id}] 방법: {method_used}")

        elif file_type == "images":
            log(f"[{job_id}] 이미지 파일 처리 시작...")
            slides_data = images_to_slide_data(saved_files)
            page_images = [s.page_image for s in slides_data]

            if use_ai:
                log(f"[{job_id}] AI Vision 분석 시작...")
                try:
                    layouts = analyze_slides_batch(page_images)
                    total_elements = sum(len(l.elements) for l in layouts)
                    log(f"[{job_id}] AI Vision 결과: {total_elements}개 요소 인식")

                    if total_elements > 0:
                        build_pptx_from_ai_data(layouts, page_images, output_path)
                        method_used = "ai_vision"
                    else:
                        raise ValueError("AI Vision이 요소를 인식하지 못했습니다")
                except Exception as ai_err:
                    log(f"[{job_id}] AI Vision 실패: {ai_err}")
                    build_pptx_with_background_images(page_images, output_path)
                    method_used = "image_fallback"
            else:
                build_pptx_with_background_images(page_images, output_path)
                method_used = "image_fallback"

            log(f"[{job_id}] 방법: {method_used}")

        log(f"[{job_id}] === 변환 완료 === 방법: {method_used}")

        return jsonify({
            "success": True,
            "job_id": job_id,
            "filename": output_filename,
            "method": method_used,
            "slide_count": len(page_images) if 'page_images' in dir() else len(saved_files),
            "download_url": f"/api/download/{job_id}/{output_filename}",
        })

    except Exception as e:
        log(f"[{job_id}] !!! 변환 오류: {e}")
        traceback.print_exc()
        if os.path.exists(job_dir):
            shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": f"변환 중 오류가 발생했습니다: {str(e)}"}), 500


@app.route("/api/download/<job_id>/<filename>")
def download(job_id, filename):
    """변환된 PPTX 파일 다운로드"""
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], job_id, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "파일을 찾을 수 없습니다."}), 404
    return send_file(filepath, as_attachment=True, download_name=filename)


if __name__ == "__main__":
    ensure_upload_dir()
    port = int(os.environ.get("FLASK_PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "True").lower() == "true"
    print(f"\n[*] NoteSlide Server Started: http://localhost:{port}")
    print(f"    Gemini API: {'[ON] Active' if os.environ.get('GEMINI_API_KEY') else '[OFF] Disabled (image fallback mode)'}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
