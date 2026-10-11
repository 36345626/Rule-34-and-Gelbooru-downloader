"""R34Downloader by AMAYORI v1.0 — качалка картинок и видео с Rule34.xxx по тегам.

Вся программа в одном файле. Разделы (ищите по «# ====»):
  sites — название, цвета, адреса сайта · i18n — тексты на 4 языках ·
  net — сеть, повторы, обход блокировки · storage — настройки, история, ключ ·
  api — запросы к сайту · engine — загрузка и докачка · theme — оформление ·
  ui — окно · app — запуск · в конце — встроенные файлы и сборка exe.

Запуск из исходника: py R34Downloader_by_AMAYORI.py
Сборка exe:          build_exe.bat  (или: py R34Downloader_by_AMAYORI.py --build)
"""

from dataclasses import dataclass
import queue
import re
import threading
import time
from urllib.parse import urlsplit
import requests
from requests.adapters import HTTPAdapter
import base64
import json
import os
import sys
import urllib.parse
from pathlib import Path
import hashlib
import html
import xml.etree.ElementTree as ET
import traceback
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass, fields
from PySide6.QtGui import QColor, QPalette
import shutil
import socket
import subprocess
import urllib.request
from PySide6.QtCore import QObject, Signal
from collections import deque
from PySide6.QtCore import QBuffer, QByteArray, QEvent, QObject, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QColor, QDesktopServices, QFont, QIcon, QImage, QImageReader, QMovie,
                           QPainter, QPixmap, QStandardItem, QStandardItemModel)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QDialog, QMenu,
                               QComboBox, QCompleter, QDoubleSpinBox, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QRadioButton,
                               QScrollArea, QSizePolicy, QSpinBox, QSplitter, QTableWidget,
                               QStackedWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)


# ====================================================================== sites: Настройки конкретных сайтов.

@dataclass(frozen=True)
class Site:
    key: str
    site_name: str           # как сайт называется в текстах
    app_name: str
    version: str
    data_dir: str            # папка настроек в %APPDATA% (та же, что у старых версий)
    letter: str              # буква-логотип в шапке
    accent: str
    accent_hover: str
    accent_text: str         # цвет текста на кнопках с акцентным фоном
    author: str              # подпись в углу окна ("" — без подписи)
    icon: str
    site_url: str
    api_url: str
    post_url: str            # .format(id=...)
    search_example: str
    page_size: int           # постов за один запрос к API
    ratings: tuple           # значения для тега rating:
    count_via_xml: bool      # JSON не отдаёт общее число постов — берём из XML
    xml_fallback: bool       # при пустом JSON-ответе пробовать XML
    autocomplete_urls: tuple
    credentials_path: str    # где на сайте взять ключ
    proxy_list: str          # встроенный список прокси для обхода блокировки
    options_url: str         # страница аккаунта с ключом API и настройками
    register_url: str
    profile_url: str         # профиль по user_id — оттуда берём ник ("" — сайт не даёт)
    ai_tags: tuple           # чем сайт помечает ИИ-арты (фильтр «Без ИИ-артов»)
    force_https: bool = True # ссылки на файлы всегда по HTTPS (важно при работе через прокси)



RULE34 = Site(
    key="rule34",
    site_name="Rule34.xxx",
    app_name="R34Downloader",
    version="1.0",
    data_dir="R34Downloader_by_AMAYORI",
    letter="R",
    accent="#AAE5A4",
    accent_hover="#C6F0C1",
    accent_text="#0b1a0a",
    author="by AMAYORI",
    icon="r34.ico",
    site_url="https://rule34.xxx/",
    api_url="https://api.rule34.xxx/index.php",
    post_url="https://rule34.xxx/index.php?page=post&s=view&id={id}",
    search_example="https://rule34.xxx/index.php?page=post&s=list&tags=blue_hair",
    page_size=100,
    ratings=("safe", "questionable", "explicit"),
    count_via_xml=True,
    xml_fallback=True,
    autocomplete_urls=(
        "https://ac.rule34.xxx/autocomplete.php?q={term}",
        "https://api.rule34.xxx/autocomplete.php?q={term}",
    ),
    credentials_path="My Account → Options → API Access Credentials",
    proxy_list="proxies_rule34.txt",
    options_url="https://rule34.xxx/index.php?page=account&s=options",
    register_url="https://rule34.xxx/index.php?page=account&s=reg",
    profile_url="",          # профиль закрыт капчей
    ai_tags=("ai_generated", "ai-created", "ai-generated"),
)

SITES = {RULE34.key: RULE34}
SITE = RULE34


# ====================================================================== i18n: Переводы интерфейса: русский, английский, китайский, японский.

_lang = "ru"


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def set_language(code):
    global _lang
    _lang = code if code in STRINGS else "ru"


def current():
    return _lang


def has(key):
    return key in STRINGS["ru"]


def t(key, **params):
    text = STRINGS.get(_lang, {}).get(key) or STRINGS["ru"].get(key) or key
    return text.format_map(_Safe(params)) if params else text


RU = {
    "unit_b": "Б", "unit_kb": "КБ", "unit_mb": "МБ", "unit_gb": "ГБ",
    "time_hm": "{h} ч {m} мин", "time_ms": "{m} мин {s} с", "time_s": "{s} с",
    "tab_download": "Загрузка", "tab_history": "История", "tab_settings": "Настройки",

    "card_search": "Что скачать",
    "lbl_tags": "Теги или ссылка на поиск",
    "ph_tags": "blue_hair smile -monochrome   или ссылка со страницы поиска",
    "btn_find": "Найти",
    "hint_tags": "Теги через пробел, «-тег» — исключить. Подсказки появляются при вводе. "
                 "Можно вставить ссылку со страницы поиска сайта — программа сама возьмёт из неё теги.",
    "lbl_rating": "Рейтинг", "lbl_media": "Тип файлов", "lbl_limit": "Сколько скачать",
    "rating_any": "Любой", "rating_general": "general", "rating_sensitive": "sensitive",
    "rating_questionable": "questionable", "rating_explicit": "explicit", "rating_safe": "safe",
    "media_all": "Всё", "media_images": "Картинки", "media_videos": "Видео и анимации",
    "limit_all": "Все", "tip_limit": "0 — скачать всё, что найдётся",
    "chk_no_ai": "Без ИИ-артов", "tip_no_ai": "Исключить из поиска и загрузки посты, помеченные как ИИ: {tags}",
    "lbl_account_nick": "Ник в углу окна:", "ph_nick_auto": "определится сам по ключу",
    "ph_nick_manual": "впишите свой ник — сайт его не сообщает",
    "footer_account": "👤 {name}", "footer_no_key": "👤 ключ не указан",
    "found_searching": "Ищу…", "found_n": "Найдено постов: {n}",
    "found_unknown": "Сайт не сообщил количество постов",
    "found_error": "Не удалось узнать количество: {err}",
    "hint_gelbooru_account": "Чтобы видеть все посты и оригиналы, включите в настройках аккаунта Gelbooru "
                             "«Display all site content» и «Always show original».",

    "card_save": "Куда и как сохранять",
    "lbl_folder": "Папка", "btn_choose": "Выбрать…", "btn_open_folder": "Открыть",
    "hint_subfolder": "Для каждого запроса создаётся своя подпапка",
    "hint_target": "Файлы попадут в: {path}",
    "lbl_names": "Имена файлов",
    "tpl_id": "Номер поста — 1234567.jpg",
    "tpl_tags_id": "Теги и номер поста — blue_hair_1234567.jpg",
    "tpl_tags_seq": "Теги и порядковый номер — blue_hair_0001.jpg (как раньше)",
    "tpl_md5": "MD5 файла — 3f2a…c9.jpg",
    "tip_names": "Как называть скачанные файлы. Номер поста — проще всего найти пост на сайте; "
                 "«как раньше» — имена как в старой версии программы.",
    "chk_split": "Раскладывать по папкам «Картинки» и «Видео и анимации»",
    "chk_skip": "Не качать повторно то, что уже скачано",
    "tip_skip": "Программа помнит номера скачанных постов в папке запроса (файл .booru_ids.txt)",

    "btn_start": "▶  Скачать", "btn_update": "⟳  Только новые", "btn_resume": "↪  Продолжить",
    "btn_stop": "■  Стоп",
    "tip_update": "Докачать посты, которые появились на сайте после прошлой загрузки по этому запросу",
    "tip_resume": "Продолжить прерванную загрузку с того же места",

    "card_progress": "Ход загрузки",
    "prog_idle": "Нажмите «Скачать», чтобы начать",
    "prog_counts": "Скачано {d}  ·  пропущено (уже есть) {s}  ·  ошибок {f}",
    "prog_filtered": "  ·  не подходит по типу {x}",
    "prog_speed": "{speed}/с", "prog_eta": "осталось ≈ {eta}", "prog_total_size": "всего {size}",
    "btn_log_show": "▸ Показать журнал", "btn_log_hide": "▾ Скрыть журнал",
    "status_starting": "Подготовка…", "status_counting": "Считаю посты…",
    "status_page": "Получаю страницу {page}…", "status_downloading": "Скачиваю…",
    "status_stopping": "Останавливаю…",
    "status_done": "Готово", "status_stopped": "Остановлено", "status_paused": "Приостановлено",
    "status_auth": "Сайт отклонил ключ", "status_error": "Ошибка",
    "wait_offline": "Нет связи с сайтом ({err}) — повтор через {s} с, попытка {n}. Загрузка продолжится сама.",
    "wait_server": "Сайт не отвечает ({err}) — повтор через {s} с, попытка {n}.",
    "hint_try_auto": "Если сайт заблокирован, включите в настройках режим «Авто».",
    "msg_finished_done": "Готово: скачано {d}, пропущено {s}, ошибок {f}.",
    "msg_finished_stopped": "Остановлено. Скачано {d}. Нажмите «Продолжить», чтобы докачать.",
    "msg_finished_paused": "Сайт долго не отвечает ({err}). Прогресс сохранён — нажмите «Продолжить» позже.",
    "msg_finished_auth": "Сайт отклонил ключ API ({err}). Проверьте ключ в настройках, потом нажмите «Продолжить».",
    "msg_finished_error": "Ошибка: {err}. Прогресс сохранён.",
    "msg_no_tags": "Введите теги или вставьте ссылку на поиск",
    "msg_no_folder": "Укажите папку для сохранения",
    "msg_running_close": "Загрузка ещё идёт. Остановить её и закрыть программу?\n"
                         "Прогресс сохранится — потом можно нажать «Продолжить».",

    "card_preview": "Последние файлы",
    "card_log": "Журнал работы", "btn_view_files": "Файлы", "btn_view_log": "Журнал",
    "btn_view_search": "Поиск", "card_results": "Что найдено",
    "search_info": "Найдено: {total}. Двойной щелчок — посмотреть в полном размере, правая кнопка — скачать.",
    "search_info_media": "Показаны только подходящие по типу файлов.",
    "search_nothing": "Ничего не найдено", "search_no_url": "⚠ У {n} постов нет ссылки на файл — наведите сюда, чтобы узнать, что делать", "page_label": "стр. {n} из {total}", "tip_prev_page": "Предыдущая страница", "tip_next_page": "Следующая страница",
    "menu_download": "⬇ Скачать", "menu_download_n": "⬇ Скачать выбранные ({n})", "menu_view": "🔍 Посмотреть в полном размере",
    "menu_open_site": "🌐 Открыть пост на сайте", "menu_copy_link": "📋 Копировать ссылку на пост",
    "single_started": "Скачиваю пост #{id}…", "single_saved": "Скачано: {name}", "single_exists": "Уже скачано: {name}",
    "single_failed": "Не удалось скачать пост #{id}: {err}", "single_no_url": "У поста #{id} нет ссылки на файл",
    "viewer_loading": "Загружаю оригинал… {p}", "viewer_failed": "Не удалось загрузить: {err}",
    "viewer_video": "Это видео — нажмите «▶ Открыть видео», оно откроется в браузере",
    "btn_open_video": "▶ Открыть видео", "btn_viewer_download": "⬇ Скачать", "btn_viewer_site": "🌐 На сайте",
    "viewer_hint": "Щелчок по картинке — 100% / по размеру окна · ← → — соседние арты · S — скачать · Esc — закрыть", "info_artist": "Автор", "info_characters": "Персонажи", "info_copyright": "Откуда",
    "info_loading": "Узнаю автора и персонажей…", "info_other": "Остальные теги", "info_more": "▸ все теги ({n})", "info_less": "▾ свернуть", "info_none": "Автор, персонажи и откуда — на сайте не указаны",
    "info_hover": "Наведите на картинку — здесь появятся автор, персонажи и откуда они.",
    "tip_tag_link": "Щёлкните по имени — поиск по этому тегу", "tip_open_post": "Двойной щелчок — посмотреть в полном размере, правая кнопка — скачать или открыть на сайте",
    "search_hint_empty": "Начните вводить теги — здесь появятся картинки с сайта, как на странице поиска.",
    "preview_empty": "Здесь появятся скачанные файлы",
    "preview_missing": "Файл не найден", "preview_unavailable": "Предпросмотр недоступен",
    "btn_file_open": "Открыть", "btn_file_folder": "Показать в папке", "btn_file_post": "Пост на сайте",

    "card_history": "История загрузок",
    "hist_query": "Запрос", "hist_count": "Скачано: в последний раз / всего",
    "hist_date": "Когда", "hist_folder": "Папка",
    "hist_empty": "История пока пуста", "hist_any_tags": "(без тегов)",
    "btn_hist_use": "Подставить в поиск", "btn_hist_update": "⟳ Докачать новые",
    "btn_hist_folder": "Открыть папку", "btn_hist_remove": "Удалить запись",

    "card_api": "Ключ API {site}",
    "api_need": "Для работы нужен API-ключ аккаунта — вставьте строку с api_key и user_id ниже.",
    "ph_api_line": "&api_key=…&user_id=…",
    "lbl_api_line": "Строка с api_key и user_id",
    "api_parsed": "Нашёл: User ID {uid}, ключ ••••{tail}",
    "chk_show_key": "Показать",
    "btn_login_browser": "🌐 Войти через браузер — ключ возьмётся сам",
    "hint_login_browser_gelbooru": "Откроется ваш браузер (Edge, Chrome, Яндекс…) отдельным окном. Войдите или зарегистрируйтесь — дальше программа сама включит «Display all site content» и «Always show original» и заберёт ключ.",
    "hint_login_browser_rule34": "Откроется ваш браузер (Edge, Chrome, Яндекс…) отдельным окном. Войдите или зарегистрируйтесь (капчу решите как обычно) — дальше программа сама создаст ключ, если его нет, и заберёт его.",
    "login_title": "Вход на {site}", "lbl_login_browser": "Браузер для входа:",
    "login_no_browser_short": "не найден — откроется обычная страница",
    "login_no_browser": "Не нашёл браузер на Chromium (Edge, Chrome, Яндекс.Браузер, Opera, Brave, Vivaldi). Открою страницу ключа в обычном браузере — скопируйте там строку ключа, программа подхватит её сама.",
    "login_starting": "Запускаю {browser}…", "login_using": "Вход через {browser}",
    "login_privacy": "Окно браузера открывается со своим отдельным профилем. Пароль вы вводите на странице сайта — программа его не видит и не сохраняет.",
    "login_launch_failed": "Не удалось запустить браузер: {err}",
    "login_no_debug": "Браузер не ответил программе. Попробуйте ещё раз или выберите в настройках другой браузер.",
    "login_closed": "Окно браузера закрыто — ключ не получен.",
    "btn_login_cancel": "Отмена", "btn_login_close": "Закрыть", "login_preparing": "Открываю сайт…",
    "login_unavailable": "Встроенный браузер не запустился: {err}",
    "login_got_key": "Ключ получен со страницы сайта — проверяю…",
    "login_step_open": "Открываю страницу ключа…",
    "login_step_login": "Войдите в свой аккаунт (нет аккаунта — «Регистрация»). Если сайт покажет капчу — решите её как обычно. "
                        "Дальше программа всё сделает сама.",
    "login_step_opening": "Вы вошли — открываю страницу ключа…",
    "login_step_settings": "Включаю «Display all site content» и «Always show original» и сохраняю…",
    "login_step_generate": "Создаю ключ API…",
    "login_step_manual": "Не получилось сделать это само. На этой странице найдите «API Access Credentials», при "
                         "необходимости отметьте создание ключа и нажмите Save — программа заберёт ключ, как только он появится.",
    "login_failed_net": "Страница не открылась — проверьте подключение (⟳ — попробовать ещё раз).",
    "login_done": "✓ Готово: ключ получен (User ID {uid}){extra}. Окно сейчас закроется.",
    "login_done_settings": ", настройки аккаунта включены",
    "btn_login": "Вход", "btn_reg": "Регистрация", "btn_key_page": "Страница ключа", "btn_close_browser": "Закрыть",
    "btn_open_key_page": "🔑 Открыть страницу ключа", "btn_register": "Регистрация на сайте",
    "hint_api_steps_gelbooru": "1. Войдите на Gelbooru (нет аккаунта — «Регистрация на сайте»).\n"
                               "2. Нажмите «Открыть страницу ключа». На этой странице включите «Display all site "
                               "content» и «Always show original», сохраните.\n"
                               "3. Внизу страницы, в «API Access Credentials», скопируйте строку целиком — "
                               "программа сама подхватит её из буфера обмена.",
    "hint_api_steps_rule34": "1. Войдите на Rule34.xxx (нет аккаунта — «Регистрация на сайте»).\n"
                             "2. Нажмите «Открыть страницу ключа», в «API Access Credentials» поставьте "
                             "галочку генерации нового ключа и сохраните.\n"
                             "3. Скопируйте появившуюся строку целиком — программа сама подхватит её из буфера обмена.",
    "hint_api_secure": "Ключ хранится зашифрованным средствами Windows и не попадает в журнал.",
    "api_from_clipboard": "Взял строку из буфера обмена — проверяю…",
    "msg_no_url_gelbooru": "У {n} постов сайт не дал ссылку на файл. Включите в настройках аккаунта Gelbooru "
                           "«Display all site content» и «Always show original» (кнопка «Открыть страницу ключа» "
                           "в настройках программы).",
    "msg_no_url_rule34": "У {n} постов сайт не дал ссылку на файл — возможно, их скрыли или удалили.",
    "hint_api": "Строка берётся на сайте: {path}. Вставьте её целиком — программа сама достанет User ID "
                "и ключ и сразу проверит их. Ключ хранится зашифрованным средствами Windows и не попадает в журнал.",
    "btn_api_check": "Проверить и сохранить",
    "api_missing": "Не нашёл в строке api_key и user_id — скопируйте её с сайта целиком",
    "api_checking": "Проверяю…",
    "api_saved_ok": "Ключ принят сайтом и сохранён",
    "api_bad": "Сайт отклонил ключ — проверьте User ID и API key.",
    "api_check_fail": "Не удалось проверить ({err}). Ключ сохранён.",

    "card_speed": "Скорость",
    "lbl_threads": "Файлов одновременно", "lbl_delay": "Пауза между файлами, с",
    "hint_speed": "3 одновременно — разумно. Если сайт начнёт отвечать «слишком много запросов», уменьшите.",
    "card_other": "Прочее",
    "btn_open_data": "Папка настроек программы",
    "hint_data": "Там лежат настройки, история и error.log. Список неудачных загрузок — failed_links.txt "
                 "в папке каждого запроса.",

    "card_net": "Подключение",
    "net_auto": "Авто: напрямую, а если сайт недоступен — через прокси (рекомендуется)",
    "hint_net_auto": "Программа сама заметит блокировку, найдёт рабочий прокси из списка ниже и будет "
                     "ходить через него только к заблокированным серверам. Остальное — напрямую.",
    "net_direct": "Только напрямую (или через системный прокси Windows)",
    "net_custom": "Всё через свой прокси:",
    "ph_proxy": "socks5h://127.0.0.1:1080  или  http://адрес:порт",
    "hint_proxy_custom": "Подойдёт прокси VPN-клиента (обычно socks5h://127.0.0.1:порт). Логин и пароль: "
                         "http://логин:пароль@адрес:порт",
    "lbl_pool": "Прокси для режима «Авто» (по одному в строке, лучшие сверху):",
    "btn_pool_check": "Проверить список", "btn_pool_reset": "Встроенный список",
    "pool_count": "В списке: {n}", "pool_checking": "Проверяю {n} прокси…",
    "pool_dead": "не ответил", "pool_result": "Отвечают {ok} из {n}; быстрые подняты наверх.",
    "hint_pool_safety": "Бесплатные прокси быстро умирают — время от времени жмите «Проверить список» "
                        "или вставляйте свежие. Ключ API через прокси не утекает: соединение с сайтом "
                        "зашифровано (HTTPS), прокси видит только адрес сервера.",
    "btn_net_check": "Проверить соединение",
    "net_checking": "Проверяю…", "net_ok": "Сайт доступен: {ms} мс, {route}", "net_fail": "Нет связи: {err}",
    "route_direct": "напрямую", "route_proxy": "через прокси {proxy}", "route_custom": "через свой прокси {proxy}",

    "log_resume": "↪ Продолжаю прерванную загрузку (уже скачано {downloaded})",
    "log_update_from": "⟳ Только новые: посты новее №{id}",
    "log_update_none": "Раньше по этому запросу ничего не скачивалось — качаю всё",
    "log_query": "🔍 Запрос: {tags}  →  {folder}",
    "log_count_failed": "Не удалось узнать количество постов: {code}",
    "log_found": "Найдено постов: {count}",
    "log_cursor_fallback": "Сайт не понял листание по номеру поста — перехожу на обычные страницы",
    "log_page": "📑 Страница {page}: {count} постов",
    "log_no_url": "Пост {id}: сайт не дал ссылку на файл (проверьте настройки аккаунта)",
    "log_long_path": "Пост {id}: слишком длинный путь — сохраняю под номером поста",
    "log_file_ok": "✓ {name}  ({size})",
    "log_file_fail": "✗ Пост {id}: {code}",
    "log_file_retry": "Пост {id}: {code} — повтор через {delay} с (попытка {attempt})",
    "log_api_retry": "⚠ API: {code} — повтор через {delay} с (попытка {attempt})",
    "log_failed_saved": "Неудачные загрузки записаны в {path}",
    "log_route_probe": "{host} не отвечает напрямую — ищу рабочий прокси ({count} в списке)…",
    "log_route_proxy": "{host}: работаю через прокси {proxy}",
    "log_route_blocked": "{host} заблокирован напрямую — дальше хожу к нему через {proxy}",
    "log_route_none": "{host}: ни один прокси из списка не ответил",

    "err_net_connection": "нет соединения с сайтом",
    "err_net_timeout": "сайт не ответил вовремя",
    "err_net_proxy": "ошибка прокси",
    "err_net_ssl": "ошибка защищённого соединения",
    "err_net_broken": "соединение оборвалось",
    "err_net_other": "сетевая ошибка",
    "err_rate_limited": "слишком много запросов, сайт просит подождать",
    "err_server_busy": "сервер перегружен или недоступен",
    "err_empty_response": "сайт прислал пустой ответ",
    "err_empty_file": "сервер отдал пустой файл",
    "err_incomplete": "файл скачался не полностью",
    "err_auth_http": "сайт отклонил ключ",
    "err_auth_server": "сайт отклонил ключ",
    "err_blocked": "доступ закрыт защитой сайта (Cloudflare)",
    "err_not_found": "файл не найден на сервере",
    "err_http_error": "ошибка сайта",
    "err_server_message": "сообщение сайта",
    "err_bad_response": "непонятный ответ сайта",
    "err_not_media": "вместо файла пришла страница",
    "err_file_error": "не удалось записать файл",
    "err_proxy_invalid": "неверный адрес прокси",
    "err_no_url": "нет ссылки на файл",
    "err_path_too_long": "слишком длинный путь к файлу",
    "err_internal": "внутренняя ошибка программы",
}

