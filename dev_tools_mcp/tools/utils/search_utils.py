import os
import pathlib
import re
from typing import List

from .constants import MAX_SEARCH_RESULTS, MAX_RIPGREP_MB, MAX_BYTE_SIZE, DEFAULT_IGNORE_FILES


class SearchResult:
    def __init__(self, file_path, line, line_number, match, before, after):
        self.file_path = file_path
        self.line = line
        self.line_number = line_number
        self.match = match
        self.before_context = before
        self.after_context = after


def search_files_with_hypergrep(dir_path: str, query: str, file_pattern: str | None, cwd: str) -> List[SearchResult]:
    """
    Search files using Python's built-in re module with .gitignore support.
    
    This function scans each file individually using regex search,
    providing similar functionality to hypergrep but with better cross-platform compatibility.
    
    Args:
        dir_path: Directory path to search in
        query: Search query string (regex pattern)
        file_pattern: Optional file pattern filter (e.g., "*.py")
        cwd: Current working directory for relative path resolution
        
    Returns:
        List of SearchResult objects containing match information
        
    Raises:
        RuntimeError: If search encounters an error
    """
    results: List[SearchResult] = []
    
    # Собираем все игнор-файлы
    ignore_files = []
    from .path_utils import collect_gitignores
    ignore_files.extend(collect_gitignores(dir_path))
    for fname in DEFAULT_IGNORE_FILES:
        path = os.path.join(dir_path, fname)
        if os.path.isfile(path):
            ignore_files.append(path)

    # Создаем set игнорируемых файлов для быстрой проверки
    ignored_files = set()
    for ignore_file in ignore_files:
        try:
            with open(ignore_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        ignored_files.add(line)
        except:
            continue

    def should_ignore_file(file_path: str) -> bool:
        """Check if file should be ignored based on .gitignore patterns"""
        rel_path = os.path.relpath(file_path, dir_path)
        for pattern in ignored_files:
            if pattern in rel_path or rel_path.endswith(pattern):
                return True
        return False

    try:
        # Компилируем regex паттерн
        try:
            search_pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            # Если паттерн невалидный, используем как простую строку
            search_pattern = re.compile(re.escape(query), re.IGNORECASE)
        
        # Рекурсивно обходим директорию и сканируем каждый файл
        files_scanned = 0
        files_filtered = 0
        for root, dirs, files in os.walk(dir_path):
            # Пропускаем скрытые директории
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if len(results) >= MAX_SEARCH_RESULTS:
                    break
                    
                # Пропускаем скрытые файлы
                if file.startswith('.'):
                    files_filtered += 1
                    continue
                    
                # Проверяем паттерн файла
                if file_pattern:
                    # Упрощенная проверка паттерна
                    if file_pattern.startswith('*.'):
                        extension = file_pattern[1:]  # убираем *
                        if not file.endswith(extension):
                            files_filtered += 1
                            continue
                    else:
                        # Если паттерн не начинается с *, проверяем точное совпадение
                        if file != file_pattern:
                            files_filtered += 1
                            continue
                    
                file_path = os.path.join(root, file)
                
                # Пропускаем игнорируемые файлы
                if should_ignore_file(file_path):
                    files_filtered += 1
                    continue
                
                # Сканируем файл с Python re
                try:
                    scan_results = []
                    
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        
                        for line_index, line_text in enumerate(lines):
                            if len(results) >= MAX_SEARCH_RESULTS:
                                break
                                
                            # Ищем совпадения
                            if search_pattern.search(line_text):
                                scan_results.append((line_index, line_text.strip()))
                    
                    files_scanned += 1
                    
                    # Обрабатываем результаты
                    for line_index, line_text in scan_results:
                        if len(results) >= MAX_SEARCH_RESULTS:
                            break
                            
                        # Получаем контекст
                        before_lines = []
                        after_lines = []
                        
                        if 0 <= line_index < len(lines):
                            # Контекст до
                            start = max(0, line_index - 1)
                            before_lines = [lines[i].strip() for i in range(start, line_index)]
                            
                            # Контекст после
                            end = min(len(lines), line_index + 2)
                            after_lines = [lines[i].strip() for i in range(line_index + 1, end)]
                        
                        results.append(SearchResult(
                            file_path=file_path,
                            line=line_text,
                            line_number=line_index + 1,  # +1 для человекочитаемого номера строки
                            match=line_text,
                            before=before_lines,
                            after=after_lines,
                        ))
                        
                except Exception as e:
                    # Пропускаем файлы с ошибками
                    continue
        
    except Exception as e:
        raise RuntimeError(f"Error during search: {str(e)}")

    return results
