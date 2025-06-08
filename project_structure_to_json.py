# mishka_ai/project_structure_to_json.py

import os
import json
from pathlib import Path
import datetime

# --- Конфигурация ---
# Папка проекта (относительно этого скрипта)
# Если скрипт лежит в mishka_ai/, то PROJECT_ROOT это текущая директория
PROJECT_ROOT = Path(__file__).resolve().parent 

# Имя выходного JSON файла
OUTPUT_FILE_NAME = f"project_structure_{PROJECT_ROOT.name}.json"

# Папки, которые нужно полностью пропустить (регистронезависимо)
EXCLUDED_DIRS = {
    ".git", 
    ".idea", 
    ".vscode",
    "__pycache__",
    "venv", 
    ".venv",
    "env",
    "node_modules",
    "build",
    "dist",
    "logs", # Папка для логов
    "data", # Папку data мы хотим видеть в структуре, но содержимое JSON файлов из нее не всегда нужно
            # Если содержимое data/ тоже не нужно, добавь "data" сюда.
            # Сейчас мы будем обрабатывать ее отдельно через EXCLUDED_FILES_CONTENT
    "chroma_db_mishka" # Папка базы ChromaDB внутри data/
}

# Файлы, содержимое которых не нужно включать (полные пути относительно PROJECT_ROOT или просто имена)
# Регистронезависимо для имен файлов, регистрочувствительно для путей
EXCLUDED_FILES_CONTENT = {
    ".env", # Конфиденциальные данные
    OUTPUT_FILE_NAME, # Сам выходной файл
    "long_term_memory.json", # Может быть большим, и сейчас не основной для LTM
    "emotional_memory.json",
    "project_structure_mishka_ai.json"
      # Может содержать личную информацию
    # "users.json", # Если не хочешь видеть его содержимое (но структуру увидим)
    # "prompts.json" # Если не хочешь видеть его содержимое
    # Можно добавлять конкретные пути: "data/some_large_file.log"
}
# Добавим сюда все файлы из папки data, если хотим видеть структуру data, но не содержимое файлов в ней
# Это можно сделать и более гибко, например, если имя папки "data" есть в EXCLUDED_DIRS_CONTENT_ONLY
# Но для простоты пока так:
EXCLUDED_FILES_CONTENT.update({
    f"data/{fname}" for fname in os.listdir(PROJECT_ROOT / "data") 
    if os.path.isfile(PROJECT_ROOT / "data" / fname) 
       and not fname.endswith(".gitkeep") # Исключаем .gitkeep, если есть
       and fname not in ["prompts.json", "users.json"] # Если эти все же хотим видеть
})


# Расширения файлов, содержимое которых не нужно включать (но сами файлы будут в структуре)
EXCLUDED_EXTENSIONS_CONTENT = {
    ".pyc",
    ".log",
    ".db", ".sqlite", ".sqlite3", # Файлы баз данных
    ".tmp",
    ".bak",
    ".swp",
    ".zip", ".gz", ".tar", ".rar", # Архивы
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", # Изображения
    ".mp3", ".wav", ".ogg", # Аудио
    ".mp4", ".mov", ".avi", # Видео
    # Добавь сюда другие бинарные или нетекстовые расширения
}

# Максимальный размер файла (в байтах) для включения содержимого, чтобы избежать очень больших JSON
MAX_FILE_SIZE_FOR_CONTENT = 1 * 1024 * 1024  # 1 MB

# --- Функции ---

def get_file_content(file_path: Path) -> str | None:
    """Читает содержимое файла, если это возможно и разрешено."""
    try:
        # Проверка на максимальный размер
        if file_path.stat().st_size > MAX_FILE_SIZE_FOR_CONTENT:
            return f"<Содержимое файла превышает лимит {MAX_FILE_SIZE_FOR_CONTENT // (1024*1024)} MB>"
        
        # Пытаемся прочитать как UTF-8, если не удается - помечаем как бинарный
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        return "<Бинарный файл или файл в неизвестной кодировке>"
    except Exception as e:
        return f"<Ошибка чтения файла: {e}>"

def build_structure(current_path: Path, project_root: Path) -> dict:
    """Рекурсивно строит структуру директории."""
    structure = {}
    for item in sorted(current_path.iterdir()): # Сортируем для консистентности
        relative_item_path_str = str(item.relative_to(project_root))
        item_name_lower = item.name.lower()

        if item.is_dir():
            if item_name_lower not in EXCLUDED_DIRS and item.name not in EXCLUDED_DIRS: # Проверка и точного имени и lower
                structure[item.name] = build_structure(item, project_root)
        
        elif item.is_file():
            # Проверяем, нужно ли исключить содержимое по полному пути или имени файла
            exclude_content_by_path_or_name = (
                item_name_lower in EXCLUDED_FILES_CONTENT or 
                item.name in EXCLUDED_FILES_CONTENT or
                relative_item_path_str in EXCLUDED_FILES_CONTENT or
                relative_item_path_str.lower() in EXCLUDED_FILES_CONTENT
            )
            
            # Проверяем, нужно ли исключить содержимое по расширению
            exclude_content_by_extension = item.suffix.lower() in EXCLUDED_EXTENSIONS_CONTENT
            
            if exclude_content_by_path_or_name or exclude_content_by_extension:
                structure[item.name] = "<Содержимое этого файла исключено из вывода>"
            else:
                structure[item.name] = get_file_content(item)
    return structure

# --- Основная логика ---
if __name__ == "__main__":
    print(f"Начинаю анализ структуры проекта в: {PROJECT_ROOT}")
    
    # Обновляем EXCLUDED_FILES_CONTENT для конкретного выходного файла
    # Это на случай, если скрипт запускается несколько раз и создает разные выходные файлы
    current_output_file_path = PROJECT_ROOT / OUTPUT_FILE_NAME
    EXCLUDED_FILES_CONTENT.add(OUTPUT_FILE_NAME) # Добавляем только имя, так как скрипт в корне
    EXCLUDED_FILES_CONTENT.add(Path(__file__).name) # Исключаем сам этот скрипт

    project_data = {
        "project_name": PROJECT_ROOT.name,
        "generated_at": datetime.datetime.now().isoformat(),
        "structure": build_structure(PROJECT_ROOT, PROJECT_ROOT)
    }

    output_path = PROJECT_ROOT / OUTPUT_FILE_NAME
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, ensure_ascii=False, indent=2)
        print(f"Структура проекта успешно сохранена в: {output_path}")
    except Exception as e:
        print(f"Ошибка при сохранении JSON файла: {e}")