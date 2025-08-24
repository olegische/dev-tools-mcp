# Константы для directory explorer tool

# Лимиты для поиска
MAX_SEARCH_RESULTS = 300
MAX_RIPGREP_MB = 0.25
MAX_BYTE_SIZE = int(MAX_RIPGREP_MB * 1024 * 1024)

# Лимиты для списков и дерева
DEFAULT_FILE_LIMIT = 100
MAX_FILE_LIMIT = 1000

# Игнор файлы для поиска
DEFAULT_IGNORE_FILES = [
    ".hgignore",
    ".ignore",
]

# Стандартные директории для игнорирования
DEFAULT_IGNORE_DIRECTORIES = {
    "node_modules", "__pycache__", "env", "venv", "target",
    "build", "dist", "out", "bundle", "vendor", "tmp", "temp",
    "deps", "Pods", ".git", ".svn", ".hg", ".DS_Store"
}
