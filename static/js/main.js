/**
 * NoteSlide — Frontend Logic
 * 파일 업로드, 변환 API 호출, 진행 상태 관리
 */

(function () {
    'use strict';

    // --- DOM 요소 ---
    const uploadArea = document.getElementById('uploadArea');
    const uploadContent = document.getElementById('uploadContent');
    const fileInput = document.getElementById('fileInput');
    const filePreview = document.getElementById('filePreview');
    const previewList = document.getElementById('previewList');
    const clearFilesBtn = document.getElementById('clearFiles');
    const convertBtn = document.getElementById('convertBtn');
    const progressArea = document.getElementById('progressArea');
    const progressText = document.getElementById('progressText');
    const progressBar = document.getElementById('progressBar');
    const progressDetail = document.getElementById('progressDetail');
    const resultArea = document.getElementById('resultArea');
    const resultMethod = document.getElementById('resultMethod');
    const downloadBtn = document.getElementById('downloadBtn');
    const retryBtn = document.getElementById('retryBtn');
    const errorToast = document.getElementById('errorToast');
    const errorMessage = document.getElementById('errorMessage');

    let selectedFiles = [];

    // --- 유틸리티 ---
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1048576).toFixed(1) + ' MB';
    }

    function getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const icons = {
            pdf: '📄',
            jpg: '🖼️',
            jpeg: '🖼️',
            png: '🖼️',
        };
        return icons[ext] || '📎';
    }

    function showError(msg) {
        errorMessage.textContent = msg;
        errorToast.style.display = 'flex';
        setTimeout(() => {
            errorToast.style.display = 'none';
        }, 5000);
    }

    function showState(state) {
        // 상태: upload, preview, progress, result
        uploadContent.style.display = state === 'upload' ? 'block' : 'none';
        filePreview.style.display = state === 'preview' ? 'block' : 'none';
        progressArea.style.display = state === 'progress' ? 'block' : 'none';
        resultArea.style.display = state === 'result' ? 'block' : 'none';

        // 업로드 영역 커서 변경
        uploadArea.style.cursor = (state === 'upload') ? 'pointer' : 'default';
    }

    // --- 파일 선택 ---
    function handleFiles(files) {
        const validExts = ['pdf', 'jpg', 'jpeg', 'png'];
        const maxSize = 50 * 1024 * 1024; // 50MB

        selectedFiles = [];
        let hasPdf = false;
        let hasImages = false;

        for (const file of files) {
            const ext = file.name.split('.').pop().toLowerCase();
            if (!validExts.includes(ext)) {
                showError(`지원하지 않는 형식: ${file.name}`);
                return;
            }
            if (file.size > maxSize) {
                showError(`파일이 너무 큽니다: ${file.name} (최대 50MB)`);
                return;
            }
            if (ext === 'pdf') hasPdf = true;
            else hasImages = true;

            selectedFiles.push(file);
        }

        // PDF와 이미지 혼합 불가
        if (hasPdf && hasImages) {
            showError('PDF와 이미지를 동시에 업로드할 수 없습니다. 하나의 유형만 선택해주세요.');
            selectedFiles = [];
            return;
        }

        // PDF는 1개만
        if (hasPdf && selectedFiles.length > 1) {
            showError('PDF 파일은 한 번에 1개만 업로드할 수 있습니다.');
            selectedFiles = [];
            return;
        }

        if (selectedFiles.length === 0) return;

        // 프리뷰 표시
        renderPreview();
        showState('preview');
    }

    function renderPreview() {
        previewList.innerHTML = '';
        selectedFiles.forEach((file) => {
            const item = document.createElement('div');
            item.className = 'preview-item';
            item.innerHTML = `
                <span class="preview-item-icon">${getFileIcon(file.name)}</span>
                <span class="preview-item-name">${file.name}</span>
                <span class="preview-item-size">${formatFileSize(file.size)}</span>
            `;
            previewList.appendChild(item);
        });
    }

    // --- 이벤트 리스너 ---

    // 클릭 업로드
    uploadArea.addEventListener('click', (e) => {
        if (uploadContent.style.display !== 'none') {
            fileInput.click();
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFiles(e.target.files);
        }
    });

    // 드래그 앤 드롭
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('drag-over');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            handleFiles(e.dataTransfer.files);
        }
    });

    // 초기화 버튼
    clearFilesBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        selectedFiles = [];
        fileInput.value = '';
        showState('upload');
    });

    // 변환 버튼
    convertBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (selectedFiles.length === 0) return;
        startConversion();
    });

    // 재시도 버튼
    retryBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        selectedFiles = [];
        fileInput.value = '';
        showState('upload');
    });

    // --- 변환 로직 ---
    function startConversion() {
        showState('progress');
        setProgress(0, '파일 업로드 중...', '서버로 전송 중...');

        const formData = new FormData();
        selectedFiles.forEach((file) => {
            formData.append('files', file);
        });

        const xhr = new XMLHttpRequest();

        // 업로드 진행률
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 40);
                setProgress(pct, '파일 업로드 중...', `${formatFileSize(e.loaded)} / ${formatFileSize(e.total)}`);
            }
        });

        xhr.upload.addEventListener('load', () => {
            setProgress(40, 'AI 분석 중...', '슬라이드 구조를 인식하고 있습니다...');
            // 서버 처리 시간 시뮬레이션
            simulateServerProgress();
        });

        xhr.addEventListener('load', () => {
            clearInterval(serverProgressInterval);

            if (xhr.status === 200) {
                try {
                    const data = JSON.parse(xhr.responseText);
                    if (data.success) {
                        setProgress(100, '완료!', '');
                        setTimeout(() => {
                            showResult(data);
                        }, 500);
                    } else {
                        showError(data.error || '변환에 실패했습니다.');
                        showState('preview');
                    }
                } catch (err) {
                    showError('서버 응답을 처리할 수 없습니다.');
                    showState('preview');
                }
            } else {
                try {
                    const data = JSON.parse(xhr.responseText);
                    showError(data.error || `서버 오류 (${xhr.status})`);
                } catch {
                    showError(`서버 오류가 발생했습니다. (코드: ${xhr.status})`);
                }
                showState('preview');
            }
        });

        xhr.addEventListener('error', () => {
            clearInterval(serverProgressInterval);
            showError('네트워크 오류가 발생했습니다. 서버가 실행 중인지 확인해주세요.');
            showState('preview');
        });

        xhr.open('POST', '/api/convert');
        xhr.send(formData);
    }

    let serverProgressInterval = null;

    function simulateServerProgress() {
        let pct = 40;
        const messages = [
            { at: 50, text: 'PDF 파일 분석 중...', detail: '텍스트와 이미지를 추출하고 있습니다' },
            { at: 60, text: 'AI Vision 분석 중...', detail: '슬라이드 레이아웃을 인식하고 있습니다' },
            { at: 75, text: 'PPTX 생성 중...', detail: '편집 가능한 요소를 배치하고 있습니다' },
            { at: 85, text: '마무리 중...', detail: '파일을 최적화하고 있습니다' },
        ];

        serverProgressInterval = setInterval(() => {
            if (pct < 90) {
                pct += 1;
                const msg = messages.find((m) => pct >= m.at && pct < m.at + 10);
                if (msg) {
                    setProgress(pct, msg.text, msg.detail);
                } else {
                    setProgress(pct);
                }
            }
        }, 300);
    }

    function setProgress(pct, text, detail) {
        progressBar.style.width = pct + '%';
        if (text) progressText.textContent = text;
        if (detail !== undefined) progressDetail.textContent = detail;
    }

    function showResult(data) {
        showState('result');

        // 변환 방법 표시
        const methodMap = {
            direct_extraction: 'PDF 직접 추출로 변환됨',
            ai_vision: 'AI Vision 분석으로 변환됨',
            image_fallback: '이미지 배경으로 변환됨 (API 키 미설정)',
        };
        resultMethod.textContent = methodMap[data.method] || data.method;

        // 다운로드 버튼 설정
        downloadBtn.href = data.download_url;
        downloadBtn.setAttribute('download', data.filename);
    }
})();
