"""Gelbooru Downloader by AMAYORI v1.0 — качалка картинок и видео с Gelbooru по тегам.

Вся программа в одном файле. Разделы (ищите по «# ====»):
  sites — название, цвета, адреса сайта · i18n — тексты на 4 языках ·
  net — сеть, повторы, обход блокировки · storage — настройки, история, ключ ·
  api — запросы к сайту · engine — загрузка и докачка · theme — оформление ·
  ui — окно · app — запуск · в конце — встроенные файлы и сборка exe.

Запуск из исходника: py GelbooruDownloader.py
Сборка exe:          build_exe.bat  (или: py GelbooruDownloader.py --build)
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


GELBOORU = Site(
    key="gelbooru",
    site_name="Gelbooru",
    app_name="Gelbooru Downloader",
    version="1.0",
    data_dir="GelbooruDownloader",
    letter="G",
    accent="#38bdf8",
    accent_hover="#7dd3fc",
    accent_text="#04121c",
    author="by AMAYORI",
    icon="gelbooru.ico",
    site_url="https://gelbooru.com/",
    api_url="https://gelbooru.com/index.php",
    post_url="https://gelbooru.com/index.php?page=post&s=view&id={id}",
    search_example="https://gelbooru.com/index.php?page=post&s=list&tags=blue_hair",
    page_size=100,
    ratings=("general", "sensitive", "questionable", "explicit"),
    count_via_xml=False,
    xml_fallback=False,
    autocomplete_urls=("https://gelbooru.com/index.php?page=autocomplete2&type=tag_query&limit=12&term={term}",),
    credentials_path="My Account → Options → API Access Credentials",
    proxy_list="proxies_gelbooru.txt",
    options_url="https://gelbooru.com/index.php?page=account&s=options",
    register_url="https://gelbooru.com/index.php?page=account&s=reg",
    profile_url="https://gelbooru.com/index.php?page=account&s=profile&id={id}",
    ai_tags=("ai-generated",),
)


SITES = {GELBOORU.key: GELBOORU}
SITE = GELBOORU


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
    "gelbooru.ico": (
        "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"
        "SUVORK5CYII="
    ),
    "splash.png": (
        "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"
        "ra2To4ONjcDBwT4j4z2fx/f0cMfWvnj5Kicnt2Ld5HL5qHFTsVWPomPUavXPPy3FVrm6NP3sSxMIrLp27YhNa7XayVNnP00u"
        "i6R790NvXb9gZmaKEHJ1aeLXyofY4f7v+Uv/nr+Ez5aWlh47fmr40MHNmrkihGg0WtMmjePiExFCzdxciE3O+T8sfRAagRBC"
        "6GFEZNSVi/p7ir7wTX4/NHzVmvV6L2YYSgNuyapKRIXhV9/9uerlmjGJMzrFjWsVO6L54+884icGPF3Y5822OZlndhUnP9Io"
        "Sw1d04+wWSx8ulBYja8zpqYmXp5l//HkcnlUdAxxbVR0LDbBYDBcmjauVpUuXbmOT6emvouIKO/wcndvgU20aVP+TfbUmXPE"
        "zU+dLp8NaNOaw2EjhCwtzPH/YGq1+szZi3gZrVZ76sx5fLZLpyC9tTr378VNW3cZMGExMrkUn6YzGNhEm9blTc7LV29gCYuJ"
        "iX3y5u1bbJrH5fm39kUIxSckFheX3dQQ4O9HoVAQQm0D/LElsU/i8BTz9/NFCAW09cO7AvQ2YxFCIQ8eEsM3IrL8/cDnff7K"
        "QWs/X8qHBx4lJj3DExYhJBYX3/jvDj7btbPuH4hCodjZ2rT28+0YFNilc1CXzkEqQhcw3pL1+PA5gRB68/bth4RFCKGXKa/j"
        "4hIq1uoL3+Rv3r6dMXN+vUpY1EBbsiUvn+RcPlQUdVOr0e3d16pVGqVCKS6Qpb1EEQghRGWyzdp0t+o5it/cT8++6hzxPySP"
        "W41rg9hldwybzU5OiPpUSVNT06rvtri4pOjj6wMvU1I6BpVdvsfba/Z2doQCHw3dzS8oFAqLsIYPlUoVCATv3qXZO5SXz8rK"
        "1snKlJRX+LTe7gKE0L8X6sVDFXi88i+/InHZiSI+ASClwkDmlylvmjQuiwAbGxuEkFqtDo981LN7N4SQmZmpm5vLu3fpLb08"
        "EEISqeRlyuvHT+IHD+yHEPJv7Xv+4pV2bQl9BRU6ZDHEWEQIFRQW4NM6F6b0Ir6EV4Q/x4cXVb7EhvAHMjY2mjZ14sD+ffA3"
        "RkX4s+oEgvKhOM+fp+gUe/3mrY9PS52FX/gmv3L1pt7hDYbVwEJWKS7IOLKuIPTS54t+oCmVF4Rd5jRyrychKywqv4BjbW3N"
        "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"
        "BAAAAABJRU5ErkJggg=="
    ),
    "proxies_gelbooru.txt": (
        "aHR0cDovLzQuMTQ0LjE0Ni4yMTo4MApodHRwOi8vMTQ0LjEyNC4yNTEuMjQ6MTAxODcKaHR0cDovLzE4OS41MS4xNjguMTY0"
        "Ojk5OQpodHRwOi8vMTQ0LjEyNC4yNTEuMjQ6MTAzNjYKaHR0cDovLzEwNC4yMjUuMTYyLjIwOjgwODIKaHR0cDovLzE1NC41"
        "OS41Ni43ODo5OTkKaHR0cDovLzEwMi4yNDQuNzguNjE6ODA4MgpodHRwOi8vMTAyLjI0NC43OC42MTo4MDg4Cmh0dHA6Ly8y"
        "MDAuMTI4Ljg0LjgyOjMxMjgKaHR0cDovLzEwMi4yNDQuNzguNjE6ODA4NwpodHRwOi8vMTU0LjU5LjU2LjczOjk5OQpodHRw"
        "Oi8vNDMuMTczLjEyMC4xMzo4ODk5Cmh0dHA6Ly8xMDIuMjQ0Ljc4LjYxOjgwODEKaHR0cDovLzQzLjE2MC4yMjIuNzA6MzEy"
        "OApodHRwOi8vMjA1LjE2NC4xOTIuMTE1Ojk5OQpodHRwOi8vMTAzLjI4LjM3LjEzMTozMTI4Cmh0dHA6Ly8xNjUuMTU0LjE2"
        "Mi43Mzo4ODg4Cmh0dHA6Ly8yMDEuNy4zMS4xNjM6ODA4MApodHRwOi8vMTk0Ljg3LjE5Ny4yMTo4MDgwCmh0dHA6Ly8xODEu"
        "NzguMTk1LjEzNzo5OTkKaHR0cDovLzIwNi4xMzUuMjEuMjo5OTkKaHR0cDovLzQ1LjE5NC40MS4xNjo4MDgwCmh0dHA6Ly84"
        "Mi40Ny4xNjEuMTUyOjg0NDMKaHR0cDovLzE1OC4xNzkuNTguMTI2OjMxMjgK"
    ),
})

# ====================================================================== сборка exe
# Запуск без ключей — сама программа. Сборка (её делает build_exe.bat):
#   py GelbooruDownloader.py --build            → GelbooruDownloader.exe рядом с этим файлом (один файл)
#   py GelbooruDownloader.py --build --folder   → папка GelbooruDownloader\ (запускается быстрее)

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
        spec = os.path.join(tmp, "GelbooruDownloader.spec")
        with open(spec, "w", encoding="utf-8") as f:
            f.write(SPEC.format(script=script, splash=files["splash.png"], icon=files[SITE.icon],
                                name="GelbooruDownloader", onefile="--folder" not in argv))
        PyInstaller.__main__.run([spec, "--noconfirm", "--clean", "--distpath", out,
                                  "--workpath", os.path.join(tmp, "work")])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if "--build" in sys.argv:
        build_exe(sys.argv)
    else:
        sys.exit(run(SITE))
