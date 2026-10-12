"""
Модуль для извлечения текста из различных форматов документов:
- PDF (.pdf)
- Word (.docx)
- Текстовые файлы (.txt, .md, .rtf)

Спроектирован для работы в изолированных серверных средах:
- DOCX парсится через встроенные zipfile + xml.etree.ElementTree без внешних зависимостей.
- PDF парсится через pypdf (включая встроенный vendor) и аварийный парсер потоков.
"""

import io
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from typing import Optional, Union

# Подключение каталога vendor для встроенных чистых python-библиотек (например, pypdf)
current_dir = os.path.dirname(os.path.abspath(__file__))
vendor_dir = os.path.join(current_dir, "vendor")
if os.path.exists(vendor_dir) and vendor_dir not in sys.path:
    sys.path.insert(0, vendor_dir)


def clean_extracted_text(text: str) -> str:
    """
    Очистка извлеченного текста:
    - Нормализация переводов строк
    - Удаление повторяющихся пустых строк
    - Склейка разорванных дефисом слов на стыке строк
    """
    if not text:
        return ""
    # Склейка переносов слов: "электро- \nпередача" -> "электропередача"
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    # Замена нескольких пустых строк на двойной перенос
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Удаление непечатаемых символов (кроме пробелов и переносов)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    return text.strip()


def _extract_docx_xml(raw_bytes: bytes) -> str:
    """
    Извлечение текста из .docx через стандартную библиотеку zipfile и xml.
    Не требует сторонней библиотеки python-docx!
    """
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
        if 'word/document.xml' not in z.namelist():
            raise ValueError("Не найден word/document.xml внутри DOCX архива")
        xml_content = z.read('word/document.xml')

    tree = ET.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

    paragraphs = []
    # 1. Извлечение параграфов
    for p in tree.iterfind('.//w:p', ns):
        text_nodes = [node.text for node in p.iterfind('.//w:t', ns) if node.text]
        if text_nodes:
            paragraphs.append(''.join(text_nodes))

    # 2. Извлечение таблиц (регламенты часто содержат таблицы этапов)
    for tbl in tree.iterfind('.//w:tbl', ns):
        tbl_rows = []
        for tr in tbl.iterfind('.//w:tr', ns):
            row_cells = []
            for tc in tr.iterfind('.//w:tc', ns):
                cell_text = ' '.join([node.text for node in tc.iterfind('.//w:t', ns) if node.text])
                if cell_text.strip():
                    row_cells.append(cell_text.strip())
            if row_cells:
                tbl_rows.append(' | '.join(row_cells))
        if tbl_rows:
            paragraphs.append('\n[Таблица]:\n' + '\n'.join(tbl_rows) + '\n')

    return '\n\n'.join(paragraphs)


def extract_from_docx(file_source: Union[str, bytes, io.BytesIO]) -> str:
    """
    Извлечение текста из Word (.docx) документа.
    """
    raw_bytes: bytes
    if isinstance(file_source, str):
        with open(file_source, 'rb') as f:
            raw_bytes = f.read()
    elif isinstance(file_source, io.BytesIO):
        raw_bytes = file_source.getvalue()
    else:
        raw_bytes = file_source

    # 1. Сначала используем встроенный парсер zipfile (не требует pip install)
    try:
        text = _extract_docx_xml(raw_bytes)
        if text.strip():
            return clean_extracted_text(text)
    except Exception as e:
        pass

    # 2. Fallback к python-docx, если установлен
    try:
        import docx
        doc = docx.Document(io.BytesIO(raw_bytes))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        return clean_extracted_text('\n\n'.join(parts))
    except Exception:
        pass

    raise ValueError("Не удалось прочитать DOCX файл. Убедитесь, что это корректный файл Microsoft Word (.docx).")