EN = {
    "unit_b": "B", "unit_kb": "KB", "unit_mb": "MB", "unit_gb": "GB",
    "time_hm": "{h} h {m} min", "time_ms": "{m} min {s} s", "time_s": "{s} s",
    "tab_download": "Download", "tab_history": "History", "tab_settings": "Settings",

    "card_search": "What to download",
    "lbl_tags": "Tags or search link",
    "ph_tags": "blue_hair smile -monochrome   or a link from the search page",
    "btn_find": "Search",
    "hint_tags": "Tags separated by spaces, “-tag” excludes. Suggestions appear as you type. "
                 "You can paste a link from the site's search page — tags are taken from it.",
    "lbl_rating": "Rating", "lbl_media": "File type", "lbl_limit": "How many",
    "rating_any": "Any",
    "media_all": "All", "media_images": "Images", "media_videos": "Videos and animations",
    "limit_all": "All", "tip_limit": "0 — download everything found",
    "chk_no_ai": "No AI art", "tip_no_ai": "Exclude posts tagged as AI from search and downloads: {tags}",
    "lbl_account_nick": "Name in the corner:", "ph_nick_auto": "detected from the key",
    "ph_nick_manual": "type your name — the site does not report it",
    "footer_account": "👤 {name}", "footer_no_key": "👤 no key",
    "found_searching": "Searching…", "found_n": "Posts found: {n}",
    "found_unknown": "The site did not report the number of posts",
    "found_error": "Could not get the count: {err}",
    "hint_gelbooru_account": "To see all posts and originals, enable “Display all site content” and "
                             "“Always show original” in your Gelbooru account settings.",

    "card_save": "Where and how to save",
    "lbl_folder": "Folder", "btn_choose": "Choose…", "btn_open_folder": "Open",
    "hint_subfolder": "Each search gets its own subfolder",
    "hint_target": "Files will go to: {path}",
    "lbl_names": "File names",
    "tpl_id": "Post number — 1234567.jpg",
    "tpl_tags_id": "Tags and post number — blue_hair_1234567.jpg",
    "tpl_tags_seq": "Tags and counter — blue_hair_0001.jpg (as before)",
    "tpl_md5": "File MD5 — 3f2a…c9.jpg",
    "tip_names": "How downloaded files are named. Post number makes it easy to find the post on the site; "
                 "“as before” matches the old version of the program.",
    "chk_split": "Sort into “Картинки” (images) and “Видео и анимации” (videos) folders",
    "chk_skip": "Don't download again what is already downloaded",
    "tip_skip": "Downloaded post numbers are remembered in the search folder (.booru_ids.txt)",

    "btn_start": "▶  Download", "btn_update": "⟳  New only", "btn_resume": "↪  Resume",
    "btn_stop": "■  Stop",
    "tip_update": "Download posts that appeared on the site since the last download of this search",
    "tip_resume": "Continue the interrupted download from where it stopped",

    "card_progress": "Progress",
    "prog_idle": "Press “Download” to start",
    "prog_counts": "Downloaded {d}  ·  skipped (already have) {s}  ·  errors {f}",
    "prog_filtered": "  ·  wrong type {x}",
    "prog_speed": "{speed}/s", "prog_eta": "≈ {eta} left", "prog_total_size": "total {size}",
    "btn_log_show": "▸ Show log", "btn_log_hide": "▾ Hide log",
    "status_starting": "Preparing…", "status_counting": "Counting posts…",
    "status_page": "Fetching page {page}…", "status_downloading": "Downloading…",
    "status_stopping": "Stopping…",
    "status_done": "Done", "status_stopped": "Stopped", "status_paused": "Paused",
    "status_auth": "The site rejected the key", "status_error": "Error",
    "wait_offline": "No connection to the site ({err}) — retry in {s} s, attempt {n}. The download will continue by itself.",
    "wait_server": "The site is not responding ({err}) — retry in {s} s, attempt {n}.",
    "hint_try_auto": "If the site is blocked, choose the “Auto” mode in settings.",
    "msg_finished_done": "Done: downloaded {d}, skipped {s}, errors {f}.",
    "msg_finished_stopped": "Stopped. Downloaded {d}. Press “Resume” to continue.",
    "msg_finished_paused": "The site has not responded for a long time ({err}). Progress is saved — press “Resume” later.",
    "msg_finished_auth": "The site rejected the API key ({err}). Check the key in settings, then press “Resume”.",
    "msg_finished_error": "Error: {err}. Progress is saved.",
    "msg_no_tags": "Enter tags or paste a search link",
    "msg_no_folder": "Choose a folder to save to",
    "msg_running_close": "A download is still running. Stop it and close the program?\n"
                         "Progress will be saved — you can press “Resume” later.",

    "card_preview": "Latest files",
    "card_log": "Activity log", "btn_view_files": "Files", "btn_view_log": "Log",
    "btn_view_search": "Search", "card_results": "Search results",
    "search_info": "Found: {total}. Double-click to view full size, right-click to download.",
    "search_info_media": "Only the selected file type is shown.",
    "search_nothing": "Nothing found", "search_no_url": "⚠ {n} posts have no file link — hover here to see what to do", "page_label": "page {n} of {total}", "tip_prev_page": "Previous page", "tip_next_page": "Next page",
    "menu_download": "⬇ Download", "menu_download_n": "⬇ Download selected ({n})", "menu_view": "🔍 View full size",
    "menu_open_site": "🌐 Open the post on the site", "menu_copy_link": "📋 Copy post link",
    "single_started": "Downloading post #{id}…", "single_saved": "Downloaded: {name}", "single_exists": "Already downloaded: {name}",
    "single_failed": "Could not download post #{id}: {err}", "single_no_url": "Post #{id} has no file link",
    "viewer_loading": "Loading the original… {p}", "viewer_failed": "Could not load: {err}",
    "viewer_video": "This is a video — press “▶ Open video” to play it in the browser",
    "btn_open_video": "▶ Open video", "btn_viewer_download": "⬇ Download", "btn_viewer_site": "🌐 On site",
    "viewer_hint": "Click the picture — 100% / fit to window · ← → — neighbouring posts · S — download · Esc — close", "info_artist": "Artist", "info_characters": "Characters", "info_copyright": "From",
    "info_loading": "Looking up artist and characters…", "info_other": "Other tags", "info_more": "▸ all tags ({n})", "info_less": "▾ collapse", "info_none": "Artist, characters and source are not tagged",
    "info_hover": "Hover over a picture — its artist, characters and source appear here.",
    "tip_tag_link": "Click a name to search for that tag", "tip_open_post": "Double-click to view full size, right-click to download or open on the site",
    "search_hint_empty": "Start typing tags — pictures from the site will appear here, like on its search page.",
    "preview_empty": "Downloaded files will appear here",
    "preview_missing": "File not found", "preview_unavailable": "No preview available",
    "btn_file_open": "Open", "btn_file_folder": "Show in folder", "btn_file_post": "Post on site",

    "card_history": "Download history",
    "hist_query": "Search", "hist_count": "Downloaded: last time / total",
    "hist_date": "When", "hist_folder": "Folder",
    "hist_empty": "No history yet", "hist_any_tags": "(no tags)",
    "btn_hist_use": "Use in search", "btn_hist_update": "⟳ Get new posts",
    "btn_hist_folder": "Open folder", "btn_hist_remove": "Remove entry",

    "card_api": "{site} API key",
    "api_need": "An account API key is required — paste the line with api_key and user_id below.",
    "ph_api_line": "&api_key=…&user_id=…",
    "lbl_api_line": "Line with api_key and user_id",
    "api_parsed": "Found: User ID {uid}, key ••••{tail}",
    "chk_show_key": "Show",
    "btn_login_browser": "🌐 Log in through the browser — the key is picked up by itself",
    "hint_login_browser_gelbooru": "Your browser (Edge, Chrome, Yandex…) opens in a separate window. Log in or sign up — then the program enables “Display all site content” and “Always show original” and takes the key.",
    "hint_login_browser_rule34": "Your browser (Edge, Chrome, Yandex…) opens in a separate window. Log in or sign up (solve the captcha as usual) — then the program creates a key if there is none and takes it.",
    "login_title": "Log in to {site}", "lbl_login_browser": "Browser for logging in:",
    "login_no_browser_short": "not found — a normal page will open",
    "login_no_browser": "No Chromium browser found (Edge, Chrome, Yandex, Opera, Brave, Vivaldi). The key page will open in your usual browser — copy the key line there and the program picks it up.",
    "login_starting": "Starting {browser}…", "login_using": "Logging in through {browser}",
    "login_privacy": "The browser window opens with its own separate profile. You type the password on the site page — the program neither sees nor saves it.",
    "login_launch_failed": "Could not start the browser: {err}",
    "login_no_debug": "The browser did not answer the program. Try again or choose another browser in settings.",
    "login_closed": "The browser window was closed — no key received.",
    "btn_login_cancel": "Cancel", "btn_login_close": "Close", "login_preparing": "Opening the site…",
    "login_unavailable": "The built-in browser did not start: {err}",
    "login_got_key": "Got the key from the site page — checking…",
    "login_step_open": "Opening the key page…",
    "login_step_login": "Log in to your account (no account? “Sign up”). If the site shows a captcha, solve it as usual. "
                        "The program does the rest.",
    "login_step_opening": "You are logged in — opening the key page…",
    "login_step_settings": "Enabling “Display all site content” and “Always show original” and saving…",
    "login_step_generate": "Creating an API key…",
    "login_step_manual": "Could not do it automatically. On this page find “API Access Credentials”, tick creating a "
                         "key if needed and press Save — the program takes the key as soon as it appears.",
    "login_failed_net": "The page did not open — check the connection (⟳ — try again).",
    "login_done": "✓ Done: got the key (User ID {uid}){extra}. This window will close now.",
    "login_done_settings": ", account settings enabled",
    "btn_login": "Log in", "btn_reg": "Sign up", "btn_key_page": "Key page", "btn_close_browser": "Close",
    "btn_open_key_page": "🔑 Open the key page", "btn_register": "Sign up on the site",
    "hint_api_steps_gelbooru": "1. Log in to Gelbooru (no account? “Sign up on the site”).\n"
                               "2. Press “Open the key page”. On that page enable “Display all site content” and "
                               "“Always show original”, then save.\n"
                               "3. At the bottom, in “API Access Credentials”, copy the whole line — the program "
                               "picks it up from the clipboard by itself.",
    "hint_api_steps_rule34": "1. Log in to Rule34.xxx (no account? “Sign up on the site”).\n"
                             "2. Press “Open the key page”, in “API Access Credentials” tick generating a new key "
                             "and save.\n"
                             "3. Copy the line that appears — the program picks it up from the clipboard by itself.",
    "hint_api_secure": "The key is stored encrypted by Windows and never appears in the log.",
    "api_from_clipboard": "Took the line from the clipboard — checking…",
    "msg_no_url_gelbooru": "The site gave no file link for {n} posts. Enable “Display all site content” and "
                           "“Always show original” in your Gelbooru account settings (“Open the key page” button "
                           "in the program settings).",
    "msg_no_url_rule34": "The site gave no file link for {n} posts — they may be hidden or deleted.",
    "hint_api": "Get the line on the site: {path}. Paste it whole — the program extracts User ID and the key "
                "and checks them right away. The key is stored encrypted by Windows and never appears in the log.",
    "btn_api_check": "Check and save",
    "api_missing": "No api_key and user_id found in the line — copy the whole line from the site",
    "api_checking": "Checking…",
    "api_saved_ok": "The site accepted the key; saved",
    "api_bad": "The site rejected the key — check User ID and API key.",
    "api_check_fail": "Could not check ({err}). The key is saved.",

    "card_speed": "Speed",
    "lbl_threads": "Files at once", "lbl_delay": "Pause between files, s",
    "hint_speed": "3 at once is reasonable. If the site starts answering “too many requests”, lower it.",
    "card_other": "Other",
    "btn_open_data": "Program settings folder",
    "hint_data": "Settings, history and error.log live there. Failed downloads are listed in "
                 "failed_links.txt inside each search folder.",

    "card_net": "Connection",
    "net_auto": "Auto: direct, and through a proxy if the site is unreachable (recommended)",
    "hint_net_auto": "The program notices blocking by itself, finds a working proxy from the list below and "
                     "uses it only for blocked servers. Everything else goes direct.",
    "net_direct": "Direct only (or the Windows system proxy)",
    "net_custom": "Everything through my proxy:",
    "ph_proxy": "socks5h://127.0.0.1:1080  or  http://host:port",
    "hint_proxy_custom": "A VPN client's proxy works (usually socks5h://127.0.0.1:port). Login and password: "
                         "http://login:password@host:port",
    "lbl_pool": "Proxies for “Auto” mode (one per line, best first):",
    "btn_pool_check": "Check list", "btn_pool_reset": "Built-in list",
    "pool_count": "In list: {n}", "pool_checking": "Checking {n} proxies…",
    "pool_dead": "no answer", "pool_result": "{ok} of {n} answer; the fastest are moved to the top.",
    "hint_pool_safety": "Free proxies die quickly — press “Check list” from time to time or paste fresh ones. "
                        "The API key does not leak through a proxy: the connection to the site is encrypted "
                        "(HTTPS), the proxy only sees the server name.",
    "btn_net_check": "Check connection",
    "net_checking": "Checking…", "net_ok": "Site reachable: {ms} ms, {route}", "net_fail": "No connection: {err}",
    "route_direct": "direct", "route_proxy": "via proxy {proxy}", "route_custom": "via my proxy {proxy}",

    "log_resume": "↪ Resuming the interrupted download (already downloaded {downloaded})",
    "log_update_from": "⟳ New only: posts newer than #{id}",
    "log_update_none": "Nothing was downloaded for this search before — downloading everything",
    "log_query": "🔍 Search: {tags}  →  {folder}",
    "log_count_failed": "Could not get the number of posts: {code}",
    "log_found": "Posts found: {count}",
    "log_cursor_fallback": "The site did not understand paging by post number — switching to normal pages",
    "log_page": "📑 Page {page}: {count} posts",
    "log_no_url": "Post {id}: the site gave no file link (check account settings)",
    "log_long_path": "Post {id}: path too long — saving under the post number",
    "log_file_ok": "✓ {name}  ({size})",
    "log_file_fail": "✗ Post {id}: {code}",
    "log_file_retry": "Post {id}: {code} — retry in {delay} s (attempt {attempt})",
    "log_api_retry": "⚠ API: {code} — retry in {delay} s (attempt {attempt})",
    "log_failed_saved": "Failed downloads are listed in {path}",
    "log_route_probe": "{host} does not answer directly — looking for a working proxy ({count} in list)…",
    "log_route_proxy": "{host}: working through proxy {proxy}",
    "log_route_blocked": "{host} is blocked directly — using {proxy} for it from now on",
    "log_route_none": "{host}: no proxy from the list answered",

    "err_net_connection": "no connection to the site",
    "err_net_timeout": "the site did not answer in time",
    "err_net_proxy": "proxy error",
    "err_net_ssl": "secure connection error",
    "err_net_broken": "connection dropped",
    "err_net_other": "network error",
    "err_rate_limited": "too many requests, the site asks to wait",
    "err_server_busy": "server overloaded or unavailable",
    "err_empty_response": "the site sent an empty response",
    "err_empty_file": "the server sent an empty file",
    "err_incomplete": "file downloaded incompletely",
    "err_auth_http": "the site rejected the key",
    "err_auth_server": "the site rejected the key",
    "err_blocked": "access denied by the site's protection (Cloudflare)",
    "err_not_found": "file not found on the server",
    "err_http_error": "site error",
    "err_server_message": "message from the site",
    "err_bad_response": "unexpected response from the site",
    "err_not_media": "a web page came instead of the file",
    "err_file_error": "could not write the file",
    "err_proxy_invalid": "invalid proxy address",
    "err_no_url": "no file link",
    "err_path_too_long": "file path too long",
    "err_internal": "internal program error",
}

ZH = {
    "unit_b": "B", "unit_kb": "KB", "unit_mb": "MB", "unit_gb": "GB",
    "time_hm": "{h} 小时 {m} 分", "time_ms": "{m} 分 {s} 秒", "time_s": "{s} 秒",
    "tab_download": "下载", "tab_history": "历史", "tab_settings": "设置",

    "card_search": "下载内容",
    "lbl_tags": "标签或搜索链接",
    "ph_tags": "blue_hair smile -monochrome   或搜索页面的链接",
    "btn_find": "搜索",
    "hint_tags": "标签用空格分隔，“-标签”表示排除。输入时会出现提示。也可以粘贴网站搜索页面的链接，程序会自动提取标签。",
    "lbl_rating": "分级", "lbl_media": "文件类型", "lbl_limit": "下载数量",
    "rating_any": "任意",
    "media_all": "全部", "media_images": "图片", "media_videos": "视频和动画",
    "limit_all": "全部", "tip_limit": "0 = 下载找到的全部内容",
    "chk_no_ai": "排除 AI 作品", "tip_no_ai": "从搜索和下载中排除标记为 AI 的帖子：{tags}",
    "lbl_account_nick": "窗口角落的昵称：", "ph_nick_auto": "根据密钥自动识别",
    "ph_nick_manual": "请输入昵称 — 网站不提供",
    "footer_account": "👤 {name}", "footer_no_key": "👤 未设置密钥",
    "found_searching": "正在搜索…", "found_n": "找到帖子：{n}",
    "found_unknown": "网站未返回帖子数量",
    "found_error": "无法获取数量：{err}",
    "hint_gelbooru_account": "要查看所有帖子和原图，请在 Gelbooru 账户设置中启用 “Display all site content” 和 “Always show original”。",

    "card_save": "保存位置和方式",
    "lbl_folder": "文件夹", "btn_choose": "选择…", "btn_open_folder": "打开",
    "hint_subfolder": "每个搜索会创建单独的子文件夹",
    "hint_target": "文件将保存到：{path}",
    "lbl_names": "文件名",
    "tpl_id": "帖子编号 — 1234567.jpg",
    "tpl_tags_id": "标签和帖子编号 — blue_hair_1234567.jpg",
    "tpl_tags_seq": "标签和序号 — blue_hair_0001.jpg（旧版方式）",
    "tpl_md5": "文件 MD5 — 3f2a…c9.jpg",
    "tip_names": "下载文件的命名方式。使用帖子编号最容易在网站上找到原帖；“旧版方式”与旧版本程序相同。",
    "chk_split": "分到 “Картинки”（图片）和 “Видео и анимации”（视频）文件夹",
    "chk_skip": "不重复下载已下载的内容",
    "tip_skip": "已下载的帖子编号记录在搜索文件夹中（.booru_ids.txt）",

    "btn_start": "▶  下载", "btn_update": "⟳  仅新帖子", "btn_resume": "↪  继续", "btn_stop": "■  停止",
    "tip_update": "下载自上次下载以来网站上新出现的帖子",
    "tip_resume": "从中断处继续下载",

    "card_progress": "下载进度",
    "prog_idle": "点击“下载”开始",
    "prog_counts": "已下载 {d}  ·  跳过（已存在）{s}  ·  错误 {f}",
    "prog_filtered": "  ·  类型不符 {x}",
    "prog_speed": "{speed}/秒", "prog_eta": "剩余约 {eta}", "prog_total_size": "共 {size}",
    "btn_log_show": "▸ 显示日志", "btn_log_hide": "▾ 隐藏日志",
    "status_starting": "准备中…", "status_counting": "正在统计帖子…",
    "status_page": "正在获取第 {page} 页…", "status_downloading": "正在下载…",
    "status_stopping": "正在停止…",
    "status_done": "完成", "status_stopped": "已停止", "status_paused": "已暂停",
    "status_auth": "网站拒绝了密钥", "status_error": "错误",
    "wait_offline": "无法连接网站（{err}）— {s} 秒后重试，第 {n} 次。下载会自动继续。",
    "wait_server": "网站无响应（{err}）— {s} 秒后重试，第 {n} 次。",
    "hint_try_auto": "如果网站被封锁，请在设置中选择“自动”模式。",
    "msg_finished_done": "完成：已下载 {d}，跳过 {s}，错误 {f}。",
    "msg_finished_stopped": "已停止。已下载 {d}。点击“继续”以完成下载。",
    "msg_finished_paused": "网站长时间无响应（{err}）。进度已保存，请稍后点击“继续”。",
    "msg_finished_auth": "网站拒绝了 API 密钥（{err}）。请在设置中检查密钥，然后点击“继续”。",
    "msg_finished_error": "错误：{err}。进度已保存。",
    "msg_no_tags": "请输入标签或粘贴搜索链接",
    "msg_no_folder": "请选择保存文件夹",
    "msg_running_close": "下载仍在进行。要停止并关闭程序吗？\n进度会被保存，之后可以点击“继续”。",

    "card_preview": "最近的文件",
    "card_log": "运行日志", "btn_view_files": "文件", "btn_view_log": "日志",
    "btn_view_search": "搜索", "card_results": "搜索结果",
    "search_info": "共找到 {total} 个。双击查看原图，右键下载。",
    "search_info_media": "只显示所选类型的文件。",
    "search_nothing": "没有找到", "search_no_url": "⚠ 有 {n} 个帖子没有文件链接 — 将鼠标移到这里查看解决办法", "page_label": "第 {n} 页，共 {total} 页", "tip_prev_page": "上一页", "tip_next_page": "下一页",
    "menu_download": "⬇ 下载", "menu_download_n": "⬇ 下载所选（{n}）", "menu_view": "🔍 查看原图",
    "menu_open_site": "🌐 在网站上打开帖子", "menu_copy_link": "📋 复制帖子链接",
    "single_started": "正在下载帖子 #{id}…", "single_saved": "已下载：{name}", "single_exists": "已经下载过：{name}",
    "single_failed": "无法下载帖子 #{id}：{err}", "single_no_url": "帖子 #{id} 没有文件链接",
    "viewer_loading": "正在加载原图… {p}", "viewer_failed": "无法加载：{err}",
    "viewer_video": "这是视频 — 点击“▶ 打开视频”在浏览器中播放",
    "btn_open_video": "▶ 打开视频", "btn_viewer_download": "⬇ 下载", "btn_viewer_site": "🌐 网站",
    "viewer_hint": "点击图片 — 100% / 适应窗口 · ← → — 相邻作品 · S — 下载 · Esc — 关闭", "info_artist": "作者", "info_characters": "角色", "info_copyright": "出处",
    "info_loading": "正在查询作者和角色…", "info_other": "其他标签", "info_more": "▸ 全部标签（{n}）", "info_less": "▾ 收起", "info_none": "网站上没有标注作者、角色和出处",
    "info_hover": "将鼠标移到图片上 — 这里会显示作者、角色和出处。",
    "tip_tag_link": "点击名称即可搜索该标签", "tip_open_post": "双击查看原图，右键下载或在网站上打开",
    "search_hint_empty": "开始输入标签 — 这里会像网站搜索页一样显示图片。",
    "preview_empty": "下载的文件会显示在这里",
    "preview_missing": "找不到文件", "preview_unavailable": "无法预览",
    "btn_file_open": "打开", "btn_file_folder": "在文件夹中显示", "btn_file_post": "网站上的帖子",

    "card_history": "下载历史",
    "hist_query": "搜索", "hist_count": "下载数：上次 / 总计", "hist_date": "时间", "hist_folder": "文件夹",
    "hist_empty": "暂无历史", "hist_any_tags": "（无标签）",
    "btn_hist_use": "填入搜索", "btn_hist_update": "⟳ 下载新帖子",
    "btn_hist_folder": "打开文件夹", "btn_hist_remove": "删除记录",

    "card_api": "{site} API 密钥",
    "api_need": "需要账户 API 密钥 — 请在下方粘贴包含 api_key 和 user_id 的字符串。",
    "ph_api_line": "&api_key=…&user_id=…",
    "lbl_api_line": "包含 api_key 和 user_id 的字符串",
    "api_parsed": "已识别：User ID {uid}，密钥 ••••{tail}",
    "chk_show_key": "显示",
    "btn_login_browser": "🌐 通过浏览器登录 — 自动获取密钥",
    "hint_login_browser_gelbooru": "您的浏览器（Edge、Chrome、Yandex…）会在单独的窗口中打开。登录或注册后，程序会自动启用 “Display all site content” 和 “Always show original” 并获取密钥。",
    "hint_login_browser_rule34": "您的浏览器（Edge、Chrome、Yandex…）会在单独的窗口中打开。登录或注册（照常完成验证码）后，程序会在没有密钥时自动创建并获取。",
    "login_title": "登录 {site}", "lbl_login_browser": "用于登录的浏览器：",
    "login_no_browser_short": "未找到 — 将打开普通页面",
    "login_no_browser": "没有找到 Chromium 内核浏览器（Edge、Chrome、Yandex、Opera、Brave、Vivaldi）。将在常用浏览器中打开密钥页面 — 在那里复制密钥字符串，程序会自动读取。",
    "login_starting": "正在启动 {browser}…", "login_using": "通过 {browser} 登录",
    "login_privacy": "浏览器窗口使用独立的配置文件打开。密码在网站页面上输入 — 程序看不到也不保存。",
    "login_launch_failed": "无法启动浏览器：{err}",
    "login_no_debug": "浏览器没有响应程序。请重试或在设置中选择其他浏览器。",
    "login_closed": "浏览器窗口已关闭 — 未获取密钥。",
    "btn_login_cancel": "取消", "btn_login_close": "关闭", "login_preparing": "正在打开网站…",
    "login_unavailable": "内置浏览器无法启动：{err}",
    "login_got_key": "已从网站页面获取密钥 — 正在检查…",
    "login_step_open": "正在打开密钥页面…",
    "login_step_login": "请登录账户（没有账户请点“注册”）。如果网站显示验证码，请照常完成。其余由程序完成。",
    "login_step_opening": "已登录 — 正在打开密钥页面…",
    "login_step_settings": "正在启用 “Display all site content” 和 “Always show original” 并保存…",
    "login_step_generate": "正在创建 API 密钥…",
    "login_step_manual": "无法自动完成。请在此页面找到 “API Access Credentials”，需要时勾选创建密钥并点击 Save — 密钥出现后程序会立即获取。",
    "login_failed_net": "页面无法打开 — 请检查连接（⟳ — 重试）。",
    "login_done": "✓ 完成：已获取密钥（User ID {uid}）{extra}。窗口即将关闭。",
    "login_done_settings": "，账户设置已启用",
    "btn_login": "登录", "btn_reg": "注册", "btn_key_page": "密钥页面", "btn_close_browser": "关闭",
    "btn_open_key_page": "🔑 打开密钥页面", "btn_register": "在网站注册",
    "hint_api_steps_gelbooru": "1. 登录 Gelbooru（没有账户请点“在网站注册”）。\n"
                               "2. 点击“打开密钥页面”，在该页面启用 “Display all site content” 和 “Always show original” 并保存。\n"
                               "3. 在页面底部的 “API Access Credentials” 中复制整行 — 程序会自动从剪贴板读取。",
    "hint_api_steps_rule34": "1. 登录 Rule34.xxx（没有账户请点“在网站注册”）。\n"
                             "2. 点击“打开密钥页面”，在 “API Access Credentials” 中勾选生成新密钥并保存。\n"
                             "3. 复制出现的整行 — 程序会自动从剪贴板读取。",
    "hint_api_secure": "密钥由 Windows 加密保存，不会出现在日志中。",
    "api_from_clipboard": "已从剪贴板读取 — 正在检查…",
    "msg_no_url_gelbooru": "有 {n} 个帖子网站没有提供文件链接。请在 Gelbooru 账户设置中启用 “Display all site content” 和 “Always show original”（程序设置中的“打开密钥页面”按钮）。",
    "msg_no_url_rule34": "有 {n} 个帖子网站没有提供文件链接 — 可能已被隐藏或删除。",
    "hint_api": "字符串在网站上获取：{path}。完整粘贴即可，程序会自动识别 User ID 和密钥并立即检查。密钥由 Windows 加密保存，不会出现在日志中。",
    "btn_api_check": "检查并保存",
    "api_missing": "字符串中没有找到 api_key 和 user_id — 请从网站完整复制",
    "api_checking": "正在检查…",
    "api_saved_ok": "网站已接受密钥，已保存",
    "api_bad": "网站拒绝了密钥 — 请检查 User ID 和 API key。",
    "api_check_fail": "无法检查（{err}）。密钥已保存。",

    "card_speed": "速度",
    "lbl_threads": "同时下载文件数", "lbl_delay": "文件间隔（秒）",
    "hint_speed": "同时 3 个比较合适。如果网站提示“请求过多”，请调低。",
    "card_other": "其他",
    "btn_open_data": "程序设置文件夹",
    "hint_data": "这里保存设置、历史和 error.log。失败的下载列在每个搜索文件夹的 failed_links.txt 中。",

    "card_net": "连接",
    "net_auto": "自动：直接连接，网站无法访问时通过代理（推荐）",
    "hint_net_auto": "程序会自动发现封锁，从下方列表中找到可用代理，并只对被封锁的服务器使用代理，其余直接连接。",
    "net_direct": "仅直接连接（或使用 Windows 系统代理）",
    "net_custom": "全部通过我的代理：",
    "ph_proxy": "socks5h://127.0.0.1:1080  或  http://地址:端口",
    "hint_proxy_custom": "可以使用 VPN 客户端的代理（通常是 socks5h://127.0.0.1:端口）。用户名和密码：http://用户名:密码@地址:端口",
    "lbl_pool": "“自动”模式使用的代理（每行一个，最好的在上面）：",
    "btn_pool_check": "检查列表", "btn_pool_reset": "内置列表",
    "pool_count": "列表中：{n}", "pool_checking": "正在检查 {n} 个代理…",
    "pool_dead": "无响应", "pool_result": "{n} 个中有 {ok} 个可用；最快的已移到顶部。",
    "hint_pool_safety": "免费代理很快失效 — 请不时点击“检查列表”或粘贴新的代理。API 密钥不会通过代理泄露：与网站的连接是加密的（HTTPS），代理只能看到服务器名称。",
    "btn_net_check": "检查连接",
    "net_checking": "正在检查…", "net_ok": "网站可访问：{ms} 毫秒，{route}", "net_fail": "无法连接：{err}",
    "route_direct": "直接连接", "route_proxy": "通过代理 {proxy}", "route_custom": "通过我的代理 {proxy}",

    "log_resume": "↪ 继续中断的下载（已下载 {downloaded}）",
    "log_update_from": "⟳ 仅新帖子：编号大于 {id}",
    "log_update_none": "此搜索之前没有下载过 — 下载全部",
    "log_query": "🔍 搜索：{tags}  →  {folder}",
    "log_count_failed": "无法获取帖子数量：{code}",
    "log_found": "找到帖子：{count}",
    "log_cursor_fallback": "网站不支持按帖子编号翻页 — 改用普通分页",
    "log_page": "📑 第 {page} 页：{count} 个帖子",
    "log_no_url": "帖子 {id}：网站没有提供文件链接（请检查账户设置）",
    "log_long_path": "帖子 {id}：路径过长 — 以帖子编号保存",
    "log_file_ok": "✓ {name}  （{size}）",
    "log_file_fail": "✗ 帖子 {id}：{code}",
    "log_file_retry": "帖子 {id}：{code} — {delay} 秒后重试（第 {attempt} 次）",
    "log_api_retry": "⚠ API：{code} — {delay} 秒后重试（第 {attempt} 次）",
    "log_failed_saved": "失败的下载已记录在 {path}",
    "log_route_probe": "{host} 无法直接访问 — 正在寻找可用代理（列表中 {count} 个）…",
    "log_route_proxy": "{host}：通过代理 {proxy} 工作",
    "log_route_blocked": "{host} 被直接封锁 — 之后通过 {proxy} 访问",
    "log_route_none": "{host}：列表中没有代理响应",

    "err_net_connection": "无法连接网站",
    "err_net_timeout": "网站未及时响应",
    "err_net_proxy": "代理错误",
    "err_net_ssl": "安全连接错误",
    "err_net_broken": "连接中断",
    "err_net_other": "网络错误",
    "err_rate_limited": "请求过多，网站要求稍候",
    "err_server_busy": "服务器过载或不可用",
    "err_empty_response": "网站返回了空响应",
    "err_empty_file": "服务器返回了空文件",
    "err_incomplete": "文件未完整下载",
    "err_auth_http": "网站拒绝了密钥",
    "err_auth_server": "网站拒绝了密钥",
    "err_blocked": "被网站防护拦截（Cloudflare）",
    "err_not_found": "服务器上找不到文件",
    "err_http_error": "网站错误",
    "err_server_message": "网站消息",
    "err_bad_response": "网站返回了无法识别的响应",
    "err_not_media": "返回的是网页而不是文件",
    "err_file_error": "无法写入文件",
    "err_proxy_invalid": "代理地址无效",
    "err_no_url": "没有文件链接",
    "err_path_too_long": "文件路径过长",
    "err_internal": "程序内部错误",
}

