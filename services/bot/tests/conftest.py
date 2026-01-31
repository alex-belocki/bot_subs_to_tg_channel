import sys
from pathlib import Path


# Добавляем корень сервиса бота в PYTHONPATH, чтобы импорты вида
# `import main` и `from modules...` корректно работали как локально,
# так и внутри Docker-контейнера.
# .../services/bot/tests -> parents[1] == .../services/bot
ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


