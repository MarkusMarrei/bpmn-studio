"""
Модуль аппаратной диагностики (Hardware Scanner) для BPMN Studio (AI BPMN Generator).
Определяет доступную оперативную память (RAM), ядра процессора (CPU)
и видеокарту (GPU/VRAM) без обязательных внешних зависимостей.
Позволяет автоматически подбирать совместимые квантованные LLM-модели (Bonsai v2, Qwen).
"""

import os
import platform
import subprocess
import shutil
from typing import Dict, Any, List, Optional

# Попытка импортировать ctypes для прямого Win32 API
try:
    import ctypes
    from ctypes import wintypes
    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False


def _get_ram_windows() -> Dict[str, float]:
    """Получение объема RAM через Windows API (GlobalMemoryStatusEx)."""
    if not HAS_CTYPES or platform.system() != "Windows":
        return {}

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_uint64),
            ("ullAvailPhys", ctypes.c_uint64),
            ("ullTotalPageFile", ctypes.c_uint64),
            ("ullAvailPageFile", ctypes.c_uint64),
            ("ullTotalVirtual", ctypes.c_uint64),
            ("ullAvailVirtual", ctypes.c_uint64),
            ("ullAvailExtendedVirtual", ctypes.c_uint64),
        ]

    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total_gb = round(stat.ullTotalPhys / (1024 ** 3), 2)
            avail_gb = round(stat.ullAvailPhys / (1024 ** 3), 2)
            used_gb = round(total_gb - avail_gb, 2)
            load_pct = stat.dwMemoryLoad
            return {
                "total_gb": total_gb,
                "avail_gb": avail_gb,
                "used_gb": used_gb,
                "percent_used": float(load_pct)
            }
    except Exception:
        pass
    return {}


def _get_ram_linux() -> Dict[str, float]:
    """Получение объема RAM на Linux через /proc/meminfo."""
    try:
        meminfo = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    meminfo[key] = int(val)
        total_kb = meminfo.get("MemTotal", 0)
        avail_kb = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
        total_gb = round(total_kb / (1024 ** 2), 2)
        avail_gb = round(avail_kb / (1024 ** 2), 2)
        used_gb = round(total_gb - avail_gb, 2)
        load_pct = round((used_gb / total_gb) * 100, 1) if total_gb > 0 else 0
        return {
            "total_gb": total_gb,
            "avail_gb": avail_gb,
            "used_gb": used_gb,
            "percent_used": load_pct
        }
    except Exception:
        return {}


def _get_ram_info() -> Dict[str, float]:
    """Универсальное получение объема оперативной памяти."""
    # 1. Попытка через psutil, если установлен
    try:
        import psutil
        v = psutil.virtual_memory()
        return {
            "total_gb": round(v.total / (1024 ** 3), 2),
            "avail_gb": round(v.available / (1024 ** 3), 2),
            "used_gb": round(v.used / (1024 ** 3), 2),
            "percent_used": float(v.percent)
        }
    except ImportError:
        pass

    # 2. Нативные механизмы
    if platform.system() == "Windows":
        info = _get_ram_windows()
        if info:
            return info
    elif platform.system() == "Linux":
        info = _get_ram_linux()
        if info:
            return info

    # Fallback по умолчанию (8 ГБ базовая заглушка)
    return {
        "total_gb": 8.0,
        "avail_gb": 4.0,
        "used_gb": 4.0,
        "percent_used": 50.0
    }


def _get_gpus() -> List[Dict[str, Any]]:
    """Детекция графических ускорителей (NVIDIA CUDA, AMD, Intel, Apple Silicon)."""
    gpus: List[Dict[str, Any]] = []

    # 1. Проверка nvidia-smi (NVIDIA CUDA)
    if shutil.which("nvidia-smi"):
        try:
            cmd = ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"]
            out = subprocess.check_output(cmd, encoding="utf-8", stderr=subprocess.DEVNULL, timeout=2)
            for line in out.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    total_mb = int(parts[1])
                    free_mb = int(parts[2])
                    gpus.append({
                        "name": parts[0],
                        "total_vram_gb": round(total_mb / 1024, 1),
                        "free_vram_gb": round(free_mb / 1024, 1),
                        "vendor": "NVIDIA",
                        "has_cuda": True,
                        "acceleration": "CUDA"
                    })
            if gpus:
                return gpus
        except Exception:
            pass

    # 2. Windows CIM/WMI запрос (AMD / Intel / встроенная графика)
    if platform.system() == "Windows":
        try:
            cmd = [
                "powershell", "-NoProfile", "-NonInteractive", "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM | ConvertTo-Json"
            ]
            out = subprocess.check_output(cmd, encoding="utf-8", stderr=subprocess.DEVNULL, timeout=3)
            import json
            data = json.loads(out)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                name = item.get("Name", "Graphics Device")
                ram_b = item.get("AdapterRAM") or 0
                vram_gb = round(ram_b / (1024 ** 3), 1) if ram_b > 0 else 0.0
                vendor = "AMD" if "AMD" in name or "Radeon" in name else ("Intel" if "Intel" in name else "Generic")
                gpus.append({
                    "name": name,
                    "total_vram_gb": vram_gb,
                    "free_vram_gb": vram_gb,
                    "vendor": vendor,
                    "has_cuda": False,
                    "acceleration": "CPU / DirectML"
                })
        except Exception:
            pass

    # Если дискретный GPU не найден — режим CPU
    if not gpus:
        gpus.append({
            "name": "CPU Acceleration (AVX2/NEON)",
            "total_vram_gb": 0.0,
            "free_vram_gb": 0.0,
            "vendor": "CPU",
            "has_cuda": False,
            "acceleration": "CPU Threads"
        })

    return gpus


def get_hardware_diagnostic() -> Dict[str, Any]:
    """
    Полный аппаратный скан компьютера пользователя.
    Возвращает структуру с метриками и рекомендуемым классом модели.
    """
    ram = _get_ram_info()
    gpus = _get_gpus()
    cpu_cores = os.cpu_count() or 4
    primary_gpu = gpus[0] if gpus else {}

    total_ram = ram.get("total_gb", 8.0)
    avail_ram = ram.get("avail_gb", 4.0)
    has_cuda = primary_gpu.get("has_cuda", False)
    vram_gb = primary_gpu.get("total_vram_gb", 0.0)

    # Оценка производительности (Hardware Tier)
    if total_ram >= 32 or (has_cuda and vram_gb >= 16):
        tier = "ultra"
        tier_label = "Высокая производительность (Ultra)"
        rec_model_size = "14B – 27B (Bonsai 2)"
        badge_color = "emerald"
    elif total_ram >= 16 or (has_cuda and vram_gb >= 8):
        tier = "high"
        tier_label = "Оптимальная система (High)"
        rec_model_size = "7B – 27B (Bonsai 2)"
        badge_color = "teal"
    elif total_ram >= 10:
        tier = "medium"
        tier_label = "Стандартный ПК (Medium)"
        rec_model_size = "3B – 7B (Bonsai / Qwen)"
        badge_color = "blue"
    else:
        tier = "low"
        tier_label = "Энергоэффективный / Офисный ПК (Light)"
        rec_model_size = "1.5B – 3B (Qwen)"
        badge_color = "amber"

    return {
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "cpu": {
            "cores": cpu_cores,
            "processor": platform.processor() or "Multi-Core CPU"
        },
        "ram": ram,
        "gpu": primary_gpu,
        "all_gpus": gpus,
        "tier": tier,
        "tier_label": tier_label,
        "rec_model_size": rec_model_size,
        "badge_color": badge_color
    }
