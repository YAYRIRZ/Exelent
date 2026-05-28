# Exelent Launcher

Premium-style PyQt6 лаунчер Minecraft с MD3-интерфейсом, Fabric, менеджером модов и гибкой кастомизацией.

## Запуск

```bash
pip install -r requirements.txt
python main.py
```

Если `config.json` ещё нет, откроется установщик. Если конфиг уже есть, откроется лаунчер.

## Сборка Windows `.exe`

```bash
python build_windows.py
```

Готовый файл будет в:

```text
dist/Exelent Launcher/Exelent Launcher.exe
```

## Возможности

- MD3 / Lunar-like интерфейс.
- Волновой Material-style прогресс загрузки.
- Vanilla и Fabric.
- Менеджер модов: добавить `.jar`, удалить, скачать по прямой ссылке.
- Свои темы через палитру.
- Иконки предметов: изумруд, алмаз, аметист и другие.
- Свой фон окна и blur-like обработка фона.
- Настройка размера окна и положения панели.
- Скрытие новостей.
- Dev режим для диагностики запуска Minecraft.

## Скриншот интерфейса

```bash
python screenshot_ui.py
```

Файл:

```text
ui_screenshot.png
```

## Важно для запуска Minecraft

- Установи зависимости из `requirements.txt`.
- Укажи Java в настройках, если автопоиск не нашёл `javaw.exe`.
- Для новых версий Minecraft нужна Java 17/21.
