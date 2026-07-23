import sys
import os
import json
import math
import threading
import logging
import time
from datetime import datetime, timedelta
import re
from collections import Counter
from urllib.parse import urlparse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import eel
from weasyprint import HTML, CSS

from wordcloud import WordCloud, STOPWORDS
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import io
import base64

# === ХАК ДЛЯ WINDOWS ===
if os.name == 'nt':
    gtk_path = r'C:\Program Files\GTK3-Runtime Win64\bin'
    if os.path.exists(gtk_path):
        os.environ['PATH'] = gtk_path + os.pathsep + os.environ.get('PATH', '')
        if hasattr(os, 'add_dll_directory'): os.add_dll_directory(gtk_path)

def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

eel.init(resource_path('web'))

# Глобальный флаг для отмены процесса
cancel_flag = threading.Event()

class EelLogHandler(logging.Handler):
    def emit(self, record): eel.addLog(self.format(record))()

logger = logging.getLogger('weasyprint')
logger.setLevel(logging.DEBUG)
eel_handler = EelLogHandler()
eel_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(eel_handler)

def get_hidden_tk_root():
    root = tk.Tk()
    root.attributes('-topmost', True); root.withdraw(); return root

@eel.expose
def cancel_process():
    cancel_flag.set()
    eel.addLog("\n[!] Получен сигнал отмены. Завершаем текущую операцию...")()

@eel.expose
def pick_file_json(current_path):
    root = get_hidden_tk_root()
    f = filedialog.askopenfilename(initialdir=current_path, filetypes=[("JSON", "*.json")])
    root.destroy(); return f if f else None