def _extract_pdf_raw_streams(raw_bytes: bytes) -> str:
    """
    Резервный парсер PDF потоков на чистом Python:
    распаковывает FlateDecode потоки через zlib и извлекает текстовые маркеры Tj / TJ.
    """
    texts = []
    # Поиск всех потоков stream ... endstream
    stream_matches = re.finditer(rb'stream[\r\n]+(.*?)[\r\n]+endstream', raw_bytes, re.DOTALL)
    for match in stream_matches:
        stream_data = match.group(1)
        decompressed = None
        try:
            decompressed = zlib.decompress(stream_data)
        except Exception:
            try:
                decompressed = zlib.decompress(stream_data, -zlib.MAX_WBITS)
            except Exception:
                decompressed = stream_data

        # Ищем текстовые фрагменты вида (текст) Tj или [(т)(е)(к)(с)(т)] TJ
        tj_matches = re.findall(rb'\((.*?)\)\s*Tj', decompressed)
        for m in tj_matches:
            try:
                # Пробуем декодировать utf-8 или cp1251
                decoded = m.decode('utf-8', errors='ignore')
                if len(decoded.strip()) > 1:
                    texts.append(decoded)
            except Exception:
                pass

    return clean_extracted_text('\n'.join(texts))


def extract_from_pdf(file_source: Union[str, bytes, io.BytesIO]) -> str:
    """
    Извлечение текста из PDF документа.
    Поддерживает pypdf (включая встроенный в vendor), fitz (PyMuPDF) и потоковый fallback.
    """
    raw_bytes: bytes
    if isinstance(file_source, str):
        with open(file_source, 'rb') as f:
            raw_bytes = f.read()
    elif isinstance(file_source, io.BytesIO):
        raw_bytes = file_source.getvalue()
    else:
        raw_bytes = file_source

    text_parts = []

    last_pdf_err = "неизвестная ошибка"
    # 1. Пробуем pypdf (из окружения или встроенного backend/vendor)
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw_bytes))
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        extracted = "\n".join(text_parts).strip()
        if extracted:
            return clean_extracted_text(extracted)
    except Exception as e:
        last_pdf_err = f"pypdf: {str(e)}"

    # 2. Пробуем pymupdf (fitz), если установлен
    try:
        import fitz
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        for page in doc:
            t = page.get_text("text")
            if t:
                text_parts.append(t)
        doc.close()
        extracted = "\n".join(text_parts).strip()
        if extracted:
            return clean_extracted_text(extracted)
    except Exception as e:
        last_pdf_err += f" | fitz: {str(e)}"

    # 3. Аварийный парсер прямых потоков
    fallback_text = _extract_pdf_raw_streams(raw_bytes)
    if fallback_text.strip():
        return fallback_text

    raise ValueError(f"Не удалось извлечь текст из PDF ({last_pdf_err}). Возможно, файл защищен паролем или содержит только растровые изображения.")


def extract_from_text(file_source: Union[str, bytes, io.BytesIO]) -> str:
    """
    Извлечение текста из текстового файла (.txt, .md).
    Автоматически определяет кодировку (UTF-8 / CP1251).
    """
    raw_bytes: bytes
    if isinstance(file_source, str):
        if os.path.isfile(file_source):
            with open(file_source, 'rb') as f:
                raw_bytes = f.read()
        else:
            return clean_extracted_text(file_source)
    elif isinstance(file_source, io.BytesIO):
        raw_bytes = file_source.getvalue()
    else:
        raw_bytes = file_source

    for encoding in ['utf-8', 'utf-8-sig', 'windows-1251', 'cp866', 'latin-1']:
        try:
            return clean_extracted_text(raw_bytes.decode(encoding))
        except UnicodeDecodeError:
            continue

    return clean_extracted_text(raw_bytes.decode('utf-8', errors='ignore'))


def extract_document_text(filename: str, content: Union[bytes, io.BytesIO]) -> str:
    """
    Универсальная точка входа для извлечения текста по расширению файла.
    """
    ext = os.path.splitext(filename.lower())[1]

    if ext == '.pdf':
        return extract_from_pdf(content)
    elif ext in ('.docx', '.doc'):
        return extract_from_docx(content)
    elif ext in ('.txt', '.md', '.rtf', '.log', '.csv'):
        return extract_from_text(content)
    else:
        # Пробуем как текстовый файл
        try:
            return extract_from_text(content)
        except Exception:
            raise ValueError(f"Неподдерживаемый формат файла: {ext}. Поддерживаются .pdf, .docx, .txt")
