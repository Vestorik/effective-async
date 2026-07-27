"""
CLI-инструмент для управления миграциями базы данных.

Аналог manage.py в Django:
    python -m app.cli migrate upgrade
    python -m app.cli migrate history
    python -m app.cli db status

Архитектура:
    - CLI-интерфейс разделён на подкоманды (migrate, db, help).
    - Используется argparse для обработки аргументов командной строки.
    - Все команды — обёртки вокруг `alembic`, с автоматической настройкой окружения.
    - Добавлена валидация переменных окружения и логирование.

Принципы:
    - KISS: одна команда — одна задача.
    - DRY: не дублирует логику `env.py`, только вызывает.
    - SOLID: Separation of Concerns (CLI ≠ Миграции ≠ БД).
    - Twelve-Factor App: настройки через переменные окружения.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

# === Константы ===
PROJECT_ROOT: Final[Path] = Path(__file__).parent.parent.parent  # .../buisenss-manage-app/
MIGRATIONS_DIR: Final[Path] = PROJECT_ROOT / "app" / "src" / "dal" / "migrations"
ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"


def setup_environment() -> None:
    """
    Настраивает окружение для корректного запуска CLI.

    Добавляет корень проекта в sys.path и загружает .env.
    """
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
        logger.debug("Добавлен корень проекта в sys.path")

    if ENV_FILE.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(ENV_FILE)
            logger.debug(f"Загружен файл окружения: {ENV_FILE}")
        except ImportError:
            logger.warning("Библиотека python-dotenv не установлена. Пропуск загрузки .env")




def run_alembic_command(*args: str) -> None:
    """
    Запускает Alembic как подпроцесс с настроенным окружением.

    Аргументы:
        args (str): Аргументы для alembic (например: ["upgrade", "head"]).
    """
    setup_environment()

    command = ["alembic", *args]

    try:
        result = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.returncode != 0:
            logger.error(f"Ошибка выполнения команды: {' '.join(command)}")
            sys.exit(result.returncode)
    except FileNotFoundError:
        logger.critical("Команда 'alembic' не найдена. Установите пакет 'alembic'.")
        sys.exit(1)


def cmd_migrate(args: argparse.Namespace) -> None:
    """
    Выполняет команду миграции (upgrade/downgrade/revision/history/current).

    Аргументы:
        args (argparse.Namespace): Парсинг аргументов командной строки (subparser migrate).
    """
    if args.subcommand == "upgrade":
        version = args.version or "head"
        run_alembic_command("upgrade", version)
    elif args.subcommand == "downgrade":
        version = args.version or "base"
        run_alembic_command("downgrade", version)
    elif args.subcommand == "revision":
        message = args.message or "Auto migration"
        run_alembic_command("revision", "--autogenerate", "-m", message)
    elif args.subcommand == "history":
        run_alembic_command("history")
    elif args.subcommand == "current":
        run_alembic_command("current")
    else:
        print(f"Неизвестная подкоманда: {args.subcommand}")
        sys.exit(1)




def create_parser() -> argparse.ArgumentParser:
    """
    Создаёт и настраивает парсер аргументов командной строки.

    Возвращает:
        argparse.ArgumentParser: Настроенный парсер с подкомандами.
    """
    parser = argparse.ArgumentParser(
        prog="app.cli",
        description="CLI-инструмент для управления БД и миграциями (аналог manage.py в Django).",
        epilog="Пример: python -m app.cli migrate upgrade head",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # === Команда migrate ===
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Управление миграциями базы данных",
        description="Выполнение миграций: upgrade, downgrade, revision, history, current",
    )
    migrate_subparsers = migrate_parser.add_subparsers(dest="subcommand", help="Доступные подкоманды")

    # migrate upgrade [version]
    upgrade_parser = migrate_subparsers.add_parser(
        "upgrade",
        help="Применить миграции до указанной версии (по умолчанию — head)",
    )
    upgrade_parser.add_argument(
        "version",
        nargs="?",
        default="head",
        help="Целевая версия миграции (по умолчанию: head)",
    )

    # migrate downgrade [version]
    downgrade_parser = migrate_subparsers.add_parser(
        "downgrade",
        help="Откатить миграции до указанной версии (по умолчанию — base)",
    )
    downgrade_parser.add_argument(
        "version",
        nargs="?",
        default="base",
        help="Целевая версия для отката (по умолчанию: base)",
    )

    # migrate revision [message]
    revision_parser = migrate_subparsers.add_parser(
        "revision",
        help="Создать новую миграцию (автогенерация)",
    )
    revision_parser.add_argument(
        "message",
        nargs="?",
        default="Auto migration",
        help="Описание миграции (по умолчанию: Auto migration)",
    )

    # migrate history
    migrate_subparsers.add_parser(
        "history",
        help="Показать историю миграций",
    )

    # migrate current
    migrate_subparsers.add_parser(
        "current",
        help="Показать текущую версию миграции",
    )

    # === Команда db ===
    db_parser = subparsers.add_parser(
        "db",
        help="Проверка состояния базы данных",
        description="Проверка переменных окружения и таблиц БД",
    )
    db_subparsers = db_parser.add_subparsers(dest="subcommand", help="Доступные подкоманды")

    # db status
    db_subparsers.add_parser(
        "status",
        help="Проверить настройку DATABASE_URL",
    )

    # db check
    db_subparsers.add_parser(
        "check",
        help="Показать список существующих таблиц в БД",
    )

    return parser


def main() -> None:
    """
    Точка входа в CLI.

    Использует argparse для разбора аргументов и вызова соответствующих обработчиков.
    """
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    match args.command:
        case "migrate":
            if not args.subcommand:
                print("Для команды 'migrate' укажите подкоманду: upgrade, downgrade, revision, history, current")
                print("Пример: python -m app.cli migrate upgrade head")
                sys.exit(1)
            cmd_migrate(args)
        case _:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()