@eel.expose
def pick_file_pdf(current_path):
    root = get_hidden_tk_root()
    f = filedialog.asksaveasfilename(initialdir=os.path.dirname(current_path) if current_path else None, defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
    root.destroy(); return f if f else None

@eel.expose
def get_default_pdf_path(json_path):
    if not json_path: return ""
    return os.path.join(os.path.dirname(json_path), "result.pdf")

@eel.expose
def get_available_fonts():
    fonts_dir = resource_path(os.path.join('web', 'fonts'))
    fonts_map = {}
    if os.path.isdir(fonts_dir):
        for file in os.listdir(fonts_dir):
            if file.lower().endswith(('.ttf', '.otf')):
                base_name = file.split('-')[0].split('.')[0]
                if base_name not in fonts_map: fonts_map[base_name] = file
    return [{"name": k, "file": v} for k, v in fonts_map.items()]

def parse_tg_text(text_obj):
    if isinstance(text_obj, str): return text_obj
    if isinstance(text_obj, list):
        res = ""
        for part in text_obj:
            if isinstance(part, str): res += part
            elif isinstance(part, dict): res += part.get('text', '')
        return res
    return ""

def parse_tg_text_md(text_obj):
    if isinstance(text_obj, str): return text_obj
    if isinstance(text_obj, list):
        md_res = ""
        for part in text_obj:
            if isinstance(part, str): md_res += part
            elif isinstance(part, dict):
                t = part.get('text', '')
                ttype = part.get('type')
                if ttype == 'bold': md_res += f"**{t}**"
                elif ttype == 'italic': md_res += f"*{t}*"
                elif ttype == 'code': md_res += f"`{t}`"
                elif ttype == 'pre': md_res += f"```\n{t}\n```"
                elif ttype in ['link', 'text_link']: 
                    url = part.get('href', part.get('text', ''))
                    md_res += f"[{t}]({url})"
                else: md_res += t
        return md_res
    return ""

def parse_tg_text_html(text_obj, domain_counter):
    if isinstance(text_obj, str): 
        urls = re.findall(r'(https?://\S+)', text_obj)
        for u in urls:
            domain = urlparse(u).netloc.replace('www.', '')
            if domain: domain_counter[domain] += 1
        return text_obj.replace('\n', '<br>')
        
    if isinstance(text_obj, list):
        html_res = ""
        for part in text_obj:
            if isinstance(part, str): html_res += part.replace('\n', '<br>')
            elif isinstance(part, dict):
                t = part.get('text', '').replace('\n', '<br>')
                ttype = part.get('type')
                
                if ttype in ['link', 'text_link']: 
                    url = part.get('href', part.get('text', ''))
                    if url.startswith('http'):
                        domain = urlparse(url).netloc.replace('www.', '')
                        if domain: domain_counter[domain] += 1
                    html_res += f"<a href='{url}'>{t}</a>"
                elif ttype == 'bold': html_res += f"<strong>{t}</strong>"
                elif ttype == 'italic': html_res += f"<em>{t}</em>"
                elif ttype == 'code': html_res += f"<code>{t}</code>"
                elif ttype == 'pre': html_res += f"<pre>{t}</pre>"
                else: html_res += t
        return html_res
    return ""

def generate_charts_b64(hourly_data, daily_data, theme):
    bg_color = '#1e1e1e' if theme == 'dark' else '#ffffff'
    text_color = '#e0e0e0' if theme == 'dark' else '#333333'
    accent = '#3b82f6'

    fig = Figure(figsize=(8, 10), dpi=150, facecolor=bg_color)
    ax1 = fig.add_subplot(211); ax1.set_facecolor(bg_color)
    ax1.bar(range(24), hourly_data, color=accent, width=0.7, alpha=0.85)
    ax1.set_title("Активность по времени суток (Часы)", color=text_color, fontsize=16, pad=20, fontweight='bold')
    ax1.tick_params(colors=text_color, length=0); ax1.grid(True, axis='y', linestyle='--', alpha=0.2, color=text_color)
    for spine in ax1.spines.values(): spine.set_visible(False)

    ax2 = fig.add_subplot(212); ax2.set_facecolor(bg_color)
    ax2.bar(['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], daily_data, color=accent, width=0.6, alpha=0.85)
    ax2.set_title("Активность по дням недели", color=text_color, fontsize=16, pad=20, fontweight='bold')
    ax2.tick_params(colors=text_color, length=0); ax2.grid(True, axis='y', linestyle='--', alpha=0.2, color=text_color)
    for spine in ax2.spines.values(): spine.set_visible(False)

    fig.tight_layout(pad=4.0)
    buf = io.BytesIO(); canvas = FigureCanvas(fig); canvas.print_png(buf)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def generate_github_heatmap_b64(daily_counts_dict, theme):
    if not daily_counts_dict: return ""
    bg_color = '#1e1e1e' if theme == 'dark' else '#ffffff'
    text_color = '#e0e0e0' if theme == 'dark' else '#333333'
    
    dates = sorted(list(daily_counts_dict.keys()))
    start_date, end_date = dates[0], dates[-1]
    if (end_date - start_date).days > 365: start_date = end_date - timedelta(days=365)
        
    num_days = (end_date - start_date).days + 1
    x_weeks, y_days, colors = [], [], []
    max_count = max(daily_counts_dict.values()) if daily_counts_dict else 1
    
    month_ticks = []
    month_labels = []
    last_month = -1
    ru_months = {1:'Янв', 2:'Фев', 3:'Мар', 4:'Апр', 5:'Май', 6:'Июн', 7:'Июл', 8:'Авг', 9:'Сен', 10:'Окт', 11:'Ноя', 12:'Дек'}
    
    for i in range(num_days):
        curr = start_date + timedelta(days=i)
        count = daily_counts_dict.get(curr, 0)
        week_num = (curr - start_date).days // 7
        
        x_weeks.append(week_num)
        y_days.append(curr.weekday()) 
        colors.append(max(0.1, count / max_count) if count > 0 else 0)
        
        if curr.month != last_month:
            if not month_ticks or (week_num - month_ticks[-1]) >= 2:
                month_ticks.append(week_num)
                month_labels.append(ru_months[curr.month])
            last_month = curr.month

    fig = Figure(figsize=(10, 2.8), dpi=200, facecolor=bg_color)
    ax = fig.add_subplot(111); ax.set_facecolor(bg_color)
    
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("", ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"] if theme != 'dark' else ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"])
    ax.scatter(x_weeks, y_days, c=colors, cmap=cmap, s=60, marker='s', vmin=0, vmax=1)
    
    ax.set_yticks([0, 2, 4, 6])
    ax.set_yticklabels(['Пн', 'Ср', 'Пт', 'Вс'], color=text_color, fontsize=8)
    ax.invert_yaxis()
    ax.set_xticks(month_ticks)
    ax.set_xticklabels(month_labels, color=text_color, fontsize=9)
    ax.xaxis.tick_top()
    
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.tick_params(length=0, pad=5)

    fig.tight_layout()
    buf = io.BytesIO(); canvas = FigureCanvas(fig); canvas.print_png(buf)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def generate_wordcloud_b64(text, theme, font_path):
    bg_color = '#1e1e1e' if theme == 'dark' else '#ffffff'
    colormap = 'cool' if theme == 'dark' else 'viridis'
    
    ru_stops = {'и', 'в', 'не', 'на', 'я', 'что', 'как', 'с', 'то', 'а', 'это', 'по', 'к', 'но', 'у', 'за', 'о', 'же', 'от', 'так', 'для', 'да', 'ты', 'мы', 'мне', 'меня', 'все', 'он', 'она', 'они', 'тут', 'там', 'уже', 'вот', 'если', 'бы', 'или', 'ну', 'только', 'еще', 'нет', 'до', 'из', 'его', 'ее', 'вас', 'нас', 'их', 'чем', 'кто', 'просто', 'будет', 'очень', 'даже', 'вы', 'тебе', 'тебя', 'которые', 'этого', 'больше', 'можно', 'было', 'где', 'сейчас', 'всегда', 'потому', 'потом', 'какой', 'какие', 'чтобы', 'вообще', 'через', 'ни', 'тоже', 'когда', 'себя', 'ли', 'без', 'будут', 'со', 'вам', 'сделать', 'делать', 'там', 'тут', 'этот', 'эта', 'эти', 'эту', 'том', 'тем', 'него', 'ней', 'ним', 'них', 'того', 'может'}
    stops = STOPWORDS.union(ru_stops)
    clean_text = re.sub(r'http\S+', '', text)
    clean_text = re.sub(r'[^а-яА-Яa-zA-Z\s]', '', clean_text)

    wc = WordCloud(width=1000, height=1300, background_color=bg_color, colormap=colormap, stopwords=stops, font_path=font_path, max_words=200, min_word_length=3)
    try:
        wc.generate(clean_text)
        img = wc.to_image().convert("RGBA")
        
        FADE_EDGE = 30
        FADE_SMOOTH = 10
        bg = Image.new("RGBA", img.size, bg_color)
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rectangle([FADE_EDGE, FADE_EDGE, img.width - FADE_EDGE, img.height - FADE_EDGE], fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(FADE_SMOOTH))
        final_img = Image.composite(img, bg, mask)

        buf = io.BytesIO(); final_img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except: return None

@eel.expose
def calculate_volume(json_path, date_from, date_to, font_size):
    try:
        font_size = int(font_size) if font_size else 12
        with open(json_path, 'r', encoding='utf-8') as f: tg_data = json.load(f)
            
        dt_from = datetime.strptime(date_from, "%Y-%m-%d") if date_from else None
        dt_to = datetime.strptime(date_to, "%Y-%m-%d") if date_to else None
        
        count_msgs = 0
        total_height_px = 0
        page_height_px = 850 
        
        for msg in tg_data.get('messages', []):
            if msg.get('type') != 'message': continue
            msg_dt_str = msg.get('date', '')
            if msg_dt_str:
                dt = datetime.strptime(msg_dt_str, "%Y-%m-%dT%H:%M:%S")
                if dt_from and dt.date() < dt_from.date(): continue
                if dt_to and dt.date() > dt_to.date(): continue
            
            text = parse_tg_text(msg.get('text', ''))
            msg_height = 80 
            line_height = font_size * 1.8
            chars_per_line = max(30, 800 // font_size) 
            
            lines = 0
            for paragraph in text.split('\n'): lines += max(1, math.ceil(len(paragraph) / chars_per_line))
            msg_height += lines * line_height
            
            if msg.get('media_type') or 'photo' in msg: msg_height += 40
            if msg.get('reply_to_message_id'): msg_height += 50
                
            total_height_px += msg_height
            count_msgs += 1
            
        est_pages = max(1, math.ceil(total_height_px / page_height_px))
        est_pages += 4 
        volumes = max(1, math.ceil(count_msgs / 5000))
        return {"success": True, "count": count_msgs, "pages": est_pages, "vols": volumes}
    except Exception as e: return {"success": False, "error": str(e)}

def _conversion_task(json_path, out_pdf, date_from, date_to, font_family, font_size, theme, show_media, show_top, show_watermark, show_charts, show_wordcloud, show_toc, show_links, create_md, only_md):
    start_time = time.time()
    cancel_flag.clear()
    
    try:
        eel.addLog("> Чтение и анализ JSON файла...")()
        with open(json_path, 'r', encoding='utf-8') as f: tg_data = json.load(f)

        channel_name = tg_data.get('name', 'Telegram Chat')
        safe_channel_name = channel_name.replace('"', "'").replace('\n', ' ')
        chat_type = tg_data.get('type', 'personal_chat')
        all_messages = tg_data.get('messages', [])
        
        dt_from = datetime.strptime(date_from, "%Y-%m-%d") if date_from else None
        dt_to = datetime.strptime(date_to, "%Y-%m-%d") if date_to else None
        
        msg_dict = {msg.get('id'): msg for msg in all_messages if 'id' in msg}
        filtered_msgs = []
        
        user_counts = {}
        activity_by_hour = [0] * 24
        activity_by_day = [0] * 7 
        daily_activity_map = {} 
        domain_counter = Counter() 
        toc_tree = {} 
        all_text_for_cloud = ""
        
        for msg in all_messages:
            if cancel_flag.is_set(): raise InterruptedError("Отменено пользователем")
            if msg.get('type') != 'message': continue
            try:
                msg_dt = datetime.strptime(msg.get('date', ''), "%Y-%m-%dT%H:%M:%S")
                if dt_from and msg_dt.date() < dt_from.date(): continue
                if dt_to and msg_dt.date() > dt_to.date(): continue
                filtered_msgs.append((msg, msg_dt))
                
                sender = msg.get('from')
                if sender: user_counts[sender] = user_counts.get(sender, 0) + 1
                activity_by_hour[msg_dt.hour] += 1
                activity_by_day[msg_dt.weekday()] += 1
                
                d_date = msg_dt.date()
                daily_activity_map[d_date] = daily_activity_map.get(d_date, 0) + 1
                
                month_str = msg_dt.strftime("%B %Y")
                day_str = msg_dt.strftime("%d %B")
                day_id = f"day-{msg_dt.strftime('%Y-%m-%d')}"
                
                if month_str not in toc_tree: toc_tree[month_str] = []
                if (day_str, day_id) not in toc_tree[month_str]:
                    toc_tree[month_str].append((day_str, day_id))
                
                if not only_md and show_wordcloud: 
                    all_text_for_cloud += parse_tg_text(msg.get('text', '')) + " "
            except: pass

        if not filtered_msgs: raise ValueError("Нет сообщений за выбранный период.")
        top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:12]
        top_domains = domain_counter.most_common(50) 

        # --- ПОДГОТОВКА ДЛЯ .MD ---
        md_lines = []
        if create_md or only_md:
            md_lines = [f"# Экспорт чата: {safe_channel_name}", f"Период: {date_from or 'Начало'} - {date_to or 'Конец'}\n"]
        md_current_date = None

        if not only_md:
            is_dark = (theme == 'dark')
            bg_page = "#1e1e1e" if is_dark else "#f4f6f8"
            text_main = "#e0e0e0" if is_dark else "#222222"
            bg_msg = "#2b2b2b" if is_dark else "#ffffff"
            border_msg = "#404040" if is_dark else "#e2e8f0"
            color_reply = "#1a1a1a" if is_dark else "#f8fafc"
            color_accent = "#60a5fa" if is_dark else "#2563eb"
            color_watermark = "#444444" if is_dark else "#bbbbbb"
            
            css_fonts = ""
            abs_font_path = None
            fonts_dir = resource_path(os.path.join('web', 'fonts'))
            if os.path.isdir(fonts_dir):
                for file in os.listdir(fonts_dir):
                    if file.lower().endswith(('.ttf', '.otf')):
                        f_abs = os.path.abspath(os.path.join(fonts_dir, file))
                        if not abs_font_path: abs_font_path = f_abs 
                        if file.split('-')[0].split('.')[0] == font_family:
                            abs_font_path = f_abs
                            uri = Path(f_abs).as_uri()
                            weight, style = "normal", "normal"
                            if "bold" in file.lower() and "italic" in file.lower(): weight, style = "bold", "italic"
                            elif "bold" in file.lower(): weight = "bold"
                            elif "italic" in file.lower(): style = "italic"
                            css_fonts += f"@font-face {{ font-family: '{font_family}'; src: url('{uri}'); font-weight: {weight}; font-style: {style}; }}\n"

            actual_font = f"'{font_family}', sans-serif" if font_family else "sans-serif"
            
            page_css = f"""
            @page {{ 
                margin: 2cm 1.5cm; 
                @bottom-center {{ content: string(pagedate, start) " ➔ " string(pagedate, last); color: {color_watermark}; font-size: 8pt; font-family: {actual_font}; }}
            }}
            """
            if show_watermark:
                page_css += f"""
                @page {{ @bottom-left {{ content: "{safe_channel_name}"; color: {color_watermark}; font-size: 8pt; font-family: {actual_font}; white-space: nowrap; overflow: hidden; }} @bottom-right {{ content: counter(page); color: {color_watermark}; font-size: 8pt; font-family: {actual_font}; }} }}
                @page :first {{ @bottom-left {{ content: none; }} @bottom-center {{ content: none; }} @bottom-right {{ content: "Сгенерировано в TG to PDF"; color: {color_watermark}; font-size: 8pt; font-family: {actual_font}; }} }}
                """

            base_css = css_fonts + page_css + f"""
            body {{ font-family: {actual_font}; background: {bg_page}; color: {text_main}; font-size: {font_size}pt; line-height: 1.5; }}
            a {{ color: {color_accent}; text-decoration: none; }}
            
            .cover-page {{ display: flex; flex-direction: column; align-items: center; justify-content: center; height: 80vh; text-align: center; page-break-after: always; }}
            .full-page {{ display: block; text-align: center; page-break-after: always; padding-top: 20px; }}
            .cover-title {{ font-size: 2.8em; color: {color_accent}; margin-bottom: 20px; font-weight: bold; }}
            .cover-stats {{ font-size: 1.2em; color: {'#aaaaaa' if is_dark else '#666666'}; background: {bg_msg}; padding: 25px; border-radius: 15px; border: 1px solid {border_msg}; display: inline-block; }}
            .page-title {{ font-size: 2em; color: {color_accent}; margin-bottom: 30px; font-weight: bold; text-align: center; border-bottom: 2px solid {border_msg}; padding-bottom: 10px; }}
            
            .img-container {{ text-align: center; margin-bottom: 30px; width: 100%; }}
            .img-container img {{ max-width: 100%; border-radius: 0px; box-shadow: none; }}
            
            ul.toc {{ list-style: none; padding: 0; text-align: left; max-width: 80%; margin: 0 auto; font-size: 1.1em; }}
            ul.toc li.toc-month {{ font-weight: bold; margin-top: 20px; color: {color_accent}; border-bottom: 1px solid {border_msg}; padding-bottom: 5px; }}
            ul.toc li.toc-day {{ margin-left: 20px; margin-top: 5px; display: block; }}
            ul.toc li.toc-day a {{ color: {text_main}; text-decoration: none; }}
            ul.toc li.toc-day a::after {{ content: leader('.') target-counter(attr(href), page); color: {'#888' if is_dark else '#666'}; }}

            .link-dir {{ text-align: left; max-width: 80%; margin: 0 auto; column-count: 2; column-gap: 40px; font-size: 0.9em; }}
            .link-dir div {{ margin-bottom: 8px; border-bottom: 1px dashed {border_msg}; display: flex; justify-content: space-between; }}
            
            .top-users {{ font-size: 1em; color: {'#aaa' if is_dark else '#555'}; text-align: left; background: {bg_msg}; padding: 20px 30px; border-radius: 12px; border: 1px solid {border_msg}; display: inline-block; min-width: 60%; margin: 0 auto; }}
            .top-users ol {{ margin: 0; padding-left: 20px; columns: 2; column-gap: 50px; font-size: 1.1em; line-height: 1.6; }}

            .msg-wrapper {{ string-set: pagedate attr(data-date); display: block; width: 100%; margin-bottom: 12px; page-break-inside: avoid; break-inside: avoid; clear: both; }}
            
            .date-divider {{ text-align: center; margin: 25px 0 15px 0; clear: both; }}
            .date-divider span {{ background: {'#333' if is_dark else '#cbd5e1'}; color: {'#fff' if is_dark else '#334155'}; padding: 4px 12px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }}
            
            .message {{ display: table; background: {bg_msg}; border-radius: 12px; padding: 10px 14px; border: 1px solid {border_msg}; max-width: 85%; }}
            .sender-name {{ font-weight: bold; color: {color_accent}; font-size: 0.85em; margin-bottom: 4px; }}
            .reply-box {{ background: {color_reply}; border-left: 4px solid {color_accent}; padding: 6px 10px; font-size: 0.85em; border-radius: 4px; margin-bottom: 8px; color: {'#aaa' if is_dark else '#555'}; }}
            .forward-box {{ font-size: 0.8em; color: {color_accent}; margin-bottom: 5px; font-style: italic; }}
            .media-tag {{ display: inline-block; background: {'#444' if is_dark else '#e2e8f0'}; padding: 4px 8px; border-radius: 6px; font-size: 0.8em; margin: 5px 0; }}
            .media-voice {{ display: inline-block; background: {'#831843' if is_dark else '#fce7f3'}; color: {'#f9a8d4' if is_dark else '#db2777'}; padding: 4px 8px; border-radius: 6px; font-size: 0.8em; margin: 5px 0; border: 1px solid {'#be185d' if is_dark else '#fbcfe8'}; }}
            .media-sticker {{ display: inline-block; background: {'#1e3a8a' if is_dark else '#dbeafe'}; color: {'#93c5fd' if is_dark else '#2563eb'}; padding: 4px 8px; border-radius: 6px; font-size: 0.8em; margin: 5px 0; border: 1px solid {'#1d4ed8' if is_dark else '#bfdbfe'}; }}
            
            .message-meta {{ text-align: right; font-size: 0.7em; color: {'#777' if is_dark else '#94a3b8'}; margin-top: 5px; }}
            pre, code {{ background: {color_reply}; padding: 2px 5px; border-radius: 4px; font-family: monospace; white-space: pre-wrap; }}
            """

            b64_charts, b64_heatmap, b64_cloud = "", "", ""
            if show_charts:
                if cancel_flag.is_set(): raise InterruptedError("Отменено пользователем")
                eel.addLog("> Рендер графиков активности...")()
                b64_charts = generate_charts_b64(activity_by_hour, activity_by_day, theme)
                b64_heatmap = generate_github_heatmap_b64(daily_activity_map, theme)
            if show_wordcloud and all_text_for_cloud:
                if cancel_flag.is_set(): raise InterruptedError("Отменено пользователем")
                eel.addLog("> Рендер облака слов (с градиентом)...")()
                b64_cloud = generate_wordcloud_b64(all_text_for_cloud, theme, abs_font_path)

        CHUNK_SIZE = 5000
        chunks = [filtered_msgs[i:i + CHUNK_SIZE] for i in range(0, len(filtered_msgs), CHUNK_SIZE)]
        is_multi_volume = len(chunks) > 1

        for idx, chunk in enumerate(chunks):
            if cancel_flag.is_set(): raise InterruptedError("Отменено пользователем")
            vol_num = idx + 1
            if not only_md: eel.updateStatus("pulsing", f"Сборка HTML Тома {vol_num} из {len(chunks)}...", "#0ea5e9")()
            
            posts_html = []
            
            if not only_md:
                # --- СТР 1: Обложка ---
                vol_title = f"<br><small style='font-size: 0.5em; color: #888;'>ТОМ {vol_num}</small>" if is_multi_volume else ""
                posts_html.append(f"""
                <div class='cover-page'>
                    <div class='cover-title'>{safe_channel_name}{vol_title}</div>
                    <div class='cover-stats'>
                        <p><b>Период:</b> {date_from or 'За всё время'} — {date_to or 'До конца'}</p>
                        <p><b>Сообщений:</b> {len(chunk)}</p>
                        <p><b>Дата экспорта:</b> {datetime.now().strftime('%d.%m.%Y')}</p>
                    </div>
                </div>
                """)

                # --- СТР 2: Графики и Heatmap ---
                if vol_num == 1 and show_charts and b64_charts:
                    heatmap_tag = f"<div class='img-container'><img src='data:image/png;base64,{b64_heatmap}' style='width: 90%; margin-top: 15px;'></div>" if b64_heatmap else ""
                    posts_html.append(f"""
                    <div class='full-page'>
                        <h2 class='page-title'>Аналитика активности</h2>
                        <div class='img-container'><img src='data:image/png;base64,{b64_charts}' style='width: 80%;'></div>
                        {heatmap_tag}
                    </div>
                    """)

                # --- СТР 3: Облако слов и Топ ---
                if vol_num == 1 and (show_wordcloud or show_top):
                    cloud_html = f"<div class='img-container'><img src='data:image/png;base64,{b64_cloud}' style='width: 85%;'></div>" if b64_cloud else ""
                    top_html = ""
                    if show_top and top_users and 'channel' not in chat_type.lower():
                        lis = "".join([f"<li>{u} <b>({c})</b></li>" for u, c in top_users])
                        top_html = f"<div class='top-users'><h3>Топ-12 авторов 🏆</h3><ol>{lis}</ol></div>"

                    if cloud_html or top_html:
                        posts_html.append(f"""
                        <div class='full-page'>
                            <h2 class='page-title'>Статистика общения</h2>
                            {cloud_html}
                            <br>{top_html}
                        </div>
                        """)

                # --- СТР 4: Оглавление (ToC) ---
                if vol_num == 1 and show_toc and toc_tree:
                    toc_html = "<ul class='toc'>"
                    for month, days in toc_tree.items():
                        toc_html += f"<li class='toc-month'>{month}</li>"
                        for d_name, d_id in days:
                            toc_html += f"<li class='toc-day'><a href='#{d_id}'>{d_name}</a></li>"
                    toc_html += "</ul>"
                    
                    posts_html.append(f"""
                    <div class='full-page'>
                        <h2 class='page-title'>Оглавление</h2>
                        {toc_html}
                    </div>
                    """)

            # --- СТР 5+: СООБЩЕНИЯ ---
            current_date = None
            for msg, dt in chunk:
                if cancel_flag.is_set(): raise InterruptedError("Отменено пользователем")
                day_str_human = dt.strftime("%d %B %Y")
                day_str_short = dt.strftime("%d %b %Y") 
                day_id = f"day-{dt.strftime('%Y-%m-%d')}"
                time_str = dt.strftime("%H:%M")
                
                reply_id = msg.get('reply_to_message_id')
                
                # --- ГЕНЕРАЦИЯ .MD ---
                if create_md or only_md:
                    day_md = dt.strftime("%Y-%m-%d")
                    if day_md != md_current_date:
                        md_lines.append(f"\n## {day_md}\n")
                        md_current_date = day_md
                    
                    sender_md = msg.get('from', 'Unknown') if 'channel' not in chat_type.lower() else safe_channel_name
                    md_msg = f"**[{time_str}] {sender_md}:** "
                    
                    if msg.get('forwarded_from'): md_msg += f"*(Переслано от: {msg['forwarded_from']})* "
                    if reply_id and reply_id in msg_dict:
                        orig_sender = msg_dict[reply_id].get('from', 'Пользователь')
                        md_msg += f"> [Ответ {orig_sender}] "
                        
                    if show_media:
                        m_type = msg.get('media_type')
                        if m_type == 'voice_message': md_msg += "[🎤 Голосовое] "
                        elif m_type == 'video_message': md_msg += "[📹 Кружок] "
                        elif m_type == 'sticker': md_msg += "[👾 Стикер] "
                        elif m_type: md_msg += f"[📎 {m_type}] "
                        elif 'photo' in msg: md_msg += "[📷 Фото] "
                        
                    md_msg += parse_tg_text_md(msg.get('text', ''))
                    md_lines.append(md_msg + "\n")
                
                # --- ГЕНЕРАЦИЯ HTML ---
                if not only_md:
                    if day_str_human != current_date: 
                        posts_html.append(f"<div class='date-divider' id='{day_id}'><span>{day_str_human}</span></div>")
                        current_date = day_str_human
                        
                    inner_html = ""
                    sender = msg.get('from')
                    if sender and 'channel' not in chat_type.lower(): inner_html += f"<div class='sender-name'>{sender}</div>"
                    if msg.get('forwarded_from'): inner_html += f"<div class='forward-box'>↪ Переслано от: {msg['forwarded_from']}</div>"
                        
                    if reply_id and reply_id in msg_dict:
                        orig_msg = msg_dict[reply_id]
                        orig_text = parse_tg_text(orig_msg.get('text', '')).replace('<', '').replace('>', '')[:80] + "..."
                        orig_sender = orig_msg.get('from', 'Пользователь')
                        inner_html += f"<div class='reply-box'><b>{orig_sender}:</b><br>{orig_text}</div>"
                    
                    if show_media:
                        m_type = msg.get('media_type')
                        if m_type == 'voice_message': inner_html += f"<div class='media-voice'>🎤 Голосовое сообщение</div><br>"
                        elif m_type == 'video_message': inner_html += f"<div class='media-voice'>📹 Видеосообщение (кружок)</div><br>"
                        elif m_type == 'sticker': inner_html += f"<div class='media-sticker'>👾 Стикер</div><br>"
                        elif m_type: inner_html += f"<div class='media-tag'>📎 Вложение: {m_type.capitalize()}</div><br>"
                        elif 'photo' in msg: inner_html += f"<div class='media-tag'>📷 Вложение: Фотография</div><br>"
                    
                    parsed_text = parse_tg_text_html(msg.get('text', ''), domain_counter)
                    if parsed_text: inner_html += f"<div class='message-content'>{parsed_text}</div>"
                    inner_html += f"<div class='message-meta'>{time_str}</div>"
                    
                    posts_html.append(f"<div class='msg-wrapper' data-date='{day_str_short}'><div class='message'>{inner_html}</div></div>")

            # --- ПОСЛЕДНЯЯ СТР: Индекс Ссылок ---
            if not only_md:
                if idx == len(chunks)-1 and show_links and top_domains:
                    links_html = "<div class='link-dir'>"
                    for domain, count in top_domains:
                        links_html += f"<div><span>🌐 {domain}</span> <b>{count}</b></div>"
                    links_html += "</div>"
                    
                    posts_html.append(f"""
                    <div class='full-page'>
                        <h2 class='page-title'>Индекс полезных ссылок (Топ-50)</h2>
                        {links_html}
                    </div>
                    """)

                final_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>{chr(10).join(posts_html)}</body></html>"
                base_name, ext = os.path.splitext(out_pdf)
                final_pdf_path = f"{base_name}_Том{vol_num}{ext}" if is_multi_volume else out_pdf

                eel.updateStatus("pulsing", f"Рендер PDF Тома {vol_num}...", "#0ea5e9")()
                if cancel_flag.is_set(): raise InterruptedError("Отменено пользователем")
                HTML(string=final_html).write_pdf(final_pdf_path, stylesheets=[CSS(string=base_css)])
                eel.addLog(f"  [+] Сохранен: {os.path.basename(final_pdf_path)}")()

        # Сохранение .md файла
        if create_md or only_md:
            eel.updateStatus("pulsing", f"Сохранение Markdown файла...", "#0ea5e9")()
            md_path = os.path.splitext(out_pdf)[0] + ".md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(md_lines))
            eel.addLog(f"  [+] Markdown сохранен: {os.path.basename(md_path)}")()

        elapsed = time.time() - start_time
        mins, secs = divmod(elapsed, 60)
        time_str = f"{int(mins)} мин. {int(secs)} сек."
        
        eel.updateStatus("success", f"Завершено за {int(mins)}м {int(secs)}с!", "#10b981")()
        eel.showFinalTime(time_str)()
        eel.addLog(f"\n[SUCCESS] Генерация успешно завершена.\nОбщее время: {time_str}")()

    except InterruptedError as e:
        eel.updateStatus("error", "Отменено пользователем", "#ef4444")()
        eel.addLog(f"\n[STOP] {str(e)}")()
    except Exception as e:
        eel.updateStatus("error", "Произошла ошибка", "#ef4444")()
        eel.addLog(f"\n[ERROR] {str(e)}")()
    finally:
        eel.enableButton()()

@eel.expose
def start_conversion(json_path, out_pdf, date_from, date_to, font_family, font_size, theme, show_media, show_top, show_watermark, show_charts, show_wordcloud, show_toc, show_links, create_md, only_md):
    threading.Thread(target=_conversion_task, args=(json_path, out_pdf, date_from, date_to, font_family, font_size, theme, show_media, show_top, show_watermark, show_charts, show_wordcloud, show_toc, show_links, create_md, only_md), daemon=True).start()

if __name__ == '__main__':
    icon_path = resource_path('icon.ico')
    if not os.path.exists(icon_path): icon_path = None
    eel.start('index.html', size=(760, 1050), port=0)