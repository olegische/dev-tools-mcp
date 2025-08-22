# План доработки: Внедрение двухфазной stateful-модели работы с файлами

## 1. Концепция: Двухфазная модель "Исследование -> Редактирование"

Отказываемся от хаотичного набора файловых инструментов в пользу строгой двухфазной модели, которая повышает безопасность и управляемость агента.

-   **Фаза 1: Исследование (Read-Only)**
    -   **Цель:** Агент изучает структуру проекта, находит нужные файлы, выбирает рабочую директорию.
    -   **Доступные инструменты:** Только stateful-инструмент для навигации (`navigator`), позволяющий выполнять `cd`, `ls`, `pwd`, `read`.
    -   **Ограничения:** Все инструменты, изменяющие состояние (`edit_tool`, `git_tool`, `json_edit_tool`), **полностью отключены**.

-   **Фаза 2: Редактирование (Read-Write)**
    -   **Цель:** Агент работает в рамках выбранной директории (`CWD`), внося изменения.
    -   **Активация:** Фаза начинается после того, как агент (или пользователь) фиксирует `CWD` с помощью специальной команды (например, `navigator.lock_cwd`).
    -   **Доступные инструменты:** Включаются инструменты `edit_tool`, `git_tool` и другие, но они теперь работают **относительно зафиксированного CWD**.
    -   **Промпт:** Системный промпт агента обновляется, сообщая ему о новом режиме работы и текущем `CWD`.

## 2. План реализации

### Шаг 1: Создание `SessionManager` и `FileSystemState`

-   **Задача:** Создать централизованное хранилище состояний (`CWD`, `root`, текущая фаза) для каждой сессии.
-   **Реализация:**
    -   Создать Pydantic-модель `FileSystemState`, хранящую `cwd: Path`, `root: Path`, `phase: Literal['discovery', 'edit']`.
    -   В `dependencies.py` создать синглтон `SessionManager` (например, `dict`), который будет хранить `FileSystemState` по `session_id`.

### Шаг 2: Инструмент Навигации (`NavigatorTool`)

-   **Задача:** Создать новый, всегда активный инструмент для read-only навигации.
-   **Реализация:**
    -   Создать `dev_tools_mcp/tools/navigator_tool.py`.
    -   Подкоманды:
        -   `cd(path)`: меняет `state.cwd`.
        -   `pwd()`: возвращает `state.cwd`.
        -   `ls(path)`: листинг директории.
        -   `read(path, view_range)`: чтение файла.
        -   `lock_cwd()`: **сигнал серверу** для перехода в фазу "Редактирование". Возвращает подтверждение.
    -   Все операции с путями должны использовать `SessionManager` для разрешения путей относительно `state.cwd` и проверки на выход из песочницы.

### Шаг 3: Модификация инструментов редактирования

-   **Задача:** Адаптировать существующие `edit_tool`, `git_tool`, `json_edit_tool`, чтобы они стали state-aware.
-   **Реализация:**
    -   Каждый из этих инструментов должен быть модифицирован. Вместо того чтобы принимать абсолютный путь, он должен:
        1.  Принимать **относительный путь**.
        2.  Использовать `SessionManager` для получения `state.cwd` текущей сессии.
        3.  Разрешать и валидировать путь (`_resolve_path`).
    -   Они больше не будут самостоятельными, а станут зависимыми от состояния, управляемого `NavigatorTool` и `SessionManager`.

### Шаг 4: Логика сервера для управления фазами

-   **Задача:** Реализовать на сервере механизм переключения между фазами.
-   **Реализация:**
    -   В `server.py` логика `list_tools` должна возвращать разный набор инструментов в зависимости от `state.phase` текущей сессии.
    -   Обработчик команды `navigator.lock_cwd()` должен менять `state.phase` на `'edit'`, после чего следующий `list_tools` вернет агенту полный набор инструментов.
    -   Сервер также должен инициировать отправку нового системного промпта агенту после смены фазы.

### Шаг 5: Модификация `BashTool`

-   **Задача:** Сохранить возможность выполнения произвольных команд, но сделать `BashTool` state-aware и интегрировать его в двухфазную модель.
-   **Реализация:**
    -   `BashTool` **не удаляется**, а **переписывается**.
    -   Он становится **stateless на уровне процесса**. Больше никаких попыток поддерживать один долгоживущий shell-процесс. Это решает все проблемы с зависаниями.
    -   При каждом вызове `BashTool` будет:
        1.  Получать `state.cwd` из `SessionManager`.
        2.  Запускать **новый, чистый** shell-процесс для выполнения одной команды.
        3.  Фактически выполняемая команда будет выглядеть так: `cd /path/to/session/cwd && {user_command}`.
    -   Таким образом, с точки зрения агента, `bash` работает в нужном CWD, но технически каждый вызов изолирован.
    -   `BashTool` будет **отключен** в фазе "Исследование" и **включен** в фазе "Редактирование".