JA = {
    "unit_b": "B", "unit_kb": "KB", "unit_mb": "MB", "unit_gb": "GB",
    "time_hm": "{h} 時間 {m} 分", "time_ms": "{m} 分 {s} 秒", "time_s": "{s} 秒",
    "tab_download": "ダウンロード", "tab_history": "履歴", "tab_settings": "設定",

    "card_search": "ダウンロードする内容",
    "lbl_tags": "タグまたは検索リンク",
    "ph_tags": "blue_hair smile -monochrome   または検索ページのリンク",
    "btn_find": "検索",
    "hint_tags": "タグはスペース区切り、「-タグ」で除外。入力中に候補が表示されます。サイトの検索ページのリンクを貼り付けると、タグが自動で取り出されます。",
    "lbl_rating": "レーティング", "lbl_media": "ファイルの種類", "lbl_limit": "ダウンロード数",
    "rating_any": "すべて",
    "media_all": "すべて", "media_images": "画像", "media_videos": "動画・アニメーション",
    "limit_all": "すべて", "tip_limit": "0 = 見つかったものをすべてダウンロード",
    "chk_no_ai": "AI作品を除外", "tip_no_ai": "AI とタグ付けされた投稿を検索とダウンロードから除外：{tags}",
    "lbl_account_nick": "ウィンドウ隅の名前：", "ph_nick_auto": "キーから自動で取得",
    "ph_nick_manual": "名前を入力してください（サイトから取得できません）",
    "footer_account": "👤 {name}", "footer_no_key": "👤 キー未設定",
    "found_searching": "検索中…", "found_n": "見つかった投稿：{n}",
    "found_unknown": "サイトが投稿数を返しませんでした",
    "found_error": "件数を取得できません：{err}",
    "hint_gelbooru_account": "すべての投稿と元画像を表示するには、Gelbooru のアカウント設定で「Display all site content」と「Always show original」を有効にしてください。",

    "card_save": "保存先と保存方法",
    "lbl_folder": "フォルダー", "btn_choose": "選択…", "btn_open_folder": "開く",
    "hint_subfolder": "検索ごとにサブフォルダーが作成されます",
    "hint_target": "保存先：{path}",
    "lbl_names": "ファイル名",
    "tpl_id": "投稿番号 — 1234567.jpg",
    "tpl_tags_id": "タグと投稿番号 — blue_hair_1234567.jpg",
    "tpl_tags_seq": "タグと連番 — blue_hair_0001.jpg（従来どおり）",
    "tpl_md5": "ファイルの MD5 — 3f2a…c9.jpg",
    "tip_names": "ダウンロードしたファイルの名前の付け方。投稿番号ならサイトで投稿を探しやすく、「従来どおり」は旧バージョンと同じ名前です。",
    "chk_split": "「Картинки」（画像）と「Видео и анимации」（動画）フォルダーに分ける",
    "chk_skip": "ダウンロード済みのものは再ダウンロードしない",
    "tip_skip": "ダウンロード済みの投稿番号は検索フォルダー内（.booru_ids.txt）に記録されます",

    "btn_start": "▶  ダウンロード", "btn_update": "⟳  新着のみ", "btn_resume": "↪  再開", "btn_stop": "■  停止",
    "tip_update": "前回のダウンロード以降にサイトに追加された投稿をダウンロード",
    "tip_resume": "中断したダウンロードを続きから再開",

    "card_progress": "進行状況",
    "prog_idle": "「ダウンロード」を押して開始",
    "prog_counts": "ダウンロード済み {d}  ·  スキップ（既存）{s}  ·  エラー {f}",
    "prog_filtered": "  ·  種類が不一致 {x}",
    "prog_speed": "{speed}/秒", "prog_eta": "残り約 {eta}", "prog_total_size": "合計 {size}",
    "btn_log_show": "▸ ログを表示", "btn_log_hide": "▾ ログを隠す",
    "status_starting": "準備中…", "status_counting": "投稿を数えています…",
    "status_page": "{page} ページ目を取得中…", "status_downloading": "ダウンロード中…",
    "status_stopping": "停止しています…",
    "status_done": "完了", "status_stopped": "停止しました", "status_paused": "一時停止",
    "status_auth": "サイトがキーを拒否しました", "status_error": "エラー",
    "wait_offline": "サイトに接続できません（{err}）— {s} 秒後に再試行、{n} 回目。ダウンロードは自動で続きます。",
    "wait_server": "サイトが応答しません（{err}）— {s} 秒後に再試行、{n} 回目。",
    "hint_try_auto": "サイトがブロックされている場合は、設定で「自動」モードを選んでください。",
    "msg_finished_done": "完了：ダウンロード {d}、スキップ {s}、エラー {f}。",
    "msg_finished_stopped": "停止しました。ダウンロード {d}。「再開」で続きをダウンロードできます。",
    "msg_finished_paused": "サイトが長時間応答しません（{err}）。進行状況は保存済みです。後で「再開」を押してください。",
    "msg_finished_auth": "サイトが API キーを拒否しました（{err}）。設定でキーを確認してから「再開」を押してください。",
    "msg_finished_error": "エラー：{err}。進行状況は保存済みです。",
    "msg_no_tags": "タグを入力するか検索リンクを貼り付けてください",
    "msg_no_folder": "保存先フォルダーを指定してください",
    "msg_running_close": "ダウンロード中です。停止してプログラムを閉じますか？\n進行状況は保存され、後で「再開」できます。",

    "card_preview": "最近のファイル",
    "card_log": "ログ", "btn_view_files": "ファイル", "btn_view_log": "ログ",
    "btn_view_search": "検索", "card_results": "検索結果",
    "search_info": "{total} 件見つかりました。ダブルクリックで原寸表示、右クリックでダウンロード。",
    "search_info_media": "選択した種類のファイルのみ表示しています。",
    "search_nothing": "見つかりませんでした", "search_no_url": "⚠ {n} 件の投稿にファイルのリンクがありません — ここにカーソルを合わせると対処法を表示", "page_label": "{n} / {total} ページ", "tip_prev_page": "前のページ", "tip_next_page": "次のページ",
    "menu_download": "⬇ ダウンロード", "menu_download_n": "⬇ 選択したものをダウンロード（{n}）", "menu_view": "🔍 原寸で表示",
    "menu_open_site": "🌐 サイトで投稿を開く", "menu_copy_link": "📋 投稿のリンクをコピー",
    "single_started": "投稿 #{id} をダウンロード中…", "single_saved": "ダウンロードしました：{name}", "single_exists": "ダウンロード済み：{name}",
    "single_failed": "投稿 #{id} をダウンロードできません：{err}", "single_no_url": "投稿 #{id} にはファイルのリンクがありません",
    "viewer_loading": "原寸画像を読み込み中… {p}", "viewer_failed": "読み込めません：{err}",
    "viewer_video": "動画です。「▶ 動画を開く」でブラウザで再生します",
    "btn_open_video": "▶ 動画を開く", "btn_viewer_download": "⬇ ダウンロード", "btn_viewer_site": "🌐 サイト",
    "viewer_hint": "画像をクリック — 100% / ウィンドウに合わせる · ← → — 前後の作品 · S — ダウンロード · Esc — 閉じる", "info_artist": "作者", "info_characters": "キャラクター", "info_copyright": "作品",
    "info_loading": "作者とキャラクターを確認中…", "info_other": "その他のタグ", "info_more": "▸ すべてのタグ（{n}）", "info_less": "▾ 閉じる", "info_none": "作者・キャラクター・作品のタグがありません",
    "info_hover": "画像にカーソルを合わせると、作者・キャラクター・作品がここに表示されます。",
    "tip_tag_link": "名前をクリックするとそのタグで検索します", "tip_open_post": "ダブルクリックで原寸表示、右クリックでダウンロードまたはサイトで開く",
    "search_hint_empty": "タグを入力すると、サイトの検索ページのように画像がここに表示されます。",
    "preview_empty": "ダウンロードしたファイルがここに表示されます",
    "preview_missing": "ファイルが見つかりません", "preview_unavailable": "プレビューできません",
    "btn_file_open": "開く", "btn_file_folder": "フォルダーで表示", "btn_file_post": "サイトの投稿",

    "card_history": "ダウンロード履歴",
    "hist_query": "検索", "hist_count": "ダウンロード数：前回 / 合計", "hist_date": "日時", "hist_folder": "フォルダー",
    "hist_empty": "履歴はまだありません", "hist_any_tags": "（タグなし）",
    "btn_hist_use": "検索に入力", "btn_hist_update": "⟳ 新着をダウンロード",
    "btn_hist_folder": "フォルダーを開く", "btn_hist_remove": "記録を削除",

    "card_api": "{site} API キー",
    "api_need": "アカウントの API キーが必要です。下に api_key と user_id を含む文字列を貼り付けてください。",
    "ph_api_line": "&api_key=…&user_id=…",
    "lbl_api_line": "api_key と user_id を含む文字列",
    "api_parsed": "検出：User ID {uid}、キー ••••{tail}",
    "chk_show_key": "表示",
    "btn_login_browser": "🌐 ブラウザでログイン — キーは自動で取得",
    "hint_login_browser_gelbooru": "お使いのブラウザ（Edge、Chrome、Yandex…）が別ウィンドウで開きます。ログインまたは登録すると、プログラムが「Display all site content」と「Always show original」を有効にしてキーを取得します。",
    "hint_login_browser_rule34": "お使いのブラウザ（Edge、Chrome、Yandex…）が別ウィンドウで開きます。ログインまたは登録（キャプチャは通常どおり）すると、キーがなければ作成して取得します。",
    "login_title": "{site} にログイン", "lbl_login_browser": "ログインに使うブラウザ：",
    "login_no_browser_short": "見つかりません — 通常のページが開きます",
    "login_no_browser": "Chromium 系のブラウザ（Edge、Chrome、Yandex、Opera、Brave、Vivaldi）が見つかりません。いつものブラウザでキーのページを開きます。そこでキーの行をコピーすれば、プログラムが自動で読み取ります。",
    "login_starting": "{browser} を起動しています…", "login_using": "{browser} でログイン",
    "login_privacy": "ブラウザは専用のプロファイルで別ウィンドウとして開きます。パスワードはサイトのページで入力します — プログラムからは見えず、保存もしません。",
    "login_launch_failed": "ブラウザを起動できません：{err}",
    "login_no_debug": "ブラウザがプログラムに応答しません。もう一度試すか、設定で別のブラウザを選んでください。",
    "login_closed": "ブラウザのウィンドウが閉じられました — キーは取得していません。",
    "btn_login_cancel": "キャンセル", "btn_login_close": "閉じる", "login_preparing": "サイトを開いています…",
    "login_unavailable": "内蔵ブラウザを起動できません：{err}",
    "login_got_key": "サイトのページからキーを取得しました — 確認中…",
    "login_step_open": "キーのページを開いています…",
    "login_step_login": "アカウントにログインしてください（アカウントがない場合は「登録」）。キャプチャが表示されたら通常どおり解いてください。残りはプログラムが行います。",
    "login_step_opening": "ログインしました — キーのページを開いています…",
    "login_step_settings": "「Display all site content」と「Always show original」を有効にして保存しています…",
    "login_step_generate": "API キーを作成しています…",
    "login_step_manual": "自動ではできませんでした。このページの「API Access Credentials」で必要ならキーの作成にチェックを入れて Save を押してください。キーが表示されるとすぐに取得します。",
    "login_failed_net": "ページが開きません — 接続を確認してください（⟳ — 再試行）。",
    "login_done": "✓ 完了：キーを取得しました（User ID {uid}）{extra}。このウィンドウは閉じます。",
    "login_done_settings": "、アカウント設定を有効化",
    "btn_login": "ログイン", "btn_reg": "登録", "btn_key_page": "キーのページ", "btn_close_browser": "閉じる",
    "btn_open_key_page": "🔑 キーのページを開く", "btn_register": "サイトで登録",
    "hint_api_steps_gelbooru": "1. Gelbooru にログインします（アカウントがない場合は「サイトで登録」）。\n"
                               "2. 「キーのページを開く」を押し、そのページで「Display all site content」と「Always show original」を有効にして保存します。\n"
                               "3. ページ下部の「API Access Credentials」の行を丸ごとコピーすると、プログラムがクリップボードから自動で読み取ります。",
    "hint_api_steps_rule34": "1. Rule34.xxx にログインします（アカウントがない場合は「サイトで登録」）。\n"
                             "2. 「キーのページを開く」を押し、「API Access Credentials」で新しいキーの生成にチェックを入れて保存します。\n"
                             "3. 表示された行を丸ごとコピーすると、プログラムがクリップボードから自動で読み取ります。",
    "hint_api_secure": "キーは Windows によって暗号化して保存され、ログには表示されません。",
    "api_from_clipboard": "クリップボードから読み取りました — 確認中…",
    "msg_no_url_gelbooru": "{n} 件の投稿でファイルのリンクがありません。Gelbooru のアカウント設定で「Display all site content」と「Always show original」を有効にしてください（プログラム設定の「キーのページを開く」ボタン）。",
    "msg_no_url_rule34": "{n} 件の投稿でファイルのリンクがありません。非表示または削除された可能性があります。",
    "hint_api": "文字列はサイトで取得できます：{path}。丸ごと貼り付けると、User ID とキーを自動で取り出してすぐに確認します。キーは Windows によって暗号化して保存され、ログには表示されません。",
    "btn_api_check": "確認して保存",
    "api_missing": "文字列に api_key と user_id が見つかりません。サイトから丸ごとコピーしてください",
    "api_checking": "確認中…",
    "api_saved_ok": "サイトがキーを受け付けました。保存しました",
    "api_bad": "サイトがキーを拒否しました。User ID と API key を確認してください。",
    "api_check_fail": "確認できませんでした（{err}）。キーは保存しました。",

    "card_speed": "速度",
    "lbl_threads": "同時ダウンロード数", "lbl_delay": "ファイル間の待機（秒）",
    "hint_speed": "同時に 3 つが妥当です。サイトが「リクエストが多すぎます」と返すようになったら減らしてください。",
    "card_other": "その他",
    "btn_open_data": "プログラムの設定フォルダー",
    "hint_data": "設定、履歴、error.log が保存されています。失敗したダウンロードは各検索フォルダーの failed_links.txt に記録されます。",

    "card_net": "接続",
    "net_auto": "自動：直接接続し、サイトにつながらない場合はプロキシ経由（推奨）",
    "hint_net_auto": "ブロックを自動で検出し、下のリストから使えるプロキシを見つけて、ブロックされたサーバーにだけ使います。それ以外は直接接続です。",
    "net_direct": "直接接続のみ（または Windows のシステムプロキシ）",
    "net_custom": "すべて自分のプロキシ経由：",
    "ph_proxy": "socks5h://127.0.0.1:1080  または  http://アドレス:ポート",
    "hint_proxy_custom": "VPN クライアントのプロキシが使えます（通常 socks5h://127.0.0.1:ポート）。ユーザー名とパスワード：http://ユーザー名:パスワード@アドレス:ポート",
    "lbl_pool": "「自動」モード用のプロキシ（1 行に 1 つ、良いものを上に）：",
    "btn_pool_check": "リストを確認", "btn_pool_reset": "内蔵リスト",
    "pool_count": "リスト内：{n}", "pool_checking": "{n} 個のプロキシを確認中…",
    "pool_dead": "応答なし", "pool_result": "{n} 個中 {ok} 個が応答。速いものを上に移動しました。",
    "hint_pool_safety": "無料プロキシはすぐに使えなくなります。ときどき「リストを確認」を押すか、新しいものを貼り付けてください。API キーがプロキシから漏れることはありません。サイトとの通信は暗号化（HTTPS）されており、プロキシに見えるのはサーバー名だけです。",
    "btn_net_check": "接続を確認",
    "net_checking": "確認中…", "net_ok": "サイトに接続できます：{ms} ms、{route}", "net_fail": "接続できません：{err}",
    "route_direct": "直接接続", "route_proxy": "プロキシ {proxy} 経由", "route_custom": "自分のプロキシ {proxy} 経由",

    "log_resume": "↪ 中断したダウンロードを再開（ダウンロード済み {downloaded}）",
    "log_update_from": "⟳ 新着のみ：{id} より新しい投稿",
    "log_update_none": "この検索はまだダウンロードされていません。すべてダウンロードします",
    "log_query": "🔍 検索：{tags}  →  {folder}",
    "log_count_failed": "投稿数を取得できません：{code}",
    "log_found": "見つかった投稿：{count}",
    "log_cursor_fallback": "サイトが投稿番号によるページ送りに対応していないため、通常のページに切り替えます",
    "log_page": "📑 {page} ページ目：{count} 件",
    "log_no_url": "投稿 {id}：ファイルのリンクがありません（アカウント設定を確認してください）",
    "log_long_path": "投稿 {id}：パスが長すぎるため投稿番号で保存します",
    "log_file_ok": "✓ {name}  （{size}）",
    "log_file_fail": "✗ 投稿 {id}：{code}",
    "log_file_retry": "投稿 {id}：{code} — {delay} 秒後に再試行（{attempt} 回目）",
    "log_api_retry": "⚠ API：{code} — {delay} 秒後に再試行（{attempt} 回目）",
    "log_failed_saved": "失敗したダウンロードは {path} に記録しました",
    "log_route_probe": "{host} に直接つながりません。使えるプロキシを探しています（リスト内 {count} 個）…",
    "log_route_proxy": "{host}：プロキシ {proxy} 経由で接続中",
    "log_route_blocked": "{host} は直接接続がブロックされています。以後 {proxy} 経由で接続します",
    "log_route_none": "{host}：リストのどのプロキシも応答しませんでした",

    "err_net_connection": "サイトに接続できません",
    "err_net_timeout": "サイトが時間内に応答しませんでした",
    "err_net_proxy": "プロキシのエラー",
    "err_net_ssl": "暗号化通信のエラー",
    "err_net_broken": "接続が切れました",
    "err_net_other": "ネットワークエラー",
    "err_rate_limited": "リクエストが多すぎます。サイトが待機を求めています",
    "err_server_busy": "サーバーが混雑しているか利用できません",
    "err_empty_response": "サイトから空の応答が返りました",
    "err_empty_file": "サーバーから空のファイルが返りました",
    "err_incomplete": "ファイルが最後までダウンロードされませんでした",
    "err_auth_http": "サイトがキーを拒否しました",
    "err_auth_server": "サイトがキーを拒否しました",
    "err_blocked": "サイトの保護機能（Cloudflare）によりアクセスが拒否されました",
    "err_not_found": "サーバーにファイルがありません",
    "err_http_error": "サイトのエラー",
    "err_server_message": "サイトからのメッセージ",
    "err_bad_response": "サイトから想定外の応答",
    "err_not_media": "ファイルの代わりにウェブページが返りました",
    "err_file_error": "ファイルを書き込めません",
    "err_proxy_invalid": "プロキシのアドレスが正しくありません",
    "err_no_url": "ファイルのリンクがありません",
    "err_path_too_long": "ファイルのパスが長すぎます",
    "err_internal": "プログラム内部のエラー",
}

STRINGS = {"ru": RU, "en": EN, "zh": ZH, "ja": JA}


# ====================================================================== net: HTTP: сессия, прокси, классификация ошибок и повторы.

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 30


class BooruError(Exception):
    """code — ключ строки для перевода, detail — пояснение (уже без секретов)."""

    def __init__(self, code, detail="", retry_after=None):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
        self.retry_after = retry_after


class AuthError(BooruError):
    """Сайт отклонил ключ — повторять бессмысленно."""


class TransientError(BooruError):
    """Временный сбой — имеет смысл повторить."""

    # Нет связи вообще (сеть, прокси, DNS) — в отличие от ответа 5xx.
    @property
    def offline(self):
        return self.code in ("net_connection", "net_timeout", "net_proxy", "net_ssl")


class ApiError(BooruError):
    """Постоянная ошибка (404, непонятный ответ и т.п.)."""


class Cancelled(Exception):
    """Пользователь нажал «Стоп»."""


# ------------------------------------------------------------------ секреты

_SECRET_PARAM = re.compile(r"(api_key|pass_hash|password)=([^&\s'\"]+)", re.I)


class Redactor:
    """Вырезает ключи из любого текста, который может попасть в журнал."""

    def __init__(self):
        self._secrets = set()
        self._lock = threading.Lock()

    def add(self, *values):
        with self._lock:
            for v in values:
                if v and len(str(v)) >= 4:
                    self._secrets.add(str(v))

    def __call__(self, text):
        text = _SECRET_PARAM.sub(lambda m: f"{m.group(1)}=•••", str(text))
        with self._lock:
            for s in self._secrets:
                text = text.replace(s, "•••")
        return text


def strip_urls(text):
    """Оставляет от адресов только хост — в журнале не нужны параметры запросов."""
    def short(m):
        try:
            return urlsplit(m.group(0)).netloc or m.group(0)
        except ValueError:
            return "…"
    text = re.sub(r"https?://[^\s'\"<>)]+", short, str(text))
    return re.sub(r"(with url: )\S+", r"\1…", text)


# ------------------------------------------------------------------ сессия

def normalize_proxy(url):
    url = (url or "").strip()
    if url and "://" not in url:
        url = "http://" + url
    return url


def proxy_label(url):
    """Адрес прокси без логина и пароля — для журнала."""
    try:
        parts = urlsplit(url)
        return f"{parts.hostname}:{parts.port}" if parts.port else (parts.hostname or url)
    except ValueError:
        return "proxy"


def parse_proxy_list(text):
    out = []
    for line in (text or "").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if re.fullmatch(r"[\w.-]+:\d{2,5}", line):
            line = "http://" + line
        if re.match(r"^(https?|socks5h?|socks4a?)://", line, re.I):
            out.append(line)
    return list(dict.fromkeys(out))


def make_session(site, proxy_mode="auto", proxy_url="", pool=16):
    """proxy_mode: "auto"/"direct" — как настроено в Windows (в режиме auto
    поверх работает Router), "custom" — всё через указанный прокси."""
    s = requests.Session()
    adapter = HTTPAdapter(pool_connections=pool, pool_maxsize=pool, max_retries=0)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": site.site_url,
    })
    if proxy_mode == "custom":
        url = normalize_proxy(proxy_url)
        if url:
            s.trust_env = False
            s.proxies = {"http": url, "https": url}
    return s


class Route:
    def __init__(self, proxy=None):
        self.proxy = proxy

    @property
    def key(self):
        return self.proxy or "direct"

    @property
    def proxies(self):
        return {"http": self.proxy, "https": self.proxy} if self.proxy else None

    def timeout(self, timeout):
        # бесплатные прокси либо отвечают быстро, либо мертвы
        if self.proxy:
            return (min(timeout[0], 7), timeout[1])
        return timeout


DIRECT = Route()


class Router:
    """Обход блокировки: каждый сервер сначала пробуем напрямую, а если связи
    нет — через прокси из списка. Рабочий прокси и заблокированные серверы
    запоминаются, мёртвые прокси на время откладываются.

    Ключ API при этом не раскрывается: запросы идут по HTTPS через туннель
    (CONNECT), прокси видит только имя сервера.
    """

    BLOCK_TTL = 6 * 3600       # через 6 часов снова пробуем напрямую
    COOLDOWN = (120, 600, 1800)
    PROBE_BATCH = 10

    def __init__(self, enabled=True, pool=(), state=None, on_change=None, on_event=None):
        self.enabled = enabled
        self.pool = list(pool)
        state = state or {}
        now = time.time()
        self.blocked = {h: t for h, t in (state.get("blocked") or {}).items() if now - t < self.BLOCK_TTL}
        self.current = state.get("current") if state.get("current") in self.pool else None
        self.suspect = {}          # сервер → время, когда напрямую не вышло
        self.bad = {}              # прокси → (до какого времени не трогать, сколько раз падал)
        self.last_scan_fail = {}   # сервер → когда перебор прокси ничего не дал
        self.on_change = on_change
        self.on_event = on_event
        self.lock = threading.RLock()
        self.probe_lock = threading.Lock()

    def state(self):
        with self.lock:
            return {"blocked": dict(self.blocked), "current": self.current}

    def _changed(self):
        if self.on_change:
            try:
                self.on_change(self.state())
            except Exception:
                pass

    def _event(self, key, **params):
        if self.on_event:
            try:
                self.on_event(key, params)
            except Exception:
                pass

    def _usable(self, proxy, exclude):
        if proxy in exclude:
            return False
        until = self.bad.get(proxy, (0, 0))[0]
        return time.time() >= until

    def route(self, url, exclude=()):
        """Маршрут для запроса или None, если пробовать больше нечего."""
        if not self.enabled:
            return DIRECT if "direct" not in exclude else None
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        with self.lock:
            blocked = host in self.blocked and time.time() - self.blocked[host] < self.BLOCK_TTL
            if not blocked and "direct" not in exclude:
                return DIRECT
            if self.current and self._usable(self.current, exclude):
                return Route(self.current)
        proxy = self._find(host, f"{parts.scheme}://{parts.netloc}/", exclude)
        return Route(proxy) if proxy else None

    def _find(self, host, probe_url, exclude):
        """Параллельно проверяет прокси из списка и берёт первый ответивший."""
        with self.probe_lock:
            with self.lock:   # пока ждали, другой поток мог уже найти
                if self.current and self._usable(self.current, exclude):
                    return self.current
                if time.time() - self.last_scan_fail.get(host, 0) < 30:
                    return None
                candidates = [p for p in self.pool if self._usable(p, exclude)]
            if not candidates:
                return None
            self._event("route_probe", host=host, count=len(candidates))
            for i in range(0, len(candidates), self.PROBE_BATCH):
                found = probe_first(candidates[i:i + self.PROBE_BATCH], probe_url)
                if found:
                    with self.lock:
                        self.current = found
                        self.last_scan_fail.pop(host, None)
                    self._event("route_proxy", host=host, proxy=proxy_label(found))
                    self._changed()
                    return found
            # не ответил никто — скорее всего, пропал сам интернет; прокси не
            # отбраковываем, просто какое-то время не повторяем перебор
            with self.lock:
                self.last_scan_fail[host] = time.time()
            self._event("route_none", host=host)
            return None

    def _mark_bad(self, proxy):
        until, fails = self.bad.get(proxy, (0, 0))
        delay = self.COOLDOWN[min(fails, len(self.COOLDOWN) - 1)]
        self.bad[proxy] = (time.time() + delay, fails + 1)

    def failed(self, url, route):
        """Запрос по маршруту не прошёл (нет связи). True — стоит сразу попробовать другой."""
        if not self.enabled:
            return False
        host = (urlsplit(url).hostname or "").lower()
        with self.lock:
            if route.proxy is None:
                self.suspect[host] = time.time()
                return bool(self.pool)
            self._mark_bad(route.proxy)
            if self.current == route.proxy:
                self.current = None
                self._changed()
            return True

    def succeeded(self, url, route):
        if not self.enabled:
            return
        host = (urlsplit(url).hostname or "").lower()
        changed = False
        with self.lock:
            if route.proxy is None:
                self.suspect.pop(host, None)
                if self.blocked.pop(host, None):
                    changed = True
            else:
                self.bad.pop(route.proxy, None)
                if self.suspect.pop(host, None) and host not in self.blocked:
                    # напрямую не вышло, а через прокси получилось — значит, блокировка
                    self.blocked[host] = time.time()
                    changed = True
                    self._event("route_blocked", host=host, proxy=proxy_label(route.proxy))
                if self.current != route.proxy:
                    self.current = route.proxy
                    changed = True
        if changed:
            self._changed()

    def describe(self):
        with self.lock:
            return {"blocked": sorted(self.blocked), "current": proxy_label(self.current) if self.current else ""}


def probe(proxy, url, timeout=(6, 10)):
    """Время ответа через прокси в мс или None. Любой ответ по HTTPS настоящий:
    сертификат проверяется, подменить сайт прокси не может."""
    t0 = time.monotonic()
    try:
        with requests.get(url, proxies={"http": proxy, "https": proxy}, timeout=timeout,
                          headers={"User-Agent": USER_AGENT}, stream=True) as r:
            if r.status_code == 407:
                return None
        return round((time.monotonic() - t0) * 1000)
    except requests.RequestException:
        return None


def probe_first(proxies, url):
    """Проверяет прокси одновременно и возвращает первый ответивший.
    Потоки фоновые: опоздавшие проверки не задерживают закрытие программы."""
    if not proxies:
        return None
    results = queue.Queue()
    for p in proxies:
        threading.Thread(target=lambda p=p: results.put((p, probe(p, url))), daemon=True).start()
    for _ in proxies:
        p, ms = results.get()
        if ms is not None:
            return p
    return None


