"""Запуск лаунчера и сохранение скриншота UI в ui_screenshot.png.
Windows:
    set EXELENT_SCREENSHOT=1 && python main.py
или:
    python screenshot_ui.py
"""
import os
os.environ["EXELENT_SCREENSHOT"] = "1"
from launcher import main

if __name__ == "__main__":
    main()