### Шаг 6: Очистка и финализация

-   **Задача:** Обновить документацию и системный промпт.
-   **Реализация:**
    -   Обновить всю релевантную документацию, чтобы отразить новую двухфазную модель с тремя типами инструментов: навигация, редактирование и выполнение команд.

## 3. Примеры реализации (псевдокод)

Ниже приведены примеры, иллюстрирующие ключевые компоненты предлагаемой архитектуры.

### `FileSystemState` и `SessionManager`

```python
# dev_tools_mcp/utils/session.py
from pathlib import Path
from typing import Literal
from pydantic import BaseModel

class FileSystemState(BaseModel):
    """Хранит состояние файловой системы для одной сессии."""
    root: Path = Path("/app/sandbox")  # Корень песочницы
    cwd: Path = root
    phase: Literal['discovery', 'edit'] = 'discovery'

# dev_tools_mcp/utils/dependencies.py
from .session import FileSystemState

# Простой dict в качестве внутрипроцессного хранилища сессий.
# В реальном приложении это может быть Redis или другой персистентный стор.
SESSION_STORAGE: dict[str, FileSystemState] = {}

def get_fs_state(session_id: str) -> FileSystemState:
    """Возвращает или создает состояние для данной сессии."""
    if session_id not in SESSION_STORAGE:
        SESSION_STORAGE[session_id] = FileSystemState()
    return SESSION_STORAGE[session_id]
```

### `NavigatorTool` (упрощенно)

```python
# dev_tools_mcp/tools/navigator_tool.py
from .base import Tool
from dev_tools_mcp.utils.session import FileSystemState, get_fs_state

class NavigatorTool(Tool):
    def _resolve_path(self, state: FileSystemState, path_str: str) -> Path:
        path = Path(path_str)
        # Если путь абсолютный, он все равно должен быть внутри root.
        # Если относительный, он соединяется с cwd.
        target_path = state.cwd / path if not path.is_absolute() else path
        
        # Нормализуем и проверяем на выход из песочницы
        resolved_path = target_path.resolve()
        if not resolved_path.is_relative_to(state.root.resolve()):
            raise PermissionError("Path is outside the sandbox")
        return resolved_path

    async def execute(self, session_id: str, subcommand: str, path: str | None = None) -> ToolExecResult:
        state = get_fs_state(session_id)

        if subcommand == "pwd":
            return ToolExecResult(output=str(state.cwd))
        
        if subcommand == "cd":
            if not path: raise ValueError("Path is required for cd")
            target_dir = self._resolve_path(state, path)
            if not target_dir.is_dir():
                raise NotADirectoryError(f"{target_dir} is not a directory")
            state.cwd = target_dir
            return ToolExecResult(output=f"CWD is now {state.cwd}")
        
        # ... реализация ls, read, lock_cwd ...
```

### Модифицированный `BashTool` (пример)

```python
# dev_tools_mcp/tools/bash_tool.py (переписанный)
import asyncio
from .base import Tool
from dev_tools_mcp.utils.session import FileSystemState, get_fs_state

class BashTool(Tool):
    async def execute(self, session_id: str, command: str) -> ToolExecResult:
        state = get_fs_state(session_id)
        
        if state.phase != 'edit':
            return ToolExecResult(error="Cannot run commands in discovery phase.")

        # Команда выполняется в новом процессе, но с правильным CWD
        full_command = f"cd {state.cwd.resolve()} && {command}"
        
        process = await asyncio.create_subprocess_shell(
            full_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()
        
        return ToolExecResult(
            output=stdout.decode(),
            error=stderr.decode(),
            error_code=process.returncode
        )
```

### Модифицированный `TextEditorTool` (пример)

```python
# dev_tools_mcp/tools/edit_tool.py (модифицированный)
from .base import Tool
from dev_tools_mcp.utils.session import FileSystemState, get_fs_state

class TextEditorTool(Tool):
    # Метод _resolve_path должен быть здесь или в общем utility-модуле
    def _resolve_path(self, state: FileSystemState, path_str: str) -> Path:
        # ... (та же реализация, что и в NavigatorTool) ...

    async def execute(self, session_id: str, subcommand: str, path: str, **kwargs) -> ToolExecResult:
        state = get_fs_state(session_id)
        
        # Проверяем, что мы в правильной фазе
        if state.phase != 'edit':
            return ToolExecResult(error="Cannot edit files in discovery phase. Use navigator.lock_cwd() first.")

        # Путь теперь относительный! Резолвим его через состояние сессии.
        resolved_path = self._resolve_path(state, path)

        if subcommand == "write":
            content = kwargs.get("content")
            resolved_path.write_text(content)
            return ToolExecResult(output=f"File {resolved_path} written successfully.")
            
        # ... реализация других команд редактирования ...
```
