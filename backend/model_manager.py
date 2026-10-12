"""
Модуль каталога и загрузки LLM-моделей (Model Manager) для BPMN Studio (AI BPMN Generator).
Управляет списком моделей линейки Bonsai 2 (1.7B, 4.8B, 8B, 27B) и Qwen,
проверяет аппаратную совместимость с ПК пользователя и обеспечивает фоновую
докачку моделей в директорию models/ с прогресс-баром и докачкой.
Поддерживает полную мультиязычность (ru, en, de, fr, es).
"""

import json
import os
import ssl
import threading
import time
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional

from backend.hardware_scanner import get_hardware_diagnostic

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# Каталог поддерживаемых локальных моделей с локализацией на 5 языков
MODEL_CATALOG = [
    {
        "id": "bonsai-2-1.7b",
        "name": "Bonsai 2 (PrismML)",
        "badge": {
            "ru": "1.7B (Ультра-легкая)",
            "en": "1.7B (Ultra-Light)",
            "de": "1.7B (Ultraleicht)",
            "fr": "1.7B (Ultra-léger)",
            "es": "1.7B (Ultraligero)"
        },
        "family": "Bonsai 2",
        "params": {
            "ru": "1.7 млрд (Ternary)",
            "en": "1.7B (Ternary)",
            "de": "1,7 Mrd. (Ternary)",
            "fr": "1,7 Md (Ternary)",
            "es": "1.7 B (Ternary)"
        },
        "format": "GGUF Ternary 1.5-bit",
        "file_size_gb": 0.44,
        "size_bytes": 463290464,
        "min_ram_gb": 1.5,
        "rec_ram_gb": 3.0,
        "filename": "Ternary-Bonsai-1.7B-Q2_0.gguf",
        "download_url": "https://huggingface.co/prism-ml/Ternary-Bonsai-1.7B-gguf/resolve/main/Ternary-Bonsai-1.7B-Q2_0.gguf",
        "description": {
            "ru": "Ультракомпактная модель PrismML. Мгновенно скачивается (~440 МБ) и работает даже на слабых ноутбуках и офисных ПК от 1.5 ГБ RAM.",
            "en": "Ultra-compact PrismML model. Downloads in seconds (~440 MB) and runs smoothly even on entry-level laptops and office PCs from 1.5 GB RAM.",
            "de": "Ultrakompaktes PrismML-Modell. Lädt blitzschnell herunter (~440 MB) und läuft selbst auf schwächeren Laptops und Büro-PCs ab 1,5 GB RAM.",
            "fr": "Modèle ultra-compact PrismML. Téléchargement instantané (~440 Mo) et fonctionne parfaitement même sur ordinateurs portables modestes dès 1,5 Go de RAM.",
            "es": "Modelo ultracompacto PrismML. Se descarga al instante (~440 MB) y funciona incluso en portátiles básicos y PCs de oficina desde 1.5 GB RAM."
        }
    },
    {
        "id": "bonsai-2-4.8b",
        "name": "Bonsai 2 (PrismML)",
        "badge": {
            "ru": "4.8B (Быстрая и сбалансированная)",
            "en": "4.8B (Fast & Balanced)",
            "de": "4.8B (Schnell & Ausgewogen)",
            "fr": "4.8B (Rapide & Équilibré)",
            "es": "4.8B (Rápido y Equilibrado)"
        },
        "family": "Bonsai 2",
        "params": {
            "ru": "4.8 млрд (Ternary)",
            "en": "4.8B (Ternary)",
            "de": "4,8 Mrd. (Ternary)",
            "fr": "4,8 Md (Ternary)",
            "es": "4.8 B (Ternary)"
        },
        "format": "GGUF Ternary 1.5-bit",
        "file_size_gb": 1.02,
        "size_bytes": 1074969344,
        "min_ram_gb": 2.5,
        "rec_ram_gb": 5.0,
        "filename": "Ternary-Bonsai-4B-Q2_0.gguf",
        "download_url": "https://huggingface.co/prism-ml/Ternary-Bonsai-4B-gguf/resolve/main/Ternary-Bonsai-4B-Q2_0.gguf",
        "description": {
            "ru": "Сбалансированная модель для бизнес-аналитики. Быстрый отклик и глубокое понимание развилок на системах с 4–8 ГБ RAM.",
            "en": "Balanced model for business process modeling. Fast response times and solid comprehension of complex gateways on systems with 4–8 GB RAM.",
            "de": "Ausgewogenes Modell für die Geschäftsprozessmodellierung. Schnelle Reaktionszeiten und präzises Verständnis von Verzweigungen ab 4–8 GB RAM.",
            "fr": "Modèle équilibré pour la modélisation des processus métier. Réponse rapide et compréhension approfondie des branchements dès 4 à 8 Go de RAM.",
            "es": "Modelo equilibrado para el modelado de procesos. Respuesta ágil y comprensión profunda de bifurcaciones en equipos con 4–8 GB RAM."
        }
    },
    {
        "id": "bonsai-2-8b",
        "name": "Bonsai 2 (PrismML)",
        "badge": {
            "ru": "8B (Высокая точность)",
            "en": "8B (High Accuracy)",
            "de": "8B (Hohe Präzision)",
            "fr": "8B (Haute précision)",
            "es": "8B (Alta precisión)"
        },
        "family": "Bonsai 2",
        "params": {
            "ru": "8.0 млрд (Ternary)",
            "en": "8.0B (Ternary)",
            "de": "8,0 Mrd. (Ternary)",
            "fr": "8,0 Md (Ternary)",
            "es": "8.0 B (Ternary)"
        },
        "format": "GGUF Ternary 1.5-bit",
        "file_size_gb": 2.03,
        "size_bytes": 2182184672,
        "min_ram_gb": 4.5,
        "rec_ram_gb": 8.0,
        "filename": "Ternary-Bonsai-8B-Q2_0.gguf",
        "download_url": "https://huggingface.co/prism-ml/Ternary-Bonsai-8B-gguf/resolve/main/Ternary-Bonsai-8B-Q2_0.gguf",
        "description": {
            "ru": "Высокая детальность выделения параллельных процессов и шлюзов исключений в сложных промышленных регламентах.",
            "en": "High detail in extracting parallel paths, error events, and exception gateways in complex industrial workflows.",
            "de": "Hohe Detailgenauigkeit bei parallelen Pfaden, Fehlerereignissen und Ausnahme-Gateways in anspruchsvollen Prozessbeschreibungen.",
            "fr": "Grande précision dans l'identification des flux parallèles, des événements d'erreur et des passerelles d'exception dans les règlements complexes.",
            "es": "Alta precisión al identificar flujos paralelos, eventos de error y compuertas de excepción en procesos complejos."
        }
    },
    {
        "id": "bonsai-2-27b",
        "name": "Bonsai 2 (PrismML)",
        "badge": {
            "ru": "27B (Флагман)",
            "en": "27B (Flagship)",
            "de": "27B (Flaggschiff)",
            "fr": "27B (Fleuron)",
            "es": "27B (Insignia)"
        },
        "family": "Bonsai 2",
        "params": {
            "ru": "27 млрд (Ternary)",
            "en": "27B (Ternary)",
            "de": "27 Mrd. (Ternary)",
            "fr": "27 Md (Ternary)",
            "es": "27 B (Ternary)"
        },
        "format": "GGUF Ternary 1.5-bit",
        "file_size_gb": 5.54,
        "size_bytes": 5946648928,
        "min_ram_gb": 8.0,
        "rec_ram_gb": 12.0,
        "filename": "Ternary-Bonsai-2-27B-PTQ1_0.gguf",
        "download_url": "https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/resolve/main/Ternary-Bonsai-2-27B-PTQ1_0.gguf",
        "description": {
            "ru": "Флагманский интеллект класса 27B со сверхсжатием PrismML. Полный аудит регламентов без галлюцинаций. Рекомендуется от 8–10 ГБ RAM.",
            "en": "Flagship 27B-class intelligence with PrismML ternary compression. Comprehensive regulation audit with zero hallucinations. Recommended with 8–10+ GB RAM.",
            "de": "Flaggschiff-KI der 27B-Klasse mit PrismML-Ternär-Kompression. Vollständiges Prozess-Audit ohne Halluzinationen. Empfohlen ab 8–10 GB RAM.",
            "fr": "Intelligence phare de classe 27B avec compression ternaire PrismML. Audit exhaustif des règlements sans hallucinations. Recommandé à partir de 8–10 Go de RAM.",
            "es": "Inteligencia insignia de clase 27B con compresión ternaria PrismML. Auditoría integral de procesos sin alucinaciones. Recomendado a partir de 8–10 GB RAM."
        }
    },
    {
        "id": "qwen2.5-1.5b-instruct",
        "name": "Qwen 2.5 Instruct",
        "badge": {
            "ru": "1.5B (Легкая)",
            "en": "1.5B (Light)",
            "de": "1.5B (Leicht)",
            "fr": "1.5B (Léger)",
            "es": "1.5B (Ligero)"
        },
        "family": "Qwen",
        "params": {
            "ru": "1.5 млрд",
            "en": "1.5B",
            "de": "1,5 Mrd.",
            "fr": "1,5 Md",
            "es": "1.5 B"
        },
        "format": "GGUF Q4_K_M",
        "file_size_gb": 1.12,
        "size_bytes": 1117320736,
        "min_ram_gb": 2.5,
        "rec_ram_gb": 4.0,
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "download_url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "description": {
            "ru": "Базовая легкая модель Qwen 2.5. Подходит для любого офисного ПК с оперативной памятью от 4 ГБ.",
            "en": "Entry-level lightweight Qwen 2.5 model. Suitable for any office PC with at least 4 GB RAM.",
            "de": "Kompaktes Qwen 2.5 Basismodell. Geeignet für jeden Büro-PC mit mindestens 4 GB RAM.",
            "fr": "Modèle léger de base Qwen 2.5. Convient à tout PC bureautique disposant d'au moins 4 Go de RAM.",
            "es": "Modelo ligero básico Qwen 2.5. Adecuado para cualquier PC de oficina con al menos 4 GB de RAM."
        }
    },
    {
        "id": "qwen2.5-3b-instruct",
        "name": "Qwen 2.5 Instruct",
        "badge": {
            "ru": "3B (Быстрая)",
            "en": "3B (Fast)",
            "de": "3B (Schnell)",
            "fr": "3B (Rapide)",
            "es": "3B (Rápido)"
        },
        "family": "Qwen",
        "params": {
            "ru": "3.0 млрд",
            "en": "3.0B",
            "de": "3,0 Mrd.",
            "fr": "3,0 Md",
            "es": "3.0 B"
        },
        "format": "GGUF Q4_K_M",
        "file_size_gb": 2.15,
        "size_bytes": 2150000000,
        "min_ram_gb": 4.0,
        "rec_ram_gb": 6.0,
        "filename": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "download_url": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
        "description": {
            "ru": "Уверенное распознавание дорожек и ролей. Отличная скорость инференса на средних ПК.",
            "en": "Reliable lane and role identification. Excellent inference speed on mid-range PCs.",
            "de": "Zuverlässige Erkennung von Lanes und Rollen. Ausgezeichnete Geschwindigkeit auf Standard-PCs.",
            "fr": "Identification fiable des couloirs et des rôles. Vitesse d'exécution remarquable sur PC intermédiaires.",
            "es": "Identificación fiable de carriles y roles. Excelente velocidad de respuesta en PCs estándar."
        }
    },
    {
        "id": "qwen2.5-7b-instruct",
        "name": "Qwen 2.5 Instruct",
        "badge": {
            "ru": "7B (Сбалансированная)",
            "en": "7B (Balanced)",
            "de": "7B (Ausgewogen)",
            "fr": "7B (Équilibré)",
            "es": "7B (Equilibrado)"
        },
        "family": "Qwen",
        "params": {
            "ru": "7.0 млрд",
            "en": "7.0B",
            "de": "7,0 Mrd.",
            "fr": "7,0 Md",
            "es": "7.0 B"
        },
        "format": "GGUF Q4_K_M",
        "file_size_gb": 4.68,
        "size_bytes": 4683074240,
        "min_ram_gb": 6.5,
        "rec_ram_gb": 10.0,
        "filename": "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "download_url": "https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "description": {
            "ru": "Популярный стандарт для локальной генерации. Высокая точность синтаксиса BPMN 2.0.",
            "en": "Popular standard for local inference. High structural precision with BPMN 2.0 syntax.",
            "de": "Beliebter Standard für lokale Ausführung. Hohe strukturelle Präzision der BPMN 2.0-Syntax.",
            "fr": "Norme populaire pour l'exécution locale. Grande précision syntaxique et structurelle BPMN 2.0.",
            "es": "Estándar popular para ejecución local. Alta precisión estructural con sintaxis BPMN 2.0."
        }
    }
]