def probe_all(proxies, url, workers=24):
    """[(прокси, мс или None)] в исходном порядке."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(proxies) or 1))) as pool:
        return list(zip(proxies, pool.map(lambda p: probe(p, url), proxies)))


# ------------------------------------------------------------------ ошибки

def from_request_exception(exc, redact):
    detail = strip_urls(redact(exc))[:300]
    if isinstance(exc, requests.exceptions.ProxyError):
        return TransientError("net_proxy", detail)
    if isinstance(exc, requests.exceptions.SSLError):
        return TransientError("net_ssl", detail)
    if isinstance(exc, requests.exceptions.Timeout):
        return TransientError("net_timeout", detail)
    if isinstance(exc, requests.exceptions.ConnectionError):
        return TransientError("net_connection", detail)
    if isinstance(exc, (requests.exceptions.ChunkedEncodingError,
                        requests.exceptions.ContentDecodingError)):
        return TransientError("net_broken", detail)
    if isinstance(exc, requests.exceptions.InvalidProxyURL):
        return ApiError("proxy_invalid", detail)
    if isinstance(exc, requests.exceptions.InvalidSchema) and "socks" in str(exc).lower():
        return ApiError("proxy_invalid", detail)
    return TransientError("net_other", detail)


def _retry_after(response):
    value = response.headers.get("Retry-After", "")
    try:
        return max(0, min(int(value), 300))
    except ValueError:
        return None


def looks_like_cloudflare(response):
    server = response.headers.get("Server", "").lower()
    head = response.text[:2000].lower() if response.content else ""
    return "cloudflare" in server and ("challenge" in head or "attention required" in head
                                       or "just a moment" in head or "cf-" in head)


def check_status(response, auth_on_401=True):
    """Бросает подходящее исключение для неуспешного ответа."""
    code = response.status_code
    if code < 400:
        return
    if code in (401, 403):
        if code == 403 and looks_like_cloudflare(response):
            raise ApiError("blocked", f"HTTP {code}")
        if auth_on_401:
            raise AuthError("auth_http", f"HTTP {code}")
        raise ApiError("http_error", f"HTTP {code}")
    if code == 429:
        raise TransientError("rate_limited", "HTTP 429", retry_after=_retry_after(response))
    if code in (408, 425) or code >= 500:
        raise TransientError("server_busy", f"HTTP {code}", retry_after=_retry_after(response))
    if code == 404:
        raise ApiError("not_found", "HTTP 404")
    raise ApiError("http_error", f"HTTP {code}")


AUTH_WORDS = ("authentication", "unauthorized", "api key", "api_key", "credential",
              "access denied", "not authorized", "invalid user")


def classify_server_message(message):
    """Сообщение, которое прислал сам сайт (а не наш текст с адресом)."""
    msg = (message or "").strip()
    low = msg.lower()
    if any(w in low for w in AUTH_WORDS):
        return AuthError("auth_server", msg[:300])
    return ApiError("server_message", msg[:300])


# ------------------------------------------------------------------ повторы

API_DELAYS = (2, 4, 8, 15, 30, 60)
FILE_DELAYS = (2, 4, 8, 15, 30)


def call_with_retries(fn, stop_event, on_wait=None, delays=API_DELAYS,
                      max_attempts=None, max_offline_attempts=None):
    """Повторяет fn() при временных сбоях; пауза прерывается кнопкой «Стоп».

    max_attempts — предел для ответов сервера (5xx, 429 и т.п.);
    max_offline_attempts — предел, когда связи нет совсем (None — ждать,
    пока не появится сеть или пользователь не остановит загрузку).
    """
    attempt = 0
    while True:
        if stop_event.is_set():
            raise Cancelled()
        try:
            return fn()
        except TransientError as exc:
            attempt += 1
            limit = max_offline_attempts if exc.offline else max_attempts
            if limit is not None and attempt >= limit:
                raise
            delay = delays[min(attempt - 1, len(delays) - 1)]
            if exc.retry_after:
                delay = max(delay, exc.retry_after)
            if on_wait:
                on_wait(exc, attempt, delay)
            if stop_event.wait(delay):
                raise Cancelled()


# ====================================================================== storage: Настройки, история и хранение ключа.

DEFAULTS = {
    "language": "ru",
    "user_id": "",
    "api_key_enc": "",
    "output_dir": "",
    "proxy_mode": "auto",          # auto | direct | custom
    "proxy_url_enc": "",
    "proxy_pool": None,            # None — встроенный список
    "route_state": {},
    "threads": 3,
    "delay": 0.3,
    "name_template": "id",
    "split_by_type": True,
    "skip_existing": True,
    "media": "all",
    "rating": "",
    "limit": 100,
    "last_query": "",
    "geometry": "",
    "show_log": False,
    "no_ai": False,
    "account_name": "",
    "account_uid": "",
    "account_name_manual": "",
    "login_browser": "",
}

LANG_FROM_OLD = {"Русский": "ru", "English": "en", "中文": "zh", "日本語": "ja"}


def resource_path(name):
    """Файлы рядом с программой (работает и в собранном exe)."""
    here = os.path.dirname(os.path.abspath(__file__))
    bases = [getattr(sys, "_MEIPASS", None), os.path.dirname(os.path.abspath(sys.argv[0])),
             os.path.join(here, ".."), os.path.join(here, "..", "..", "assets")]
    for base in bases:
        if base and os.path.exists(os.path.join(base, name)):
            return os.path.abspath(os.path.join(base, name))
    return os.path.join(bases[1], name)


# Встроенные файлы (иконка, заставка, список прокси). В однофайловой версии программы
# они лежат прямо в коде (base64), в обычной — рядом с программой.
EMBEDDED = {}


def resource_bytes(name):
    if name in EMBEDDED:
        return base64.b64decode(EMBEDDED[name])
    try:
        with open(resource_path(name), "rb") as f:
            return f.read()
    except OSError:
        return b""


def builtin_proxies(site):
    return parse_proxy_list(resource_bytes(site.proxy_list).decode("utf-8", "replace"))


def data_dir(site):
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home())
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    p = base / site.data_dir
    p.mkdir(parents=True, exist_ok=True)
    return p


def default_output_dir(site):
    name = "Gelbooru" if site.key == "gelbooru" else "Rule34"
    return str(Path.home() / "Downloads" / name)


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ------------------------------------------------------------------ секреты

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    _crypt32 = ctypes.windll.crypt32
    _kernel32 = ctypes.windll.kernel32
    _crypt32.CryptProtectData.argtypes = [ctypes.POINTER(_Blob), wintypes.LPCWSTR, ctypes.POINTER(_Blob),
                                          ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
    _crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.POINTER(_Blob),
                                            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]

    def _dpapi(data, encrypt):
        buf = ctypes.create_string_buffer(data, len(data))
        inp = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        out = _Blob()
        if encrypt:
            ok = _crypt32.CryptProtectData(ctypes.byref(inp), "booru", None, None, None, 0x1, ctypes.byref(out))
        else:
            ok = _crypt32.CryptUnprotectData(ctypes.byref(inp), None, None, None, None, 0x1, ctypes.byref(out))
        if not ok:
            raise OSError("DPAPI error")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            _kernel32.LocalFree(out.pbData)


def protect(text):
    """Шифрует строку ключом текущего пользователя Windows (DPAPI)."""
    if not text:
        return ""
    raw = text.encode("utf-8")
    if os.name == "nt":
        try:
            return "dpapi:" + base64.b64encode(_dpapi(raw, True)).decode()
        except OSError:
            pass
    return "plain:" + base64.b64encode(raw).decode()


def unprotect(value):
    if not value:
        return ""
    kind, _, data = value.partition(":")
    try:
        raw = base64.b64decode(data)
        if kind == "dpapi" and os.name == "nt":
            raw = _dpapi(raw, False)
        elif kind != "plain":
            return ""
        return raw.decode("utf-8")
    except (OSError, ValueError):
        return ""


def parse_api_line(text):
    """Достаёт user_id и api_key из строки вида &api_key=…&user_id=…"""
    decoded = urllib.parse.unquote(text or "").strip()
    a = re.search(r"(?:^|[?&\s])api_key=([^&\s]+)", decoded, re.I)
    u = re.search(r"(?:^|[?&\s])user_id=(\d+)", decoded, re.I)
    return (u.group(1) if u else ""), (a.group(1).strip() if a else "")


# ------------------------------------------------------------------ настройки

class Config:
    def __init__(self, site):
        self.site = site
        self.path = data_dir(site) / "config.json"
        data = load_json(self.path, {})
        if not isinstance(data, dict):
            data = {}
        self.data = dict(DEFAULTS)
        self.data.update(data)
        self._migrate(data)
        if not self.data.get("output_dir"):
            self.data["output_dir"] = default_output_dir(site)

    def _migrate(self, old):
        """Старые версии хранили ключ открытым текстом в api_line."""
        changed = False
        line = old.get("api_line")
        if line:
            uid, key = parse_api_line(line)
            if uid and key and not self.data.get("api_key_enc"):
                self.data["user_id"] = uid
                self.data["api_key_enc"] = protect(key)
            self.data.pop("api_line", None)
            changed = True
        lang = old.get("language")
        if lang in LANG_FROM_OLD:
            self.data["language"] = LANG_FROM_OLD[lang]
            changed = True
        self.data.pop("last_downloaded_path", None)
        if self.data.get("proxy_mode") not in ("auto", "direct", "custom"):
            self.data["proxy_mode"] = "auto"
        if changed:
            self.save()

    def __getitem__(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self.data[key] = value

    def save(self):
        try:
            save_json(self.path, self.data)
        except OSError:
            pass

    @property
    def api_key(self):
        return unprotect(self.data.get("api_key_enc", ""))

    @api_key.setter
    def api_key(self, value):
        self.data["api_key_enc"] = protect(value.strip()) if value else ""

    def proxy_pool(self, site):
        pool = self.data.get("proxy_pool")
        if isinstance(pool, list):
            return [p for p in pool if isinstance(p, str)]
        return builtin_proxies(site)

    @property
    def proxy_url(self):
        return unprotect(self.data.get("proxy_url_enc", ""))

    @proxy_url.setter
    def proxy_url(self, value):
        self.data["proxy_url_enc"] = protect(value.strip()) if value else ""


# ------------------------------------------------------------------ история

class History:
    """Одна запись на поиск (теги + папка); повторные запуски её обновляют."""

    def __init__(self, site):
        self.path = data_dir(site) / "history.json"
        items = load_json(self.path, [])
        self.items = []
        for h in items if isinstance(items, list) else []:
            if not isinstance(h, dict):
                continue
            if "query" not in h and "tags" in h:      # формат старых версий
                h = {"query": h.get("tags", ""), "last_count": h.get("count", 0),
                     "total": h.get("count", 0), "date": h.get("date", ""), "output_dir": ""}
            self.items.append(h)

    def save(self):
        try:
            save_json(self.path, self.items[-500:])
        except OSError:
            pass

    def record(self, query, output_dir, folder, count, total, rating="", media="all"):
        for h in self.items:
            if h.get("query") == query and os.path.normcase(h.get("output_dir", "")) == os.path.normcase(output_dir):
                self.items.remove(h)
                break
        self.items.append({
            "query": query, "output_dir": output_dir, "folder": folder,
            "rating": rating, "media": media, "last_count": count, "total": total,
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        self.save()

    def remove(self, entry):
        if entry in self.items:
            self.items.remove(entry)
            self.save()


# ====================================================================== api: Клиент DAPI (Gelbooru и Rule34.xxx устроены одинаково).

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".avif"}
VIDEO_EXTS = {".mp4", ".webm", ".gif", ".mkv", ".mov"}


@dataclass
class Post:
    id: int
    file_url: str
    ext: str
    md5: str = ""
    tags: str = ""
    rating: str = ""
    score: str = ""
    width: int = 0
    height: int = 0
    preview_url: str = ""

    @property
    def is_video(self):
        return self.ext in VIDEO_EXTS

    def matches(self, media):
        if media == "images":
            return self.ext in IMAGE_EXTS
        if media == "videos":
            return self.ext in VIDEO_EXTS
        return self.ext in IMAGE_EXTS or self.ext in VIDEO_EXTS


def _to_int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _ext_of(*candidates):
    for c in candidates:
        if not c:
            continue
        c = str(c).strip().lower()
        if re.fullmatch(r"\.?[a-z0-9]{1,10}", c):
            ext = c if c.startswith(".") else "." + c
        else:
            ext = os.path.splitext(urllib.parse.urlsplit(c).path)[1].lower()
        if re.fullmatch(r"\.[a-z0-9]{1,10}", ext):
            return ext
    return ""


def _fix_url(url, site):
    url = str(url or "").strip()
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("http://") and site.force_https:
        url = "https://" + url[7:]       # оба сайта отдают файлы по HTTPS
    elif url and not url.startswith(("http://", "https://")):
        url = urllib.parse.urljoin(site.site_url, url)
    return url


def normalize_post(raw, site):
    pid = _to_int(raw.get("id"), -1)
    if pid < 0:
        return None
    url = _fix_url(raw.get("file_url"), site)
    return Post(
        id=pid,
        file_url=url,
        ext=_ext_of(url, raw.get("image"), raw.get("file_ext")),
        md5=str(raw.get("md5") or raw.get("hash") or "").strip().lower(),
        tags=str(raw.get("tags") or "").strip(),
        rating=str(raw.get("rating") or "").strip(),
        score=str(raw.get("score") or "").strip(),
        width=_to_int(raw.get("width")),
        height=_to_int(raw.get("height")),
        preview_url=_fix_url(raw.get("preview_url"), site),
    )


# ------------------------------------------------------------------ теги

# Типы тегов в DAPI: 0 — обычный, 1 — автор, 3 — откуда (копирайт), 4 — персонаж, 5/6 — служебные
TAG_KINDS = {"1": "artist", "3": "copyright", "4": "character", "5": "metadata", "6": "metadata"}


def tag_kind(value):
    v = str(value or "").strip().lower()
    if v in TAG_KINDS:
        return TAG_KINDS[v]
    if v in ("artist", "copyright", "character", "metadata"):
        return v
    return "metadata" if v == "meta" else "general"


def tags_from_input(text):
    """Принимает и теги через пробел, и ссылку со страницы поиска."""
    text = (text or "").strip()
    if not text:
        return ""
    if "://" in text or text.startswith(("index.php", "?")) or "tags=" in text:
        query = urllib.parse.urlsplit(text).query if "://" in text else text.split("?", 1)[-1]
        try:
            pairs = urllib.parse.parse_qsl(query, keep_blank_values=True, errors="replace")
        except ValueError:
            pairs = []
        values = [v for k, v in pairs if k.lower() == "tags"]
        if values:
            text = " ".join(values)
        elif "://" in text:
            return ""
    text = text.replace("+", " ") if " " not in text and "+" in text else text
    text = re.sub(r"\s+", " ", text).strip().strip("\\/").strip()
    return text


def has_custom_sort(tags):
    for t in tags.split():
        t = t.lower()
        if t.startswith("sort:") and t not in ("sort:id", "sort:id:desc"):
            return True
    return False


# ------------------------------------------------------------------ клиент

class Client:
    def __init__(self, site, session, user_id="", api_key="", redact=None, router=None):
        self.site = site
        self.session = session
        self.router = router
        self.user_id = str(user_id or "").strip()
        self.api_key = str(api_key or "").strip()
        self.redact = redact or Redactor()
        self.redact.add(self.api_key)

    # --- низкий уровень

    def _get(self, url, params=None, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), **kw):
        """GET с обходом блокировки: если напрямую нет связи, Router подставляет прокси."""
        router = self.router
        tried = set()
        first_error = None
        while True:
            route = router.route(url, tried) if router else DIRECT
            if route is None:
                raise first_error or TransientError("net_connection")
            try:
                r = self.session.get(url, params=params, timeout=route.timeout(timeout),
                                     proxies=route.proxies, **kw)
            except requests.RequestException as exc:
                err = from_request_exception(exc, self.redact)
                if not (router and isinstance(err, TransientError) and err.offline):
                    raise err from None
                first_error = first_error or err
                tried.add(route.key)
                if not router.failed(url, route) or len(tried) > 6:
                    raise first_error from None
                continue
            if router:
                router.succeeded(url, route)
            return r

    def _dapi(self, extra):
        params = {"page": "dapi", "s": "post", "q": "index"}
        params.update(extra)
        if self.user_id and self.api_key:
            params.update(user_id=self.user_id, api_key=self.api_key)
        r = self._get(self.site.api_url, params)
        check_status(r)
        return r.text.strip()

    # --- разбор ответов

    def _parse_xml(self, body):
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            snippet = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))[:200]
            raise ApiError("bad_response", snippet) from None
        tag = root.tag.lower()
        if tag == "error":
            raise classify_server_message(root.text or "")
        if tag == "response" and str(root.get("success", "")).lower() == "false":
            raise classify_server_message(root.get("reason") or root.text or "")
        elements = [root] if tag == "post" else root.findall(".//post")
        posts = []
        for el in elements:
            raw = dict(el.attrib)
            for child in el:
                raw.setdefault(child.tag, child.text or "")
            posts.append(raw)
        count = _to_int(root.get("count"), None) if tag == "posts" else None
        return posts, count

    def _parse(self, body):
        """Возвращает (сырые посты, общее число или None)."""
        try:
            data = json.loads(body)
        except ValueError:
            return self._parse_xml(body)
        if isinstance(data, str):
            raise classify_server_message(data)
        if isinstance(data, list):
            return [p for p in data if isinstance(p, dict)], None
        if isinstance(data, dict):
            if data.get("success") is False or str(data.get("success")).lower() == "false":
                raise classify_server_message(data.get("message") or data.get("reason") or "")
            attrs = data.get("@attributes") or {}
            count = _to_int(attrs.get("count"), None) if attrs else None
            posts = data.get("post", [])
            if isinstance(posts, dict):
                posts = [posts]
            return [p for p in posts if isinstance(p, dict)] if isinstance(posts, list) else [], count
        return [], None

    # --- публичные методы

    def posts(self, tags, limit, pid=0):
        """Одна страница постов: (list[Post], count|None)."""
        params = {"tags": tags, "limit": limit, "pid": pid}
        body = self._dapi(dict(params, json=1))
        if not body and self.site.xml_fallback:
            body = self._dapi(params)
        if not body:
            raise TransientError("empty_response")
        raw, count = self._parse(body)
        posts = [p for p in (normalize_post(r, self.site) for r in raw) if p]
        return posts, count

    def search(self, tags, limit, pid=0):
        """Страница поиска (pid — её номер с нуля) и общее число постов — для предпросмотра."""
        if self.site.count_via_xml:      # XML отдаёт и посты, и количество за один запрос
            body = self._dapi({"tags": tags, "limit": limit, "pid": pid})
            if not body:
                raise TransientError("empty_response")
            raw, count = self._parse_xml(body)
            return [p for p in (normalize_post(r, self.site) for r in raw) if p], count
        return self.posts(tags, limit, pid)

    TAG_BATCH = 80      # сайт отдаёт не больше 100 тегов за запрос — берём с запасом

    def tag_kinds(self, names, max_url=3000):
        """{тег: artist|character|copyright|metadata|general} — сайт отдаёт тип тега
        отдельным запросом (в самом посте теги идут одной строкой). Теги, которых
        в ответе нет, в результат не попадают — их уточняет tag_kind_lookup()."""
        names = [n for n in dict.fromkeys(names) if n]
        out = {}
        batch, size = [], 0
        for name in names + [None]:
            if (name is not None and len(batch) < self.TAG_BATCH
                    and size + len(urllib.parse.quote(name)) + 3 < max_url):
                batch.append(name)
                size += len(urllib.parse.quote(name)) + 3
                continue
            if batch:
                out.update(self._tag_batch(batch))
            batch, size = ([name], len(urllib.parse.quote(name)) + 3) if name is not None else ([], 0)
        return out

    def tag_kind_lookup(self, name):
        """Тип одного тега через подсказки сайта (работают и без ключа). None — не нашёлся."""
        for value, _count, category in self.autocomplete(name):
            if value == name:
                return tag_kind(category)
        return None

    def _tag_batch(self, batch, limit=100):
        params = {"s": "tag", "names": " ".join(batch), "limit": limit}
        if not self.site.count_via_xml:
            params["json"] = 1
        body = self._dapi(params)
        items = []
        if body:
            try:
                data = json.loads(body)
            except ValueError:
                data = None
            if data is None:
                try:
                    root = ET.fromstring(body)
                except ET.ParseError:
                    raise ApiError("bad_response", body[:120]) from None
                if root.tag.lower() == "error":
                    raise classify_server_message(root.text or "")
                items = [dict(el.attrib) for el in root.iter("tag")]
            elif isinstance(data, str):
                raise classify_server_message(data)
            elif isinstance(data, dict):
                items = data.get("tag") or []
                items = [items] if isinstance(items, dict) else items
            elif isinstance(data, list):
                items = data
        if len(items) >= limit and len(batch) > 1:
            # ответ обрезан пределом сайта — делим пачку пополам и спрашиваем заново
            half = len(batch) // 2
            out = self._tag_batch(batch[:half], limit)
            out.update(self._tag_batch(batch[half:], limit))
            return out
        wanted = set(batch)
        found = {str(i.get("name")): tag_kind(i.get("type")) for i in items
                 if isinstance(i, dict) and str(i.get("name")) in wanted}
        if items and not found:
            # сайт проигнорировал names= и вернул что-то своё — дальше не спрашиваем
            raise ApiError("tags_unsupported")
        return found

    def account_name(self):
        """Ник владельца ключа: со страницы профиля, иначе через API. "" — не удалось."""
        uid = self.user_id
        if not uid:
            return ""
        if self.site.profile_url:
            try:
                r = self._get(self.site.profile_url.format(id=uid), timeout=(8, 15))
                m = re.search(r"UsernameDisplay[^>]*>\s*([^<]+?)\s*(?:-\s*)?<", r.text)
                if r.status_code == 200 and m:
                    return html.unescape(m.group(1)).strip()
            except BooruError:
                pass
        try:
            body = self._dapi({"s": "user", "id": uid, "limit": 1})
            for m in re.finditer(r"<user\b([^>]*)>", body or ""):
                attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
                if attrs.get("id") == uid and attrs.get("name"):
                    return html.unescape(attrs["name"])
        except BooruError:
            pass
        return ""

    def fetch_bytes(self, url, limit=2_000_000, on_progress=None, stop_event=None):
        """Файл целиком в память (превью, просмотр арта). on_progress(получено, всего)."""
        r = self._get(url, timeout=(CONNECT_TIMEOUT, 30), stream=True)
        try:
            check_status(r, auth_on_401=False)
            total = _to_int(r.headers.get("Content-Length"), 0)
            chunks, size = [], 0
            for chunk in r.iter_content(64 * 1024):
                if stop_event is not None and stop_event.is_set():
                    raise Cancelled()
                chunks.append(chunk)
                size += len(chunk)
                if on_progress:
                    on_progress(size, total)
                if size > limit:
                    break
            return b"".join(chunks)
        except requests.RequestException as exc:
            raise from_request_exception(exc, self.redact) from None
        finally:
            r.close()

    def count(self, tags):
        if self.site.count_via_xml:
            body = self._dapi({"tags": tags, "limit": 1, "pid": 0})
            if not body:
                raise TransientError("empty_response")
            _, count = self._parse_xml(body)
            return count
        _, count = self.posts(tags, 1, 0)
        return count

    def check_key(self):
        """True — ключ принят. Бросает AuthError, если сайт его отклонил."""
        self.posts("", 1, 0)
        return True

    def autocomplete(self, term):
        """[(тег, число постов или None, категория)]"""
        term = term.strip()
        if not term:
            return []
        last_error = None
        for template in self.site.autocomplete_urls:
            url = template.format(term=urllib.parse.quote(term))
            try:
                r = self._get(url, timeout=(6, 10))
                check_status(r, auth_on_401=False)
                data = r.json()
            except (BooruError, ValueError) as exc:
                last_error = exc
                continue
            out = []
            for item in data if isinstance(data, list) else []:
                if not isinstance(item, dict):
                    continue
                value = str(item.get("value") or "").strip()
                if not value:
                    continue
                count = item.get("post_count")
                if count is None:
                    m = re.search(r"\((\d+)\)\s*$", str(item.get("label") or ""))
                    count = m.group(1) if m else None
                out.append((value, _to_int(count, None), str(item.get("category") or item.get("type") or "")))
            return out
        if last_error:
            raise last_error
        return []

    # --- файлы

    def download(self, post, path, stop_event, on_bytes=None, register=None):
        """Скачивает файл через .part. Возвращает (размер в байтах, md5)."""
        tmp = path + ".part"
        r = self._get(post.file_url, stream=True, timeout=(CONNECT_TIMEOUT, 20))
        if register:
            register(r)
        try:
            check_status(r, auth_on_401=False)
            ctype = r.headers.get("Content-Type", "").lower()
            if "text/html" in ctype or "application/json" in ctype:
                raise ApiError("not_media", ctype.split(";")[0])
            expected = _to_int(r.headers.get("Content-Length"), 0)
            size = 0
            md5 = hashlib.md5()
            try:
                with open(tmp, "wb") as f:
                    chunks = r.iter_content(64 * 1024)
                    while True:
                        try:
                            chunk = next(chunks)
                        except StopIteration:
                            break
                        except requests.RequestException as exc:
                            if stop_event.is_set():
                                raise Cancelled() from None
                            raise from_request_exception(exc, self.redact) from None
                        except Exception as exc:
                            # соединение закрыто кнопкой «Стоп» из другого потока
                            if stop_event.is_set():
                                raise Cancelled() from None
                            raise TransientError("net_broken", str(exc)[:200]) from None
                        if stop_event.is_set():
                            raise Cancelled()
                        if chunk:
                            f.write(chunk)
                            md5.update(chunk)
                            size += len(chunk)
                            if on_bytes:
                                on_bytes(len(chunk))
            except OSError as exc:
                raise ApiError("file_error", str(exc)[:200]) from None
            if size == 0:
                raise TransientError("empty_file")
            if expected and size != expected and "content-encoding" not in r.headers:
                raise TransientError("incomplete", f"{size}/{expected}")
            os.replace(tmp, path)
            return size, md5.hexdigest()
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
        finally:
            r.close()
            if register:
                register(r, remove=True)


# ====================================================================== engine: Задача скачивания: обход страниц API, параллельная загрузка, докачка.

TASK_FILE = ".booru_task.json"     # контрольная точка для «Продолжить»
IDS_FILE = ".booru_ids.txt"        # номера уже скачанных постов
FAILED_FILE = "failed_links.txt"
IMAGES_DIR = "Картинки"
VIDEOS_DIR = "Видео и анимации"
MAX_PATH = 240                     # запас до лимита Windows в 260 символов
API_MIN_INTERVAL = 1.0             # не чаще одного запроса к API в секунду
TEMPLATES = ("id", "tags_id", "tags_seq", "md5")


def safe_name(text, max_len=80):
    name = re.sub(r"\s+", "_", (text or "").strip())
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip(" .")
    if re.fullmatch(r"(?i)(con|prn|aux|nul|com\d|lpt\d)(\..*)?", name):
        name = "_" + name
    if len(name) > max_len:
        digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
        name = name[: max_len - 9].rstrip(" ._") + "_" + digest
    return name


def seq_prefix(query):
    """Префикс имён «теги_0001» — как в старых версиях программы."""
    return re.sub(r"[^\w -]+", "", query, flags=re.UNICODE).strip().replace(" ", "_")[:60] or "post"


@dataclass
class JobSpec:
    query: str
    output_dir: str
    rating: str = ""
    media: str = "all"            # all | images | videos
    limit: int = 0                # 0 — без ограничения
    name_template: str = "id"
    split_by_type: bool = True
    skip_existing: bool = True
    update_only: bool = False     # только посты новее уже скачанных
    exclude: tuple = ()           # теги, которые исключить (фильтр «Без ИИ-артов»)
    threads: int = 3
    delay: float = 0.3

    @classmethod
    def from_dict(cls, data):
        names = {f.name for f in fields(cls)}
        spec = cls(**{k: v for k, v in (data or {}).items() if k in names})
        spec.exclude = tuple(spec.exclude or ())      # из JSON приходит списком
        return spec

    @property
    def search_tags(self):
        parts = [self.query] if self.query else []
        if self.rating and not re.search(r"(?i)(^|\s)-?rating:", self.query):
            parts.append(f"rating:{self.rating}")
        have = set(self.query.split())
        parts += [f"-{tag}" for tag in self.exclude if f"-{tag}" not in have]
        return " ".join(parts)

    @property
    def folder_name(self):
        return safe_name(self.query or f"rating_{self.rating}", 80) or "posts"

    @property
    def folder(self):
        return os.path.join(self.output_dir, self.folder_name)


def task_path(spec):
    return os.path.join(spec.folder, TASK_FILE)


def load_task(spec):
    state = load_json(task_path(spec), None)
    if isinstance(state, dict) and state.get("version") == 2:
        return state
    return None


def downloaded_ids(folder):
    ids = set()
    try:
        with open(os.path.join(folder, IDS_FILE), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.isdigit():
                    ids.add(int(line))
    except OSError:
        pass
    return ids


def file_path(spec, post):
    """Куда ляжет файл поста (так же называет файлы и массовая загрузка)."""
    folder = spec.folder
    if spec.split_by_type:
        folder = os.path.join(folder, VIDEOS_DIR if post.is_video else IMAGES_DIR)
    return os.path.join(folder, f"{post.id}{post.ext}")


def mark_downloaded(folder, post_id):
    """Запомнить, что пост скачан, — массовая загрузка его потом пропустит."""
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, IDS_FILE), "a", encoding="utf-8") as f:
        f.write(f"{post_id}\n")


class Job:
    def __init__(self, site, spec, client, emit, resume_state=None):
        self.site = site
        self.spec = spec
        self.client = client
        self.emit = emit
        self.resume_state = resume_state
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.ids_lock = threading.Lock()
        self.thread = None
        self.stats = dict(downloaded=0, skipped=0, failed=0, filtered=0, processed=0,
                          bytes=0, inflight=0, found=None, pages=0, no_url=0)
        self.status = ("status_starting", {})
        self.wait_info = None
        self.failures = []
        self.responses = set()
        self.started_at = time.monotonic()
        self.outcome = None
        self._last_api = 0.0
        self._last_start = 0.0
        self._seq = 0

    # ---------------------------------------------------------- управление

    def start(self):
        self.thread = threading.Thread(target=self._run, name="booru-job", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        with self.lock:
            responses = list(self.responses)
        for r in responses:      # обрываем зависшие скачивания сразу
            try:
                r.close()
            except Exception:
                pass

    def is_running(self):
        return bool(self.thread and self.thread.is_alive())

    def snapshot(self):
        with self.lock:
            snap = dict(self.stats)
            snap["status"] = self.status
            snap["wait"] = dict(self.wait_info) if self.wait_info else None
        snap["elapsed"] = time.monotonic() - self.started_at
        snap["limit"] = self.spec.limit
        return snap

    # ---------------------------------------------------------- служебное

    def _log(self, key, level="info", **params):
        self.emit("log", key=key, level=level, params=params)

    def _set_status(self, key, **params):
        with self.lock:
            self.status = (key, params)

    def _register(self, response, remove=False):
        with self.lock:
            if remove:
                self.responses.discard(response)
            else:
                self.responses.add(response)
        if not remove and self.stop_event.is_set():
            response.close()

    def _add_bytes(self, n):
        with self.lock:
            self.stats["bytes"] += n

    def _bump(self, key, n=1):
        with self.lock:
            self.stats[key] += n

    def _sleep(self, seconds):
        if seconds > 0 and self.stop_event.wait(seconds):
            raise Cancelled()

    def _mark_done(self, post_id):
        with self.ids_lock:
            if post_id in self.done_ids:
                return
            self.done_ids.add(post_id)
            try:
                with open(self.ids_path, "a", encoding="utf-8") as f:
                    f.write(f"{post_id}\n")
            except OSError:
                pass

    def _on_api_wait(self, exc, attempt, delay):
        with self.lock:
            self.wait_info = {"code": exc.code, "detail": exc.detail, "attempt": attempt,
                              "until": time.monotonic() + delay, "offline": exc.offline}
        self._log("log_api_retry", "warn", code=exc.code, detail=exc.detail, attempt=attempt, delay=delay)

    def _api(self, fn):
        """Вызов API: пауза между запросами и повторы при сбоях."""
        def call():
            self._sleep(API_MIN_INTERVAL - (time.monotonic() - self._last_api))
            self._last_api = time.monotonic()
            return fn()
        try:
            return call_with_retries(call, self.stop_event, self._on_api_wait,
                                         delays=API_DELAYS, max_attempts=8,
                                         max_offline_attempts=None)
        finally:
            with self.lock:
                self.wait_info = None

    # ---------------------------------------------------------- основной цикл

    def _run(self):
        err = None
        try:
            self._prepare()
            self._loop()
            outcome = "stopped" if self.stop_event.is_set() else "done"
        except Cancelled:
            outcome = "stopped"
        except AuthError as exc:
            outcome, err = "auth", exc
        except TransientError as exc:
            outcome, err = "paused", exc
        except BooruError as exc:
            outcome, err = "error", exc
        except Exception as exc:
            outcome = "error"
            err = ApiError("internal", self.client.redact(f"{type(exc).__name__}: {exc}"))
            self._write_crash_log()
        self._finish(outcome, err)

    def _prepare(self):
        spec = self.spec
        self.folder = spec.folder
        os.makedirs(self.folder, exist_ok=True)
        self.ids_path = os.path.join(self.folder, IDS_FILE)
        self.task_path = task_path(spec)
        self.done_ids = downloaded_ids(self.folder)
        state = self.resume_state

        if state:
            self.tags = state.get("tags", spec.search_tags)
            self.mode = state.get("mode", "cursor")
            self.cursor = state.get("cursor")
            self.pid = int(state.get("pid", 0) or 0)
            for k in ("downloaded", "skipped", "failed", "filtered", "processed", "bytes", "pages", "no_url"):
                self.stats[k] = int(state.get("stats", {}).get(k, 0) or 0)
            self.stats["found"] = state.get("found")
            self._log("log_resume", downloaded=self.stats["downloaded"])
        else:
            tags = spec.search_tags
            if spec.update_only:
                if self.done_ids:
                    floor = max(self.done_ids)
                    tags = f"{tags} id:>{floor}".strip()
                    self._log("log_update_from", id=floor)
                else:
                    self._log("log_update_none")
            self.tags = tags
            self.mode = "pid" if has_custom_sort(tags) else "cursor"
            self.cursor = None
            self.pid = 0

        self._log("log_query", tags=self.tags or "—", folder=self.folder)
        if spec.name_template == "tags_seq":
            self._init_seq()

        if self.stats["found"] is None:
            self._set_status("status_counting")
            try:
                found = self._api(lambda: self.client.count(self.tags))
            except AuthError:
                raise
            except BooruError as exc:
                found = None
                self._log("log_count_failed", "warn", code=exc.code, detail=exc.detail)
            with self.lock:
                self.stats["found"] = found
        if self.stats["found"] is not None:
            self._log("log_found", count=self.stats["found"])
        self._save_task()

    def _loop(self):
        spec = self.spec
        page_size = self.site.page_size
        self.seen = set()
        fell_back = False
        workers = max(1, min(int(spec.threads or 1), 8))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="dl") as pool:
            self.pool = pool
            while not self.stop_event.is_set():
                if spec.limit and self.stats["downloaded"] >= spec.limit:
                    break
                page_tags = self.tags
                if self.mode == "cursor" and self.cursor:
                    page_tags = f"{page_tags} id:<{self.cursor}".strip()
                pid = self.pid if self.mode == "pid" else 0
                self._set_status("status_page", page=self.stats["pages"] + 1)
                posts, _ = self._api(lambda: self.client.posts(page_tags, page_size, pid))
                if not posts:
                    break
                fresh = [p for p in posts if p.id not in self.seen]
                if not fresh:
                    if self.mode == "cursor" and not fell_back:
                        # сайт проигнорировал id:< — листаем по номерам страниц
                        self._log("log_cursor_fallback", "warn")
                        self.mode, self.pid, fell_back = "pid", self.stats["pages"], True
                        continue
                    break
                self._bump("pages")
                self._log("log_page", page=self.stats["pages"], count=len(posts))
                complete, last_id = self._process_page(fresh, workers)
                if self.stop_event.is_set():
                    break
                if complete:
                    if self.mode == "cursor":
                        self.cursor = min(p.id for p in posts)
                    else:
                        self.pid += 1
                elif self.mode == "cursor" and last_id is not None:
                    self.cursor = last_id
                self._save_task()
                if complete and len(posts) < page_size:
                    break

    def _process_page(self, posts, workers):
        spec = self.spec
        futures = set()
        complete = True
        last_id = None
        self._set_status("status_downloading")
        for post in posts:
            if self.stop_event.is_set():
                complete = False
                break
            with self.lock:
                reserved = self.stats["downloaded"] + self.stats["inflight"]
            if spec.limit and reserved >= spec.limit:
                complete = False
                break
            last_id = post.id
            self.seen.add(post.id)
            self._bump("processed")
            if not post.file_url:
                self._bump("failed")
                self._bump("no_url")      # обычно из-за настроек аккаунта на сайте
                self.failures.append((post, "no_url", ""))
                self._log("log_no_url", "warn", id=post.id)
                continue
            if not post.matches(spec.media):
                self._bump("filtered")
                continue
            if spec.skip_existing and post.id in self.done_ids:
                self._bump("skipped")
                continue
            path = self._target_path(post)
            if path is None:
                continue
            if spec.skip_existing and os.path.exists(path):
                self._bump("skipped")
                self._mark_done(post.id)
                continue
            while len(futures) >= workers:
                _, futures = wait(futures, timeout=0.5, return_when=FIRST_COMPLETED)
                if self.stop_event.is_set():
                    break
            if self.stop_event.is_set():
                complete = False
                break
            self._sleep(spec.delay - (time.monotonic() - self._last_start))
            self._last_start = time.monotonic()
            with self.lock:
                self.stats["inflight"] += 1
            futures.add(self.pool.submit(self._download_one, post, path))
        while futures:
            _, futures = wait(futures, timeout=0.5)
        return complete, last_id

    # ---------------------------------------------------------- файлы

    def _init_seq(self):
        prefix = seq_prefix(self.spec.query)
        pattern = re.compile(re.escape(prefix) + r"_(\d+)\.")
        top = 0
        for sub in (IMAGES_DIR, VIDEOS_DIR, ""):
            try:
                for entry in os.scandir(os.path.join(self.folder, sub)):
                    m = pattern.match(entry.name)
                    if m:
                        top = max(top, int(m.group(1)))
            except OSError:
                pass
        self._seq = top

    def _target_path(self, post):
        spec = self.spec
        folder = self.folder
        if spec.split_by_type:
            folder = os.path.join(folder, VIDEOS_DIR if post.is_video else IMAGES_DIR)
        template = spec.name_template if spec.name_template in TEMPLATES else "id"
        if template == "tags_id":
            name = f"{safe_name(spec.query, 60) or 'post'}_{post.id}"
        elif template == "tags_seq":
            self._seq += 1
            name = f"{seq_prefix(spec.query)}_{self._seq:04d}"
        elif template == "md5" and re.fullmatch(r"[0-9a-f]{32}", post.md5):
            name = post.md5
        else:
            name = str(post.id)
        path = os.path.join(folder, name + post.ext)
        if len(os.path.abspath(path)) > MAX_PATH:
            path = os.path.join(folder, f"{post.id}{post.ext}")
            self._log("log_long_path", "warn", id=post.id)
            if len(os.path.abspath(path)) > MAX_PATH:
                self._bump("failed")
                self.failures.append((post, "path_too_long", ""))
                return None
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            raise ApiError("file_error", str(exc)[:200]) from None
        return path

    def _download_one(self, post, path):
        def on_wait(exc, attempt, delay):
            self._log("log_file_retry", "warn", id=post.id, code=exc.code,
                      detail=exc.detail, attempt=attempt, delay=delay)
        try:
            if self.stop_event.is_set():
                return
            size, _md5 = call_with_retries(
                lambda: self.client.download(post, path, self.stop_event, self._add_bytes, self._register),
                self.stop_event, on_wait, delays=FILE_DELAYS,
                max_attempts=4, max_offline_attempts=12)
            self._mark_done(post.id)
            self._bump("downloaded")
            self.emit("file", path=path, post_id=post.id, is_video=post.is_video, size=size)
            self._log("log_file_ok", "ok", name=os.path.basename(path), size=size)
        except Cancelled:
            pass
        except BooruError as exc:
            self._bump("failed")
            self.failures.append((post, exc.code, exc.detail))
            self._log("log_file_fail", "error", id=post.id, code=exc.code, detail=exc.detail)
        except Exception as exc:
            self._bump("failed")
            detail = self.client.redact(f"{type(exc).__name__}: {exc}")[:200]
            self.failures.append((post, "internal", detail))
            self._log("log_file_fail", "error", id=post.id, code="internal", detail=detail)
        finally:
            with self.lock:
                self.stats["inflight"] -= 1

    # ---------------------------------------------------------- сохранение

    def _save_task(self):
        with self.lock:
            stats = {k: self.stats[k] for k in ("downloaded", "skipped", "failed", "filtered",
                                                "processed", "bytes", "pages", "no_url")}
            found = self.stats["found"]
        state = {
            "version": 2, "site": self.site.key, "spec": asdict(self.spec),
            "tags": self.tags, "mode": self.mode, "cursor": self.cursor, "pid": self.pid,
            "stats": stats, "found": found, "updated_at": time.time(),
        }
        try:
            save_json(self.task_path, state)
        except OSError:
            pass

    def _write_failures(self):
        if not self.failures:
            return
        path = os.path.join(self.folder, FAILED_FILE)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} · {self.tags} ---\n")
                for post, code, detail in self.failures:
                    f.write(f"{post.id}; {self.site.post_url.format(id=post.id)}; "
                            f"{post.file_url or '-'}; {code}{' ' + detail if detail else ''}\n")
            self._log("log_failed_saved", "warn", path=path)
        except OSError:
            pass

    def _write_crash_log(self):
        try:
            log = data_dir(self.site) / "error.log"
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                f.write(self.client.redact(traceback.format_exc()))
        except OSError:
            pass

    def _finish(self, outcome, err):
        self.outcome = outcome
        folder = getattr(self, "folder", self.spec.folder)
        if hasattr(self, "task_path"):
            if outcome == "done":
                try:
                    os.remove(self.task_path)
                except OSError:
                    pass
            elif hasattr(self, "tags"):
                self._save_task()
        if hasattr(self, "folder"):
            self._write_failures()
        self._set_status("status_" + outcome)
        snap = self.snapshot()
        self.emit("finished", outcome=outcome,
                  code=err.code if err else "", detail=err.detail if err else "",
                  stats=snap, folder=folder,
                  total=len(getattr(self, "done_ids", ())))


# ====================================================================== theme: Тёмная тема в стиле старых версий (цвета фона и карточек сохранены).

BG = "#10131a"
PANEL = "#191e29"
PANEL2 = "#202736"
FIELD = "#11151d"
BORDER = "#2c3445"
BORDER_HI = "#465166"
TEXT = "#f3f4f6"
MUTED = "#9ca3af"
DIM = "#6b7486"
RED = "#ef4444"
GREEN = "#22c55e"
YELLOW = "#f59e0b"


def palette(site):
    p = QPalette()
    p.setColor(QPalette.Window, QColor(BG))
    p.setColor(QPalette.WindowText, QColor(TEXT))
    p.setColor(QPalette.Base, QColor(FIELD))
    p.setColor(QPalette.AlternateBase, QColor(PANEL))
    p.setColor(QPalette.Text, QColor(TEXT))
    p.setColor(QPalette.Button, QColor(PANEL2))
    p.setColor(QPalette.ButtonText, QColor(TEXT))
    p.setColor(QPalette.Highlight, QColor(site.accent))
    p.setColor(QPalette.HighlightedText, QColor(site.accent_text))
    p.setColor(QPalette.ToolTipBase, QColor(PANEL2))
    p.setColor(QPalette.ToolTipText, QColor(TEXT))
    p.setColor(QPalette.PlaceholderText, QColor(DIM))
    p.setColor(QPalette.Link, QColor(site.accent))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(DIM))
    return p


def stylesheet(site):
    a, ah, at = site.accent, site.accent_hover, site.accent_text
    return f"""
