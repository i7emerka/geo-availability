# Geo Availability

Автоматическая проверка **гео-доступности** сайта (не Web Vitals).

Гео: **UZ, BD, RU, EG, CI**.

Ежедневно через **облачные прокси** (RU — локальный IP) проверяем:

1. **Открывается ли** сайт (HTTP / загрузка страницы)
2. **Редирект** на правильную geo/locale-версию
3. **Язык** (html lang / URL / locale)
4. **Местная валюта** на странице

Стек тот же, что у `playwrightmonitoring`: **Python + Playwright + pandas + dotenv**.

---

## Быстрый старт

```bash
cd C:\Users\iksau\Desktop\geo-availability

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium
```

Скопируйте env:

```bash
copy .env.example .env
```

Заполните прокси для гео:

```env
SITE_URL=https://fastpari.com

UZ_PROXY_SERVER=socks5://host:port:user:pass
BD_PROXY_SERVER=socks5://host:port:user:pass
RU_PROXY_SERVER=socks5://host:port:user:pass
```

Форматы прокси — как в monitoring (строка Dolphin/Mango или `http://user:pass@host:port`).

---

## Команды

```bash
# Все гео (UZ, BD, RU)
python check_geo.py

# Только нужные
python check_geo.py --geos UZ,RU

# Только RU через ваш интернет (без прокси)
python check_geo.py --geos RU

# С окном браузера
python check_geo.py --geos BD --headed

# Список ожиданий по гео
python check_geo.py --list

# Без HTML-отчёта
python check_geo.py --no-report
```

**RU** по умолчанию: **ваш IP, без прокси**, старт только `https://fastpari.com`  
(настройка `use_local_ip` в `config/geos.py`). UZ/BD — через облачные прокси.

Результаты:

| Файл | Описание |
|------|----------|
| `reports/geo_checks.csv` | История проверок |
| `reports/report.html` | Таблица PASS / PARTIAL / FAIL |

После каждой проверки отчёт **автоматически публикуется** на GitHub Pages (если настроен remote).

```bash
python check_geo.py              # проверка + HTML + publish
python check_geo.py --no-publish # без публикации
```

Коды выхода:

- `0` — нет FAIL
- `1` — неверные аргументы / все SKIP (нет прокси)
- `2` — есть FAIL

---

## GitHub Pages (как в monitoring)

После `python check_geo.py` скрипт:

1. Собирает `reports/report.html`
2. Кладёт его в ветку **`gh-pages`** как `index.html`
3. Пушит на `origin`

### Разовый сетап

1. Создайте **отдельный** репозиторий на GitHub, например `geo-availability`  
   (не путать с `monitoring` — там уже свой Pages).

2. Привяжите remote и запушьте код:

```bash
cd C:\Users\iksau\Desktop\geo-availability
git remote add origin https://github.com/<user>/geo-availability.git
git branch -M main
git push -u origin main
```

3. В GitHub: **Settings → Pages → Build and deployment**  
   - Source: **Deploy from a branch**  
   - Branch: **`gh-pages`** / **/ (root)** → Save  

4. В `.env` (уже по умолчанию):

```env
GITHUB_PAGES_PUBLISH=1
GITHUB_PAGES_BRANCH=gh-pages
GITHUB_PAGES_REMOTE=origin
```

5. Следующий прогон сам обновит сайт:

```bash
python check_geo.py
# GitHub Pages: отчёт опубликован — https://<user>.github.io/geo-availability/
```

Отключить публикацию: `GITHUB_PAGES_PUBLISH=0` или `--no-publish`.

---

## Что считается успехом

| Проверка | PASS если |
|----------|-----------|
| **Opened** | Страница загрузилась (HTTP &lt; 400 или есть контент) |
| **Redirect** | Final URL содержит geo-hint (`/uz`, `/ru`, зеркало и т.д.) |
| **Language** | `html[lang]`, og:locale или path совпали с ожидаемым |
| **Currency** | На `/registration` в поле валюты выбран **ровно** `expected_currency` (ISO), напр. RUB / UZS — без подбора синонимов |

Итоговый **status**:

- `PASS` — всё ок
- `PARTIAL` — сайт открылся, но язык/валюта/редирект частично
- `FAIL` — не открылся или всё мимо
- `SKIP` — нет прокси в `.env`

Ожидания по гео правятся в `config/geos.py`.

---

## Отличия от playwrightmonitoring

| | monitoring | geo-availability |
|--|------------|------------------|
| Цель | скорость (LCP, TTFB, CLS…) | доступность и локаль |
| Dolphin / GeeLark | да | пока не нужен (прокси-облако) |
| Прогрев / web-vitals | да | нет |
| Результат | метрики ms | PASS/FAIL по правилам |
| GitHub Pages | да | да (тот же механизм) |

---

## Ежедневный запуск (Windows Task Scheduler)

Пример (после активации venv):

```text
Program: C:\Users\iksau\Desktop\geo-availability\.venv\Scripts\python.exe
Arguments: check_geo.py
Start in: C:\Users\iksau\Desktop\geo-availability
```

Или через bat:

```bat
@echo off
cd /d C:\Users\iksau\Desktop\geo-availability
call .venv\Scripts\activate
python check_geo.py
```

---

## Структура

```text
geo-availability/
  check_geo.py          # CLI
  config/
    geos.py             # ожидания: язык, валюта, URL-hints
    proxies.py          # парсинг прокси из .env
    sites.py            # SITE_URL и стартовые URL
  core/
    browser.py          # Playwright + proxy
    checker.py          # сценарий проверки
    detectors.py        # open / redirect / lang / currency
    store.py            # CSV
    html_report.py      # HTML
    publish_report.py   # GitHub Pages
  reports/
  .env.example
```

---

## Дальше (по желанию)

- больше гео (KZ, TR, …) — запись в `config/geos.py` + `XX_PROXY_SERVER`
- Telegram / email алерт при `FAIL`
- GitHub Pages публикация отчёта
- отдельный mobile-контур (GeeLark), если нужен