COMPAT_TEXTS = {
    "ru": {
        "recommended_badge": "🟢 Рекомендуется",
        "recommended_desc": "Ваш ПК ({ram:.1f} ГБ RAM) идеально подходит.",
        "compatible_badge": "🟡 Поддерживается",
        "compatible_desc": "Работает на вашем ПК. Рекомендуется закрыть тяжелые программы.",
        "insufficient_badge": "🔴 Недостаточно памяти",
        "insufficient_desc": "Требуется от {min_ram:.1f} ГБ RAM (на вашем ПК {ram:.1f} ГБ).",
    },
    "en": {
        "recommended_badge": "🟢 Recommended",
        "recommended_desc": "Your PC ({ram:.1f} GB RAM) is ideally suited.",
        "compatible_badge": "🟡 Supported",
        "compatible_desc": "Runs on your PC. It is recommended to close background apps.",
        "insufficient_badge": "🔴 Insufficient Memory",
        "insufficient_desc": "Requires at least {min_ram:.1f} GB RAM (your PC has {ram:.1f} GB).",
    },
    "de": {
        "recommended_badge": "🟢 Empfohlen",
        "recommended_desc": "Ihr PC ({ram:.1f} GB RAM) ist optimal geeignet.",
        "compatible_badge": "🟡 Unterstützt",
        "compatible_desc": "Läuft auf Ihrem PC. Es wird empfohlen, ressourcenintensive Apps zu schließen.",
        "insufficient_badge": "🔴 Nicht genug Speicher",
        "insufficient_desc": "Erfordert mind. {min_ram:.1f} GB RAM (Ihr PC hat {ram:.1f} GB).",
    },
    "fr": {
        "recommended_badge": "🟢 Recommandé",
        "recommended_desc": "Votre PC ({ram:.1f} Go RAM) est parfaitement adapté.",
        "compatible_badge": "🟡 Pris en charge",
        "compatible_desc": "Fonctionne sur votre PC. Il est conseillé de fermer les applications lourdes.",
        "insufficient_badge": "🔴 Mémoire insuffisante",
        "insufficient_desc": "Nécessite au moins {min_ram:.1f} Go RAM (votre PC dispose de {ram:.1f} Go).",
    },
    "es": {
        "recommended_badge": "🟢 Recomendado",
        "recommended_desc": "Su PC ({ram:.1f} GB RAM) es ideal para este modelo.",
        "compatible_badge": "🟡 Compatible",
        "compatible_desc": "Funciona en su PC. Se recomienda cerrar aplicaciones pesadas.",
        "insufficient_badge": "🔴 Memoria insuficiente",
        "insufficient_desc": "Requiere al menos {min_ram:.1f} GB RAM (su PC tiene {ram:.1f} GB).",
    }
}