QWidget {{ color: {TEXT}; font-size: 10pt; }}
QMainWindow, QWidget#root {{ background: {BG}; }}
QToolTip {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER_HI}; padding: 4px 6px; }}

QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 14px; }}
QLabel#cardTitle {{ font-size: 11.5pt; font-weight: 600; }}
QLabel#appTitle {{ font-size: 17pt; font-weight: 700; }}
QLabel#logo {{ background: {a}; color: {at}; border-radius: 12px; font-size: 18pt; font-weight: 800; }}
QLabel#muted, QCheckBox#muted {{ color: {MUTED}; }}
QLabel#hint {{ color: {MUTED}; font-size: 9pt; }}
QLabel#found {{ color: {a}; font-weight: 600; }}
QLabel#error {{ color: {RED}; }}
QLabel#ok {{ color: {GREEN}; }}
QLabel#warn {{ color: {YELLOW}; }}
QLabel#banner {{ background: #3b1d22; color: #fecaca; border: 1px solid #7f1d1d; border-radius: 10px; padding: 8px 12px; }}
QLabel#preview {{ background: {FIELD}; border: 1px solid {BORDER}; border-radius: 12px; color: {DIM}; }}
QLabel#author {{ color: {a}; font-weight: 700; }}
QLabel#postInfo {{ background: {FIELD}; border: 1px solid {BORDER}; border-radius: 10px; padding: 6px 10px; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
    background: {FIELD}; border: 1px solid {BORDER_HI}; border-radius: 9px;
    padding: 6px 9px; selection-background-color: {a}; selection-color: {at};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color: {a}; }}
QLineEdit[error="true"] {{ border: 2px solid {RED}; }}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{ color: {DIM}; border-color: {BORDER}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {PANEL2}; border: 1px solid {BORDER_HI}; selection-background-color: {a}; selection-color: {at}; outline: 0; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 18px; border: none; }}

QPushButton {{ background: {PANEL2}; border: 1px solid {BORDER_HI}; border-radius: 10px; padding: 7px 14px; }}
QPushButton:hover {{ background: #2a3346; }}
QPushButton:pressed {{ background: #323c52; }}
QPushButton:disabled {{ color: {DIM}; background: #161b25; border-color: {BORDER}; }}
QPushButton#primary {{ background: {a}; color: {at}; border: none; font-weight: 700; font-size: 11pt; padding: 10px 18px; }}
QPushButton#primary:hover {{ background: {ah}; }}
QPushButton#primary:disabled {{ background: #2b3243; color: {DIM}; }}
QPushButton#resume {{ background: #16805d; border: none; color: white; font-weight: 600; }}
QPushButton#resume:hover {{ background: #1a9a70; }}
QPushButton#resume:disabled {{ background: #161b25; color: {DIM}; border: 1px solid {BORDER}; }}
QPushButton#stop:enabled {{ background: #4a2026; border-color: #7f1d1d; }}
QPushButton#stop:enabled:hover {{ background: #5c2830; }}
QPushButton#seg {{ padding: 6px 12px; }}
QPushButton#seg:checked {{ background: {a}; color: {at}; border-color: {a}; font-weight: 600; }}
QPushButton#seg:disabled:checked {{ background: #2b3243; color: {MUTED}; }}
QPushButton#link {{ background: transparent; border: none; color: {a}; padding: 2px 4px; text-align: left; }}
QPushButton#link:hover {{ text-decoration: underline; }}
QToolButton {{ background: transparent; border: none; padding: 2px; }}

QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}
QCheckBox::indicator {{ border: 1px solid {BORDER_HI}; border-radius: 4px; background: {FIELD}; }}
QCheckBox::indicator:checked {{ background: {a}; border-color: {a}; }}
QRadioButton::indicator {{ border: 1px solid {BORDER_HI}; border-radius: 8px; background: {FIELD}; }}
QRadioButton::indicator:checked {{ background: {a}; border: 1px solid {a}; }}

QProgressBar {{ background: {FIELD}; border: 1px solid {BORDER}; border-radius: 8px; height: 18px; text-align: center; color: {TEXT}; }}
QProgressBar::chunk {{ background: {a}; border-radius: 7px; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: {PANEL}; color: {MUTED}; padding: 8px 18px; margin-right: 4px; border-radius: 9px; border: 1px solid {BORDER}; }}
QTabBar::tab:selected {{ background: {a}; color: {at}; border-color: {a}; font-weight: 600; }}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}

QListWidget, QTableWidget {{ background: {FIELD}; border: 1px solid {BORDER}; border-radius: 10px; outline: 0; }}
QListWidget::item {{ border-radius: 8px; }}
QListWidget::item:selected {{ background: {PANEL2}; border: 2px solid {a}; }}
QTableWidget {{ gridline-color: {BORDER}; selection-background-color: {PANEL2}; selection-color: {TEXT}; }}
QTableWidget::item {{ padding: 4px 6px; }}
QTableWidget::item:selected {{ background: {PANEL2}; color: {TEXT}; }}
QHeaderView::section {{ background: {PANEL}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER}; padding: 6px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER_HI}; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDER_HI}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QStatusBar {{ background: {BG}; color: {MUTED}; }}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background: transparent; }}
QMenu {{ background: {PANEL2}; border: 1px solid {BORDER_HI}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {a}; color: {at}; }}
"""


# ====================================================================== browser: Вход на сайт через установленный браузер (Edge, Chrome, Яндекс, Opera, Brave, Vivaldi).

# Общие помощники для скриптов на странице: найти элемент управления по name или по подписи
_HELPERS = r"""
const norm = s => (s || '').replace(/\s+/g, ' ').trim().toLowerCase();
const near = phrase => {
  phrase = phrase.toLowerCase();
  if (!document.body) return null;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!norm(node.nodeValue).includes(phrase)) continue;
    let el = node.parentElement;
    for (let i = 0; i < 4 && el; i++, el = el.parentElement) {
      const list = Array.from(el.querySelectorAll('input[type=checkbox], select'));
      const after = list.find(c => node.compareDocumentPosition(c) & Node.DOCUMENT_POSITION_FOLLOWING);
      if (after) return after;
    }
  }
  return null;
};
const byName = n => document.querySelector('input[name="' + n + '"]');
const fringe = () => byName('fringeBenefits') || near('display all site content');
const original = () => byName('show_sample') || near('always show original');
const generate = () => {
  const text = document.body ? norm(document.body.innerText) : '';
  return near('generate new key') || near('generate api key') || near('generate a new key')
      || (text.includes('api access') ? near('generate') : null);
};
const isOn = c => !c ? null : (c.type === 'checkbox' ? c.checked : /^(1|yes|on|true)$/i.test(c.value));
"""

ANALYZE_JS = "(() => {" + _HELPERS + r"""
  const fields = Array.from(document.querySelectorAll('textarea, input[type=text], input:not([type])'))
                      .map(e => e.value || e.textContent || '');
  const text = (document.body ? document.body.innerText : '') + '\n' + fields.join('\n');
  let m = text.match(/api_key=([A-Za-z0-9]{6,})&(?:amp;)?user_id=(\d+)/i);
  let key = m ? m[1] : '', uid = m ? m[2] : '';
  if (!key) {   // отдельными полями: «API Key: …», «User ID: …»
    const k = text.match(/api[\s_-]*key\W{0,8}([A-Fa-f0-9]{24,})/i);
    const u = text.match(/user[\s_-]*id\W{0,8}(\d+)/i);
    if (k && u) { key = k[1]; uid = u[1]; }
  }
  return JSON.stringify({key: key, uid: uid, fringe: isOn(fringe()), original: isOn(original()),
                         generate: !!generate(), password: !!document.querySelector('input[type=password]')});
})()"""

APPLY_JS = "((wantSettings, wantGenerate) => {" + _HELPERS + r"""
  const turnOn = c => {
    if (!c || isOn(c)) return false;
    if (c.type === 'checkbox') { c.click(); return true; }
    const opt = Array.from(c.options || []).find(o => /^(1|yes|on|true)$/i.test(o.value) || /yes|on/i.test(o.text));
    if (!opt) return false;
    c.value = opt.value; c.dispatchEvent(new Event('change', {bubbles: true})); return true;
  };
  let changed = 0, form = null;
  const take = c => { if (turnOn(c)) { changed++; form = form || c.form; } };
  if (wantSettings) { take(fringe()); take(original()); }
  if (wantGenerate) take(generate());
  if (changed && form) {
    const btn = form.querySelector('input[type=submit], button[type=submit], button:not([type])');
    if (btn) btn.click(); else form.submit();
  }
  return JSON.stringify({changed: changed, submitted: !!(changed && form)});
})(%s, %s)"""



# ------------------------------------------------------------------ поиск браузера

CHROMIUM_EXES = {"msedge.exe": "Microsoft Edge", "chrome.exe": "Google Chrome", "browser.exe": "Яндекс.Браузер",
                 "brave.exe": "Brave", "vivaldi.exe": "Vivaldi", "opera.exe": "Opera", "launcher.exe": "Opera",
                 "chromium.exe": "Chromium"}
WINDOWS_PATHS = (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
                 r"Yandex\YandexBrowser\Application\browser.exe", r"BraveSoftware\Brave-Browser\Application\brave.exe",
                 r"Vivaldi\Application\vivaldi.exe", r"Programs\Opera\launcher.exe", r"Opera\launcher.exe",
                 r"Chromium\Application\chrome.exe")
UNIX_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge",
              "brave-browser", "vivaldi", "yandex-browser")


def _registry(root, path, value=""):
    try:
        import winreg
        with winreg.OpenKey(getattr(winreg, root), path) as key:
            return winreg.QueryValueEx(key, value)[0]
    except OSError:
        return ""


def _default_browser_exe():
    progid = _registry("HKEY_CURRENT_USER", r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations"
                       r"\https\UserChoice", "ProgId")
    cmd = _registry("HKEY_CLASSES_ROOT", progid + r"\shell\open\command") if progid else ""
    if not cmd:
        return ""
    return cmd.split('"')[1] if cmd.startswith('"') else cmd.split(" ")[0]


def find_browsers():
    """[(путь, название)] браузеров на Chromium — первым браузер по умолчанию."""
    found = []

    def add(path, name=None):
        if not path or not os.path.isfile(path):
            return
        name = name or CHROMIUM_EXES.get(os.path.basename(path).lower())
        if name and all(os.path.normcase(p) != os.path.normcase(path) for p, _ in found):
            found.append((path, name))

    if os.name == "nt":
        add(_default_browser_exe())
        roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")]
        for root in filter(None, roots):
            for rel in WINDOWS_PATHS:
                add(os.path.join(root, rel))
        for exe in ("msedge.exe", "chrome.exe"):
            add(_registry("HKEY_LOCAL_MACHINE", r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths" + "\\" + exe))
    else:
        for name in UNIX_NAMES:
            add(shutil.which(name) or "", name)
    return found


def chrome_proxy(proxy_url):
    """Прокси в виде, который понимает флаг --proxy-server (без логина и пароля)."""
    if not proxy_url:
        return ""
    parts = urlsplit(proxy_url)
    scheme = "socks5" if parts.scheme.startswith("socks") else "http"
    return f"{scheme}://{parts.hostname}:{parts.port or 8080}"


# ------------------------------------------------------------------ DevTools

class CdpError(Exception):
    pass


class Cdp:
    """Минимальный клиент протокола DevTools для одной вкладки."""

    def __init__(self, ws_url):
        import websocket
        # без заголовка Origin: иначе новые Chrome отказывают в подключении
        self.ws = websocket.create_connection(ws_url, timeout=15, suppress_origin=True)
        self.seq = 0

    def call(self, method, **params):
        self.seq += 1
        self.ws.send(json.dumps({"id": self.seq, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.seq:
                if "error" in msg:
                    raise CdpError(msg["error"].get("message", "error"))
                return msg.get("result", {})

    def eval(self, expression):
        res = self.call("Runtime.evaluate", expression=expression, returnByValue=True)
        if res.get("exceptionDetails"):
            raise CdpError("js error")
        return res.get("result", {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _json(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


class BrowserSession(QObject):
    """Ведёт окно браузера: ждёт входа, включает настройки, забирает ключ."""

    status = Signal(str)
    key_found = Signal(str, str)          # user_id, api_key
    finished = Signal(str)                # done | closed | cancelled | error

    POLL = 1.2
    TIMEOUT = 20 * 60

    def __init__(self, site, exe, profile_dir, proxy_url=""):
        super().__init__()
        self.site, self.exe, self.profile_dir, self.proxy = site, exe, profile_dir, proxy_url
        self.host = (urlsplit(site.site_url).hostname or "").lower()
        self.stop_event = threading.Event()
        self.proc = None
        self.port = None

    def url(self, what):
        # страница входа без code=00 у Gelbooru почти пустая
        extra = "&code=00" if what == "login" else ""
        return f"{self.site.site_url}index.php?page=account&s={what}{extra}"

    def start(self):
        threading.Thread(target=self._run, name="browser-session", daemon=True).start()

    def cancel(self):
        self.stop_event.set()

    # --- запуск и подключение

    def _launch(self):
        self.port = _free_port()
        os.makedirs(self.profile_dir, exist_ok=True)
        args = [self.exe, f"--remote-debugging-port={self.port}", f"--user-data-dir={self.profile_dir}",
                "--no-first-run", "--no-default-browser-check", "--new-window"]
        proxy = chrome_proxy(self.proxy)
        if proxy:
            args.append(f"--proxy-server={proxy}")
        args.append(self.url("options"))
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)

    def _page(self, deadline):
        """Вкладка с сайтом (или любая обычная вкладка)."""
        while time.monotonic() < deadline and not self.stop_event.is_set():
            try:
                pages = [p for p in _json(self.port, "/json/list") if p.get("type") == "page"
                         and p.get("webSocketDebuggerUrl")]
                pages.sort(key=lambda p: self.host not in (p.get("url") or ""))
                if pages:
                    return pages[0]["webSocketDebuggerUrl"]
            except (OSError, ValueError):
                pass
            time.sleep(0.5)
        return None

    def _close_browser(self):
        """Закрыть окно браузера, которое открыла программа (только его — у него свой профиль)."""
        try:
            ws = _json(self.port, "/json/version").get("webSocketDebuggerUrl")
            if ws:
                Cdp(ws).call("Browser.close")
        except Exception:
            pass
        if self.proc is None:
            return
        try:
            self.proc.wait(3)
        except subprocess.TimeoutExpired:
            try:
                self.proc.terminate()
                self.proc.wait(3)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass

    # --- основной цикл

    def _run(self):
        try:
            self._launch()
        except OSError as exc:
            self.status.emit(t("login_launch_failed", err=str(exc)[:200]))
            self.finished.emit("error")
            return
        ws_url = self._page(time.monotonic() + 30)
        if not ws_url:
            self.status.emit(t("login_no_debug"))
            self.finished.emit("cancelled" if self.stop_event.is_set() else "error")
            return
        cdp = None
        state = dict(settings_tries=0, generate_tries=0, settings_done=False, sent_to_login=False, last_nav=0.0)
        deadline = time.monotonic() + self.TIMEOUT
        try:
            while time.monotonic() < deadline:
                if self.stop_event.is_set():
                    self._close_browser()
                    self.finished.emit("cancelled")
                    return
                try:
                    if cdp is None:
                        cdp = Cdp(ws_url)
                    result = self._step(cdp, state)
                except CdpError:
                    result = None                 # страница перезагружается — посмотрим ещё раз
                except Exception:
                    if cdp is not None:
                        cdp.close()
                    cdp = None                    # вкладку закрыли или переоткрыли — ищем заново
                    ws_url = self._page(time.monotonic() + 5)
                    if not ws_url:
                        self.status.emit(t("login_closed"))
                        self.finished.emit("closed")
                        return
                    result = None
                if result == "done":
                    time.sleep(2)
                    self._close_browser()
                    self.finished.emit("done")
                    return
                time.sleep(self.POLL)
            self.finished.emit("error")
        finally:
            if cdp is not None:
                cdp.close()

    def _navigate(self, cdp, what, state):
        if time.monotonic() - state["last_nav"] > 4:
            state["last_nav"] = time.monotonic()
            cdp.call("Page.navigate", url=self.url(what))

    def _step(self, cdp, state):
        cookies = cdp.call("Network.getCookies", urls=[self.site.site_url]).get("cookies", [])
        logged = {"user_id", "pass_hash"} <= {c.get("name") for c in cookies}
        href = cdp.eval("location.href") or ""
        if cdp.eval("document.readyState") != "complete":
            return None
        if "s=options" not in href:
            if logged:
                self.status.emit(t("login_step_opening"))
                self._navigate(cdp, "options", state)
            else:
                self.status.emit(t("login_step_login"))
            return None
        info = json.loads(cdp.eval(ANALYZE_JS) or "{}")
        key, uid = info.get("key") or "", info.get("uid") or ""
        if self.site.key == "gelbooru" and (key or logged):
            need = info.get("fringe") is False or info.get("original") is False
            if need and state["settings_tries"] < 2:
                state["settings_tries"] += 1
                self.status.emit(t("login_step_settings"))
                cdp.eval(APPLY_JS % ("true", "false"))
                time.sleep(2)
                return None
            state["settings_done"] = info.get("fringe") is not False and info.get("original") is not False
        if key and uid:
            extra = t("login_done_settings") if self.site.key == "gelbooru" and state["settings_done"] else ""
            self.status.emit(t("login_done", uid=uid, extra=extra))
            self.key_found.emit(uid, key)
            return "done"
        if not logged:
            self.status.emit(t("login_step_login"))
            if not info.get("password") and not state["sent_to_login"]:
                state["sent_to_login"] = True
                self._navigate(cdp, "login", state)
            return None
        if info.get("generate") and state["generate_tries"] < 2:
            state["generate_tries"] += 1
            self.status.emit(t("login_step_generate"))
            cdp.eval(APPLY_JS % ("false", "true"))
            time.sleep(2)
            return None
        self.status.emit(t("login_step_manual"))
        return None


# ====================================================================== ui: Окно программы (PySide6).

LANGS = (("ru", "Русский"), ("en", "English"), ("zh", "中文"), ("ja", "日本語"))
MAX_THUMBS = 60
PREVIEW_COUNT = 60      # сколько постов показывать в предпросмотре поиска
PREVIEW_SIZE = 130


# ====================================================================== утилиты

def human_size(n):
    n = float(n or 0)
    units = (t("unit_b"), t("unit_kb"), t("unit_mb"), t("unit_gb"))
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.0f} {units[i]}" if i == 0 else f"{n:.1f} {units[i]}"


def human_time(sec):
    sec = int(max(0, sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return t("time_hm", h=h, m=m)
    if m:
        return t("time_ms", m=m, s=s)
    return t("time_s", s=s)


def fmt_num(n):
    if n is None:
        return "—"
    return f"{int(n):,}".replace(",", " " if current() == "ru" else ",")


def compact(n):
    if n is None:
        return ""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.0f}K"
    return str(n)


def open_path(path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def reveal(path):
    """Открыть папку и выделить в ней файл."""
    if os.name == "nt" and os.path.exists(path):
        subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
    else:
        open_path(os.path.dirname(path) if os.path.isfile(path) else path)


def load_image(path, max_w, max_h):
    """Читает картинку уже уменьшенной (вызывается в фоновом потоке)."""
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and (size.width() > max_w or size.height() > max_h):
        reader.setScaledSize(size.scaled(max_w, max_h, Qt.KeepAspectRatio))
    img = reader.read()
    return None if img.isNull() else img


def video_placeholder(w, h, ext, accent):
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(FIELD))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QColor(accent))
    f = QFont()
    f.setPixelSize(max(14, h // 4))
    p.setFont(f)
    p.drawText(img.rect().adjusted(0, -h // 8, 0, -h // 8), Qt.AlignCenter, "▶")
    f.setPixelSize(max(9, h // 9))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(MUTED))
    p.drawText(img.rect().adjusted(0, h // 3, 0, 0), Qt.AlignCenter, ext.upper().lstrip("."))
    p.end()
    return img


_qt_translator = None


def install_qt_translator(code):
    """Стандартные кнопки Qt («Да», «Нет», «Отмена») на языке программы."""
    global _qt_translator
    from PySide6.QtCore import QLibraryInfo, QTranslator
    app = QApplication.instance()
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    name = {"ru": "qtbase_ru", "zh": "qtbase_zh_CN", "ja": "qtbase_ja"}.get(code)
    if name:
        tr = QTranslator(app)
        if tr.load(name, QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
            app.installTranslator(tr)
            _qt_translator = tr


# ====================================================================== фон

class Async(QObject):
    """Запускает функцию в фоне и вызывает callback(result, error) в окне."""

    _done = Signal(int, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._callbacks = {}
        self._n = 0
        self._done.connect(self._dispatch)

    def run(self, fn, callback=None):
        self._n += 1
        token = self._n
        self._callbacks[token] = callback

        def target():
            try:
                result, error = fn(), None
            except Exception as exc:          # noqa: BLE001 — отдаём в окно как есть
                result, error = None, exc
            self._done.emit(token, result, error)

        threading.Thread(target=target, daemon=True).start()

    def _dispatch(self, token, result, error):
        cb = self._callbacks.pop(token, None)
        if cb:
            cb(result, error)


class Bridge(QObject):
    event = Signal(str, object)


# ====================================================================== виджеты

class TagEdit(QLineEdit):
    """Поле тегов с подсказками с сайта; ссылку на поиск превращает в теги."""

    def __init__(self, suggest, parent=None):
        super().__init__(parent)
        self._suggest = suggest
        self._model = QStandardItemModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self._completer.setMaxVisibleItems(12)
        self._completer.activated.connect(self._insert)
        self._timer = QTimer(self, singleShot=True, interval=280, timeout=self._request)
        self._req = 0
        self._values = {}
        self.textEdited.connect(self._edited)

    def _token(self):
        text, pos = self.text(), self.cursorPosition()
        start = text.rfind(" ", 0, pos) + 1
        end = text.find(" ", pos)
        return start, (len(text) if end < 0 else end), text[start:(len(text) if end < 0 else end)]

    def _edited(self, text):
        if "://" in text or "tags=" in text:
            tags = tags_from_input(text)
            if tags:
                self.setText(tags)
                self._completer.popup().hide()
                return
        self._timer.start()

    def _request(self):
        _, _, token = self._token()
        term = token.lstrip("-~")
        if len(term) < 2 or ":" in term:
            self._completer.popup().hide()
            return
        self._req += 1
        req = self._req
        self._suggest(term, lambda items: self._show(req, term, items))

    def _show(self, req, term, items):
        if req != self._req or not self.hasFocus():
            return
        if self._token()[2].lstrip("-~") != term:
            return
        self._model.clear()
        self._values = {}
        for value, count, _cat in items:
            label = f"{value}    {compact(count)}" if count is not None else value
            self._values[label] = value
            self._model.appendRow(QStandardItem(label))
        if items:
            self._completer.setCompletionPrefix("")
            self._completer.complete()
        else:
            self._completer.popup().hide()

    def _insert(self, label):
        value = self._values.get(label, label.split()[0] if label.split() else "")
        start, end, token = self._token()
        prefix = token[: len(token) - len(token.lstrip("-~"))]
        text = self.text()
        new = text[:start] + prefix + value + " " + text[end:].lstrip()
        self.setText(new)
        self.setCursorPosition(start + len(prefix) + len(value) + 1)


class ImageView(QLabel):
    """Превью, которое не меняет размер карточки и подстраивается под окно."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("preview")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(260, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setWordWrap(True)
        self._image = None

    def set_image(self, image):
        self._image = image
        self._rescale()

    def clear_image(self, text=""):
        self._image = None
        self.setPixmap(QPixmap())
        self.setText(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self):
        if self._image is None:
            return
        dpr = self.devicePixelRatioF()
        w, h = max(1, int((self.width() - 16) * dpr)), max(1, int((self.height() - 16) * dpr))
        pm = QPixmap.fromImage(self._image.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        pm.setDevicePixelRatio(dpr)
        self.setText("")
        self.setPixmap(pm)


def make_card(title_widget=None):
    frame = QFrame()
    frame.setObjectName("card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 14, 16, 16)
    lay.setSpacing(8)
    if title_widget is not None:
        title_widget.setObjectName("cardTitle")
        lay.addWidget(title_widget)
    return frame, lay


def hint(text=""):
    lbl = QLabel(text)
    lbl.setObjectName("hint")
    lbl.setWordWrap(True)
    return lbl


class LoginStatus(QDialog):
    """Пока человек входит в браузере — что происходит и кнопка «Отмена»."""

    def __init__(self, win, browser_name):
        super().__init__(win)
        self.setWindowTitle(t("login_title", site=win.site.site_name))
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        head = QLabel(t("login_using", browser=browser_name))
        head.setObjectName("cardTitle")
        head.setWordWrap(True)
        lay.addWidget(head)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"background: {PANEL2}; border: 1px solid {win.site.accent}; "
                                  "border-radius: 10px; padding: 10px 12px;")
        lay.addWidget(self.status)
        lay.addWidget(hint(t("login_privacy")))
        row = QHBoxLayout()
        row.addStretch(1)
        self.cancel_btn = QPushButton(t("btn_login_cancel"))
        row.addWidget(self.cancel_btn)
        lay.addLayout(row)

    def set_status(self, text):
        self.status.setText(text)


class PostViewer(QDialog):
    """Арт в полный размер: по размеру окна или 100 % (щелчок), ← → — соседние, Esc — закрыть."""

    loaded = Signal(int, object, object)      # поколение, байты, ошибка
    progress = Signal(int, int, int)          # поколение, получено, всего

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle(win.windowTitle())
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        screen = win.screen().availableGeometry()
        self.resize(int(screen.width() * 0.8), int(screen.height() * 0.85))
        self.posts, self.index, self.gen = [], 0, 0
        self.data = None          # байты текущего арта (для «Скачать» без повторной загрузки)
        self.image = None
        self.movie = None
        self.fit = True
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        top = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("cardTitle")
        top.addWidget(self.title, 1)
        self.prev_btn = QPushButton("◀")
        self.next_btn = QPushButton("▶")
        self.dl_btn = QPushButton()
        self.site_btn = QPushButton()
        self.video_btn = QPushButton()
        for b in (self.prev_btn, self.next_btn):
            b.setFixedWidth(44)
        self.prev_btn.clicked.connect(lambda: self.step(-1))
        self.next_btn.clicked.connect(lambda: self.step(1))
        self.dl_btn.setObjectName("primary")
        self.dl_btn.clicked.connect(self.download)
        self.site_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.win.site.post_url.format(id=self.post.id))))
        self.video_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.post.file_url)))
        for b in (self.prev_btn, self.next_btn, self.video_btn, self.site_btn, self.dl_btn):
            top.addWidget(b)
        lay.addLayout(top)
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setWidgetResizable(False)
        self.scroll.setStyleSheet(f"QScrollArea {{ background: {FIELD}; border-radius: 12px; }}")
        self.view = QLabel()
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setStyleSheet(f"color: {MUTED}; background: transparent;")
        self.view.mousePressEvent = lambda e: self.toggle_fit()
        self.scroll.setWidget(self.view)
        lay.addWidget(self.scroll, 1)
        self.info = QLabel()
        self.info.setObjectName("postInfo")
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.RichText)
        self.info.linkActivated.connect(self._tag_clicked)
        lay.addWidget(self.info)
        self.hint = hint()
        lay.addWidget(self.hint)
        self.loaded.connect(self._on_loaded)
        self.progress.connect(self._on_progress)

    @property
    def post(self):
        return self.posts[self.index]

    def show_posts(self, posts, index):
        self.posts, self.index = posts, index
        self.load()
        self.show()
        self.raise_()
        self.activateWindow()

    def retranslate(self):
        self.dl_btn.setText(t("btn_viewer_download"))
        self.site_btn.setText(t("btn_viewer_site"))
        self.video_btn.setText(t("btn_open_video"))
        self.hint.setText(t("viewer_hint"))

    def step(self, delta):
        if self.posts:
            self.index = (self.index + delta) % len(self.posts)
            self.load()

    def refresh_info(self):
        if self.posts:
            self.info.setText(self.win._post_info_html(self.post, expandable=False))

    def load(self):
        self.retranslate()
        self.gen += 1
        gen, post = self.gen, self.post
        self.data, self.image = None, None
        if self.movie:
            self.movie.stop()
            self.movie = None
        self.view.setMovie(None)
        self.view.setPixmap(QPixmap())
        self.title.setText(f"#{post.id}  ·  {post.ext.lstrip('.').upper()}"
                           + (f"  ·  {post.width}×{post.height}" if post.width else "")
                           + f"  ·  {self.index + 1} / {len(self.posts)}")
        self.refresh_info()
        self.video_btn.setVisible(post.is_video and post.ext != ".gif")
        self.dl_btn.setEnabled(bool(post.file_url))
        if post.is_video and post.ext != ".gif":
            thumb = self.win._thumb_cache.get(post.preview_url)
            self.view.setText(t("viewer_video"))
            if thumb is not None:
                self.image = thumb
                self._render()
            return
        if not post.file_url:
            self.view.setText(t("single_no_url", id=post.id))
            self._fit_label()
            return
        self.view.setText(t("viewer_loading", p="…"))
        self._fit_label()
        client = self.win._client()

        def run():
            try:
                data = client.fetch_bytes(post.file_url, limit=200_000_000,
                                          on_progress=lambda done, total: self.progress.emit(gen, done, total))
                self.loaded.emit(gen, data, None)
            except Exception as exc:     # noqa: BLE001
                self.loaded.emit(gen, None, exc)

        threading.Thread(target=run, daemon=True).start()

    def _on_progress(self, gen, done, total):
        if gen == self.gen and self.image is None and self.movie is None:
            pct = f"{done * 100 // total}%" if total else human_size(done)
            self.view.setText(t("viewer_loading", p=pct))

    def _on_loaded(self, gen, data, err):
        if gen != self.gen:
            return
        if err is not None:
            self.view.setText(t("viewer_failed", err=self.win._err_text(err)))
            return
        self.data = data
        if self.post.ext == ".gif":
            self._buffer = QBuffer()
            self._buffer.setData(QByteArray(data))
            self._buffer.open(QBuffer.ReadOnly)
            self.movie = QMovie(self._buffer, b"gif")
            if self.movie.isValid():
                self.view.setMovie(self.movie)
                self.movie.start()
                self.image = self.movie.currentImage()
                self._render()
                return
            self.movie = None
        img = QImage.fromData(data)
        if img.isNull():
            self.view.setText(t("preview_unavailable"))
            return
        self.image = img
        self._render()

    def _fit_label(self):
        self.view.resize(self.scroll.viewport().size())

    def _render(self):
        if self.image is None:
            return
        area = self.scroll.viewport().size()
        size = self.image.size()
        if self.fit:
            size = size.scaled(area, Qt.KeepAspectRatio) if (size.width() > area.width()
                                                            or size.height() > area.height()) else size
        if self.movie:
            self.movie.setScaledSize(size)
            self.view.resize(max(size.width(), area.width()), max(size.height(), area.height()))
            return
        pm = QPixmap.fromImage(self.image.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.view.setPixmap(pm)
        self.view.resize(max(pm.width(), area.width()), max(pm.height(), area.height()))

    def toggle_fit(self):
        self.fit = not self.fit
        self._render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render() if self.image is not None else self._fit_label()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Left, Qt.Key_PageUp):
            self.step(-1)
        elif key in (Qt.Key_Right, Qt.Key_PageDown, Qt.Key_Space):
            self.step(1)
        elif key in (Qt.Key_F, Qt.Key_Z):
            self.toggle_fit()
        elif key in (Qt.Key_S, Qt.Key_D):
            self.download()
        else:
            super().keyPressEvent(event)

    def download(self):
        if self.posts and self.post.file_url:
            self.win._download_posts([self.post], data=self.data)

    def _tag_clicked(self, tag):
        self.close()
        self.win._search_tag(tag)


