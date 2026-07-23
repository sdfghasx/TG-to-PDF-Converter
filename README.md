# 📄 TG to PDF Converter

Десктопный инструмент для конвертации JSON-экспортов из Telegram в красивые, структурированные PDF-отчеты. 

<img width="917" height="1079" alt="image" src="https://github.com/user-attachments/assets/192f8d87-0a7c-4af7-8ab8-2d5eec53afca" />

Приложение генерирует не просто текст, а полноценный типографский документ с оглавлением, графиками активности, облаком слов и умными ссылками.

## ✨ Главные фичи
- **Умный парсинг**: Поддержка форматирования Telegram (жирный, курсив, код, ссылки, ответы, пересылки).
- **Медиа-заглушки**: Красивые плашки для голосовых, кружочков, фото и стикеров.
- **Немного аналитики**: 
  - Matplotlib графики активности (по часам и дням недели).
  - GitHub-style Contribution Heatmap (Календарь активности).
  - WordCloud (Круглое облако частых слов с градиентом).
  - Индекс полезных ссылок (Топ-50 доменов).
- **Интерактивность**: Кликабельное оглавление (ToC) по месяцам и дням.
- **Кастомизация**: Поддержка темной и светлой темы, выбор размера шрифта и установка кастомных шрифтов.

## 🛠 Технологии
- **Backend:** Python 3, Eel, Matplotlib, WordCloud, NumPy, WeasyPrint.
- **Frontend:** HTML5, CSS3, Vanilla JS (Glassmorphism UI).

## 📦 Скачать
Готовый установщик `.exe` для Windows доступен во вкладке **Releases**.

---

## 🚀 Установка и запуск (Для разработчиков)
1. Клонируйте репозиторий: `git clone https://github.com/sdfghasx/TG-to-PDF-Converter.git`
2. Установите зависимости: `pip install -r requirements.txt`
3. *Для Windows:* Установите [GTK3 Runtime](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases).
4. Запустите `python main.py`