# Глобальное состояние загрузки
_download_state = {
    "status": "idle",           # idle, downloading, completed, error, cancelled
    "model_id": None,
    "model_name": None,
    "progress_percent": 0.0,
    "downloaded_bytes": 0,
    "total_bytes": 0,
    "downloaded_mb": 0.0,
    "total_mb": 0.0,
    "speed_mb_s": 0.0,
    "eta_seconds": 0,
    "error": None
}
_download_lock = threading.Lock()
_cancel_flag = threading.Event()


def ensure_models_dir():
    """Создание директории models, если она отсутствует."""
    if not os.path.exists(MODELS_DIR):
        os.makedirs(MODELS_DIR, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """Чтение локального конфига приложения."""
    ensure_models_dir()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "active_model_id": None,
        "custom_openai_url": "",
        "custom_openai_key": "",
        "custom_openai_model": "qwen2.5:7b",
        "language": "ru"
    }


def save_config(cfg: Dict[str, Any]):
    """Сохранение локального конфига."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_model_catalog_status(locale: str = "ru") -> Dict[str, Any]:
    """
    Возвращает каталог моделей с оценкой аппаратной совместимости
    с ПК пользователя и статусом загрузки каждого файла.
    Учитывает язык интерфейса пользователя (ru, en, de, fr, es).
    """
    ensure_models_dir()
    hw = get_hardware_diagnostic()
    total_ram = hw["ram"].get("total_gb", 8.0)

    cfg = load_config()
    active_id = cfg.get("active_model_id")

    # Нормализуем локаль
    loc = locale if locale in COMPAT_TEXTS else "ru"
    txts = COMPAT_TEXTS[loc]

    catalog_result = []
    for m in MODEL_CATALOG:
        m_copy = dict(m)

        # Выбираем локализованный текст
        badge_val = m["badge"].get(loc, m["badge"]["ru"]) if isinstance(m["badge"], dict) else m["badge"]
        params_val = m["params"].get(loc, m["params"]["ru"]) if isinstance(m["params"], dict) else m["params"]
        desc_val = m["description"].get(loc, m["description"]["ru"]) if isinstance(m["description"], dict) else m["description"]

        m_copy["badge"] = badge_val
        m_copy["params"] = params_val
        m_copy["description"] = desc_val

        filepath = os.path.join(MODELS_DIR, m["filename"])
        is_downloaded = os.path.exists(filepath) and os.path.getsize(filepath) > 1024 * 1024
        file_size_on_disk = os.path.getsize(filepath) if is_downloaded else 0

        # Оценка совместимости с компьютером
        if total_ram >= m["rec_ram_gb"]:
            compat = "recommended"
            compat_badge = txts["recommended_badge"]
            compat_desc = txts["recommended_desc"].format(ram=total_ram)
        elif total_ram >= m["min_ram_gb"]:
            compat = "compatible"
            compat_badge = txts["compatible_badge"]
            compat_desc = txts["compatible_desc"]
        else:
            compat = "insufficient"
            compat_badge = txts["insufficient_badge"]
            compat_desc = txts["insufficient_desc"].format(min_ram=m["min_ram_gb"], ram=total_ram)

        m_copy["is_downloaded"] = is_downloaded
        m_copy["is_active"] = (m["id"] == active_id) and is_downloaded
        m_copy["disk_size_mb"] = round(file_size_on_disk / (1024 ** 2), 1) if is_downloaded else 0
        m_copy["compatibility"] = compat
        m_copy["compatibility_badge"] = compat_badge
        m_copy["compatibility_desc"] = compat_desc

        catalog_result.append(m_copy)

    # Если есть скачанные модели, но ни одна не активна — активируем первую скачанную
    if not any(m["is_active"] for m in catalog_result) and active_id != "custom_openai":
        downloaded = [m for m in catalog_result if m["is_downloaded"]]
        if downloaded:
            downloaded[0]["is_active"] = True
            cfg["active_model_id"] = downloaded[0]["id"]
            save_config(cfg)

    return {
        "hardware": hw,
        "config": {
            "custom_openai_url": cfg.get("custom_openai_url", ""),
            "custom_openai_key": cfg.get("custom_openai_key", ""),
            "custom_openai_model": cfg.get("custom_openai_model", "qwen2.5:7b"),
            "language": cfg.get("language", loc)
        },
        "active_model_id": cfg.get("active_model_id"),
        "models": catalog_result,
        "download_state": get_download_status()
    }


def get_download_status() -> Dict[str, Any]:
    """Текущий статус загрузки модели."""
    with _download_lock:
        return dict(_download_state)


def _download_worker(model_id: str, url: str, filename: str, target_size: int, model_name: str):
    """
    Фоновый воркер загрузки файла модели с Hugging Face.
    Поддерживает докачку (HTTP Range), обход проблем SSL на Windows и отслеживание скорости.
    """
    global _download_state, _cancel_flag
    ensure_models_dir()
    target_path = os.path.join(MODELS_DIR, filename)
    part_path = target_path + ".part"

    try:
        resume_bytes = 0
        if os.path.exists(part_path):
            resume_bytes = os.path.getsize(part_path)
            # Если временный файл больше или равен целевому, сбрасываем его
            if target_size and resume_bytes >= target_size:
                try:
                    os.remove(part_path)
                    resume_bytes = 0
                except Exception:
                    pass

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*"
        }

        # Если файл частично скачан, запрашиваем остаток
        if 0 < resume_bytes < target_size:
            headers["Range"] = f"bytes={resume_bytes}-"

        with _download_lock:
            _download_state.update({
                "status": "downloading",
                "model_id": model_id,
                "model_name": model_name,
                "progress_percent": round((resume_bytes / target_size) * 100, 1) if target_size else 0.0,
                "downloaded_bytes": resume_bytes,
                "total_bytes": target_size,
                "downloaded_mb": round(resume_bytes / (1024 ** 2), 1),
                "total_mb": round(target_size / (1024 ** 2), 1),
                "speed_mb_s": 0.0,
                "eta_seconds": 0,
                "error": None
            })

        def open_url_with_ssl(target_url, req_headers):
            req = urllib.request.Request(target_url, headers=req_headers)
            try:
                ctx = ssl.create_default_context()
                return urllib.request.urlopen(req, timeout=60, context=ctx)
            except Exception:
                unverified_ctx = ssl._create_unverified_context()
                return urllib.request.urlopen(req, timeout=60, context=unverified_ctx)

        # Выполняем запрос с обработкой HTTP 416 (Range Not Satisfiable)
        try:
            resp = open_url_with_ssl(url, headers)
        except urllib.error.HTTPError as http_err:
            if http_err.code == 416:
                # Сбрасываем поврежденный частичный файл и пробуем с 0
                if os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except Exception:
                        pass
                headers.pop("Range", None)
                resume_bytes = 0
                resp = open_url_with_ssl(url, headers)
            else:
                raise

        with resp:
            content_length = resp.headers.get("Content-Length")
            is_partial = (getattr(resp, 'status', 200) == 206)

            if is_partial and resume_bytes > 0:
                total_size = resume_bytes + int(content_length) if content_length else target_size
                mode = "ab"
                downloaded = resume_bytes
            else:
                total_size = int(content_length) if content_length else target_size
                mode = "wb"
                downloaded = 0

            with _download_lock:
                _download_state["total_bytes"] = total_size
                _download_state["total_mb"] = round(total_size / (1024 ** 2), 1)

            start_time = time.time()
            last_calc_time = start_time
            last_bytes = downloaded

            with open(part_path, mode) as f:
                while True:
                    if _cancel_flag.is_set():
                        with _download_lock:
                            _download_state.update({
                                "status": "cancelled",
                                "error": "Загрузка отменена пользователем"
                            })
                        return

                    chunk = resp.read(1024 * 512)  # 512 КБ
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    elapsed_calc = now - last_calc_time
                    if elapsed_calc >= 0.4:
                        bytes_diff = downloaded - last_bytes
                        speed_mb = (bytes_diff / elapsed_calc) / (1024 ** 2) if elapsed_calc > 0 else 0.0
                        rem_bytes = max(0, total_size - downloaded)
                        eta_sec = int(rem_bytes / (speed_mb * (1024 ** 2))) if speed_mb > 0.05 else 0
                        pct = round((downloaded / total_size) * 100, 1) if total_size > 0 else 0.0

                        with _download_lock:
                            _download_state.update({
                                "progress_percent": pct,
                                "downloaded_bytes": downloaded,
                                "downloaded_mb": round(downloaded / (1024 ** 2), 1),
                                "speed_mb_s": round(speed_mb, 2),
                                "eta_seconds": eta_sec
                            })
                        last_calc_time = now
                        last_bytes = downloaded

        # Завершение скачивания: перемещаем в финальный файл
        if not _cancel_flag.is_set():
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except Exception:
                    pass
            os.rename(part_path, target_path)

            # Автоматически активируем модель
            cfg = load_config()
            cfg["active_model_id"] = model_id
            save_config(cfg)

            with _download_lock:
                _download_state.update({
                    "status": "completed",
                    "progress_percent": 100.0,
                    "downloaded_bytes": total_size,
                    "downloaded_mb": round(total_size / (1024 ** 2), 1),
                    "speed_mb_s": 0.0,
                    "eta_seconds": 0,
                    "error": None
                })

    except Exception as ex:
        with _download_lock:
            _download_state.update({
                "status": "error",
                "error": f"Ошибка скачивания: {str(ex)}"
            })


def start_model_download(model_id: str) -> Dict[str, Any]:
    """
    Запуск фоновой загрузки модели.
    Если уже выполняется скачивание другой модели, мягко переключает загрузку
    на новую без ошибок блокировки.
    """
    global _cancel_flag, _download_state

    model = next((m for m in MODEL_CATALOG if m["id"] == model_id), None)
    if not model:
        return {"success": False, "error": f"Модель с ID '{model_id}' не найдена в каталоге."}

    with _download_lock:
        if _download_state["status"] == "downloading":
            if _download_state.get("model_id") == model_id:
                return {"success": True, "message": f"Модель {model['name']} уже скачивается."}
            # Если скачивалась другая модель, мягко отменяем её для переключения
            _cancel_flag.set()

    # Небольшая пауза для корректной остановки предыдущего воркера
    time.sleep(0.15)
    _cancel_flag.clear()

    # Предварительно устанавливаем статус загрузки
    with _download_lock:
        _download_state.update({
            "status": "downloading",
            "model_id": model_id,
            "model_name": model["name"],
            "progress_percent": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": model["size_bytes"],
            "downloaded_mb": 0.0,
            "total_mb": round(model["size_bytes"] / (1024 ** 2), 1),
            "speed_mb_s": 0.0,
            "eta_seconds": 0,
            "error": None
        })

    t = threading.Thread(
        target=_download_worker,
        args=(model_id, model["download_url"], model["filename"], model["size_bytes"], model["name"]),
        daemon=True
    )
    t.start()
    return {"success": True, "message": f"Начата загрузка {model['name']}"}


def cancel_model_download() -> Dict[str, Any]:
    """Отмена текущей загрузки или сброс ошибки."""
    global _cancel_flag
    _cancel_flag.set()
    with _download_lock:
        _download_state.update({
            "status": "idle",
            "model_id": None,
            "model_name": None,
            "progress_percent": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "downloaded_mb": 0.0,
            "total_mb": 0.0,
            "speed_mb_s": 0.0,
            "eta_seconds": 0,
            "error": None
        })
    return {"success": True, "message": "Загрузка сброшена"}


def set_active_model(model_id: str) -> Dict[str, Any]:
    """Установка активной модели."""
    cfg = load_config()

    if model_id == "custom_openai":
        cfg["active_model_id"] = "custom_openai"
        save_config(cfg)
        return {"success": True, "active_model_id": "custom_openai", "name": f"Внешний сервер ({cfg.get('custom_openai_model', 'OpenAI API')})"}

    model = next((m for m in MODEL_CATALOG if m["id"] == model_id), None)
    if not model:
        return {"success": False, "error": f"Модель '{model_id}' не найдена в каталоге"}

    filepath = os.path.join(MODELS_DIR, model["filename"])
    if not os.path.exists(filepath):
        return {"success": False, "error": f"Файл модели ещё не скачан: {model['filename']}"}

    cfg["active_model_id"] = model_id
    save_config(cfg)
    return {"success": True, "active_model_id": model_id, "name": model["name"]}


def delete_model_file(model_id: str) -> Dict[str, Any]:
    """Удаление скачанного файла модели для освобождения места на диске."""
    model = next((m for m in MODEL_CATALOG if m["id"] == model_id), None)
    if not model:
        return {"success": False, "error": "Модель не найдена"}

    filepath = os.path.join(MODELS_DIR, model["filename"])
    part_path = filepath + ".part"
    deleted = False

    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            deleted = True
        except Exception as e:
            return {"success": False, "error": f"Ошибка удаления файла: {str(e)}"}

    if os.path.exists(part_path):
        try:
            os.remove(part_path)
            deleted = True
        except Exception:
            pass

    if deleted:
        cfg = load_config()
        if cfg.get("active_model_id") == model_id:
            cfg["active_model_id"] = None
            save_config(cfg)
        return {"success": True, "message": f"Модель {model['name']} успешно удалена"}

    return {"success": False, "error": "Файл модели отсутствует на диске"}