# ====================================================================== окно

class MainWindow(QMainWindow):
    thumb_ready = Signal(int, object, str, object)
    tags_ready = Signal(int)

    def __init__(self, site):
        super().__init__()
        self.site = site
        self.cfg = Config(site)
        set_language(self.cfg["language"])
        install_qt_translator(self.cfg["language"])
        self.history = History(site)
        self.redact = Redactor()
        self.redact.add(self.cfg.api_key)
        self.async_ = Async(self)
        self.bridge = Bridge(self)
        self.bridge.event.connect(self._on_event)
        self.job = None
        self.job_spec = None
        self._tr = []
        self._tr_combos = []
        self._bytes_hist = deque(maxlen=30)
        self._value_hist = deque(maxlen=60)
        self._last_preview = 0.0
        self._pinned_until = 0.0
        self._pending_preview = None
        self._found_cache = None
        self._make_router()

        self.setWindowTitle(f"{site.app_name} {site.author}".strip())
        icon = QPixmap()
        if icon.loadFromData(resource_bytes(site.icon)):
            self.setWindowIcon(QIcon(icon))
        self.resize(1200, 780)
        self.setMinimumSize(980, 660)

        self.progress_timer = QTimer(self, interval=400, timeout=self._tick)
        self.preview_timer = QTimer(self, singleShot=True, interval=700, timeout=self._show_pending_preview)
        self.targets_timer = QTimer(self, singleShot=True, interval=300, timeout=self._refresh_targets)
        self.search_timer = QTimer(self, singleShot=True, interval=1000, timeout=lambda: self._find(auto=True))
        self._search_gen = 0
        self._search_busy = False
        self._last_search = None
        self._search_items = {}
        self._search_page = 0
        self._search_count = None
        self._search_spec = None
        self._downloaded = set()
        self._single_sem = threading.Semaphore(3)
        self._viewer = None
        self._thumb_cache = {}
        self._thumbs = queue.Queue()
        self.thumb_ready.connect(self._on_thumb)
        self._tag_kinds = {}           # тег → artist | character | copyright | metadata | general
        self._tag_pending = set()      # основной запрос их не вернул — уточняем по одному
        self._tag_queued = {}          # тег → приоритет, с которым уже стоит в очереди
        self._tag_seq = 0
        self._tags_disabled = False    # сайт не понимает пачечный запрос — только по одному
        self._info_post = None
        self._info_expanded = False
        self._tag_jobs = queue.PriorityQueue()
        self.tags_ready.connect(self._on_tags_ready)
        threading.Thread(target=self._tag_worker, daemon=True).start()
        for _ in range(6):
            threading.Thread(target=self._thumb_worker, daemon=True).start()
        blank = QPixmap(PREVIEW_SIZE, PREVIEW_SIZE)
        blank.fill(QColor(PANEL2))
        self._blank_icon = QIcon(blank)

        self._clip_taken = None
        self._login_session = None
        self._login_dialog = None
        self._build()
        self._fill_browsers()
        self._load_ui_from_cfg()
        self.retranslate()
        self._refresh_targets()
        self._refresh_history()
        self._refresh_conn_label()

        QApplication.clipboard().dataChanged.connect(self._clipboard_check)
        geo = self.cfg["geometry"]
        if geo:
            self.restoreGeometry(QByteArray.fromBase64(geo.encode()))
        if not self._have_key():
            QTimer.singleShot(250, lambda: self._goto_settings(t("api_need")))
        self._resolve_account()

    # ------------------------------------------------------------ перевод

    def T(self, widget, key, method="setText", **fmt):
        self._tr.append((widget, method, key, fmt))
        getattr(widget, method)(t(key, **fmt))
        return widget

    def TC(self, combo, items):
        """items: [(ключ перевода, data)]"""
        combo.clear()
        for key, data in items:
            combo.addItem(t(key), data)
        self._tr_combos.append((combo, [k for k, _ in items]))
        return combo

    def retranslate(self):
        for widget, method, key, fmt in self._tr:
            getattr(widget, method)(t(key, **fmt))
        for combo, keys in self._tr_combos:
            for i, key in enumerate(keys):
                combo.setItemText(i, t(key))
        self.tabs.setTabText(0, t("tab_download"))
        self.tabs.setTabText(1, t("tab_history"))
        self.tabs.setTabText(2, t("tab_settings"))
        self.limit_spin.setSpecialValueText(t("limit_all"))
        current = next(n for n, (i, _) in self.VIEWS.items() if i == self.view_stack.currentIndex())
        self.view_title.setText(t(self.VIEWS[current][1]))
        if not self.search_grid.count() and not self._search_busy:
            self.search_info.setText(t("search_hint_empty"))
        self.history_table.setHorizontalHeaderLabels(
            [t("hist_query"), t("hist_count"), t("hist_date"), t("hist_folder")])
        self._refresh_history()
        self._refresh_targets()
        self._refresh_conn_label()
        self._refresh_account()
        if self._found_cache:
            self._set_found(*self._found_cache)
        if not (self.job and self.job.is_running()):
            self.status_label.setText(t("prog_idle"))

    # ------------------------------------------------------------ сеть

    def _make_router(self):
        mode = self.cfg["proxy_mode"]
        self.router = Router(
            enabled=(mode == "auto"), pool=self.cfg.proxy_pool(self.site),
            state=self.cfg["route_state"],
            on_change=lambda state: self.bridge.event.emit("route_state", {"state": state}),
            on_event=lambda key, params: self.bridge.event.emit(
                "log", {"key": "log_" + key, "level": "warn" if key in ("route_none", "route_blocked") else "info",
                        "params": params}))
        self.ui_session = make_session(self.site, mode, self.cfg.proxy_url, pool=4)

    def _client(self, session=None, user_id=None, api_key=None):
        return Client(self.site, session or self.ui_session,
                          self.cfg["user_id"] if user_id is None else user_id,
                          self.cfg.api_key if api_key is None else api_key,
                          self.redact, self.router)

    def _have_key(self):
        return bool(self.cfg["user_id"] and self.cfg.api_key)

    # ------------------------------------------------------------ построение

    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 14, 18, 8)
        outer.setSpacing(10)

        header = QHBoxLayout()
        logo = QLabel(self.site.letter)
        logo.setObjectName("logo")
        logo.setFixedSize(44, 44)
        logo.setAlignment(Qt.AlignCenter)
        title = QLabel(self.site.app_name)
        title.setObjectName("appTitle")
        header.addWidget(logo)
        header.addSpacing(6)
        header.addWidget(title)
        header.addStretch(1)
        self.conn_label = QLabel()
        self.conn_label.setObjectName("muted")
        header.addWidget(self.conn_label)
        header.addSpacing(12)
        self.lang_combo = QComboBox()
        for code, name in LANGS:
            self.lang_combo.addItem(name, code)
        self.lang_combo.currentIndexChanged.connect(self._language_changed)
        header.addWidget(self.lang_combo)
        outer.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_download_tab(), "")
        self.tabs.addTab(self._build_history_tab(), "")
        self.tabs.addTab(self._build_settings_tab(), "")
        outer.addWidget(self.tabs, 1)

        status = self.statusBar()
        self.account_label = QLabel()
        self.account_label.setObjectName("muted")
        status.addPermanentWidget(self.account_label)
        if self.site.author:
            author = QLabel(self.site.author)
            author.setObjectName("author")
            status.addPermanentWidget(author)

    # --- вкладка «Загрузка»

    def _build_download_tab(self):
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(0, 8, 0, 0)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        lay.addWidget(splitter)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left = QWidget()
        left_scroll.setWidget(left)
        col = QVBoxLayout(left)
        col.setContentsMargins(0, 0, 8, 0)
        col.setSpacing(12)

        # поиск
        card, c = make_card(self.T(QLabel(), "card_search"))
        c.addWidget(self.T(QLabel(), "lbl_tags"))
        row = QHBoxLayout()
        self.tags_edit = TagEdit(self._suggest)
        self.T(self.tags_edit, "ph_tags", "setPlaceholderText")
        self.tags_edit.setMinimumHeight(38)
        self.tags_edit.textChanged.connect(lambda _: self._tags_changed())
        self.tags_edit.returnPressed.connect(self._find)
        self.find_btn = self.T(QPushButton(), "btn_find")
        self.find_btn.clicked.connect(self._find)
        row.addWidget(self.tags_edit, 1)
        row.addWidget(self.find_btn)
        c.addLayout(row)
        c.addWidget(self.T(hint(), "hint_tags"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(4)
        grid.addWidget(self.T(QLabel(), "lbl_rating"), 0, 0)
        grid.addWidget(self.T(QLabel(), "lbl_media"), 0, 1)
        grid.addWidget(self.T(QLabel(), "lbl_limit"), 0, 2)
        self.rating_combo = QComboBox()
        self.TC(self.rating_combo, [("rating_any", "")] + [("rating_" + r, r) for r in self.site.ratings])
        self.rating_combo.currentIndexChanged.connect(lambda _: self._tags_changed())
        grid.addWidget(self.rating_combo, 1, 0)
        seg = QHBoxLayout()
        seg.setSpacing(4)
        self.media_group = QButtonGroup(self)
        self.media_buttons = {}
        for key, value in (("media_all", "all"), ("media_images", "images"), ("media_videos", "videos")):
            b = self.T(QPushButton(), key)
            b.setObjectName("seg")
            b.setCheckable(True)
            self.media_group.addButton(b)
            self.media_buttons[value] = b
            seg.addWidget(b)
        grid.addLayout(seg, 1, 1)
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 10_000_000)
        self.limit_spin.setSingleStep(50)
        self.limit_spin.setMinimumWidth(120)
        self.limit_spin.setToolTip(t("tip_limit"))
        grid.addWidget(self.limit_spin, 1, 2)
        self.no_ai_chk = self.T(QCheckBox(), "chk_no_ai")
        self.T(self.no_ai_chk, "tip_no_ai", "setToolTip", tags=" ".join("-" + x for x in self.site.ai_tags))
        self.no_ai_chk.toggled.connect(lambda _: self._tags_changed())
        grid.setColumnStretch(3, 1)
        c.addLayout(grid)
        c.addWidget(self.no_ai_chk)
        self.found_label = QLabel()
        self.found_label.setObjectName("found")
        c.addWidget(self.found_label)
        if self.site.key == "gelbooru":
            c.addWidget(self.T(hint(), "hint_gelbooru_account"))
        col.addWidget(card)

        # сохранение
        card, c = make_card(self.T(QLabel(), "card_save"))
        c.addWidget(self.T(QLabel(), "lbl_folder"))
        row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setMinimumHeight(36)
        self.folder_edit.textChanged.connect(lambda _: self.targets_timer.start())
        choose = self.T(QPushButton(), "btn_choose")
        choose.clicked.connect(self._choose_folder)
        opn = self.T(QPushButton(), "btn_open_folder")
        opn.clicked.connect(self._open_target_folder)
        row.addWidget(self.folder_edit, 1)
        row.addWidget(choose)
        row.addWidget(opn)
        c.addLayout(row)
        self.target_hint = hint()
        c.addWidget(self.target_hint)
        self.split_chk = self.T(QCheckBox(), "chk_split")
        self.skip_chk = self.T(QCheckBox(), "chk_skip")
        self.T(self.skip_chk, "tip_skip", "setToolTip")
        c.addWidget(self.split_chk)
        c.addWidget(self.skip_chk)
        col.addWidget(card)

        # кнопки
        row = QHBoxLayout()
        row.setSpacing(8)
        self.start_btn = self.T(QPushButton(), "btn_start")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(lambda: self._start())
        self.update_btn = self.T(QPushButton(), "btn_update")
        self.T(self.update_btn, "tip_update", "setToolTip")
        self.update_btn.clicked.connect(lambda: self._start(update_only=True))
        self.resume_btn = self.T(QPushButton(), "btn_resume")
        self.resume_btn.setObjectName("resume")
        self.T(self.resume_btn, "tip_resume", "setToolTip")
        self.resume_btn.clicked.connect(lambda: self._start(resume=True))
        self.stop_btn = self.T(QPushButton(), "btn_stop")
        self.stop_btn.setObjectName("stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        for b in (self.start_btn, self.update_btn, self.resume_btn, self.stop_btn):
            b.setMinimumHeight(44)
        row.addWidget(self.start_btn, 2)
        row.addWidget(self.update_btn, 1)
        row.addWidget(self.resume_btn, 1)
        row.addWidget(self.stop_btn, 1)
        col.addLayout(row)

        col.addStretch(1)
        splitter.addWidget(left_scroll)

        right = QWidget()
        rcol = QVBoxLayout(right)
        rcol.setContentsMargins(8, 0, 0, 0)
        rcol.setSpacing(12)

        # ход загрузки — всегда на виду
        card, c = make_card(self.T(QLabel(), "card_progress"))
        self.bar = QProgressBar()
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.bar.setFormat("")
        c.addWidget(self.bar)
        self.counts_label = QLabel()
        self.counts_label.setWordWrap(True)
        self.speed_label = QLabel()
        self.speed_label.setObjectName("muted")
        self.status_label = QLabel()
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        c.addWidget(self.counts_label)
        c.addWidget(self.speed_label)
        c.addWidget(self.status_label)
        rcol.addWidget(card)

        # файлы / журнал
        card, c = make_card()
        head = QHBoxLayout()
        self.view_title = QLabel()
        self.view_title.setObjectName("cardTitle")
        head.addWidget(self.view_title)
        head.addStretch(1)
        self.view_group = QButtonGroup(self)
        self.view_buttons = {}
        for name, key in (("search", "btn_view_search"), ("files", "btn_view_files"), ("log", "btn_view_log")):
            b = self.T(QPushButton(), key)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, name=name: self._set_view(name))
            self.view_group.addButton(b)
            self.view_buttons[name] = b
            head.addWidget(b)
        c.addLayout(head)
        self.view_stack = QStackedWidget()
        c.addWidget(self.view_stack, 1)

        files = QWidget()
        fl = QVBoxLayout(files)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(8)
        self.image_view = ImageView()
        self.T(self.image_view, "preview_empty")
        fl.addWidget(self.image_view, 1)
        self.file_name = QLabel()
        self.file_name.setObjectName("muted")
        self.file_name.setWordWrap(True)
        fl.addWidget(self.file_name)
        row = QHBoxLayout()
        self.file_open_btn = self.T(QPushButton(), "btn_file_open")
        self.file_open_btn.clicked.connect(lambda: self._current_file and open_path(self._current_file["path"]))
        self.file_dir_btn = self.T(QPushButton(), "btn_file_folder")
        self.file_dir_btn.clicked.connect(lambda: self._current_file and reveal(self._current_file["path"]))
        self.file_post_btn = self.T(QPushButton(), "btn_file_post")
        self.file_post_btn.clicked.connect(self._open_post)
        for b in (self.file_open_btn, self.file_dir_btn, self.file_post_btn):
            b.setEnabled(False)
            row.addWidget(b)
        fl.addLayout(row)
        self.thumbs = QListWidget()          # лента последних файлов
        self.thumbs.setViewMode(QListWidget.IconMode)
        self.thumbs.setFlow(QListWidget.LeftToRight)
        self.thumbs.setWrapping(False)
        self.thumbs.setIconSize(QSize(80, 80))
        self.thumbs.setGridSize(QSize(90, 90))
        self.thumbs.setMovement(QListWidget.Static)
        self.thumbs.setUniformItemSizes(True)
        self.thumbs.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.thumbs.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumbs.setFixedHeight(108)
        self.thumbs.itemClicked.connect(self._thumb_clicked)
        self.thumbs.itemDoubleClicked.connect(lambda it: open_path(it.data(Qt.UserRole)["path"]))
        fl.addWidget(self.thumbs)
        self._current_file = None
        self.view_stack.addWidget(files)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumBlockCount(3000)
        self.view_stack.addWidget(self.log_box)

        # предпросмотр поиска — первая страница, как на сайте
        search = QWidget()
        sl = QVBoxLayout(search)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(6)
        self.search_info = hint()
        sl.addWidget(self.search_info)
        nav = QHBoxLayout()               # листание — под сеткой, как на сайте
        nav.addStretch(1)
        self.page_prev = QPushButton("◀")
        self.page_next = QPushButton("▶")
        self.page_label = QLabel()
        self.page_label.setObjectName("muted")
        for b, step in ((self.page_prev, -1), (self.page_next, 1)):
            b.setFixedWidth(40)
            b.setEnabled(False)
            b.clicked.connect(lambda _=False, step=step: self._find(page=self._search_page + step))
        self.T(self.page_prev, "tip_prev_page", "setToolTip")
        self.T(self.page_next, "tip_next_page", "setToolTip")
        nav.addWidget(self.page_prev)
        nav.addWidget(self.page_label)
        nav.addWidget(self.page_next)
        nav.addStretch(1)
        self.search_grid = QListWidget()
        self.search_grid.setViewMode(QListWidget.IconMode)
        self.search_grid.setIconSize(QSize(PREVIEW_SIZE, PREVIEW_SIZE))
        self.search_grid.setGridSize(QSize(PREVIEW_SIZE + 10, PREVIEW_SIZE + 10))
        self.search_grid.setResizeMode(QListWidget.Adjust)
        self.search_grid.setMovement(QListWidget.Static)
        self.search_grid.setUniformItemSizes(True)
        self.search_grid.setWrapping(True)
        self.search_grid.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.search_grid.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.search_grid.itemDoubleClicked.connect(lambda it: self._open_viewer(it.data(Qt.UserRole)))
        self.search_grid.setContextMenuPolicy(Qt.CustomContextMenu)
        self.search_grid.customContextMenuRequested.connect(self._grid_menu)
        sl.addWidget(self.search_grid, 1)
        sl.addLayout(nav)
        self.search_grid.setMouseTracking(True)
        self.search_grid.itemEntered.connect(lambda it: self._show_post_info(it.data(Qt.UserRole)))
        self.search_grid.currentItemChanged.connect(
            lambda it, _prev: it is not None and self._show_post_info(it.data(Qt.UserRole)))
        self.search_grid.viewport().installEventFilter(self)
        self.post_info = QLabel()          # автор, персонажи, откуда — как в колонке тегов на сайте
        self.post_info.setObjectName("postInfo")
        self.post_info.setWordWrap(True)
        self.post_info.setTextFormat(Qt.RichText)
        self.post_info.setMinimumHeight(62)
        self.post_info.setMaximumHeight(220)
        self.post_info.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.post_info.linkActivated.connect(self._search_tag)
        self.T(self.post_info, "tip_tag_link", "setToolTip")
        sl.addWidget(self.post_info)
        self.view_stack.addWidget(search)
        rcol.addWidget(card, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([680, 480])
        return page

    # --- вкладка «История»

    def _build_history_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 8, 0, 0)
        card, c = make_card(self.T(QLabel(), "card_history"))
        self.history_table = QTableWidget(0, 4)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setShowGrid(False)
        self.history_table.setWordWrap(False)
        hh = self.history_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Interactive)
        hh.resizeSection(3, 320)
        self.history_table.itemDoubleClicked.connect(lambda _: self._history_use())
        self.history_table.itemSelectionChanged.connect(self._history_selection)
        c.addWidget(self.history_table, 1)
        self.history_empty = self.T(hint(), "hist_empty")
        c.addWidget(self.history_empty)
        row = QHBoxLayout()
        self.h_use = self.T(QPushButton(), "btn_hist_use")
        self.h_use.clicked.connect(self._history_use)
        self.h_update = self.T(QPushButton(), "btn_hist_update")
        self.h_update.clicked.connect(self._history_update)
        self.h_folder = self.T(QPushButton(), "btn_hist_folder")
        self.h_folder.clicked.connect(self._history_folder)
        self.h_remove = self.T(QPushButton(), "btn_hist_remove")
        self.h_remove.clicked.connect(self._history_remove)
        for b in (self.h_use, self.h_update, self.h_folder):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(self.h_remove)
        c.addLayout(row)
        lay.addWidget(card)
        return page

    # --- вкладка «Настройки»

    def _build_settings_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        page = QWidget()
        scroll.setWidget(page)
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 8, 8, 8)
        grid.setSpacing(12)

        # ключ API
        card, c = make_card(self.T(QLabel(), "card_api", site=self.site.site_name))
        self.api_banner = QLabel()
        self.api_banner.setObjectName("banner")
        self.api_banner.setWordWrap(True)
        self.api_banner.setVisible(False)
        c.addWidget(self.api_banner)
        self.login_browser_btn = self.T(QPushButton(), "btn_login_browser")
        self.login_browser_btn.setObjectName("primary")
        self.login_browser_btn.clicked.connect(self._open_login_browser)
        c.addWidget(self.login_browser_btn)
        row = QHBoxLayout()
        row.addWidget(self.T(QLabel(), "lbl_login_browser"))
        self.browser_combo = QComboBox()
        row.addWidget(self.browser_combo, 1)
        c.addLayout(row)
        c.addWidget(self.T(hint(), "hint_login_browser_" + self.site.key))
        c.addSpacing(4)
        c.addWidget(self.T(hint(), "hint_api_steps_" + self.site.key))
        row = QHBoxLayout()
        key_page = self.T(QPushButton(), "btn_open_key_page")
        key_page.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.site.options_url)))
        register = self.T(QPushButton(), "btn_register")
        register.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.site.register_url)))
        row.addWidget(key_page)
        row.addWidget(register)
        row.addStretch(1)
        c.addLayout(row)
        c.addSpacing(4)
        c.addWidget(self.T(QLabel(), "lbl_api_line"))
        row = QHBoxLayout()
        self.api_edit = QLineEdit()        # одна строка: программа сама достаёт api_key и user_id
        self.api_edit.setEchoMode(QLineEdit.Password)
        self.api_edit.setMinimumHeight(38)
        self.T(self.api_edit, "ph_api_line", "setPlaceholderText")
        self.api_edit.textChanged.connect(self._api_text_changed)
        self.api_edit.returnPressed.connect(self._check_key)
        row.addWidget(self.api_edit, 1)
        self.show_key = self.T(QCheckBox(), "chk_show_key")
        self.show_key.toggled.connect(lambda on: self.api_edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        row.addWidget(self.show_key)
        c.addLayout(row)
        self.api_parsed = hint()
        c.addWidget(self.api_parsed)
        row = QHBoxLayout()
        row.addWidget(self.T(QLabel(), "lbl_account_nick"))
        self.nick_edit = QLineEdit()
        self.T(self.nick_edit, "ph_nick_" + ("auto" if self.site.profile_url else "manual"), "setPlaceholderText")
        self.nick_edit.editingFinished.connect(self._nick_changed)
        row.addWidget(self.nick_edit, 1)
        c.addLayout(row)
        self.api_timer = QTimer(self, singleShot=True, interval=700, timeout=lambda: self._check_key(auto=True))
        c.addWidget(self.T(hint(), "hint_api_secure"))
        row = QHBoxLayout()
        self.api_btn = self.T(QPushButton(), "btn_api_check")
        self.api_btn.setObjectName("primary")
        self.api_btn.clicked.connect(self._check_key)
        row.addWidget(self.api_btn)
        self.api_status = QLabel()
        self.api_status.setWordWrap(True)
        row.addWidget(self.api_status, 1)
        c.addLayout(row)
        c.addStretch(1)
        grid.addWidget(card, 0, 0)

        # скорость
        card, c = make_card(self.T(QLabel(), "card_speed"))
        form = QGridLayout()
        form.addWidget(self.T(QLabel(), "lbl_threads"), 0, 0)
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 8)
        self.threads_spin.valueChanged.connect(lambda v: self._cfg_set("threads", v))
        form.addWidget(self.threads_spin, 0, 1)
        form.addWidget(self.T(QLabel(), "lbl_delay"), 1, 0)
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0, 10)
        self.delay_spin.setSingleStep(0.1)
        self.delay_spin.setDecimals(1)
        self.delay_spin.valueChanged.connect(lambda v: self._cfg_set("delay", round(v, 1)))
        form.addWidget(self.delay_spin, 1, 1)
        form.setColumnStretch(2, 1)
        c.addLayout(form)
        c.addWidget(self.T(hint(), "hint_speed"))
        c.addStretch(1)
        grid.addWidget(card, 1, 0)

        # прочее
        card, c = make_card(self.T(QLabel(), "card_other"))
        btn = self.T(QPushButton(), "btn_open_data")
        btn.clicked.connect(lambda: open_path(str(data_dir(self.site))))
        c.addWidget(btn, 0, Qt.AlignLeft)
        c.addWidget(self.T(hint(), "hint_data"))
        c.addStretch(1)
        grid.addWidget(card, 2, 0)

        # подключение
        card, c = make_card(self.T(QLabel(), "card_net"))
        self.net_group = QButtonGroup(self)
        self.net_radios = {}
        for mode, key in (("auto", "net_auto"), ("direct", "net_direct"), ("custom", "net_custom")):
            rb = self.T(QRadioButton(), key)
            self.net_group.addButton(rb)
            self.net_radios[mode] = rb
            c.addWidget(rb)
            if mode == "auto":
                c.addWidget(self.T(hint(), "hint_net_auto"))
            if mode == "custom":
                self.custom_edit = QLineEdit()
                self.T(self.custom_edit, "ph_proxy", "setPlaceholderText")
                self.custom_edit.editingFinished.connect(self._custom_proxy_changed)
                c.addWidget(self.custom_edit)
                c.addWidget(self.T(hint(), "hint_proxy_custom"))
        self.net_group.buttonToggled.connect(self._net_mode_changed)
        c.addSpacing(6)
        c.addWidget(self.T(QLabel(), "lbl_pool"))
        self.pool_edit = QPlainTextEdit()
        self.pool_edit.setFixedHeight(150)
        self.pool_edit.setPlaceholderText("http://1.2.3.4:8080\nsocks5h://127.0.0.1:1080")
        self.pool_timer = QTimer(self, singleShot=True, interval=800, timeout=self._pool_changed)
        self.pool_edit.textChanged.connect(lambda: self.pool_timer.start())
        c.addWidget(self.pool_edit)
        row = QHBoxLayout()
        self.pool_check_btn = self.T(QPushButton(), "btn_pool_check")
        self.pool_check_btn.clicked.connect(self._pool_check)
        self.pool_reset_btn = self.T(QPushButton(), "btn_pool_reset")
        self.pool_reset_btn.clicked.connect(self._pool_reset)
        row.addWidget(self.pool_check_btn)
        row.addWidget(self.pool_reset_btn)
        row.addStretch(1)
        c.addLayout(row)
        self.pool_status = hint()
        c.addWidget(self.pool_status)
        c.addWidget(self.T(hint(), "hint_pool_safety"))
        c.addSpacing(6)
        row = QHBoxLayout()
        self.net_btn = self.T(QPushButton(), "btn_net_check")
        self.net_btn.clicked.connect(self._net_check)
        row.addWidget(self.net_btn)
        self.net_status = QLabel()
        self.net_status.setWordWrap(True)
        row.addWidget(self.net_status, 1)
        c.addLayout(row)
        c.addStretch(1)
        grid.addWidget(card, 0, 1, 3, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(3, 1)
        return scroll

    # ------------------------------------------------------------ настройки ↔ окно

    def _load_ui_from_cfg(self):
        cfg = self.cfg
        idx = max(0, [c for c, _ in LANGS].index(cfg["language"]) if cfg["language"] in [c for c, _ in LANGS] else 0)
        self.lang_combo.blockSignals(True)
        self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.blockSignals(False)
        self.tags_edit.setText(cfg["last_query"] or "")
        self.folder_edit.setText(cfg["output_dir"])
        i = self.rating_combo.findData(cfg["rating"] or "")
        self.rating_combo.setCurrentIndex(max(0, i))
        self.media_buttons.get(cfg["media"], self.media_buttons["all"]).setChecked(True)
        self.limit_spin.setValue(int(cfg["limit"] or 0))
        self.split_chk.setChecked(bool(cfg["split_by_type"]))
        self.skip_chk.setChecked(bool(cfg["skip_existing"]))
        self.no_ai_chk.blockSignals(True)
        self.no_ai_chk.setChecked(bool(cfg["no_ai"]))
        self.no_ai_chk.blockSignals(False)
        self.nick_edit.setText(cfg["account_name_manual"] or "")
        if cfg["user_id"] and cfg.api_key:
            self.api_edit.blockSignals(True)
            self.api_edit.setText(f"&api_key={cfg.api_key}&user_id={cfg['user_id']}")
            self.api_edit.blockSignals(False)
            self._show_parsed(cfg["user_id"], cfg.api_key)
        self.threads_spin.setValue(int(cfg["threads"] or 3))
        self.delay_spin.setValue(float(cfg["delay"] if cfg["delay"] is not None else 0.3))
        self.net_radios.get(cfg["proxy_mode"], self.net_radios["auto"]).setChecked(True)
        self.custom_edit.setText(cfg.proxy_url)
        self.pool_edit.blockSignals(True)
        self.pool_edit.setPlainText("\n".join(cfg.proxy_pool(self.site)))
        self.pool_edit.blockSignals(False)
        self._set_view("log" if cfg["show_log"] else "files")
        self._update_net_controls()

    def _save_ui_to_cfg(self):
        cfg = self.cfg
        cfg["last_query"] = self.tags_edit.text().strip()
        cfg["output_dir"] = self.folder_edit.text().strip()
        cfg["rating"] = self.rating_combo.currentData() or ""
        cfg["media"] = self._media()
        cfg["limit"] = self.limit_spin.value()
        cfg["split_by_type"] = self.split_chk.isChecked()
        cfg["skip_existing"] = self.skip_chk.isChecked()
        cfg["no_ai"] = self.no_ai_chk.isChecked()
        cfg.save()

    def _cfg_set(self, key, value):
        self.cfg[key] = value
        self.cfg.save()

    def _media(self):
        for value, b in self.media_buttons.items():
            if b.isChecked():
                return value
        return "all"

    def _language_changed(self, _index):
        code = self.lang_combo.currentData()
        set_language(code)
        install_qt_translator(code)
        self._cfg_set("language", code)
        self.retranslate()

    # ------------------------------------------------------------ поиск

    def _suggest(self, term, callback):
        self.async_.run(lambda: self._client().autocomplete(term),
                        lambda res, err: callback(res or []))

    def _tags_changed(self):
        self._found_cache = None
        self.found_label.setText("")
        self.tags_edit.setProperty("error", False)
        self.tags_edit.style().polish(self.tags_edit)
        self.targets_timer.start()
        if self._have_key() and not (self.job and self.job.is_running()):
            self.search_timer.start()      # пауза в наборе — показать, что найдётся

    def _spec_from_ui(self, update_only=False):
        return JobSpec(
            query=tags_from_input(self.tags_edit.text()),
            output_dir=self.folder_edit.text().strip(),
            rating=self.rating_combo.currentData() or "",
            media=self._media(),
            limit=self.limit_spin.value(),
            name_template="id",
            split_by_type=self.split_chk.isChecked(),
            skip_existing=self.skip_chk.isChecked(),
            update_only=update_only,
            threads=self.threads_spin.value(),
            delay=round(self.delay_spin.value(), 1),
            exclude=tuple(self.site.ai_tags) if self.no_ai_chk.isChecked() else (),
        )

    def _tags_error(self):
        self.tags_edit.setProperty("error", True)
        self.tags_edit.style().polish(self.tags_edit)
        self.found_label.setText(t("msg_no_tags"))
        self.tags_edit.setFocus()

    def _find(self, auto=False, page=0):
        self.search_timer.stop()
        spec = self._spec_from_ui()
        if not spec.query and not spec.rating:
            if not auto:
                self._tags_error()
            return
        if not self._have_key():
            if not auto:
                self._goto_settings(t("api_need"))
            return
        tags = spec.search_tags
        page = max(0, page)
        if auto and (tags, page) == self._last_search:
            return
        self._last_search = (tags, page)
        self._search_page = page
        self._search_spec = spec
        for b in (self.page_prev, self.page_next):
            b.setEnabled(False)
        self._search_gen += 1
        gen = self._search_gen
        self._search_busy = True
        self.found_label.setText(t("found_searching"))
        self.search_info.setText(t("found_searching"))
        if not (self.job and self.job.is_running()):
            self._set_view("search")

        def done(result, err):
            if gen != self._search_gen:
                return
            self._search_busy = False
            posts, count = result if result else ([], None)
            self._set_found(count, err)
            self._fill_search(posts, count, err, spec.media)
            if isinstance(err, AuthError) and not auto:
                self._goto_settings(t("api_bad"))

        self.async_.run(lambda: self._client().search(tags, PREVIEW_COUNT, page), done)

    def _fill_search(self, posts, count, err, media):
        self.search_grid.clear()
        self.search_grid.scrollToTop()
        self._search_items = {}
        self.post_info.setText("")
        if err is not None:
            self.search_info.setText(t("found_error", err=self._err_text(err)))
            return
        shown = [p for p in posts if p.matches(media)]
        if not shown:
            self.search_info.setText(t("search_nothing"))
            self.page_label.setText("")
            self.page_prev.setEnabled(self._search_page > 0)
            return
        self._downloaded = downloaded_ids(self._search_spec.folder)
        self._search_count = count
        pages = max(1, -(-count // PREVIEW_COUNT)) if count is not None else None
        self.page_label.setText(t("page_label", n=self._search_page + 1, total=pages or "?"))
        self.page_prev.setEnabled(self._search_page > 0)
        self.page_next.setEnabled(len(posts) >= PREVIEW_COUNT and (pages is None or self._search_page + 1 < pages))
        info = t("search_info", total=fmt_num(count if count is not None else len(posts)))
        if len(shown) < len(posts):
            info += " " + t("search_info_media")
        no_url = sum(1 for p in posts if not p.file_url)
        self.search_info.setToolTip(t("msg_no_url_" + self.site.key, n=no_url) if no_url else "")
        if no_url:
            info += "\n" + t("search_no_url", n=no_url)
        self.search_info.setText(info)
        gen = self._search_gen
        for post in shown:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, post.id)
            item.setIcon(self._blank_icon)
            self.search_grid.addItem(item)
            self._search_items[post.id] = (item, post)
            item.setToolTip(self._post_tooltip(post))
            cached = self._thumb_cache.get(post.preview_url)
            if cached is not None:
                self._set_thumb(gen, post.id, cached)
            elif post.preview_url:
                self._thumbs.put((gen, post.id, post.preview_url))
        self.post_info.setText(t("info_hover"))
        self._tag_put(1, "page", gen, shown)

    def _tag_put(self, prio, job, gen, payload):
        self._tag_seq += 1
        self._tag_jobs.put((prio, self._tag_seq, job, gen, payload))

    def _tag_lookup(self, names, prio, gen):
        """Поставить теги в очередь на уточнение (0 — картинка под курсором, 2 — фоном)."""
        for n in names:
            if n in self._tag_kinds:
                continue
            if n in self._tag_queued and self._tag_queued[n] <= prio:
                continue
            self._tag_queued[n] = prio
            self._tag_put(prio, "lookup", gen, n)

    def _tag_worker(self):
        """Фоновый поток: узнаёт у сайта, какие теги — автор, персонажи, откуда
        (то же, что блоки Artist / Character / Copyright на странице поста)."""
        since_emit = 0
        while True:
            prio, _seq, job, gen, payload = self._tag_jobs.get()
            if job == "page":
                if gen != self._search_gen:
                    continue
                names = [n for p in payload for n in p.tags.split()
                         if n not in self._tag_kinds and n not in self._tag_pending]
                names = list(dict.fromkeys(names))
                kinds = {}
                if names and not self._tags_disabled:
                    try:
                        kinds = self._client().tag_kinds(names)
                    except (ApiError, AuthError):
                        self._tags_disabled = True
                    except Exception:
                        pass
                self._tag_kinds.update(kinds)
                self._tag_pending.update(n for n in names if n not in kinds)
                self.tags_ready.emit(gen)
                if not self._tags_disabled:     # остаток уточняем фоном, по одному
                    rest = [n for p in payload for n in p.tags.split() if n in self._tag_pending]
                    self._tag_lookup(list(dict.fromkeys(rest))[:200], 2, gen)
                continue
            # job == "lookup": один тег через подсказки сайта
            name = payload
            if name in self._tag_kinds or (prio > 0 and gen != self._search_gen):
                self._tag_queued.pop(name, None)
                continue
            try:
                kind = self._client().tag_kind_lookup(name)
            except Exception:
                self._tag_queued.pop(name, None)     # сеть — попробуем при следующем наведении
                continue
            self._tag_kinds[name] = kind or "general"
            self._tag_pending.discard(name)
            self._tag_queued.pop(name, None)
            since_emit += 1
            if prio == 0 or since_emit >= 8 or self._tag_jobs.empty():
                since_emit = 0
                self.tags_ready.emit(self._search_gen)
            if prio > 0:
                time.sleep(0.1)                      # фоном — не торопимся
            if len(self._tag_kinds) > 50000:
                self._tag_kinds.clear()

    def _on_tags_ready(self, gen):
        if gen != self._search_gen:
            return
        for item, post in self._search_items.values():
            try:
                item.setToolTip(self._post_tooltip(post))
            except RuntimeError:
                pass
        current = self._info_post if self._info_post in self._search_items else None
        if current is not None:
            self._show_post_info(current)
        if self._viewer is not None and self._viewer.isVisible():
            self._viewer.refresh_info()

    def _post_groups(self, post):
        """(группы тегов, состояние): состояние «loading» — тип тегов ещё не спрашивали,
        «partial» — часть уточняется, «done» — всё известно."""
        groups = {"artist": [], "character": [], "copyright": [], "other": []}
        state = "done"
        for n in post.tags.split():
            kind = self._tag_kinds.get(n)
            if kind in ("artist", "character", "copyright"):
                groups[kind].append(n)
            else:
                groups["other"].append(n)
                if kind is None:
                    state = "partial" if (n in self._tag_pending or self._tags_disabled) else "loading"
        return groups, state

    INFO_ROWS = (("artist", "info_artist", "#f87171"), ("character", "info_characters", "#4ade80"),
                 ("copyright", "info_copyright", "#c084fc"))

    def _post_tooltip(self, post):
        head = f"#{post.id}  ·  {post.ext.lstrip('.').upper()}  ·  rating: {post.rating}"
        groups, state = self._post_groups(post)
        lines = [f"{t(key)}: {', '.join(n.replace('_', ' ') for n in groups[kind])}"
                 for kind, key, _ in self.INFO_ROWS if groups[kind]]
        if state != "done":
            lines.append(t("info_loading"))
        body = "\n".join(lines) or t("info_none")
        return f"{head}\n{body}\n\n{t('tip_open_post')}"

    def _show_post_info(self, post_id):
        entry = self._search_items.get(post_id)
        if not entry:
            return
        self._info_post = post_id
        self.post_info.setText(self._post_info_html(entry[1]))

    def _post_info_html(self, post, expandable=True):
        groups, state = self._post_groups(post)
        if state == "partial":   # уточнить теги этой картинки в первую очередь
            self._tag_lookup([n for n in post.tags.split() if n not in self._tag_kinds], 0, self._search_gen)
        link = lambda n, color: (f'<a href="{html.escape(n)}" style="color:{color};text-decoration:none">'
                                 f'{html.escape(n.replace("_", " "))}</a>')
        muted = lambda text: f'<span style="color:{MUTED}">{text}</span>'
        rows = [muted(f"#{post.id} · {post.ext.lstrip('.').upper()} · rating: {html.escape(post.rating)}")]
        for kind, key, color in self.INFO_ROWS:
            if groups[kind]:
                rows.append(muted(t(key) + ":") + " " + ", ".join(link(n, color) for n in groups[kind]))
        if state != "done":
            rows.append(muted(t("info_loading")))
        elif len(rows) == 1:
            rows.append(muted(t("info_none")))
        if groups["other"] and expandable:
            if self._info_expanded:
                rows.append(muted(t("info_other") + ":") + " "
                            + ", ".join(link(n, "#60a5fa") for n in groups["other"]))
                rows.append(f'<a href="#less" style="color:{MUTED}">{t("info_less")}</a>')
            else:
                rows.append(f'<a href="#more" style="color:{MUTED}">'
                            f'{t("info_more", n=len(groups["other"]))}</a>')
        return "<br>".join(rows)

    def _search_tag(self, tag):
        """Щелчок по автору / персонажу — искать по этому тегу."""
        if tag in ("#more", "#less"):        # развернуть / свернуть остальные теги
            self._info_expanded = tag == "#more"
            if self._info_post is not None:
                self._show_post_info(self._info_post)
            return
        if self.job and self.job.is_running():
            return
        self.tags_edit.setText(tag)
        self._find()

    def _selected_posts(self):
        return [self._search_items[it.data(Qt.UserRole)][1] for it in self.search_grid.selectedItems()
                if it.data(Qt.UserRole) in self._search_items]

    def _grid_menu(self, pos):
        item = self.search_grid.itemAt(pos)
        if item is None:
            return
        if not item.isSelected():
            self.search_grid.clearSelection()
            item.setSelected(True)
        posts = self._selected_posts()
        post = self._search_items[item.data(Qt.UserRole)][1]
        menu = QMenu(self)
        label = t("menu_download") if len(posts) == 1 else t("menu_download_n", n=len(posts))
        menu.addAction(label, lambda: self._download_posts(posts))
        menu.addAction(t("menu_view"), lambda: self._open_viewer(post.id))
        menu.addSeparator()
        menu.addAction(t("menu_open_site"), lambda: QDesktopServices.openUrl(QUrl(self.site.post_url.format(id=post.id))))
        menu.addAction(t("menu_copy_link"), lambda: QApplication.clipboard().setText(self.site.post_url.format(id=post.id)))
        menu.exec(self.search_grid.viewport().mapToGlobal(pos))

    def _download_posts(self, posts, data=None):
        """Скачать выбранные арты в папку загрузки — туда же, куда качает «Скачать»."""
        spec = self._search_spec or self._spec_from_ui()
        if not spec.output_dir:
            QMessageBox.warning(self, self.windowTitle(), t("msg_no_folder"))
            return
        for post in posts:
            if not post.file_url:
                self._append_log(t("single_no_url", id=post.id), "warn")
                self.statusBar().showMessage(t("single_no_url", id=post.id), 8000)
                continue
            path = file_path(spec, post)
            if os.path.exists(path):
                self._single_done(spec, post, path, None, existed=True)
                continue
            self.statusBar().showMessage(t("single_started", id=post.id), 4000)

            def run(post=post, path=path):
                with self._single_sem:      # не больше трёх файлов разом
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    if data is not None:
                        tmp = path + ".part"
                        with open(tmp, "wb") as f:
                            f.write(data)
                        os.replace(tmp, path)
                        return len(data)
                    size, _md5 = call_with_retries(
                        lambda: self._client().download(post, path, threading.Event()),
                        threading.Event(), delays=FILE_DELAYS, max_attempts=3, max_offline_attempts=3)
                    return size

            self.async_.run(run, lambda size, err, post=post, path=path: self._single_done(spec, post, path, err))

    def _single_done(self, spec, post, path, err, existed=False):
        name = os.path.basename(path)
        if err is not None:
            msg = t("single_failed", id=post.id, err=self._err_text(err))
            self._append_log(msg, "error")
            self.statusBar().showMessage(msg, 10000)
            return
        try:
            if post.id not in downloaded_ids(spec.folder):
                mark_downloaded(spec.folder, post.id)
        except OSError:
            pass
        if spec.folder == (self._search_spec.folder if self._search_spec else None):
            self._downloaded.add(post.id)
            img = self._thumb_cache.get(post.preview_url)
            if img is not None:
                self._set_thumb(self._search_gen, post.id, img)
        msg = t("single_exists" if existed else "single_saved", name=name)
        self._append_log(msg, "ok")
        self.statusBar().showMessage(msg, 6000)
        if not existed:
            self._add_file({"path": path, "post_id": post.id, "is_video": post.is_video, "size": 0})

    def _open_viewer(self, post_id):
        posts = [self._search_items[self.search_grid.item(i).data(Qt.UserRole)][1]
                 for i in range(self.search_grid.count())]
        index = next((i for i, p in enumerate(posts) if p.id == post_id), 0)
        if not posts:
            return
        if self._viewer is None:
            self._viewer = PostViewer(self)
        self._viewer.show_posts(posts, index)

    def eventFilter(self, obj, event):
        if obj is self.search_grid.viewport() and event.type() == QEvent.Leave:
            item = self.search_grid.currentItem()
            if item is not None:
                self._show_post_info(item.data(Qt.UserRole))
        return super().eventFilter(obj, event)

    def _thumb_worker(self):
        """Фоновые потоки: качают миниатюры для предпросмотра."""
        while True:
            gen, post_id, url = self._thumbs.get()
            if gen != self._search_gen:
                continue                     # поиск уже сменился
            try:
                data = self._client().fetch_bytes(url)
                img = QImage.fromData(data)
                if img.isNull():
                    continue
                img = img.scaled(PREVIEW_SIZE, PREVIEW_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            except Exception:
                continue
            self.thumb_ready.emit(gen, post_id, url, img)

    def _on_thumb(self, gen, post_id, url, img):
        self._thumb_cache[url] = img
        while len(self._thumb_cache) > 400:
            self._thumb_cache.pop(next(iter(self._thumb_cache)))
        self._set_thumb(gen, post_id, img)

    def _set_thumb(self, gen, post_id, img):
        if gen != self._search_gen or post_id not in self._search_items:
            return
        item, post = self._search_items[post_id]
        is_video = post.is_video
        canvas = QPixmap(PREVIEW_SIZE, PREVIEW_SIZE)
        canvas.fill(Qt.transparent)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawImage((PREVIEW_SIZE - img.width()) // 2, (PREVIEW_SIZE - img.height()) // 2, img)
        if post.id in self._downloaded:    # уже скачан — галочка в углу
            p.setBrush(QColor(0, 0, 0, 170))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(PREVIEW_SIZE - 28, 4, 24, 22, 6, 6)
            p.setPen(QColor("#4ade80"))
            p.drawText(PREVIEW_SIZE - 28, 4, 24, 22, Qt.AlignCenter, "✓")
        if is_video:                       # значок «видео» в углу
            p.setBrush(QColor(0, 0, 0, 170))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(PREVIEW_SIZE - 34, PREVIEW_SIZE - 26, 30, 22, 6, 6)
            p.setPen(QColor(self.site.accent))
            p.drawText(PREVIEW_SIZE - 34, PREVIEW_SIZE - 26, 30, 22, Qt.AlignCenter, "▶")
        p.end()
        try:
            item.setIcon(QIcon(canvas))
        except RuntimeError:               # элемент уже удалён
            pass

    def _set_found(self, count, err):
        self._found_cache = (count, err)
        if err is not None:
            self.found_label.setText(t("found_error", err=self._err_text(err)))
        elif count is None:
            self.found_label.setText(t("found_unknown"))
        else:
            self.found_label.setText(t("found_n", n=fmt_num(count)))

    def _refresh_targets(self):
        spec = self._spec_from_ui()
        running = bool(self.job and self.job.is_running())
        if (spec.query or spec.rating) and spec.output_dir:
            self.target_hint.setText(t("hint_target", path=spec.folder))
            state = load_task(spec)
            can_resume = bool(state and state.get("site") == self.site.key)
            can_update = os.path.exists(os.path.join(spec.folder, IDS_FILE))
        else:
            self.target_hint.setText(t("hint_subfolder"))
            can_resume = can_update = False
        self.resume_btn.setEnabled(can_resume and not running)
        self.update_btn.setEnabled(can_update and not running)
        self.start_btn.setEnabled(not running)

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, t("btn_choose"), self.folder_edit.text() or os.path.expanduser("~"))
        if folder:
            self.folder_edit.setText(os.path.normpath(folder))

    def _open_target_folder(self):
        spec = self._spec_from_ui()
        folder = spec.folder if (spec.query or spec.rating) and os.path.isdir(spec.folder) else spec.output_dir
        if folder:
            os.makedirs(folder, exist_ok=True)
            open_path(folder)

    # ------------------------------------------------------------ загрузка

    def _start(self, update_only=False, resume=False):
        if self.job and self.job.is_running():
            return
        if not self._have_key():
            self._goto_settings(t("api_need"))
            return
        spec = self._spec_from_ui(update_only)
        state = None
        if resume:
            state = load_task(spec)
            if not state or state.get("site") != self.site.key:
                self._refresh_targets()
                return
            saved = JobSpec.from_dict(state.get("spec"))
            saved.threads, saved.delay = spec.threads, spec.delay
            spec = saved
        if not spec.query and not spec.rating:
            self._tags_error()
            return
        if not spec.output_dir:
            QMessageBox.warning(self, self.windowTitle(), t("msg_no_folder"))
            return
        self._save_ui_to_cfg()
        session = make_session(self.site, self.cfg["proxy_mode"], self.cfg.proxy_url, pool=spec.threads + 4)
        client = self._client(session=session)
        self.job = Job(self.site, spec, client,
                              lambda kind, **data: self.bridge.event.emit(kind, data), state)
        self.job_spec = spec
        self._bytes_hist.clear()
        self._value_hist.clear()
        self._append_log("—" * 30, "info")
        self.job.start()
        self._set_running(True)
        self.search_timer.stop()
        self._set_view("files")
        self.progress_timer.start()

    def _stop(self):
        if self.job and self.job.is_running():
            self.job.stop()
            self.stop_btn.setEnabled(False)
            self.status_label.setText(t("status_stopping"))

    def _set_running(self, running):
        for w in (self.tags_edit, self.find_btn, self.rating_combo, self.limit_spin, self.folder_edit,
                  self.split_chk, self.skip_chk, self.no_ai_chk, *self.media_buttons.values()):
            w.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        for rb in self.net_radios.values():
            rb.setEnabled(not running)
        self._refresh_targets()

    def _tick(self):
        if self.job:
            self._render_progress(self.job.snapshot())

    def _render_progress(self, snap, final=False):
        limit, found = snap["limit"], snap["found"]
        if limit:
            maximum = min(limit, found) if found is not None else limit
            value = snap["downloaded"]
        elif found is not None:
            maximum, value = found, snap["processed"]
        else:
            maximum, value = 0, 0
        if final and maximum == 0:
            maximum = value = 1
        self.bar.setRange(0, maximum)
        if maximum:
            self.bar.setValue(min(value, maximum))
            self.bar.setFormat(f"{fmt_num(min(value, maximum))} / {fmt_num(maximum)}")
        counts = t("prog_counts", d=fmt_num(snap["downloaded"]), s=fmt_num(snap["skipped"]), f=fmt_num(snap["failed"]))
        if snap.get("filtered"):
            counts += t("prog_filtered", x=fmt_num(snap["filtered"]))
        self.counts_label.setText(counts)

        now = time.monotonic()
        self._bytes_hist.append((now, snap["bytes"]))
        self._value_hist.append((now, value))
        parts = []
        if not final:
            t0, b0 = self._bytes_hist[0]
            if now - t0 > 1:
                parts.append(t("prog_speed", speed=human_size((snap["bytes"] - b0) / (now - t0))))
            v_t0, v0 = self._value_hist[0]
            if maximum and value > v0 and now - v_t0 > 3:
                rate = (value - v0) / (now - v_t0)
                parts.append(t("prog_eta", eta=human_time((maximum - value) / rate)))
        parts.append(t("prog_total_size", size=human_size(snap["bytes"])))
        self.speed_label.setText("  ·  ".join(parts))

        wait = snap.get("wait")
        if wait and not final:
            left = max(0, int(wait["until"] - time.monotonic()))
            key = "wait_offline" if wait.get("offline") else "wait_server"
            text = t(key, s=left, n=wait["attempt"], err=self._err_text(wait["code"], wait.get("detail", "")))
            if wait.get("offline") and self.cfg["proxy_mode"] != "auto":
                text += " " + t("hint_try_auto")
            self.status_label.setObjectName("warn")
            self.status_label.setText(text)
        else:
            key, params = snap["status"]
            self.status_label.setObjectName("muted")
            self.status_label.setText(t(key, **params))
        self.status_label.style().polish(self.status_label)

    def _finished(self, data):
        self.progress_timer.stop()
        outcome, st = data["outcome"], data["stats"]
        self._render_progress(st, final=True)
        err = self._err_text(data.get("code", ""), data.get("detail", "")) if data.get("code") else ""
        fmt = dict(d=fmt_num(st["downloaded"]), s=fmt_num(st["skipped"]), f=fmt_num(st["failed"]), err=err)
        msg = t("msg_finished_" + outcome, **fmt)
        level = {"done": "ok", "stopped": "warn", "paused": "warn"}.get(outcome, "error")
        self._append_log(msg, level)
        self.status_label.setObjectName({"ok": "ok", "warn": "warn"}.get(level, "error"))
        self.status_label.setText(msg)
        self.status_label.style().polish(self.status_label)
        self.statusBar().showMessage(msg, 15000)
        if st.get("no_url"):
            note = t("msg_no_url_" + self.site.key, n=fmt_num(st["no_url"]))
            self._append_log(note, "warn")
            self.status_label.setText(msg + "\n" + note)
            self.api_banner.setText(note)
            self.api_banner.setVisible(True)
        spec = self.job_spec
        if spec and (st["downloaded"] or outcome == "done"):
            self.history.record(spec.query or f"rating:{spec.rating}", spec.output_dir, spec.folder_name,
                                st["downloaded"], data.get("total", 0), spec.rating, spec.media)
            self._refresh_history()
        if outcome == "auth":
            self._goto_settings(t("api_bad"))
        self._set_running(False)
        if not self.isActiveWindow():
            QApplication.alert(self)

    # ------------------------------------------------------------ события задачи

    def _on_event(self, kind, data):
        if kind == "log":
            self._append_log(self._fmt_log(data["key"], data.get("params", {})), data.get("level", "info"))
        elif kind == "file":
            self._add_file(data)
        elif kind == "finished":
            self._finished(data)
        elif kind == "route_state":
            self.cfg["route_state"] = data["state"]
            self.cfg.save()
            self._refresh_conn_label()

    ERR_DETAIL = {"server_message", "auth_server", "bad_response", "http_error", "not_media", "file_error",
                  "internal", "incomplete", "auth_http", "rate_limited", "server_busy", "proxy_invalid", "blocked"}

    def _err_text(self, code, detail=""):
        if isinstance(code, BooruError):
            code, detail = code.code, code.detail
        elif isinstance(code, Exception):
            return self.redact(str(code))[:200]
        text = t("err_" + code) if has("err_" + code) else code
        if detail and code in self.ERR_DETAIL:
            text += f" ({detail})"
        return text

    def _fmt_log(self, key, params):
        p = dict(params)
        if "code" in p:
            p["code"] = self._err_text(p.pop("code"), p.pop("detail", ""))
        if "size" in p:
            p["size"] = human_size(p["size"])
        for k in ("count", "downloaded"):
            if isinstance(p.get(k), int):
                p[k] = fmt_num(p[k])
        return t(key, **p)

    def _append_log(self, text, level="info"):
        color = {"ok": "#86efac", "warn": "#fbbf24", "error": "#f87171"}.get(level, "#cbd5e1")
        stamp = time.strftime("%H:%M:%S")
        self.log_box.appendHtml(f'<span style="color:#6b7486">{stamp}</span> '
                                f'<span style="color:{color}">{html.escape(text)}</span>')

    VIEWS = {"files": (0, "card_preview"), "log": (1, "card_log"), "search": (2, "card_results")}

    def _set_view(self, name):
        index, title = self.VIEWS[name]
        self.view_stack.setCurrentIndex(index)
        self.view_buttons[name].setChecked(True)
        self.view_title.setText(t(title))
        self.cfg["show_log"] = name == "log"

    # ------------------------------------------------------------ превью

    def _add_file(self, data):
        path, is_video = data["path"], data["is_video"]
        ext = os.path.splitext(path)[1]
        item = QListWidgetItem()
        item.setData(Qt.UserRole, data)
        item.setToolTip(os.path.basename(path))
        self.thumbs.insertItem(0, item)
        while self.thumbs.count() > MAX_THUMBS:
            self.thumbs.takeItem(self.thumbs.count() - 1)
        if is_video:
            item.setIcon(QIcon(QPixmap.fromImage(video_placeholder(80, 80, ext, self.site.accent))))
        else:
            def set_icon(img, err, item=item):
                try:
                    if img is not None:
                        item.setIcon(QIcon(QPixmap.fromImage(img)))
                except RuntimeError:      # элемент уже убран из списка
                    pass
            self.async_.run(lambda: load_image(path, 160, 160), set_icon)
        self._pending_preview = data
        if time.monotonic() >= self._pinned_until and not self.preview_timer.isActive():
            self.preview_timer.start()

    def _show_pending_preview(self):
        if self._pending_preview and time.monotonic() >= self._pinned_until:
            self._show_file(self._pending_preview)

    def _thumb_clicked(self, item):
        self._pinned_until = time.monotonic() + 15     # не перебивать выбранный файл новыми
        self._show_file(item.data(Qt.UserRole))

    def _show_file(self, data):
        self._current_file = data
        path = data["path"]
        name = os.path.basename(path)
        self.file_name.setText(name)
        for b in (self.file_open_btn, self.file_dir_btn, self.file_post_btn):
            b.setEnabled(True)
        if not os.path.isfile(path):
            self.image_view.clear_image(t("preview_missing"))
            return
        ext = os.path.splitext(path)[1].lower()
        if data.get("is_video"):
            self.image_view.set_image(video_placeholder(480, 360, ext, self.site.accent))
            return
        w, h = max(600, self.image_view.width() * 2), max(600, self.image_view.height() * 2)

        def done(img, err, path=path):
            if not self._current_file or self._current_file["path"] != path:
                return
            if img is None:
                self.image_view.clear_image(t("preview_unavailable") + "\n" + name)
            else:
                self.image_view.set_image(img)

        self.async_.run(lambda: load_image(path, min(w, 2000), min(h, 2000)), done)

    def _open_post(self):
        if self._current_file:
            QDesktopServices.openUrl(QUrl(self.site.post_url.format(id=self._current_file["post_id"])))

    # ------------------------------------------------------------ история

    def _refresh_history(self):
        items = list(reversed(self.history.items))
        self.history_table.setRowCount(len(items))
        for row, h in enumerate(items):
            query = h.get("query") or t("hist_any_tags")
            if h.get("rating"):
                query += f"  · rating:{h['rating']}"
            if h.get("media") and h["media"] != "all":
                query += "  · " + t("media_" + h["media"])
            cells = [query, f"{fmt_num(h.get('last_count', 0))} / {fmt_num(h.get('total', 0))}",
                     h.get("date", ""), os.path.join(h.get("output_dir", ""), h.get("folder", "")) if h.get("output_dir") else "—"]
            for col, text in enumerate(cells):
                it = QTableWidgetItem(text)
                it.setData(Qt.UserRole, h)
                self.history_table.setItem(row, col, it)
        self.history_empty.setVisible(not items)
        self._history_selection()

    def _history_entry(self):
        rows = self.history_table.selectionModel().selectedRows() if self.history_table.selectionModel() else []
        if not rows:
            return None
        it = self.history_table.item(rows[0].row(), 0)
        return it.data(Qt.UserRole) if it else None

    def _history_selection(self):
        h = self._history_entry()
        for b in (self.h_use, self.h_update, self.h_folder, self.h_remove):
            b.setEnabled(h is not None)
        if h is not None:
            self.h_update.setEnabled(bool(h.get("output_dir")) and not (self.job and self.job.is_running()))

    def _history_fill(self, h):
        self.tags_edit.setText(h.get("query", ""))
        if h.get("output_dir"):
            self.folder_edit.setText(h["output_dir"])
        i = self.rating_combo.findData(h.get("rating", ""))
        self.rating_combo.setCurrentIndex(max(0, i))
        self.media_buttons.get(h.get("media", "all"), self.media_buttons["all"]).setChecked(True)
        self.tabs.setCurrentIndex(0)
        self._refresh_targets()

    def _history_use(self):
        h = self._history_entry()
        if h and not (self.job and self.job.is_running()):
            self._history_fill(h)

    def _history_update(self):
        h = self._history_entry()
        if h and not (self.job and self.job.is_running()):
            self._history_fill(h)
            self._start(update_only=True)

    def _history_folder(self):
        h = self._history_entry()
        if h and h.get("output_dir"):
            path = os.path.join(h["output_dir"], h.get("folder", ""))
            open_path(path if os.path.isdir(path) else h["output_dir"])

    def _history_remove(self):
        h = self._history_entry()
        if h:
            self.history.remove(h)
            self._refresh_history()

    # ------------------------------------------------------------ ключ API

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            self._clipboard_check()     # вернулись в программу после копирования на сайте

    def _clipboard_check(self):
        try:
            text = QApplication.clipboard().text()
        except RuntimeError:
            return
        if not text or len(text) > 2000 or "api_key=" not in text:
            return
        uid, key = parse_api_line(text)
        if not (uid and key) or (uid, key) == self._clip_taken:
            return
        self._clip_taken = (uid, key)
        if (uid, key) == (self.cfg["user_id"], self.cfg.api_key):
            return
        self.api_edit.setText(f"&api_key={key}&user_id={uid}")   # дальше — обычная автопроверка
        self._set_api_status(t("api_from_clipboard"), "muted")
        if not (self.job and self.job.is_running()):
            self.tabs.setCurrentIndex(2)

    def _goto_settings(self, banner=""):
        self.tabs.setCurrentIndex(2)
        if banner:
            self.api_banner.setText(banner)
            self.api_banner.setVisible(True)
        self.api_edit.setFocus()

    def _show_parsed(self, uid, key):
        if uid and key:
            self.api_parsed.setText(t("api_parsed", uid=uid, tail=key[-4:]))
        elif self.api_edit.text().strip():
            self.api_parsed.setText(t("api_missing"))
        else:
            self.api_parsed.setText("")

    def _api_text_changed(self, text):
        uid, key = parse_api_line(text)
        self._show_parsed(uid, key)
        if self.api_status.text() != t("api_from_clipboard"):
            self.api_status.setText("")
        # вставили правильную строку — сразу проверяем и сохраняем, без кнопки
        if uid and key and (uid, key) != (self.cfg["user_id"], self.cfg.api_key):
            self.api_timer.start()
        else:
            self.api_timer.stop()

    def _set_api_status(self, text, kind):
        self.api_status.setObjectName(kind)
        self.api_status.setText(text)
        self.api_status.style().polish(self.api_status)

    def _check_key(self, auto=False):
        self.api_timer.stop()
        uid, key = parse_api_line(self.api_edit.text())
        if not uid or not key:
            if not auto:
                self._set_api_status(t("api_missing"), "error")
            return
        self.cfg["user_id"] = uid
        self.cfg.api_key = key
        self.cfg.save()
        self.redact.add(key)
        self._set_api_status(t("api_checking"), "muted")
        self.api_btn.setEnabled(False)

        def done(_res, err):
            self.api_btn.setEnabled(True)
            if isinstance(err, AuthError):
                self._set_api_status(t("api_bad"), "error")
                self.api_banner.setText(t("api_bad"))
                self.api_banner.setVisible(True)
            elif err is not None:
                self._set_api_status(t("api_check_fail", err=self._err_text(err)), "warn")
                self.api_banner.setVisible(False)
            else:
                self._set_api_status(t("api_saved_ok"), "ok")
                self._resolve_account(force=True)
                self.api_banner.setVisible(False)
            self._refresh_conn_label()

        self.async_.run(lambda: self._client(user_id=uid, api_key=key).check_key(), done)

    # ------------------------------------------------------------ подключение

    def _update_net_controls(self):
        mode = self._net_mode()
        self.custom_edit.setEnabled(mode == "custom")
        for w in (self.pool_edit, self.pool_check_btn, self.pool_reset_btn):
            w.setEnabled(mode == "auto")

    def _net_mode(self):
        for mode, rb in self.net_radios.items():
            if rb.isChecked():
                return mode
        return "auto"

    def _net_mode_changed(self, _button, checked):
        if not checked:
            return
        mode = self._net_mode()
        self._update_net_controls()
        if mode != self.cfg["proxy_mode"]:
            self._cfg_set("proxy_mode", mode)
            self._make_router()
            self._refresh_conn_label()
            self.net_status.setText("")

    def _custom_proxy_changed(self):
        url = normalize_proxy(self.custom_edit.text())
        if url != self.cfg.proxy_url:
            self.cfg.proxy_url = url
            self.cfg.save()
            if url:
                self.redact.add(url)
            self._make_router()

    def _pool_changed(self):
        pool = parse_proxy_list(self.pool_edit.toPlainText())
        builtin = builtin_proxies(self.site)
        self._cfg_set("proxy_pool", None if pool == builtin else pool)
        self.router.pool = pool
        self.pool_status.setText(t("pool_count", n=len(pool)))

    def _pool_reset(self):
        self.pool_edit.setPlainText("\n".join(builtin_proxies(self.site)))
        self._pool_changed()

    def _pool_check(self):
        pool = parse_proxy_list(self.pool_edit.toPlainText())
        if not pool:
            return
        host = self.site.api_url.split("/")[2]
        self.pool_check_btn.setEnabled(False)
        self.pool_status.setText(t("pool_checking", n=len(pool)))

        def done(results, err):
            self.pool_check_btn.setEnabled(True)
            if err or not results:
                self.pool_status.setText(t("net_fail", err=self._err_text(err)) if err else "")
                return
            alive = sorted((r for r in results if r[1] is not None), key=lambda r: r[1])
            dead = [p for p, ms in results if ms is None]
            lines = [f"{p}    # {ms} ms" for p, ms in alive] + [f"{p}    # {t('pool_dead')}" for p in dead]
            self.pool_edit.setPlainText("\n".join(lines))
            self._pool_changed()
            self.pool_status.setText(t("pool_result", ok=len(alive), n=len(results)))

        self.async_.run(lambda: probe_all(pool, f"https://{host}/"), done)

    def _net_check(self):
        self.net_btn.setEnabled(False)
        self.net_status.setObjectName("muted")
        self.net_status.setText(t("net_checking"))
        self.net_status.style().polish(self.net_status)
        client = self._client()

        def run():
            t0 = time.monotonic()
            client._get(self.site.api_url, timeout=(8, 15)).close()
            return round((time.monotonic() - t0) * 1000)

        def done(ms, err):
            self.net_btn.setEnabled(True)
            if err is not None:
                self.net_status.setObjectName("error")
                self.net_status.setText(t("net_fail", err=self._err_text(err)))
            else:
                self.net_status.setObjectName("ok")
                self.net_status.setText(t("net_ok", ms=ms, route=self._route_text()))
            self.net_status.style().polish(self.net_status)
            self._refresh_conn_label()

        self.async_.run(run, done)

    def _route_text(self):
        mode = self.cfg["proxy_mode"]
        if mode == "custom" and self.cfg.proxy_url:
            return t("route_custom", proxy=proxy_label(self.cfg.proxy_url))
        info = self.router.describe()
        host = self.site.api_url.split("/")[2]
        if mode == "auto" and host in info["blocked"] and info["current"]:
            return t("route_proxy", proxy=info["current"])
        return t("route_direct")

    def _fill_browsers(self):
        self.browser_combo.clear()
        for path, name in find_browsers():
            self.browser_combo.addItem(name, path)
        if not self.browser_combo.count():
            self.browser_combo.addItem(t("login_no_browser_short"), "")
        i = self.browser_combo.findData(self.cfg["login_browser"])
        self.browser_combo.setCurrentIndex(max(0, i))
        self.browser_combo.currentIndexChanged.connect(
            lambda _: self._cfg_set("login_browser", self.browser_combo.currentData() or ""))

    def _open_login_browser(self):
        """Сайт открывается в установленном браузере: человек входит сам, ключ и настройки — сами."""
        session = getattr(self, "_login_session", None)
        if session is not None and not session.stop_event.is_set() and self._login_dialog is not None:
            self._login_dialog.show()
            self._login_dialog.raise_()
            return
        exe, name = self.browser_combo.currentData() or "", self.browser_combo.currentText()
        if not exe:
            QMessageBox.information(self, self.windowTitle(), t("login_no_browser"))
            QDesktopServices.openUrl(QUrl(self.site.options_url))     # старый путь: страница + буфер обмена
            return
        self.login_browser_btn.setEnabled(False)
        self._set_api_status(t("login_preparing"), "muted")
        client = self._client()
        host = self.site.site_url.split("/")[2]

        def decide():                 # нужен ли браузеру прокси: тот же выбор, что у программы
            mode = self.cfg["proxy_mode"]
            if mode == "custom":
                return self.cfg.proxy_url or ""
            if mode != "auto":
                return ""
            try:
                client._get(self.site.options_url, timeout=(6, 12)).close()
            except Exception:
                pass
            info = self.router.state()
            return info["current"] if host in info["blocked"] and info["current"] else ""

        def start(proxy, err):
            self._set_api_status("", "muted")
            dlg = LoginStatus(self, name)
            session = BrowserSession(self.site, exe, str(data_dir(self.site) / "browser-profile"),
                                             proxy or "")
            session.status.connect(dlg.set_status)
            session.key_found.connect(self._login_key_found)
            session.finished.connect(lambda result: self._login_finished(result, dlg))
            dlg.cancel_btn.clicked.connect(session.cancel)
            self._login_session, self._login_dialog = session, dlg
            dlg.set_status(t("login_starting", browser=name))
            dlg.show()
            session.start()

        self.async_.run(decide, start)

    def _login_finished(self, result, dlg):
        self.login_browser_btn.setEnabled(True)
        self._login_session = None
        if result in ("done", "cancelled"):
            QTimer.singleShot(1500 if result == "done" else 0, dlg.close)
        else:
            dlg.cancel_btn.setText(t("btn_login_close"))
            try:
                dlg.cancel_btn.clicked.disconnect()
            except (RuntimeError, TypeError):
                pass
            dlg.cancel_btn.clicked.connect(dlg.close)

    def _login_key_found(self, uid, key):
        self.redact.add(key)
        self.api_edit.setText(f"&api_key={key}&user_id={uid}")      # дальше — обычная автопроверка
        self._set_api_status(t("login_got_key"), "ok")

    def _nick_changed(self):
        self._cfg_set("account_name_manual", self.nick_edit.text().strip())
        self._refresh_account()

    def _resolve_account(self, force=False):
        """Узнать ник владельца ключа (для подписи в углу окна)."""
        uid = self.cfg["user_id"]
        if not self._have_key() or (not force and self.cfg["account_uid"] == uid and self.cfg["account_name"]):
            self._refresh_account()
            return

        def done(name, err):
            if name and self.cfg["user_id"] == uid:
                self.cfg["account_name"], self.cfg["account_uid"] = name, uid
                self.cfg.save()
            self._refresh_account()

        self.async_.run(lambda: self._client().account_name(), done)

    def _refresh_account(self):
        uid = self.cfg["user_id"]
        if not self._have_key():
            self.account_label.setText(t("footer_no_key"))
            return
        name = self.cfg["account_name_manual"] or (
            self.cfg["account_name"] if self.cfg["account_uid"] == uid else "") or f"ID {uid}"
        self.account_label.setText(t("footer_account", name=name))

    def _refresh_conn_label(self):
        self.conn_label.setText("🌐 " + self._route_text())

    # ------------------------------------------------------------ закрытие

    def _close_browser(self):
        """При выходе — закрыть окно браузера, открытое для входа."""
        session = getattr(self, "_login_session", None)
        if session is not None:
            session.cancel()
            time.sleep(0.3)

    def closeEvent(self, event):
        if self.job and self.job.is_running():
            answer = QMessageBox.question(self, self.windowTitle(), t("msg_running_close"))
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.job.stop()
            deadline = time.monotonic() + 6
            while self.job.is_running() and time.monotonic() < deadline:
                QApplication.processEvents()
                self.job.thread.join(0.05)
        self._close_browser()
        self._save_ui_to_cfg()
        self.cfg["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        self.cfg.save()
        event.accept()


# ====================================================================== app: Запуск окна.

def run(site):
    if os.name == "nt":
        try:   # своя иконка на панели задач, а не значок Python
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"booru.{site.key}.downloader")
        except Exception:
            pass
    if os.environ.get("BOORU_SMOKE_SHOT"):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"   # самопроверка — окно на экран не выводим
        if os.environ.get("BOORU_SMOKE_FONTDIR"):
            os.environ["QT_QPA_FONTDIR"] = os.environ["BOORU_SMOKE_FONTDIR"]
    splash = None
    try:                 # заставка exe-файла (PyInstaller): показывается ещё до запуска Python
        import pyi_splash
        splash = pyi_splash
        splash.update_text("")
    except ImportError:
        pass
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName(site.app_name)
    app.setStyle("Fusion")
    app.setPalette(palette(site))
    app.setStyleSheet(stylesheet(site))
    win = MainWindow(site)
    win.show()
    if splash:
        try:
            splash.close()
        except Exception:
            pass
    shot = os.environ.get("BOORU_SMOKE_SHOT")
    if shot:   # самопроверка сборки: снимок окна (и проверка сети) без участия человека
        from PySide6.QtCore import QTimer
        if os.environ.get("BOORU_SMOKE_NET"):
            QTimer.singleShot(500, lambda: (win.tabs.setCurrentIndex(2), win._net_check()))
        if os.environ.get("BOORU_SMOKE_LOGIN"):
            QTimer.singleShot(800, win._open_login_browser)
        def finish():
            win.grab().save(shot)
            with open(shot + ".txt", "w", encoding="utf-8") as f:
                for name in ("conn_label", "net_status", "api_status", "status_label", "found_label"):
                    f.write(f"{name}: {getattr(win, name).text()}\n")
                dlg = getattr(win, "_login_dialog", None)
                if dlg is not None:
                    f.write(f"login: {dlg.status.text()}\n")
            app.quit()
        QTimer.singleShot(int(os.environ.get("BOORU_SMOKE_DELAY", "3000")), finish)
    return app.exec()


# ====================================================================== встроенные файлы: иконка, заставка, список прокси

EMBEDDED.update({
    "r34.ico": (
        "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"
    ),
    "splash.png": (
        "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"
        "Qk1TUeFIftTR1S4t4yKEunYx/ffSaYFQuH7jtklTZ41xnyIUCqXWvXP3kfuYUWQyeeyYkTdu32t0+18ss2X7rjHjpk6eNuvw"
        "EY+RI4csX7Kgmdp+P5o5282curKKcoSQssSPGEVFxWb20tQ3cUFhgTKn3i8hNpvdaEnQgbVpyLo4O5HJ5PT0DIRQ/359rly9"
        "8eDRk9S0tPyCQnV11S+ujhBydXHGp7s7OxUWFWdlZSOEMjI/hkdEDRrUb+CAvg8fPcWumGFS3qfGxSc9efbi1Onzfdx6SKbV"
        "zt0HkpLenDl5RFGh9tL/19Wqiao61VW1uwNCKC4uASEUGBzq4miPXbhHCJFIpIED+kVE1vUGNMrF2ZFEImHTxkZG6mqq8fGJ"
        "CKFePV3JZMrvG7fHxiZkZedQaVQajSa17t17Dy0sus6aMU1RUeHJ0+eNbv+LZTIyPr1+kxwXn3Tn7oOI8CjJ4Q0YFouloaGO"
        "TdOoVH19PfwADQ0N8Mq3sWbOdjOnLinpTU1NTa9ePfDtODp+oT+nUUlv3irIK0iOZ3C0s5EsYKCvh/eeaWtr4qNflJWVlL+2"
        "nwp8bwjsLhg3dtTQoYN8ff0+fvpEoVCtLM1nTp+WkPj60RMvhFBG5kcnJ3tVFU61QDB0yMBBA/t/cYNCoWj1L0vlGPT379Pd"
        "eroOHzZ4/8EjeDbdvnN/1cqlmprqm7b8gc0ZPnSQYSeD16/fFhUVaWtpL1o4NzUtraioGN+gSCRauWr99asXjxzeu2DxSqFQ"
        "9BW1asrAgf1W5eUHh4TrG+iuXbPC1y8w5X0qQujS3/+Ndx9z8azH6XMXq6r4kyaOMzbutGXb7ua3psxRPnJ43+3bdyk06trV"
        "K/LyC+4/eIIQysj4SKVS+vZ18/MPMjTQ+339Gqlhcwih3Ny84JCwNauX3737sKnf+F8so6urbWbamUqlmpt3c3FxPHnmolSB"
        "c6eP2thY9XAbVFrKXb9u9fSfJk+bPi8iMnrSRPc/tm3ctmPPf9dutfDUfR0VDmfgwL74x8KC4uiY2GbOdjOnLicn78nT58sW"
        "z+NXVr55+87SotvE8WO+okre3n4p71MP7d+578CR4pKS/v16O0iM7nJ1cbp88dSFS//u3X9YVYXj7fUgLCJq5uxFCKGH925Q"
        "KBTXXgO/5YSA7wSBIRsbl9Cjh8uC+bNVVTgkEinz46cr/904ffaSQCBACP22fvO2zet9Xz6qrOQ/f+GzbMXaE8cPNr/BGlSz"
        "6tffN6xb3bWLaWFh8cHDx89d+Btf+tTrxeZNa1PT0hOT3mBzcvPyp0wZP/PnqYqKCkVFxWERkYf+8pDaZnlF+YLFK29d/3vT"
        "779t27HnK2rVlC3bd48ZOWzWjGlCkejZs5e79hzC5peWcif/NGvdr7/s3bWNRqMmJL6eNWdxdExs81v7+5+rCgoK+/f+wWIx"
        "I6Nili5fW1ZejhDyeuF9+syFbVs2KCuxU1PTDx46Wl0taLj6bc8HvXq63rzTeF9BS8rs2rEZISQUinJzc/+7evOCxJnHZGR+"
        "1NLUwK5WffqUxeWWFRWVIIRyc3J5PF52Tm7zB/jtunQx9Tj6J/4xOCRs5pzFzZzt5k/dhk3bf/v1l2VLFjAYcmHh0T/NmP/y"
        "WXNnr1FisXj+opVbN63bv3eHUCj0ev7S49S5tWtWYEuLiovLyss/fsxCCFXyq/LyCjIzPmKLMjM/kmXU9getjjTYfUF8pP+X"
        "C8raxAljd+3Y3M3KWbIrQBKNRgvy8zp/6Z9Tpy+0cd2kGBjov3h6d+acxcEhrXMp2d/nyW3P+9iAMNCuzZs9fdHCuY7d+8q6"
        "IqCNWDm4tbOncDXz7T586CCWPMvz7sM2rE5zWrcXkoSgXdMRuHR3xq5JgB8H4Xd8EY1GpZpbdNXV1v59/ZrrN27n5ubJukYA"
        "1Ll47sTLl68+ZGYKqoVDhw7s49YDv0EG/CDafcgyWcy/L5wWCATPvF7uO3DkyysA0IaS372fPn2ypoYGjUbLyPy4Y+f+B4+e"
        "yLpSoE21mz5ZAABod9pfnywAALQvELIAAEAgCFkAACAQhCwAABAIQhYAAAgEIQsAAASCkAUAAAJByAIAAIEgZAEAgEAQsgAA"
        "QCACn11AoVGHzevlMtyGraZA3F7AV+AWlIc8irp//LlAIP2uGgB+LCQShUKj0ujEPeaOwJAdNq/XoBk9ids++GpsNYXBM3sj"
        "hG4fhoeVgB9bTY1IWI0QotHoXyz7dQjsLnAZbvPlQkB2XEbYfbkQAD8AkaiR94m0FuiTBQAAAhEYsqGPv/DeKiBboY+iZV0F"
        "AL4LFIr0O55bEYF9sk/OBSCEnIdbK6k198560PZKC8pCH0XfP97468EB+IF8vvBF3B4IDFmRQPjwpO/Dk77E7QJ8CwqVQWn3"
        "b8YA4HsHfbIAAEAgCFkAACAQhCwAABAIQhYAAAgEIQsAAASCkAUAAAJByAIAAIEgZAEAgEAQsgAAQCAIWQAAIBCELAAAEAhC"
        "FgAACAQhCwAABIKQBQAAAkHIAgAAgSBkAQCAQBCyAABAIAhZAAAgEIQsAAAQCEIWAAAIBCELAAAEgpAFAAACQcgCAACBIGQB"
        "AIBAELIAAEAgCFkAACAQhCwAABAIQhYAAAgEIQsAAASCkAUAAAJByAIAAIEgZAEAgEAQsgAAQCAIWQAAIBC5nFss6zoAAEDH"
        "VM4tJssxWDQaXdY1AQCAjoZKo8sxWGRBdRUFQhYAAFobjS4nqOKTeRVcKoUq68oAAEBHQ6VQeBVcMq+Cq6ikIuvKAABAR6PA"
        "Vqmo4JKLC3LYyqqyrgwAAHQ0ShzV4oIcchWfx6vgyjFYsq4PAAB0HEwmq6KstLqqkowQKsjJ1NQxkHWVAACg41DXMczPyUTY"
        "zQhFBdlUGo0lryjrWgEAQEfAkmdTKNTiwhyE3/H1ISWRo6Yl01oBAEAHwVHT/JASj03Xhmw5t7ispEBbv7PsagUAAB2BroFJ"
        "aXFeRVkp9rHu2QW5Wel8XpmOnpGMKgYAAO2etn5nXnlpfnYGPqfeA2KyMt7xKyt09E3avGIAANDu6RqY8Cu4WZkpkjMpDFa9"
        "611lpUU0Ol1dS08kFAgE1W1bQwAAaJdY8mwNHYPSkvzcT2lSi6RDFiFUUVZaVVWpZ9hFUYlTxecJhYK2qicAALQzDCZLx9BE"
        "UUnlY/qbksLchgVIyqo6Ta2soqatpqknr6BUWlpYXlIkFAmFgmpo3gIAfmRUGp1Gl6NQKYqKKkoc1fKy0oKcTGy0VqOaC1kM"
        "ncHkqGrJy7NZCko0ulwVn6fA5rR2tQEAoB0o5xbLMViCKj6vgltRwS0uyKmuqmx+lf8BuRT/nhHFpngAAAAASUVORK5CYII="
    ),
    "proxies_rule34.txt": (
        "aHR0cDovLzQuMTQ0LjE0Ni4yMTo4MApodHRwOi8vMTQ0LjEyNC4yNTEuMjQ6MTAxODcKaHR0cDovLzEwNC4yMjUuMTYyLjIw"
        "OjgwODIKaHR0cDovLzE0NC4xMjQuMjUxLjI0OjEwMzY2Cmh0dHA6Ly8yMDAuMTI4Ljg0LjgyOjMxMjgKaHR0cDovLzEwMi4y"
        "NDQuNzguNjE6ODA4OApodHRwOi8vMTAyLjI0NC43OC42MTo4MDg3Cmh0dHA6Ly8xNTQuNTkuNTYuNzM6OTk5Cmh0dHA6Ly80"
        "My4xNzMuMTIwLjEzOjg4OTkKaHR0cDovLzEwMi4yNDQuNzguNjE6ODA4MgpodHRwOi8vMTAyLjI0NC43OC42MTo4MDgxCmh0"
        "dHA6Ly80My4xNjAuMjIyLjcwOjMxMjgKaHR0cDovLzIwNS4xNjQuMTkyLjExNTo5OTkKaHR0cDovLzUuMTI5LjI1NC41MTo4"
        "ODg4Cmh0dHA6Ly8yMDEuNy4zMS4xNjM6ODA4MApodHRwOi8vMTk0Ljg3LjE5Ny4yMTo4MDgwCmh0dHA6Ly84NS4yMDkuMTU2"
        "LjE0ODoxMDgwCmh0dHA6Ly8xNjUuMTU0LjE2Mi43Mzo4ODg4Cmh0dHA6Ly8xNTkuMTk1LjE5NC4yNDI6ODA4MApodHRwOi8v"
        "MjEwLjIxMS4xMTMuMzQ6ODAK"
    ),
})

# ====================================================================== сборка exe
# Запуск без ключей — сама программа. Сборка (её делает build_exe.bat):
#   py R34Downloader_by_AMAYORI.py --build            → R34Downloader_by_AMAYORI.exe рядом с этим файлом (один файл)
#   py R34Downloader_by_AMAYORI.py --build --folder   → папка R34Downloader_by_AMAYORI\ (запускается быстрее)

SPEC = """
# -*- mode: python ; coding: utf-8 -*-
a = Analysis([{script!r}], pathex=[], datas=[],
             hiddenimports=["socks", "websocket"],
             excludes=["tkinter", "unittest", "pydoc", "PyInstaller", "PySide6.QtNetwork", "PySide6.QtQml",
                       "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtOpenGL", "PySide6.QtDBus",
                       "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"])
# лишнее: программный OpenGL (20 МБ), ненужные плагины и переводы
DROP = ("opengl32sw", "qt6pdf", "qt6virtualkeyboard", "qt6dbus", "qtuiotouchplugin", "qdirect2d",
        "qminimal", "qicns", "qtga", "qtiff", "qwbmp", ".debug.", "devtools_resources")
KEEP_TR = ("qtbase_ru", "qtbase_ja", "qtbase_zh_cn")
KEEP_WEB = ("en-us.pak", "ru.pak", "ja.pak", "zh-cn.pak")

def keep(dest):
    d = dest.replace("\\\\", "/").lower()
    if any(x in d for x in DROP):
        return False
    if "/qtwebengine_locales/" in d:
        return d.rsplit("/", 1)[-1] in KEEP_WEB
    if "/translations/" in d:
        return any(k in d for k in KEEP_TR)
    return True

a.binaries = [b for b in a.binaries if keep(b[0])]
a.datas = [d for d in a.datas if keep(d[0])]

# QML-модули и Qt Quick 3D сборщик тянет «на всякий случай» — браузеру они не нужны.
# Оставляем только те библиотеки Qt, до которых реально доходят зависимости программы.
import os
import pefile

def is_qml(dest):
    return "qml" in os.path.dirname(dest).lower().split(os.sep) or "qmltooling" in dest.lower()

def imports_of(path):
    try:
        pe = pefile.PE(path, fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                                               pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"]])
        found = getattr(pe, "DIRECTORY_ENTRY_IMPORT", []) + getattr(pe, "DIRECTORY_ENTRY_DELAY_IMPORT", [])
        return [entry.dll.decode(errors="replace").lower() for entry in found]
    except Exception:
        return []

a.binaries = [b for b in a.binaries if not is_qml(b[0])]
a.datas = [d for d in a.datas if not is_qml(d[0])]
by_name = dict((os.path.basename(b[0]).lower(), b) for b in a.binaries)
qt_dll = lambda name: name.startswith("qt6") and name.endswith(".dll")
todo = [b for b in a.binaries if not qt_dll(os.path.basename(b[0]).lower())]
reached = set()
while todo:
    entry = todo.pop()
    for dep in imports_of(entry[1]):
        if dep in by_name and dep not in reached:
            reached.add(dep)
            todo.append(by_name[dep])
a.binaries = [b for b in a.binaries
              if not qt_dll(os.path.basename(b[0]).lower()) or os.path.basename(b[0]).lower() in reached]
pyz = PYZ(a.pure)
splash = Splash({splash!r}, binaries=a.binaries, datas=a.datas,
                text_pos=(30, 205), text_size=9, text_color="#6b7486", always_on_top=False)
if {onefile!r}:
    exe = EXE(pyz, a.scripts, splash, splash.binaries, a.binaries, a.datas, [], name={name!r},
              console=False, upx=False, icon={icon!r})
else:
    exe = EXE(pyz, a.scripts, splash, [], exclude_binaries=True, name={name!r}, console=False,
              upx=False, icon={icon!r})
    coll = COLLECT(exe, splash.binaries, a.binaries, a.datas, upx=False, name={name!r})
"""


def build_exe(argv):
    import shutil
    import tempfile
    import PyInstaller.__main__
    script = os.path.abspath(__file__)
    out = argv[argv.index("--out") + 1] if "--out" in argv else os.path.dirname(script)
    tmp = tempfile.mkdtemp(prefix="booru-build-")
    try:
        files = {}
        for name in (SITE.icon, "splash.png"):
            files[name] = os.path.join(tmp, name)
            with open(files[name], "wb") as f:
                f.write(resource_bytes(name))
        spec = os.path.join(tmp, "R34Downloader_by_AMAYORI.spec")
        with open(spec, "w", encoding="utf-8") as f:
            f.write(SPEC.format(script=script, splash=files["splash.png"], icon=files[SITE.icon],
                                name="R34Downloader_by_AMAYORI", onefile="--folder" not in argv))
        PyInstaller.__main__.run([spec, "--noconfirm", "--clean", "--distpath", out,
                                  "--workpath", os.path.join(tmp, "work")])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if "--build" in sys.argv:
        build_exe(sys.argv)
    else:
        sys.exit(run(SITE))
