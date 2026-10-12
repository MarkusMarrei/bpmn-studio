"""
BPMN Studio — Локальный сервер приложения на базе FastAPI / Uvicorn (AI BPMN Generator).
Обеспечивает работу веб-интерфейса, аппаратного сканера ПК, менеджера
скачивания моделей (Bonsai v2, Qwen), парсера документов и BPMN 2.0 движка.
"""

import os
import sys

# Обеспечиваем безопасный вывод UTF-8 в Windows-консоли (CP1251/CP866)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import threading
import webbrowser
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Добавляем корневую директорию в sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.bpmn_engine import execute_dsl_code
from backend.document_parser import extract_document_text
from backend.hardware_scanner import get_hardware_diagnostic
from backend.model_manager import (
    get_model_catalog_status,
    start_model_download,
    cancel_model_download,
    set_active_model,
    delete_model_file,
    get_download_status,
    load_config,
    save_config
)
from backend.llm_runner import run_process_generation

app = FastAPI(title="BPMN Studio — AI BPMN Generator")

# Разрешаем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PUBLIC_DIR = os.path.join(BASE_DIR, "public_html")


# =============================================================================
# МОДЕЛИ ДАННЫХ Pydantic
# =============================================================================
class GenerateRequest(BaseModel):
    text: str
    history: Optional[List[Dict[str, Any]]] = None
    current_dsl: Optional[str] = None
    locale: Optional[str] = "ru"


class ModelActionRequest(BaseModel):
    model_id: str


class ConfigUpdateRequest(BaseModel):
    custom_openai_url: Optional[str] = None
    custom_openai_key: Optional[str] = None
    custom_openai_model: Optional[str] = None
    language: Optional[str] = None


# =============================================================================
# МАРШРУТЫ ФРОНТЕНДА
# =============================================================================
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(PUBLIC_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/presets")
async def get_presets():
    return {"presets": []}


# =============================================================================
# АППАРАТНЫЙ СКАНЕР И МЕНЕДЖЕР МОДЕЛЕЙ (Bonsai / Qwen)
# =============================================================================
@app.get("/api/system/info")
async def api_system_info():
    """Аппаратная диагностика ПК (RAM, CPU, GPU)."""
    return get_hardware_diagnostic()


@app.get("/api/models")
async def api_get_models(locale: Optional[str] = "ru"):
    """Каталог моделей с аппаратной оценкой совместимости."""
    return get_model_catalog_status(locale=locale or "ru")


@app.post("/api/models/download")
async def api_download_model(req: ModelActionRequest):
    """Запуск фонового скачивания выбранной модели."""
    res = start_model_download(req.model_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Ошибка запуска скачивания"))
    return res


@app.get("/api/models/download-progress")
async def api_download_progress():
    """Получение прогресса текущего скачивания (проценты, скорость, МБ)."""
    return get_download_status()


@app.post("/api/models/cancel-download")
async def api_cancel_download():
    """Отмена текущего скачивания."""
    return cancel_model_download()


@app.post("/api/models/activate")
async def api_activate_model(req: ModelActionRequest):
    """Активация скачанной модели для генерации."""
    res = set_active_model(req.model_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Не удалось активировать модель"))
    return res


@app.post("/api/models/delete")
async def api_delete_model(req: ModelActionRequest):
    """Удаление скачанного файла модели с диска."""
    res = delete_model_file(req.model_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Ошибка при удалении модели"))
    return res


@app.post("/api/models/config")
async def api_update_config(req: ConfigUpdateRequest):
    """Сохранение параметров кастомного OpenAI эндпоинта (Ollama / LM Studio)."""
    cfg = load_config()
    if req.custom_openai_url is not None:
        cfg["custom_openai_url"] = req.custom_openai_url.strip()
    if req.custom_openai_key is not None:
        cfg["custom_openai_key"] = req.custom_openai_key.strip()
    if req.custom_openai_model is not None:
        cfg["custom_openai_model"] = req.custom_openai_model.strip()
    if req.language is not None:
        cfg["language"] = req.language.strip()
    save_config(cfg)
    return {"success": True, "config": cfg}


# =============================================================================
# ПАРСИНГ ДОКУМЕНТОВ И ГЕНЕРАЦИЯ ДИАГРАММ
# =============================================================================
@app.post("/api/extract")
async def extract_text_endpoint(file: UploadFile = File(...)):
    """Извлечение текста из регламентов (.pdf, .docx, .txt)."""
    try:
        content = await file.read()
        extracted_text = extract_document_text(file.filename, content)
        return {
            "filename": file.filename,
            "text": extracted_text,
            "length": len(extracted_text)
        }
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.post("/api/generate")
async def generate_diagram_endpoint(req: GenerateRequest):
    """
    Генерация BPMN 2.0 диаграммы по тексту с аудитом бизнес-логики через LLM.
    """
    user_text = req.text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Текст процесса не может быть пустым")

    try:
        result = run_process_generation(
            text=user_text,
            history=req.history,
            current_dsl=req.current_dsl,
            locale=req.locale or "ru"
        )
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Ошибка генерации: {str(e)}"})


# =============================================================================
# ТОЧКА ВХОДА (Локальный запуск)
# =============================================================================
def _open_browser_when_ready():
    """Автоматическое открытие браузера при старте."""
    try:
        webbrowser.open_new_tab("http://localhost:8000")
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn

    print("=" * 65)
    print(">> BPMN Studio -- AI BPMN Generator")
    print(">> Server running at: http://127.0.0.1:8000 (http://localhost:8000)")
    print("=" * 65)

    # Автоматически открываем браузер через 1.2 секунды после старта сервера
    timer = threading.Timer(1.2, _open_browser_when_ready)
    timer.daemon = True
    timer.start()

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
