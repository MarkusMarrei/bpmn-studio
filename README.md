# BPMN Studio (⚡ bpmn-studio)

> **AI BPMN Generator** — Local, privacy-first AI Studio for Text-to-BPMN 2.0 process modeling with quantized LLMs (Bonsai 2 & Qwen) and 5-language support (RU, EN, DE, FR, ES).  
> Transform text regulations, SOPs, and documents (PDF, DOCX, TXT) into production-ready OMG BPMN 2.0 diagrams with intelligent business-logic auditing.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-green.svg)](https://www.python.org/)
[![OMG BPMN 2.0](https://img.shields.io/badge/BPMN-2.0.2%20Compliant-orange.svg)](https://www.omg.org/spec/BPMN/2.0/)
[![Local LLM](https://img.shields.io/badge/Local%20LLM-Bonsai%202%20%7C%20Qwen%202.5-purple.svg)](https://huggingface.co/prism-ml/Bonsai-2-27B-GGUF)
[![Languages](https://img.shields.io/badge/Languages-RU%20%7C%20EN%20%7C%20DE%20%7C%20FR%20%7C%20ES-blueviolet.svg)](#)

---

## 🌟 Overview

**BPMN Studio** is an open-source, privacy-first desktop application designed for business analysts, enterprise architects, and software engineers. It enables running quantized state-of-the-art LLMs locally on consumer hardware to parse complex operational procedures and automatically generate validated, beautiful **BPMN 2.0 XML** diagrams.

Whether you run it completely offline on a low-spec laptop or connect it to high-end GPUs and local servers (Ollama, LM Studio), the system automatically adapts to your hardware capabilities.

---

## 🚀 Key Features

### 🌐 1. Native Multi-Language Support (5 Languages)
- Fully localized in **Russian, English, German, French, and Spanish** (`RU`, `EN`, `DE`, `FR`, `ES`).
- Interactive language selector on startup, dynamic switching without page reloads.
- LLM prompting dynamically commands the model to speak and build BPMN artifacts in the user's active locale.

### 💻 2. Built-in Hardware Diagnostic Scanner
- **Zero external dependencies**: Automatically detects available RAM, CPU threads, and GPU / VRAM on Windows and Linux using native OS APIs.
- **Hardware Tier Scoring**: Classifies your system (Light, Standard, High, Ultra) and assigns color-coded compatibility badges (🟢 Recommended, 🟡 Supported, 🔴 Memory Warning).

### 🧠 3. Integrated LLM Manager & Catalog
- **Bonsai 2 Family (PrismML Ternary Qwen)**: Extreme 1.5-bit quantization providing ultra-compact models that run smoothly on consumer hardware:
  - **Bonsai 2 (1.7B)**: ~442 MB download — ultra-fast generation even on low-power devices.
  - **Bonsai 2 (4.8B)**: ~1.02 GB download — optimal balance between speed and precision.
  - **Bonsai 2 (8B)**: ~2.03 GB download — high accuracy and lane assignment.
  - **Bonsai 2 (27B)**: ~5.54 GB download — flagship 27B reasoning inside ~6 GB RAM/VRAM.
- **Qwen 2.5 Instruct**: 1.5B (Light), 3B (Fast), and 7B (Balanced).
- **1-Click Downloader**: Downloads `.gguf` weights directly from Hugging Face with real-time speed, MB progress, and ETA calculation with HTTP Range resume support.
- **External API & Ollama Connect**: Point directly to your local Ollama (`http://localhost:11434/v1`), LM Studio (`http://localhost:1234/v1`), or any OpenAI-compatible API endpoint.

### 📐 4. Hybrid BPMN Engine & Layout Calculation
- **100% OMG BPMN 2.0 Valid XML**: Standard `<bpmn:definitions>`, `<bpmn:collaboration>`, `<bpmn:laneSet>`, and `<bpmndi:BPMNDiagram>`.
- **Topological Auto-Layout**: Solves coordinate collision, calculates ortholine waypoints, and maintains clean clearances around tasks and gateways.
- **Business Logic Auditor**: Automatically identifies unhandled exception paths, bottleneck approvals, and dead ends.

### 🎨 5. Modern Interactive Studio UI
- **bpmn-js Modeler**: In-browser drag-and-drop editing, zoom, pan, and live XML inspection.
- **Dark & Light Monochrome Themes**: High-contrast, accessibility-tested palette with automatic canvas inversion.
- **Document Ingestion**: Drag-and-drop `.pdf`, `.docx`, `.txt`, and `.md` files with automatic text parsing and normalization.
- **Export Formats**: Download `.bpmn` XML, vector `.svg`, or copy generated Python DSL code.

---

## 📦 Architecture

```
bpmn-studio/
├── app.py                    # FastAPI / Uvicorn server (REST API & Web UI)
├── run.bat                   # 1-Click Windows Desktop Launcher
├── requirements.txt          # Python dependencies
├── LICENSE                   # Apache 2.0 License (Markus Marrei)
├── backend/
│   ├── hardware_scanner.py   # Native RAM / CPU / GPU hardware scanner
│   ├── model_manager.py      # LLM catalog, download tracker & compatibility evaluator
│   ├── llm_runner.py         # Local GGUF inference & OpenAI / Ollama integration
│   ├── bpmn_engine.py        # Topological layout & OMG BPMN 2.0 XML generator
│   ├── document_parser.py    # Multi-format PDF / DOCX / TXT extractor
│   └── prompts.py            # Multilingual system prompts for process extraction
├── public_html/
│   └── index.html            # Single-page UI with bpmn-js Modeler & LLM Manager Modal
└── models/                   # Local storage for downloaded .gguf weights (git-ignored)
```

---

## ⚡ Quick Start

### Windows (One-Click)
Double-click `run.bat` in the repository root. The launcher will automatically:
1. Verify Python 3.10+ installation.
2. Install dependencies if missing.
3. Start the server and launch your default browser at `http://localhost:8000`.

### Manual CLI Launch

1. **Clone the repository:**
   ```bash
   git clone https://github.com/MarkusMarrei/bpmn-studio.git
   cd bpmn-studio
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server:**
   ```bash
   python app.py
   # or on Windows with py launcher:
   py app.py
   ```

4. **Open in browser:**
   Navigate to [http://localhost:8000](http://localhost:8000).

---

## 🛠 Model Selection Guide

| Model | Parameters | Quantization | File Size | Minimum RAM | Recommended RAM | Target Hardware |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bonsai 2 (1.7B)** | 1.7 Billion | Ternary 1.5-bit | ~442 MB | 1.5 GB | 3.0 GB | Entry-level laptops & CPU |
| **Bonsai 2 (4.8B)** | 4.8 Billion | Ternary 1.5-bit | ~1.02 GB | 2.5 GB | 4.0 GB | Balanced consumer PCs |
| **Bonsai 2 (8B)** | 8.0 Billion | Ternary 1.5-bit | ~2.03 GB | 4.0 GB | 6.0 GB | High-accuracy business analysis |
| **Bonsai 2 (27B)** | 27.0 Billion | Ternary 1.5-bit | ~5.54 GB | 7.5 GB | 12.0 GB | Flagship reasoning & edge GPUs |
| **Qwen 2.5 1.5B** | 1.5 Billion | Q4_K_M | ~1.12 GB | 2.5 GB | 4.0 GB | Budget laptops |
| **Qwen 2.5 3B** | 3.0 Billion | Q4_K_M | ~2.15 GB | 4.0 GB | 6.0 GB | 8 GB RAM machines |
| **Qwen 2.5 7B** | 7.0 Billion | Q4_K_M | ~4.68 GB | 6.5 GB | 10.0 GB | Modern workstations |
| **External Ollama** | Any | Remote / Local | 0 MB | 500 MB | 1.0 GB | Existing Ollama / LM Studio |

---

## 📄 License & Legal Notice

Copyright (c) 2026 **Markus Marrei**.  
Licensed under the **Apache License, Version 2.0**. See the [LICENSE](LICENSE) file for details.

> **Trademark Notice:** BPMN® and Business Process Model and Notation™ are registered trademarks of the Object Management Group (OMG). BPMN Studio is an independent open-source project compliant with the OMG BPMN 2.0 specification.
