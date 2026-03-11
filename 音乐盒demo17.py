#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CS2 音乐盒控制器 v6.4 (PySide6 毛玻璃版) - 发布版
原 Tkinter 版本功能完全保留，UI 使用毛玻璃 + 随机背景
"""

import sys
import os
import json
import time
import math
import random
import threading
import traceback
import wave
import audioop
import webbrowser
import socket
import urllib.parse
import http.server
import socketserver
from collections import OrderedDict

# PySide6 导入
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QTreeWidget, QTreeWidgetItem,
    QTabWidget, QFrame, QDialog, QMessageBox, QFileDialog,
    QInputDialog, QTextEdit, QListWidget, QMenu, QHeaderView
)
from PySide6.QtCore import Qt, QTimer, QPoint, Signal, QObject
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QAction,
    QKeyEvent, QResizeEvent, QCloseEvent
)

# 第三方音频库
import pyaudio
from pynput import keyboard
from pynput.keyboard import Controller, Key

# 尝试导入 pydub（用于 MP3 支持）
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("警告: pydub 未安装，MP3 支持受限。请运行: pip install pydub")

# 背景图片获取
import requests
from PIL import Image, ImageFilter
import io


# ==================== 毛玻璃背景标签 ====================
class BlurBackgroundLabel(QLabel):
    """从樱花 API 获取随机二次元图片并模糊，支持动态调整大小"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScaledContents(True)
        self.original_pil = None
        self.load_background()
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.delayed_resize)

    def load_background(self):
        try:
            api_url = "https://www.dmoe.cc/random.php?return=json"
            response = requests.get(api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                img_url = data.get('imgurl')
                if img_url:
                    img_data = requests.get(img_url, timeout=15).content
                    pil_img = Image.open(io.BytesIO(img_data))
                    if pil_img.mode != 'RGB':
                        pil_img = pil_img.convert('RGB')
                    self.original_pil = pil_img
                    # 初始更新
                    parent_window = self.parent()
                    if parent_window:
                        w = parent_window.width()
                        h = parent_window.height()
                        self.update_size(w, h)
                else:
                    print("API 未返回图片 URL")
            else:
                print(f"API 请求失败，状态码: {response.status_code}")
        except Exception as e:
            print(f"背景加载失败: {e}")
            self.setStyleSheet("background-color: #0a0f1e;")

    def update_size(self, width, height):
        if self.original_pil is None:
            return
        try:
            # 限制最大尺寸，防止内存爆炸
            max_dim = 2000
            if width > max_dim or height > max_dim:
                ratio = min(max_dim / width, max_dim / height)
                width = int(width * ratio)
                height = int(height * ratio)

            resized = self.original_pil.resize((width, height), Image.Resampling.LANCZOS)
            blurred = resized.filter(ImageFilter.GaussianBlur(radius=3))
            if blurred.mode != 'RGB':
                blurred = blurred.convert('RGB')
            data = blurred.tobytes("raw", "RGB")
            qimg = QImage(data, blurred.width, blurred.height, QImage.Format_RGB888)
            if qimg.isNull():
                print("QImage 创建失败")
                return
            pixmap = QPixmap.fromImage(qimg)
            if pixmap.isNull():
                print("QPixmap 创建失败")
                return
            self.setPixmap(pixmap)
        except Exception as e:
            print(f"update_size 出错: {e}")
            traceback.print_exc()

    def resizeEvent(self, event):
        self.resize_timer.start(200)
        super().resizeEvent(event)

    def delayed_resize(self):
        parent = self.parent()
        if parent:
            w = parent.width()
            h = parent.height()
            self.setGeometry(0, 0, w, h)
            self.update_size(w, h)


# ==================== 毛玻璃面板 ====================
class BlurPanel(QFrame):
    """带实时毛玻璃效果的半透明面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.blur_radius = 4

    def paintEvent(self, event):
        try:
            super().paintEvent(event)

            if self.parent() is None:
                return

            parent_bg = self.parent().findChild(BlurBackgroundLabel)
            if parent_bg is None or parent_bg.pixmap() is None:
                return

            panel_rect = self.geometry()
            global_pos = self.mapToGlobal(self.rect().topLeft())
            bg_pixmap = parent_bg.pixmap()

            x = global_pos.x() - self.parent().geometry().x()
            y = global_pos.y() - self.parent().geometry().y()
            x = max(0, min(x, bg_pixmap.width() - 1))
            y = max(0, min(y, bg_pixmap.height() - 1))
            w = min(panel_rect.width(), bg_pixmap.width() - x)
            h = min(panel_rect.height(), bg_pixmap.height() - y)

            if w <= 0 or h <= 0:
                return

            bg_sub = bg_pixmap.copy(x, y, w, h)
            qimage = bg_sub.toImage()
            if qimage.format() != QImage.Format_ARGB32:
                qimage = qimage.convertToFormat(QImage.Format_ARGB32)

            buffer = qimage.constBits().tobytes()
            pil_img = Image.frombuffer("RGBA", (qimage.width(), qimage.height()),
                                       buffer, "raw", "BGRA", 0, 1)

            blurred = pil_img.filter(ImageFilter.GaussianBlur(radius=self.blur_radius))

            data = blurred.tobytes("raw", "BGRA")
            qimg_blurred = QImage(data, blurred.width, blurred.height, QImage.Format_ARGB32)
            blurred_pixmap = QPixmap.fromImage(qimg_blurred)

            painter = QPainter(self)
            painter.drawPixmap(self.rect(), blurred_pixmap)

            # 绘制霓虹边框
            painter.setPen(QColor(0, 255, 249))
            painter.drawRoundedRect(0, 0, self.width() - 1, self.height() - 1, 15, 15)

            painter.end()
        except Exception as e:
            print(f"BlurPanel.paintEvent 出错: {e}")
            traceback.print_exc()


# ==================== Web 服务器（完整移植自原 Tkinter 版本）====================
class WebServer:
    """简单的 HTTP 服务器，用于手机控制"""

    def __init__(self, music_box, port=54188):
        self.music_box = music_box
        self.port = port
        self.server = None
        self.server_thread = None
        self.running = False

    def get_local_ip(self):
        """获取本机IP地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def generate_html(self):
        """生成HTML页面，不再包含关于信息"""
        ip = self.get_local_ip()
        url = f"http://{ip}:{self.port}"
        volume_percent = int(self.music_box.volume * 100)
        mic_key_display = self.music_box.format_hotkey_for_display(self.music_box.mic_key)

        html = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>CS2音乐盒控制器 - 手机控制</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f0f0f0;
                }}
                h1, h2 {{
                    color: #333;
                }}
                .container {{
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .status {{
                    background: #e8f5e9;
                    padding: 10px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                .control-section {{
                    margin-bottom: 30px;
                }}
                .button {{
                    display: block;
                    width: 100%;
                    padding: 15px;
                    margin: 10px 0;
                    background: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 16px;
                    cursor: pointer;
                    text-align: center;
                }}
                .button:hover {{ background: #1976D2; }}
                .stop-btn {{ background: #f44336; }}
                .collection-btn {{ background: #4CAF50; }}
                .test-btn {{ background: #FF9800; }}
                .upload-btn {{ background: #9C27B0; }}
                .lock-btn {{ background: #607D8B; }}
                .file-list {{
                    background: #f5f5f5;
                    border-radius: 5px;
                    padding: 10px;
                    max-height: 300px;
                    overflow-y: auto;
                }}
                .file-item {{
                    padding: 8px;
                    border-bottom: 1px solid #ddd;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                .c-key-status {{
                    display: inline-block;
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-weight: bold;
                }}
                .c-key-pressed {{ background: #4CAF50; color: white; }}
                .c-key-released {{ background: #f44336; color: white; }}
                .message {{
                    background: #e8f5e9;
                    padding: 10px;
                    border-radius: 5px;
                    margin: 10px 0;
                    display: none;
                }}
                .message.show {{ display: block; }}
                .upload-form {{
                    background: #f5f5f5;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 15px 0;
                }}
                .upload-input {{
                    width: 100%;
                    padding: 10px;
                    margin: 10px 0;
                    border: 2px dashed #2196F3;
                    border-radius: 5px;
                    background: white;
                    box-sizing: border-box;
                }}
                .upload-progress {{ display: none; width: 100%; height: 20px; }}
                .volume-control {{
                    background: #fff3e0;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                .volume-slider {{ width: 100%; margin: 10px 0; }}
                .volume-value {{ font-size: 18px; font-weight: bold; color: #2196F3; }}
                @media (max-width: 600px) {{
                    .button {{ font-size: 14px; padding: 12px; }}
                    h1 {{ font-size: 20px; }}
                }}
            </style>
            <script>
                function playAudio(name) {{
                    fetch('/play?name=' + encodeURIComponent(name))
                        .then(response => response.json())
                        .then(data => {{ showMessage('播放请求已发送: ' + name); updateStatus(); }});
                }}
                function playCollection(name) {{
                    fetch('/play_collection?name=' + encodeURIComponent(name))
                        .then(response => response.json())
                        .then(data => {{ showMessage('合集播放请求已发送: ' + name); updateStatus(); }});
                }}
                function stopPlayback() {{
                    fetch('/stop').then(response => response.json())
                        .then(data => {{ showMessage('停止播放请求已发送'); updateStatus(); }});
                }}
                function testCKey(hold) {{
                    fetch('/test_c_key?hold=' + hold).then(response => response.json())
                        .then(data => {{ showMessage('开麦键测试: ' + (hold === 'true' ? '按下' : '释放')); updateStatus(); }});
                }}
                function toggleCKey() {{
                    fetch('/toggle_c_key').then(response => response.json())
                        .then(data => {{ showMessage('开麦键锁定状态已切换'); updateStatus(); }});
                }}
                function setVolume(level) {{
                    fetch('/set_volume?level=' + level).then(response => response.json())
                        .then(data => {{
                            document.getElementById('volume-display').textContent = level + '%';
                            showMessage('音量已设置为 ' + level + '%');
                        }});
                }}
                function showMessage(text) {{
                    const msgDiv = document.getElementById('message');
                    msgDiv.textContent = text;
                    msgDiv.classList.add('show');
                    setTimeout(() => msgDiv.classList.remove('show'), 3000);
                }}
                function updateStatus() {{
                    fetch('/status').then(response => response.json()).then(data => {{
                        const micKeyDiv = document.getElementById('c-key-status');
                        micKeyDiv.textContent = data.c_key_held ? '按下' : '释放';
                        micKeyDiv.className = 'c-key-status ' + (data.c_key_held ? 'c-key-pressed' : 'c-key-released');
                        document.getElementById('mic-key-name').textContent = data.mic_key_display;
                        document.getElementById('play-status').textContent = data.is_playing ? '播放中: ' + data.current_playing : '空闲';
                        document.getElementById('device-status').textContent = data.device_name || '未选择设备';
                        document.getElementById('volume-display').textContent = Math.round(data.volume * 100) + '%';
                        document.getElementById('volume-slider').value = data.volume * 100;
                    }});
                }}
                function uploadAudio() {{
                    const fileInput = document.getElementById('audio-file');
                    if (!fileInput.files.length) {{ showMessage('请先选择音频文件'); return; }}
                    const file = fileInput.files[0];
                    if (!['mp3','wav','ogg','flac','m4a'].includes(file.name.split('.').pop().toLowerCase())) {{
                        showMessage('只支持 MP3, WAV, OGG, FLAC, M4A'); return;
                    }}
                    if (file.size > 50*1024*1024) {{ showMessage('文件大小不能超过50MB'); return; }}
                    const formData = new FormData(); formData.append('audio', file);
                    const xhr = new XMLHttpRequest();
                    xhr.upload.addEventListener('progress', e => {{
                        if (e.lengthComputable) document.getElementById('upload-progress').value = (e.loaded / e.total) * 100;
                    }});
                    xhr.onload = () => {{
                        if (xhr.status === 200) {{
                            showMessage('上传成功，页面即将刷新');
                            setTimeout(() => location.reload(), 2000);
                        }} else {{
                            showMessage('上传失败');
                        }}
                    }};
                    xhr.open('POST', '/upload_audio'); xhr.send(formData);
                }}
                document.addEventListener('DOMContentLoaded', () => {{
                    updateStatus();
                    setInterval(updateStatus, 3000);
                }});
            </script>
        </head>
        <body>
            <div class="container">
                <h1>🎵 CS2音乐盒控制器</h1>
                <div class="status">
                    <p><strong>服务器地址:</strong> {url}</p>
                    <p><strong>播放状态:</strong> <span id="play-status">获取中...</span></p>
                    <p><strong>开麦键状态:</strong> <span id="c-key-status" class="c-key-status c-key-released">获取中...</span> (键位: <span id="mic-key-name">{mic_key_display}</span>)</p>
                    <p><strong>音频设备:</strong> <span id="device-status">获取中...</span></p>
                </div>
                <div id="message" class="message"></div>
                <div class="volume-control">
                    <h3>🔊 音量调节</h3>
                    <input type="range" id="volume-slider" class="volume-slider" min="0" max="100" value="{volume_percent}" onchange="setVolume(this.value)">
                    <div style="text-align: center;">当前音量: <span id="volume-display" class="volume-value">{volume_percent}%</span></div>
                </div>
                <div class="control-section">
                    <h2>📤 音频上传</h2>
                    <div class="upload-form">
                        <input type="file" id="audio-file" class="upload-input" accept=".mp3,.wav,.ogg,.flac,.m4a">
                        <progress id="upload-progress" class="upload-progress" value="0" max="100"></progress>
                        <button class="button upload-btn" onclick="uploadAudio()">📤 上传音频文件</button>
                        <p style="font-size:12px;">支持MP3/WAV/OGG/FLAC/M4A ≤50MB</p>
                    </div>
                </div>
                <div class="control-section">
                    <h2>🎮 控制面板</h2>
                    <button class="button stop-btn" onclick="stopPlayback()">⏹️ 停止播放</button>
                    <button class="button test-btn" onclick="testCKey('true')">🔊 测试{mic_key_display}按下</button>
                    <button class="button test-btn" onclick="testCKey('false')">🔈 测试{mic_key_display}释放</button>
                    <button class="button lock-btn" onclick="toggleCKey()">锁定开麦键</button>
                </div>
        """

        # 添加单个音效
        if self.music_box.audio_files:
            html += '<div class="control-section"><h2>🎵 单个音效</h2><div class="file-list">'
            for file_name, info in self.music_box.audio_files.items():
                hotkey_display = self.music_box.format_hotkey_for_display(info.get('hotkey',''))
                source = info.get('source','本地添加')
                html += f'<div class="file-item"><div><span>{file_name}</span><br><small>来源: {source} | 快捷键: {hotkey_display}</small></div><div><button onclick="playAudio(\'{file_name}\')">播放</button></div></div>'
            html += '</div></div>'

        # 添加合集
        if self.music_box.collections:
            html += '<div class="control-section"><h2>📁 音乐盒合集</h2><div class="file-list">'
            for collection_name, collection_info in self.music_box.collections.items():
                hotkey_display = self.music_box.format_hotkey_for_display(collection_info.get('hotkey',''))
                files_count = len(collection_info.get('files',[]))
                html += f'<div class="file-item"><div><strong>{collection_name}</strong><br><small>{files_count}个音效 | 快捷键: {hotkey_display}</small></div><button class="collection-btn" onclick="playCollection(\'{collection_name}\')">随机播放</button></div>'
            html += '</div></div>'

        html += """
            </div>
            <footer style="text-align:center; margin-top:30px; color:#666;">CS2音乐盒控制器 v6.4 | 手机控制端</footer>
        </body></html>
        """
        return html

    def start(self):
        """启动Web服务器"""
        if self.running:
            return True

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                self.webserver = self.webserver_instance
                super().__init__(*args, **kwargs)

            def parse_multipart_form_data(self):
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    if content_length == 0:
                        return None
                    content_type = self.headers.get('Content-Type', '')
                    if 'boundary=' not in content_type:
                        return None
                    boundary = content_type.split('boundary=')[1].strip()
                    if boundary.startswith('"') and boundary.endswith('"'):
                        boundary = boundary[1:-1]
                    boundary = boundary.encode('utf-8')
                    read_boundary = b'--' + boundary
                    data = self.rfile.read(content_length)
                    parts = []
                    start = 0
                    while True:
                        boundary_pos = data.find(read_boundary, start)
                        if boundary_pos == -1:
                            break
                        start = boundary_pos + len(read_boundary)
                        next_boundary = data.find(read_boundary, start)
                        if next_boundary == -1:
                            next_boundary = data.find(b'--' + boundary + b'--', start)
                            if next_boundary == -1:
                                break
                        part_data = data[start:next_boundary]
                        if part_data.startswith(b'\r\n'):
                            part_data = part_data[2:]
                        parts.append(part_data)
                    form_data = {}
                    for part in parts:
                        if b'\r\n\r\n' not in part:
                            continue
                        headers_data, body_data = part.split(b'\r\n\r\n', 1)
                        headers = headers_data.decode('utf-8', errors='ignore').split('\r\n')
                        name = None
                        filename = None
                        for header in headers:
                            if header.lower().startswith('content-disposition:'):
                                import re
                                name_match = re.search(r'name="([^"]+)"', header, re.IGNORECASE)
                                if name_match:
                                    name = name_match.group(1)
                                filename_match = re.search(r'filename="([^"]+)"', header, re.IGNORECASE)
                                if filename_match:
                                    filename = filename_match.group(1)
                        if name:
                            if filename:
                                clean_body = body_data.rstrip(b'\r\n')
                                form_data[name] = {'filename': filename, 'data': clean_body}
                            else:
                                form_data[name] = body_data.decode('utf-8', errors='ignore').rstrip('\r\n')
                    return form_data
                except Exception as e:
                    print(f"解析multipart数据时出错: {e}")
                    traceback.print_exc()
                    return None

            def do_POST(self):
                try:
                    parsed_path = urllib.parse.urlparse(self.path)
                    path = parsed_path.path
                    if path == '/upload_audio':
                        content_length = int(self.headers.get('Content-Length', 0))
                        if content_length == 0:
                            self.send_json({'success': False, 'message': '请求内容为空'}, 400)
                            return
                        if content_length > 50 * 1024 * 1024:
                            self.send_json({'success': False, 'message': '文件大小超过50MB限制'}, 413)
                            return
                        content_type = self.headers.get('Content-Type', '')
                        if 'multipart/form-data' not in content_type:
                            self.send_json({'success': False, 'message': '不支持的Content-Type'}, 400)
                            return
                        try:
                            form_data = self.parse_multipart_form_data()
                            if not form_data or 'audio' not in form_data:
                                self.send_json({'success': False, 'message': '没有上传音频文件'}, 400)
                                return
                            file_info = form_data['audio']
                            if not isinstance(file_info, dict) or 'filename' not in file_info:
                                self.send_json({'success': False, 'message': '文件数据格式不正确'}, 400)
                                return
                            file_data = file_info['data']
                            filename = file_info['filename']
                            import os
                            file_ext = os.path.splitext(filename)[1].lower()
                            allowed = ['.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac']
                            if file_ext not in allowed:
                                self.send_json({'success': False, 'message': f'只支持 {", ".join(allowed)} 格式'}, 400)
                                return
                            import re, unicodedata
                            safe_filename = re.sub(r'[<>:"/\\|?*]', '', filename)
                            safe_filename = ''.join(ch for ch in safe_filename if unicodedata.category(ch)[0] != 'C')
                            safe_filename = safe_filename[:100]
                            if not safe_filename:
                                import time
                                safe_filename = f"上传音频_{int(time.time())}{file_ext}"
                            base_dir = self.webserver.music_box.base_dir
                            audio_dir = os.path.join(base_dir, "音频")
                            os.makedirs(audio_dir, exist_ok=True)
                            original_name = safe_filename
                            counter = 1
                            while os.path.exists(os.path.join(audio_dir, safe_filename)):
                                name, ext = os.path.splitext(original_name)
                                safe_filename = f"{name}_{counter}{ext}"
                                counter += 1
                                if counter > 100:
                                    safe_filename = f"上传音频_{int(time.time())}{ext}"
                                    break
                            file_path = os.path.join(audio_dir, safe_filename)
                            with open(file_path, 'wb') as f:
                                f.write(file_data)

                            # 使用信号触发添加到音乐盒
                            self.webserver.music_box.web_upload_complete.emit(safe_filename, file_path)

                            # 直接返回成功（文件已保存，添加操作由信号异步处理）
                            self.send_json({'success': True, 'message': f'音频 {safe_filename} 上传成功',
                                            'filename': safe_filename})
                        except Exception as e:
                            traceback.print_exc()
                            self.send_json({'success': False, 'message': f'上传失败: {str(e)}'}, 500)
                    else:
                        self.send_json({'success': False, 'message': 'Not Found'}, 404)
                except Exception as e:
                    traceback.print_exc()
                    self.send_json({'success': False, 'message': f'服务器内部错误: {str(e)}'}, 500)

            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()

            def do_GET(self):
                parsed_path = urllib.parse.urlparse(self.path)
                path = parsed_path.path
                query = urllib.parse.parse_qs(parsed_path.query)

                if path == '/':
                    html = self.webserver.generate_html()
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(html.encode('utf-8'))
                elif path == '/play':
                    name = query.get('name', [''])[0]
                    if name:
                        self.webserver.music_box.web_play_requested.emit(name)
                    self.send_json({'status': 'ok'})
                elif path == '/play_collection':
                    name = query.get('name', [''])[0]
                    if name and name in self.webserver.music_box.collections:
                        self.webserver.music_box.web_collection_requested.emit(name)
                    self.send_json({'status': 'ok'})
                elif path == '/stop':
                    self.webserver.music_box.web_stop_requested.emit()
                    self.send_json({'status': 'ok'})
                elif path == '/test_c_key':
                    hold = query.get('hold', [''])[0] == 'true'
                    self.webserver.music_box.web_test_c_key_signal.emit(hold)
                    self.send_json({'status': 'ok'})
                elif path == '/toggle_c_key':
                    self.webserver.music_box.web_toggle_c_key_signal.emit()
                    self.send_json({'status': 'ok'})
                elif path == '/set_volume':
                    level = query.get('level', ['100'])[0]
                    try:
                        vol = int(level) / 100.0
                        vol = max(0.0, min(1.0, vol))
                        self.webserver.music_box.volume = vol
                        self.send_json({'status': 'ok', 'volume': vol})
                    except:
                        self.send_json({'status': 'error'})
                elif path == '/status':
                    status = {
                        'is_playing': self.webserver.music_box.is_playing,
                        'current_playing': self.webserver.music_box.current_playing,
                        'c_key_held': self.webserver.music_box.c_key_held,
                        'mic_key_display': self.webserver.music_box.format_hotkey_for_display(
                            self.webserver.music_box.mic_key),
                        'volume': self.webserver.music_box.volume,
                        'device_name': '未选择设备'
                    }
                    if self.webserver.music_box.selected_device_index is not None:
                        for info in self.webserver.music_box.devices_info or []:
                            if info['index'] == self.webserver.music_box.selected_device_index:
                                status['device_name'] = info['name']
                                break
                    self.send_json(status)
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'404')

            def send_json(self, data, status=200):
                self.send_response(status)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode('utf-8'))

            def log_message(self, *args):
                pass

        Handler.webserver_instance = self

        try:
            self.server = socketserver.TCPServer(("", self.port), Handler)
            self.server.timeout = 1
            self.running = True
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            print(f"Web服务器已启动，地址: http://{self.get_local_ip()}:{self.port}")
            return True
        except Exception as e:
            print(f"启动Web服务器失败: {e}")
            return False

    def _run_server(self):
        while self.running:
            try:
                self.server.handle_request()
            except:
                pass

    def stop(self):
        self.running = False
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except:
                pass
        print("Web服务器已停止")


# ==================== 主应用程序类 ====================
class CS2MusicBox(QMainWindow):
    """主窗口，整合所有功能"""

    # 自定义信号，用于线程安全地更新 GUI
    update_status_signal = Signal(str)
    update_play_status_signal = Signal(bool, str)
    update_c_key_indicator_signal = Signal(bool)
    update_listener_status_signal = Signal(str, str)  # text, color
    show_message_signal = Signal(str, str)  # title, message
    web_play_requested = Signal(str)
    web_collection_requested = Signal(str)
    web_stop_requested = Signal()
    web_test_c_key_signal = Signal(bool)  # True=按下, False=释放
    web_toggle_c_key_signal = Signal()
    web_upload_complete = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CS2 音乐盒控制器 v6.4 (更换UI库重构近1500行)")
        screen = QApplication.primaryScreen().availableGeometry()
        max_width = screen.width()
        max_height = screen.height()
        self.setMaximumSize(max_width, max_height)
        # 调整初始窗口尺寸（用户可自行修改）
        self.resize(min(1300, max_width), min(900, max_height))
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 设置透明背景
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QMainWindow{background:transparent;}")

        # 背景层
        self.bg_label = BlurBackgroundLabel(self)
        self.bg_label.setGeometry(0, 0, self.width(), self.height())

        # 毛玻璃面板
        self.panel = BlurPanel(self)
        self.content = QWidget(self.panel)
        self.content.setAttribute(Qt.WA_TranslucentBackground)

        # 初始化所有数据成员（与原 __init__ 一致）
        self.audio_files = OrderedDict()
        self.collections = OrderedDict()
        self.current_playing = None
        self.is_playing = False
        self.c_key_held = False
        self.selected_device_index = None
        self.stream = None
        self.play_thread = None
        self.stop_flag = False
        self.listener = None
        self.listener_paused = False
        self.hotkey_window = None
        self.collection_hotkey_window = None
        self.volume = 1.0
        self.mic_key = 'c'          # 默认开麦键
        self.stop_key = 'down'       # 默认停止快捷键
        self.c_key_lock = threading.Lock()

        # 获取程序基础目录
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        print(f"基础目录: {self.base_dir}")

        # 初始化音频
        try:
            self.p = pyaudio.PyAudio()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法初始化音频系统: {str(e)}\n请确保音频设备正常工作。")
            sys.exit(1)

        self.keyboard_controller = Controller()

        # 键名映射（与原代码相同）
        self.key_map = {
            'Return': 'Enter', 'space': 'Space', 'Tab': 'Tab', 'BackSpace': 'Backspace',
            'Delete': 'Delete', 'Escape': 'Esc', 'Up': '↑', 'Down': '↓', 'Left': '←', 'Right': '→',
            'Shift_L': 'Left Shift', 'Shift_R': 'Right Shift', 'Control_L': 'Left Ctrl', 'Control_R': 'Right Ctrl',
            'Alt_L': 'Left Alt', 'Alt_R': 'Right Alt', 'Caps_Lock': 'CapsLock', 'Num_Lock': 'NumLock',
            'Scroll_Lock': 'ScrollLock', 'Pause': 'Pause', 'Print': 'Print Screen', 'Insert': 'Insert',
            'Home': 'Home', 'End': 'End', 'Page_Up': 'Page Up', 'Page_Down': 'Page Down',
            'F1': 'F1', 'F2': 'F2', 'F3': 'F3', 'F4': 'F4', 'F5': 'F5', 'F6': 'F6', 'F7': 'F7', 'F8': 'F8',
            'F9': 'F9', 'F10': 'F10', 'F11': 'F11', 'F12': 'F12',
        }

        # 配置文件
        self.config_file = os.path.join(self.base_dir, "music_box_config.json")
        self.play_counts_file = os.path.join(self.base_dir, "play_counts.json")

        # 加载配置
        self.load_config()
        self.load_play_counts()

        # 初始化 Web 服务器
        self.web_server = WebServer(self, port=54188)
        self.web_server_enabled = False

        # 创建界面
        self.setup_ui()

        # 刷新列表显示（解决列表空白问题）
        self.refresh_treeview()
        self.refresh_collection_treeview()

        # 启动快捷键监听
        self.start_key_listener()

        # 连接信号
        self.update_status_signal.connect(lambda text: self.status_label.setText(text))
        self.update_play_status_signal.connect(self.update_play_status)
        self.update_c_key_indicator_signal.connect(self._set_c_key_indicator)
        self.update_listener_status_signal.connect(self._set_listener_status)
        self.show_message_signal.connect(lambda t, m: QMessageBox.information(self, t, m))
        self.web_play_requested.connect(self.play_from_web)
        self.web_collection_requested.connect(self.play_from_collection_web)
        self.web_stop_requested.connect(self.stop_playback)
        self.web_test_c_key_signal.connect(self.handle_web_test_c_key)
        self.web_toggle_c_key_signal.connect(self.handle_web_toggle_c_key)
        self.web_upload_complete.connect(self.add_uploaded_audio)


        # 刷新设备列表（同时会根据优先级选择设备）
        QTimer.singleShot(100, self.refresh_device_list)

        # 如果配置中启用了 Web 服务器，立即启动（不再使用延迟）
        if self.web_server_enabled:
            print("检测到配置中启用了 Web 服务器，正在启动...")
            self.start_web_server()

        # 如果没有 pydub，弹出提示
        if not PYDUB_AVAILABLE:
            QTimer.singleShot(2000, self.show_mp3_warning)

    # ------------------ 辅助方法：线程安全更新 GUI ------------------
    def after(self, ms, func):
        QTimer.singleShot(ms, func)

    def _set_c_key_indicator(self, held):
        if held:
            self.c_key_indicator.setText("按下")
            self.c_key_indicator.setStyleSheet("background-color: green; color: white; padding: 2px 5px; border-radius: 3px;")
        else:
            self.c_key_indicator.setText("释放")
            self.c_key_indicator.setStyleSheet("background-color: red; color: white; padding: 2px 5px; border-radius: 3px;")

    def handle_web_test_c_key(self, hold):
        if hold:
            self.hold_c_key(True)
            QTimer.singleShot(2000, lambda: self.release_c_key(True))
        else:
            self.release_c_key(True)

    def handle_web_toggle_c_key(self):
        current = self.c_key_held
        if current:
            self.release_c_key(False)
        else:
            self.hold_c_key(False)

    def _set_listener_status(self, text, color):
        self.listener_status.setText(text)
        self.listener_status.setStyleSheet(f"color: {color}; font-weight: bold;")

    # ------------------ 快捷键辅助函数（与原代码相同） ------------------
    def key_event_to_string(self, event):
        # 完全复制原代码中的方法（用于 Tkinter 兼容，此处可能不再使用，但保留）
        numpad_keycodes = {96,97,98,99,100,101,102,103,104,105, 110, 107, 109, 106, 111}
        if event.keysym.startswith('KP_'):
            suffix = event.keysym[3:].lower()
            if suffix.isdigit():
                return f'num{suffix}'
            elif suffix == 'add':
                return 'num_add'
            elif suffix == 'subtract':
                return 'num_sub'
            elif suffix == 'multiply':
                return 'num_mul'
            elif suffix == 'divide':
                return 'num_div'
            elif suffix == 'decimal':
                return 'num_dec'
            else:
                return f'num_{suffix}'
        elif event.keycode in numpad_keycodes:
            if event.char and event.char.isprintable():
                return f'num{event.char}'
            else:
                return f'num_{event.keysym.lower()}'
        elif event.keysym in self.key_map:
            return self.key_map[event.keysym].lower().replace(' ', '_')
        elif event.char and event.char.isprintable():
            return event.char.lower()
        else:
            return event.keysym.lower()

    def pynput_key_to_string(self, key):
        from pynput.keyboard import Key, KeyCode
        numpad_vk = {96,97,98,99,100,101,102,103,104,105, 110, 107, 109, 106, 111}
        if isinstance(key, KeyCode):
            if key.char is not None:
                return key.char.lower()
            else:
                if key.vk in numpad_vk:
                    if 96 <= key.vk <= 105:
                        return f'num{key.vk - 96}'
                    elif key.vk == 110:
                        return 'num_dec'
                    elif key.vk == 107:
                        return 'num_add'
                    elif key.vk == 109:
                        return 'num_sub'
                    elif key.vk == 106:
                        return 'num_mul'
                    elif key.vk == 111:
                        return 'num_div'
                return ''
        elif isinstance(key, Key):
            return key.name.lower()
        return ''

    # 将 Qt 按键事件转换为与 pynput 一致的字符串
    def qt_key_to_string(self, event):
        key = event.key()
        text = event.text()

        # 处理可打印字符
        if text and text.isprintable():
            # 小键盘数字（通过 key 范围判断）
            if Qt.Key_0 <= key <= Qt.Key_9:
                return f'num{text}'
            # 小键盘符号
            if key == Qt.Key_Period:
                return 'num_dec'
            if key == Qt.Key_Plus:
                return 'num_add'
            if key == Qt.Key_Minus:
                return 'num_sub'
            if key == Qt.Key_Asterisk:
                return 'num_mul'
            if key == Qt.Key_Slash:
                return 'num_div'
            return text.lower()

        # 功能键映射
        key_map = {
            Qt.Key_Return: 'enter', Qt.Key_Enter: 'enter', Qt.Key_Space: 'space',
            Qt.Key_Tab: 'tab', Qt.Key_Backspace: 'backspace', Qt.Key_Delete: 'delete',
            Qt.Key_Escape: 'esc', Qt.Key_Up: 'up', Qt.Key_Down: 'down', Qt.Key_Left: 'left',
            Qt.Key_Right: 'right', Qt.Key_Home: 'home', Qt.Key_End: 'end', Qt.Key_PageUp: 'page_up',
            Qt.Key_PageDown: 'page_down', Qt.Key_Insert: 'insert', Qt.Key_Pause: 'pause',
            Qt.Key_Print: 'print', Qt.Key_F1: 'f1', Qt.Key_F2: 'f2', Qt.Key_F3: 'f3',
            Qt.Key_F4: 'f4', Qt.Key_F5: 'f5', Qt.Key_F6: 'f6', Qt.Key_F7: 'f7', Qt.Key_F8: 'f8',
            Qt.Key_F9: 'f9', Qt.Key_F10: 'f10', Qt.Key_F11: 'f11', Qt.Key_F12: 'f12',
        }
        if key in key_map:
            return key_map[key]

        # 未处理的按键
        return ''

    def format_hotkey_for_display(self, hotkey):
        if not hotkey:
            return '无'
        if hotkey.startswith('num') and hotkey[3:].isdigit():
            return f'小键盘 {hotkey[3:]}'
        mapping = {
            'num_add': '小键盘 +', 'num_sub': '小键盘 -', 'num_mul': '小键盘 *',
            'num_div': '小键盘 /', 'num_dec': '小键盘 .', 'num_delete': '小键盘 Del',
            'num_insert': '小键盘 Ins', 'num_home': '小键盘 Home', 'num_end': '小键盘 End',
            'num_page_up': '小键盘 PgUp', 'num_page_down': '小键盘 PgDn',
        }
        if hotkey in mapping:
            return mapping[hotkey]
        return hotkey.upper()

    # ------------------ 全局监听暂停/恢复 ------------------
    def pause_key_listener(self):
        """暂停全局快捷键监听"""
        if self.listener and not self.listener_paused:
            self.listener.stop()
            self.listener_paused = True
            self.update_listener_status_signal.emit("已暂停", "orange")
            print("快捷键监听已暂停")

    def resume_key_listener(self):
        """恢复全局快捷键监听"""
        if self.listener_paused:
            self.start_key_listener()
            self.listener_paused = False
            self.update_listener_status_signal.emit("正常", "green")
            print("快捷键监听已恢复")

    # ------------------ GUI 构建 ------------------
    def setup_ui(self):
        """创建所有控件并布局"""
        # 主布局：面板内嵌 content
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(20, 20, 20, 20)
        panel_layout.addWidget(self.content)

        # content 内部使用垂直布局
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        # 标题
        title = QLabel("🎵 CS2 音乐盒控制器")
        title.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 24px;
                font-weight: bold;
                background: transparent;
            }
        """)
        title.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(title)

        # 选项卡
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 0; background: transparent; }
            QTabBar::tab { background: rgba(0,0,0,0.5); color: white; padding: 8px 16px;
                           margin-right: 2px; border-top-left-radius: 5px; border-top-right-radius: 5px; }
            QTabBar::tab:selected { background: rgba(0,255,249,0.7); font-weight: bold; }
        """)
        content_layout.addWidget(self.tab_widget)

        # 创建四个标签页
        self.create_single_tab()
        self.create_collection_tab()
        self.create_web_tab()
        self.create_about_tab()

        # 底部状态栏
        status_frame = QFrame()
        status_frame.setStyleSheet("background: rgba(0,0,0,0.4); border-radius: 3px;")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(5, 2, 5, 2)
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #00fff9; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        content_layout.addWidget(status_frame)

        # 更新面板几何
        self.update_panel_geometry()

    def create_single_tab(self):
        """单个音效标签页"""
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)

        # 左侧：设备选择和音效列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 设备选择区域
        device_group = QFrame()
        device_group.setStyleSheet("background: rgba(0,0,0,0.3); border-radius: 5px; padding: 5px;")
        dev_layout = QVBoxLayout(device_group)
        dev_layout.addWidget(QLabel("音频输出设备:"))

        # 修复设备下拉列表样式，使下拉项可见
        self.device_combo = QComboBox()
        self.device_combo.setStyleSheet("""
            QComboBox {
                background: rgba(255,255,255,0.2);
                color: white;
                padding: 5px;
                border: 1px solid #00fff9;
                border-radius: 3px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: white;
                selection-background-color: #00fff9;
                selection-color: black;
            }
        """)
        self.device_combo.currentIndexChanged.connect(self.on_device_select)
        dev_layout.addWidget(self.device_combo)

        btn_frame = QHBoxLayout()
        self.refresh_dev_btn = QPushButton("刷新设备列表")
        self.refresh_dev_btn.clicked.connect(self.refresh_device_list)
        self.test_dev_btn = QPushButton("测试设备")
        self.test_dev_btn.clicked.connect(self.test_device)
        btn_frame.addWidget(self.refresh_dev_btn)
        btn_frame.addWidget(self.test_dev_btn)
        dev_layout.addLayout(btn_frame)

        self.device_info_label = QLabel("未选择设备")
        self.device_info_label.setStyleSheet("color: #aaa; font-size: 10px;")
        dev_layout.addWidget(self.device_info_label)

        left_layout.addWidget(device_group)

        # 音效列表
        list_group = QFrame()
        list_group.setStyleSheet("background: rgba(0,0,0,0.3); border-radius: 5px; padding: 5px;")
        list_layout = QVBoxLayout(list_group)
        list_layout.addWidget(QLabel("音效列表:"))

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['文件名', '快捷键', '时长', '格式', '来源'])
        self.tree.setStyleSheet("""
            QTreeWidget {
                background: rgba(0,0,0,0.4);
                color: white;
                alternate-background-color: rgba(255,255,255,0.05);
            }
            QTreeWidget::item:hover { background: rgba(255,255,255,0.1); }
            QTreeWidget::item:selected { background: rgba(0,255,249,0.3); }
            QHeaderView::section {
                background: rgba(0,0,0,0.6);
                color: white;
                padding: 4px;
                border: none;
            }
        """)
        self.tree.setAlternatingRowColors(True)
        self.tree.setIndentation(0)
        self.tree.setSortingEnabled(False)
        self.tree.itemDoubleClicked.connect(self.on_item_double_click)
        self.tree.itemSelectionChanged.connect(self.on_tree_select)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_tree_menu)

        # 设置列宽
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # 文件名列自适应
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        list_layout.addWidget(self.tree)
        left_layout.addWidget(list_group)

        # 右侧：控制面板
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)

        # 控制面板
        ctrl_group = QFrame()
        ctrl_group.setStyleSheet("background: rgba(0,0,0,0.3); border-radius: 5px; padding: 10px;")
        ctrl_layout = QVBoxLayout(ctrl_group)

        self.add_btn = QPushButton("添加音效文件")
        self.add_btn.clicked.connect(self.add_audio_file)
        ctrl_layout.addWidget(self.add_btn)

        self.delete_btn = QPushButton("删除选中音效")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self.remove_audio_file)
        ctrl_layout.addWidget(self.delete_btn)

        self.hotkey_btn = QPushButton("设置快捷键")
        self.hotkey_btn.setEnabled(False)
        self.hotkey_btn.clicked.connect(self.set_hotkey)
        ctrl_layout.addWidget(self.hotkey_btn)

        play_frame = QHBoxLayout()
        self.play_btn = QPushButton("▶ 播放")
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self.test_play)
        self.stop_btn = QPushButton("■ 停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_playback)
        play_frame.addWidget(self.play_btn)
        play_frame.addWidget(self.stop_btn)
        ctrl_layout.addLayout(play_frame)

        right_layout.addWidget(ctrl_group)

        # 状态信息
        status_group = QFrame()
        status_group.setStyleSheet("background: rgba(0,0,0,0.3); border-radius: 5px; padding: 10px;")
        status_layout = QVBoxLayout(status_group)

        self.play_status_label = QLabel("状态: 空闲")
        status_layout.addWidget(self.play_status_label)

        self.current_file_label = QLabel("当前: 无")
        status_layout.addWidget(self.current_file_label)

        ckey_frame = QHBoxLayout()
        ckey_frame.addWidget(QLabel("开麦键状态:"))
        self.c_key_indicator = QLabel("释放")
        self.c_key_indicator.setStyleSheet("background-color: red; color: white; padding: 2px 5px; border-radius: 3px;")
        ckey_frame.addWidget(self.c_key_indicator)
        self.mic_key_display_label = QLabel(f"键位: {self.format_hotkey_for_display(self.mic_key)}")
        ckey_frame.addWidget(self.mic_key_display_label)
        ckey_frame.addStretch()
        status_layout.addLayout(ckey_frame)

        stopkey_frame = QHBoxLayout()
        stopkey_frame.addWidget(QLabel("停止快捷键:"))
        self.stop_key_display_label = QLabel(self.format_hotkey_for_display(self.stop_key))
        self.stop_key_display_label.setStyleSheet("font-weight: bold; color: #00fff9;")
        stopkey_frame.addWidget(self.stop_key_display_label)
        stopkey_frame.addStretch()
        status_layout.addLayout(stopkey_frame)

        listener_frame = QHBoxLayout()
        listener_frame.addWidget(QLabel("快捷键监听:"))
        self.listener_status = QLabel("正常")
        self.listener_status.setStyleSheet("color: green; font-weight: bold;")
        listener_frame.addWidget(self.listener_status)
        listener_frame.addStretch()
        status_layout.addLayout(listener_frame)

        right_layout.addWidget(status_group)

        # 调试工具
        debug_group = QFrame()
        debug_group.setStyleSheet("background: rgba(0,0,0,0.3); border-radius: 5px; padding: 10px;")
        debug_layout = QVBoxLayout(debug_group)

        self.test_c_key_down_btn = QPushButton("测试开麦键按下")
        self.test_c_key_down_btn.clicked.connect(lambda: self.hold_c_key(True))
        debug_layout.addWidget(self.test_c_key_down_btn)

        self.test_c_key_up_btn = QPushButton("测试开麦键释放")
        self.test_c_key_up_btn.clicked.connect(lambda: self.release_c_key(True))
        debug_layout.addWidget(self.test_c_key_up_btn)

        self.set_mic_key_btn = QPushButton("设置开麦键")
        self.set_mic_key_btn.clicked.connect(self.set_mic_key)
        debug_layout.addWidget(self.set_mic_key_btn)

        self.set_stop_key_btn = QPushButton("设置停止快捷键")
        self.set_stop_key_btn.clicked.connect(self.set_stop_key)
        debug_layout.addWidget(self.set_stop_key_btn)

        self.play_test_tone_btn = QPushButton("播放测试音")
        self.play_test_tone_btn.clicked.connect(self.play_test_tone)
        debug_layout.addWidget(self.play_test_tone_btn)

        self.show_device_info_btn = QPushButton("查看设备信息")
        self.show_device_info_btn.clicked.connect(self.show_device_info)
        debug_layout.addWidget(self.show_device_info_btn)

        self.check_hotkeys_btn = QPushButton("检查快捷键")
        self.check_hotkeys_btn.clicked.connect(self.check_hotkeys)
        debug_layout.addWidget(self.check_hotkeys_btn)

        right_layout.addWidget(debug_group)
        right_layout.addStretch()

        # 左右布局
        layout.addWidget(left_widget, 2)
        layout.addWidget(right_widget, 1)

        self.tab_widget.addTab(tab, "单个音效")

        # 统一按钮样式
        btn_style = """
            QPushButton {
                background: rgba(0,0,0,0.5);
                border: 2px solid #00fff9;
                border-radius: 5px;
                color: white;
                font-weight: bold;
                padding: 5px 10px;
            }
            QPushButton:hover { background: rgba(0,0,0,0.7); border-color: white; }
            QPushButton:pressed { background: rgba(0,255,249,0.3); }
            QPushButton:disabled { background: rgba(80,80,80,0.5); border-color: gray; color: #ccc; }
        """
        for btn in self.findChildren(QPushButton):
            btn.setStyleSheet(btn_style)

    def create_collection_tab(self):
        """音乐盒合集标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 合集列表
        self.collection_tree = QTreeWidget()
        self.collection_tree.setHeaderLabels(['合集名称', '快捷键', '音效数量'])
        self.collection_tree.setStyleSheet("""
            QTreeWidget {
                background: rgba(0,0,0,0.4);
                color: white;
                alternate-background-color: rgba(255,255,255,0.05);
            }
            QTreeWidget::item:hover { background: rgba(255,255,255,0.1); }
            QTreeWidget::item:selected { background: rgba(0,255,249,0.3); }
            QHeaderView::section {
                background: rgba(0,0,0,0.6);
                color: white;
                padding: 4px;
                border: none;
            }
        """)
        self.collection_tree.setAlternatingRowColors(True)
        self.collection_tree.itemSelectionChanged.connect(self.view_collection_details)
        header = self.collection_tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self.collection_tree)

        # 按钮行
        btn_layout = QHBoxLayout()
        self.create_col_btn = QPushButton("新建合集")
        self.create_col_btn.clicked.connect(self.create_collection)
        self.delete_col_btn = QPushButton("删除合集")
        self.delete_col_btn.clicked.connect(self.delete_collection)
        self.add_to_col_btn = QPushButton("添加音效到合集")
        self.add_to_col_btn.clicked.connect(self.add_files_to_collection_direct)
        self.remove_from_col_btn = QPushButton("移除音效")
        self.remove_from_col_btn.clicked.connect(self.remove_file_from_collection)
        self.view_col_detail_btn = QPushButton("查看详情")
        self.view_col_detail_btn.clicked.connect(self.view_collection_details)
        self.reset_play_counts_btn = QPushButton("重置播放计数")
        self.reset_play_counts_btn.clicked.connect(self.reset_collection_play_counts)
        self.set_col_hotkey_btn = QPushButton("设置快捷键")
        self.set_col_hotkey_btn.clicked.connect(self.set_collection_hotkey)

        for btn in [self.create_col_btn, self.delete_col_btn, self.add_to_col_btn,
                    self.remove_from_col_btn, self.view_col_detail_btn,
                    self.reset_play_counts_btn, self.set_col_hotkey_btn]:
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)

        # 合集详情
        self.collection_detail_text = QTextEdit()
        self.collection_detail_text.setReadOnly(True)
        self.collection_detail_text.setStyleSheet("background: rgba(0,0,0,0.4); color: white; border-radius: 5px;")
        layout.addWidget(self.collection_detail_text)

        self.tab_widget.addTab(tab, "音乐盒合集")

    def create_web_tab(self):
        """网页控制标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 服务器状态
        self.web_status_label = QLabel("服务器状态: 未启动")
        self.web_status_label.setStyleSheet("font-size: 14px; color: white;")
        layout.addWidget(self.web_status_label)

        self.web_address_label = QLabel("地址: 未启动")
        self.web_address_label.setStyleSheet("color: #00fff9;")
        layout.addWidget(self.web_address_label)

        # 按钮
        btn_layout = QHBoxLayout()
        self.web_start_btn = QPushButton("启动Web服务器")
        self.web_start_btn.clicked.connect(self.start_web_server)
        self.web_stop_btn = QPushButton("停止Web服务器")
        self.web_stop_btn.setEnabled(False)
        self.web_stop_btn.clicked.connect(self.stop_web_server)
        self.web_open_btn = QPushButton("在浏览器中打开")
        self.web_open_btn.setEnabled(False)
        self.web_open_btn.clicked.connect(self.open_web_browser)

        btn_layout.addWidget(self.web_start_btn)
        btn_layout.addWidget(self.web_stop_btn)
        btn_layout.addWidget(self.web_open_btn)
        layout.addLayout(btn_layout)

        # 使用说明
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setStyleSheet("background: rgba(0,0,0,0.4); color: white; border-radius: 5px;")
        instructions.setText("""
1. 启动Web服务器后，在同一局域网内的手机或电脑浏览器中访问上述地址
2. 网页将显示所有音效和合集，点击即可播放
3. 播放时会自动按下开麦键，播放完成后自动释放开麦键
4. 网页会自动更新播放状态和开麦键状态
5. 确保手机和电脑连接在同一WiFi网络下
6. 如有防火墙提示，请允许Python通过防火墙
        """)
        layout.addWidget(instructions)

        self.tab_widget.addTab(tab, "网页控制")

    def create_about_tab(self):
        """关于标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        about_text = QTextEdit()
        about_text.setReadOnly(True)
        about_text.setStyleSheet("background: rgba(0,0,0,0.4); color: white; border-radius: 5px;")
        about_text.setText("""
【使用教程】

1. 添加音效文件
   - 在“单个音效”标签页点击“添加音效文件”，选择音频文件（支持MP3、WAV、OGG、FLAC、M4A）。
   - 添加后文件会出现在列表中，可设置快捷键。

2. 设置快捷键（单曲/合集）
   - 右键点击列表中的项目，选择“设置快捷键”。
   - 在弹出窗口中按下您想绑定的按键（开麦键和停止键除外）。
   - 按回车键确认，按ESC取消。
   - 也可在选中项目后点击界面上的“设置快捷键”按钮。

3. 清除快捷键
   - 在设置快捷键窗口中点击“清除”按钮，或右键菜单选择“清除快捷键”（如已添加）。

4. 播放音效
   - 双击列表中的文件，或选中后点击“播放”按钮，或按下已绑定的快捷键。

5. 音乐盒合集
   - 新建合集后，点击“添加音效到合集”选择文件。
   - 合集播放采用智能随机算法：优先播放次数最少的音效，确保所有音效均匀播放。
   - 可以查看合集详情，包括每个音效的播放次数。

6. 自定义开麦键
   - 默认开麦键为 C。在调试工具中点击“设置开麦键”，按下您希望的按键即可。
   - 开麦键在播放音效时自动按下，播放结束后自动释放（如果播放前已锁定则保持按下）。
   - 开麦键不会触发任何音效播放。

7. 自定义停止快捷键
   - 默认停止键为 ↓（下方向键）。在调试工具中点击“设置停止快捷键”，按下您希望的按键即可。
   - 按下停止键将立即终止当前播放。

8. 网页控制
   - 启动Web服务器后，同一局域网内的手机/电脑浏览器访问显示的地址，可远程控制播放、调节音量、上传音频。
   - 网页端状态自动刷新。

9. 音量调节
   - 拖动滑块可调节全局音量。WAV文件即使没有安装pydub也能调节音量，MP3等格式需安装pydub以获得完整支持。

10. 快捷键冲突
    - 设置快捷键时，如果按键已被其他音效或合集使用，会提示是否覆盖。
    - 开麦键和停止键不可用作音效快捷键。

11. 其他
    - 下方向键（或自定义停止键）可随时停止播放。
    - 程序会自动保存配置（快捷键、设备选择等），下次启动时恢复。
    - 如遇MP3播放问题，请安装pydub：pip install pydub

【版权声明】
本软件（包括但不限于程序代码、图标、配置脚本及相关文档）由 [蓝烨] 独立开发，著作权归开发者所有。
© 2024-至今 [by.蓝烨]。保留所有权利。

【使用许可】
- 本软件为免费软件，允许个人用户自由使用。
- 未经开发者书面许可，禁止将本软件或其部分用于商业用途、重新打包分发或修改后以原创形式发布。
- 您可以将本软件分享给朋友，但请务必保留完整文件及本说明文档。

【免责声明】
1. 本软件按“现状”提供，不提供任何明示或暗示的担保，包括但不限于适销性、特定用途适用性及不侵权。
2. 使用本软件所产生的一切风险由您自行承担。开发者不对因使用本软件而导致的任何直接或间接损失（包括但不限于游戏封禁、数据丢失、设备故障等）承担责任。
3. 本软件可能调用第三方组件（如 pyaudio、pynput、pydub 等），这些组件遵循其各自的许可证。您在使用时请遵守相关条款。
        """)
        layout.addWidget(about_text)

        # 联系作者按钮
        contact_btn = QPushButton("📞 联系作者 (QQ群)")
        contact_btn.clicked.connect(lambda: webbrowser.open("https://qm.qq.com/q/XOza7RQt2Y"))
        layout.addWidget(contact_btn)

        self.tab_widget.addTab(tab, "关于")

    def update_panel_geometry(self):
        w = self.width()
        h = self.height()
        margin = 20
        panel_w = w - 2 * margin
        panel_h = h - 2 * margin
        self.panel.setGeometry(margin, margin, panel_w, panel_h)
        content_margin = 10
        self.content.setGeometry(content_margin, content_margin,
                                 panel_w - 2 * content_margin,
                                 panel_h - 2 * content_margin)

    def resizeEvent(self, event: QResizeEvent):
        w = event.size().width()
        h = event.size().height()
        self.bg_label.setGeometry(0, 0, w, h)
        self.update_panel_geometry()
        super().resizeEvent(event)

    # ------------------ 音频设备相关 ------------------
    def get_audio_devices(self):
        devices = []
        try:
            for i in range(self.p.get_device_count()):
                try:
                    device_info = self.p.get_device_info_by_index(i)
                    if device_info.get('maxOutputChannels', 0) > 0:
                        devices.append({
                            'index': i,
                            'name': device_info.get('name', f'Device {i}'),
                            'channels': device_info.get('maxOutputChannels', 0),
                            'defaultSampleRate': device_info.get('defaultSampleRate', 44100),
                        })
                except:
                    continue
        except:
            pass
        return devices

    def refresh_device_list(self):
        try:
            self.devices_info = self.get_audio_devices()
            self.device_combo.clear()
            if not self.devices_info:
                self.device_combo.addItem("未找到音频输出设备")
                self.device_info_label.setText("错误: 没有可用的音频输出设备")
                return
            # 将设备信息添加到下拉框
            for info in self.devices_info:
                self.device_combo.addItem(f"{info['index']}: {info['name']}", info)

            # 根据优先级选择设备
            selected_index = None
            # 1. 优先选择 Voicemeeter Input (VB-Audio Voi)
            for info in self.devices_info:
                if "Voicemeeter Input" in info['name'] and "VB-Audio Voi" in info['name']:
                    selected_index = info['index']
                    break
            # 2. 其次选择 Voicemeeter AUX Input (VB-Audio)
            if selected_index is None:
                for info in self.devices_info:
                    if "Voicemeeter AUX Input" in info['name'] and "VB-Audio" in info['name']:
                        selected_index = info['index']
                        break
            # 3. 然后选择上次使用的设备（如果存在）
            if selected_index is None and self.selected_device_index is not None:
                for info in self.devices_info:
                    if info['index'] == self.selected_device_index:
                        selected_index = info['index']
                        break
            # 4. 最后选择第一个可用设备
            if selected_index is None and self.devices_info:
                selected_index = self.devices_info[0]['index']

            # 设置当前选中项
            if selected_index is not None:
                for i in range(self.device_combo.count()):
                    if self.device_combo.itemData(i)['index'] == selected_index:
                        self.device_combo.setCurrentIndex(i)
                        self.selected_device_index = selected_index
                        break

            self.update_device_info_label()
            self.status_label.setText(f"找到 {len(self.devices_info)} 个音频设备")
        except Exception as e:
            print(f"刷新设备列表失败: {e}")

    def on_device_select(self, index):
        if index >= 0 and index < self.device_combo.count():
            data = self.device_combo.itemData(index)
            if data:
                self.selected_device_index = data['index']
                self.update_device_info_label()
                self.save_config()

    def update_device_info_label(self):
        if self.selected_device_index is not None:
            for info in self.devices_info:
                if info['index'] == self.selected_device_index:
                    self.device_info_label.setText(
                        f"设备ID: {info['index']} | 通道: {info['channels']} | 采样率: {info['defaultSampleRate']}Hz"
                    )
                    break

    def show_device_info(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("音频设备信息")
        dialog.resize(700, 500)
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        layout.addWidget(text)

        info_str = "=== 所有音频设备 ===\n\n"
        for i in range(self.p.get_device_count()):
            try:
                info = self.p.get_device_info_by_index(i)
                info_str += f"[设备 {i}]\n"
                info_str += f"  名称: {info.get('name', 'Unknown')}\n"
                info_str += f"  输入通道: {info.get('maxInputChannels', 0)}\n"
                info_str += f"  输出通道: {info.get('maxOutputChannels', 0)}\n"
                info_str += f"  默认采样率: {info.get('defaultSampleRate', 0)} Hz\n"
                info_str += "-" * 50 + "\n\n"
            except:
                info_str += f"[设备 {i}] 无法获取信息\n\n"
        text.setText(info_str)
        dialog.exec()

    def test_device(self):
        if self.selected_device_index is None:
            QMessageBox.warning(self, "提示", "请先选择音频设备")
            return
        try:
            duration = 1.0
            sample_rate = 44100
            frequency = 440
            samples = int(sample_rate * duration)
            frames = bytearray()
            for i in range(samples):
                sample = int(32767 * 0.5 * math.sin(2 * math.pi * frequency * i / sample_rate))
                frames.extend(sample.to_bytes(2, 'little', signed=True))
            stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=sample_rate,
                output=True,
                output_device_index=self.selected_device_index
            )
            stream.write(bytes(frames))
            stream.stop_stream()
            stream.close()
            self.status_label.setText("设备测试完成")
            QMessageBox.information(self, "测试成功", "音频设备工作正常！")
        except Exception as e:
            QMessageBox.critical(self, "测试失败", f"无法播放测试音: {str(e)}")

    def play_test_tone(self):
        self.test_device()

    # ------------------ 音频文件管理 ------------------
    def add_audio_file(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择音频文件（可多选）",
            "",
            "音频文件 (*.mp3 *.wav *.ogg *.flac *.m4a *.aac);;所有文件 (*.*)"
        )
        if not files:
            return

        supported_ext = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac'}
        added_count = 0
        replaced_count = 0
        skipped_count = 0
        unsupported_count = 0

        for file_path in files:
            file_name = os.path.basename(file_path)
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in supported_ext:
                unsupported_count += 1
                continue

            if file_name in self.audio_files:
                reply = QMessageBox.question(self, "文件已存在",
                                             f"'{file_name}' 已经存在于列表中。\n是否替换？",
                                             QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No:
                    skipped_count += 1
                    continue
                else:
                    replaced_count += 1
            else:
                added_count += 1

            duration = "未知"
            try:
                if file_ext == '.wav':
                    with wave.open(file_path, 'rb') as wf:
                        frames = wf.getnframes()
                        rate = wf.getframerate()
                        duration = f"{frames / rate:.2f}秒"
                elif PYDUB_AVAILABLE:
                    audio = AudioSegment.from_file(file_path)
                    duration = f"{len(audio) / 1000:.2f}秒"
            except Exception as e:
                print(f"获取音频时长失败 {file_name}: {e}")

            self.audio_files[file_name] = {
                'path': file_path,
                'hotkey': '',
                'duration': duration,
                'format': file_ext.replace('.', '').upper(),
                'source': '本地添加'
            }

        self.refresh_treeview()
        self.save_config()

        total = added_count + replaced_count
        if total > 0:
            msg = f"成功添加 {total} 个音效"
            if added_count > 0:
                msg += f"（新加 {added_count}）"
            if replaced_count > 0:
                msg += f"（替换 {replaced_count}）"
            if skipped_count > 0:
                msg += f"，跳过 {skipped_count} 个（用户取消）"
            if unsupported_count > 0:
                msg += f"，{unsupported_count} 个格式不支持"
            QMessageBox.information(self, "批量添加完成", msg)
            self.status_label.setText(msg)
        else:
            msg = "没有添加任何音效"
            if skipped_count > 0 or unsupported_count > 0:
                msg += f"（跳过 {skipped_count}，不支持 {unsupported_count}）"
            QMessageBox.warning(self, "批量添加", msg)
            self.status_label.setText(msg)

    def remove_audio_file(self):
        selected = self.tree.currentItem()
        if not selected:
            return
        file_name = selected.text(0)
        reply = QMessageBox.question(self, "确认删除", f"确定要删除 '{file_name}' 吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.is_playing and self.current_playing == file_name:
                self.stop_playback()
            if file_name in self.audio_files:
                del self.audio_files[file_name]
            # 从所有合集中移除
            for collection_name, collection_info in self.collections.items():
                if 'files' in collection_info and file_name in collection_info['files']:
                    collection_info['files'].remove(file_name)
                    if collection_name in self.collection_play_counts:
                        if file_name in self.collection_play_counts[collection_name]:
                            del self.collection_play_counts[collection_name][file_name]
            self.refresh_treeview()
            self.refresh_collection_treeview()
            self.save_config()
            self.save_play_counts()
            self.status_label.setText(f"已删除: {file_name}")

    def refresh_treeview(self):
        self.tree.clear()
        for file_name, info in self.audio_files.items():
            item = QTreeWidgetItem([
                file_name,
                self.format_hotkey_for_display(info.get('hotkey', '')),
                info.get('duration', '未知'),
                info.get('format', '未知'),
                info.get('source', '本地添加')
            ])
            self.tree.addTopLevelItem(item)

    def refresh_collection_treeview(self):
        self.collection_tree.clear()
        for collection_name, collection_info in self.collections.items():
            item = QTreeWidgetItem([
                collection_name,
                self.format_hotkey_for_display(collection_info.get('hotkey', '')),
                str(len(collection_info.get('files', [])))
            ])
            self.collection_tree.addTopLevelItem(item)

    def on_tree_select(self):
        selected = self.tree.currentItem() is not None
        self.delete_btn.setEnabled(selected)
        self.hotkey_btn.setEnabled(selected)
        self.play_btn.setEnabled(selected)

    def on_item_double_click(self, item, column):
        self.test_play()

    def test_play(self):
        selected = self.tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择一个音效")
            return
        if self.selected_device_index is None:
            QMessageBox.warning(self, "提示", "请先选择音频输出设备")
            return
        if self.is_playing:
            QMessageBox.warning(self, "提示", "请等待当前音效播放完毕")
            return
        file_name = selected.text(0)
        file_info = self.audio_files.get(file_name)
        if not file_info:
            return
        file_path = file_info['path']
        self.play_thread = threading.Thread(target=self.play_audio_thread, args=(file_name, file_path), daemon=True)
        self.play_thread.start()

    def play_audio_thread(self, file_name, file_path):
        try:
            self.is_playing = True
            self.current_playing = file_name
            self.stop_flag = False
            self.update_play_status_signal.emit(True, file_name)
            with self.c_key_lock:
                was_c_key_held = self.c_key_held
            self.hold_c_key(False)
            self.play_audio_file(file_path)
        except Exception as e:
            print(f"播放错误: {traceback.format_exc()}")
            self.show_message_signal.emit("播放错误", str(e))
        finally:
            if not was_c_key_held:
                self.release_c_key(False)
            self.is_playing = False
            self.current_playing = None
            self.update_play_status_signal.emit(False, None)

    def play_audio_file(self, file_path):
        stream = None
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
            file_ext = os.path.splitext(file_path)[1].lower()

            if file_ext == '.wav':
                with wave.open(file_path, 'rb') as wf:
                    sampwidth = wf.getsampwidth()
                    channels = wf.getnchannels()
                    rate = wf.getframerate()
                    frames_per_buffer = 1024
                    all_data = wf.readframes(wf.getnframes())
                    if self.volume != 1.0:
                        scaled_data = audioop.mul(all_data, sampwidth, self.volume)
                    else:
                        scaled_data = all_data
                    format = self.p.get_format_from_width(sampwidth)
                    stream = self.p.open(
                        format=format,
                        channels=channels,
                        rate=rate,
                        output=True,
                        output_device_index=self.selected_device_index,
                        frames_per_buffer=frames_per_buffer
                    )
                    self.stream = stream
                    chunk_size = frames_per_buffer * sampwidth * channels
                    pos = 0
                    while pos < len(scaled_data) and not self.stop_flag:
                        chunk = scaled_data[pos:pos+chunk_size]
                        stream.write(chunk)
                        pos += chunk_size
            elif PYDUB_AVAILABLE:
                audio = AudioSegment.from_file(file_path)
                if self.volume != 1.0:
                    gain = 20 * math.log10(self.volume) if self.volume > 0 else -float('inf')
                    audio = audio.apply_gain(gain)
                raw_audio = audio.raw_data
                channels = audio.channels
                sample_width = audio.sample_width
                frame_rate = audio.frame_rate
                if sample_width == 1:
                    format = pyaudio.paInt8
                elif sample_width == 2:
                    format = pyaudio.paInt16
                elif sample_width == 3:
                    format = pyaudio.paInt24
                elif sample_width == 4:
                    format = pyaudio.paFloat32
                else:
                    format = pyaudio.paInt16
                stream = self.p.open(
                    format=format,
                    channels=channels,
                    rate=frame_rate,
                    output=True,
                    output_device_index=self.selected_device_index
                )
                self.stream = stream
                chunk_size = 1024 * sample_width * channels
                pos = 0
                while pos < len(raw_audio) and not self.stop_flag:
                    chunk = raw_audio[pos:pos + chunk_size]
                    stream.write(chunk)
                    pos += chunk_size
                    time.sleep(0.001)
            else:
                for i in range(20):
                    if self.stop_flag:
                        break
                    time.sleep(0.1)
        except Exception as e:
            print(f"播放文件时出错: {e}")
            raise
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except:
                    pass
            self.stream = None

    def update_play_status(self, playing, file_name):
        if playing:
            self.play_status_label.setText(f"状态: 播放中")
            self.current_file_label.setText(f"当前: {file_name}")
            self.play_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_label.setText(f"正在播放: {file_name}")
        else:
            self.play_status_label.setText("状态: 空闲")
            self.current_file_label.setText("当前: 无")
            self.play_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setText("播放完成")

    def stop_playback(self):
        if self.is_playing:
            print("停止播放...")
            self.stop_flag = True
            self.status_label.setText("播放已停止")

    def hold_c_key(self, manual=False):
        with self.c_key_lock:
            if not self.c_key_held:
                try:
                    self.keyboard_controller.press(self.mic_key)
                    self.c_key_held = True
                    self.update_c_key_indicator_signal.emit(True)
                    if manual:
                        self.status_label.setText(f"{self.mic_key.upper()}键已按下 (手动测试)")
                        QTimer.singleShot(1000, lambda: self.release_c_key(True))
                except Exception as e:
                    print(f"按下{self.mic_key.upper()}键失败: {e}")

    def release_c_key(self, manual=False):
        with self.c_key_lock:
            if self.c_key_held:
                try:
                    self.keyboard_controller.release(self.mic_key)
                    self.c_key_held = False
                    self.update_c_key_indicator_signal.emit(False)
                    if manual:
                        self.status_label.setText(f"{self.mic_key.upper()}键已释放 (手动测试)")
                except Exception as e:
                    print(f"释放{self.mic_key.upper()}键失败: {e}")

    def set_mic_key(self):
        self.pause_key_listener()
        dialog = KeyCaptureDialog(self, "设置开麦键", "请按下您要设置为开麦键的按键", self.mic_key)
        if dialog.exec() == QDialog.Accepted and dialog.captured_key:
            new_key = dialog.captured_key
            # 检查冲突
            conflicts = []
            for name, info in self.audio_files.items():
                if info.get('hotkey') == new_key:
                    conflicts.append(f"音效: {name}")
            for cname, cinfo in self.collections.items():
                if cinfo.get('hotkey') == new_key:
                    conflicts.append(f"合集: {cname}")
            if conflicts:
                msg = "以下快捷键将被覆盖（因为它们将无法使用）：\n" + "\n".join(conflicts) + "\n\n是否仍然设置？"
                if QMessageBox.warning(self, "警告", msg, QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                    self.resume_key_listener()
                    return
            self.mic_key = new_key
            self.save_config()
            self.mic_key_display_label.setText(f"键位: {self.format_hotkey_for_display(self.mic_key)}")
            QMessageBox.information(self, "成功", f"开麦键已设置为: {self.format_hotkey_for_display(self.mic_key)}")
            self.status_label.setText(f"开麦键已更新为: {self.format_hotkey_for_display(self.mic_key)}")
        self.resume_key_listener()

    def set_stop_key(self):
        self.pause_key_listener()
        dialog = KeyCaptureDialog(self, "设置停止快捷键", "请按下您要设置为停止的按键", self.stop_key)
        if dialog.exec() == QDialog.Accepted and dialog.captured_key:
            new_key = dialog.captured_key
            if new_key == self.mic_key:
                QMessageBox.warning(self, "错误", "开麦键不能作为停止键")
                self.resume_key_listener()
                return
            # 检查冲突
            conflicts = []
            for name, info in self.audio_files.items():
                if info.get('hotkey') == new_key:
                    conflicts.append(f"音效: {name}")
            for cname, cinfo in self.collections.items():
                if cinfo.get('hotkey') == new_key:
                    conflicts.append(f"合集: {cname}")
            if conflicts:
                msg = "以下快捷键将与停止键冲突（它们将无法触发播放）：\n" + "\n".join(conflicts) + "\n\n是否仍然设置？"
                if QMessageBox.warning(self, "警告", msg, QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                    self.resume_key_listener()
                    return
            self.stop_key = new_key
            self.save_config()
            self.stop_key_display_label.setText(self.format_hotkey_for_display(self.stop_key))
            QMessageBox.information(self, "成功", f"停止快捷键已设置为: {self.format_hotkey_for_display(self.stop_key)}")
            self.status_label.setText(f"停止键已更新为: {self.format_hotkey_for_display(self.stop_key)}")
        self.resume_key_listener()

    def set_hotkey(self):
        selected = self.tree.currentItem()
        if not selected:
            return
        file_name = selected.text(0)
        if file_name not in self.audio_files:
            return
        self.pause_key_listener()
        dialog = KeyCaptureDialog(self, f"设置快捷键 - {file_name}",
                                  "请按下您要设置的按键", self.audio_files[file_name].get('hotkey', ''))
        if dialog.exec() == QDialog.Accepted:
            if dialog.captured_key is None and dialog.clear:
                # 清除快捷键
                self.audio_files[file_name]['hotkey'] = ''
                self.save_config()
                self.refresh_treeview()
                QMessageBox.information(self, "成功", f"已清除 '{file_name}' 的快捷键")
            elif dialog.captured_key:
                new_key = dialog.captured_key
                if new_key == self.mic_key:
                    QMessageBox.warning(self, "错误", "开麦键不能用作快捷键")
                    self.resume_key_listener()
                    return
                if new_key == self.stop_key:
                    QMessageBox.warning(self, "错误", "停止键不能用作快捷键")
                    self.resume_key_listener()
                    return
                # 检查冲突
                used_by = None
                for name, info in self.audio_files.items():
                    if name != file_name and info.get('hotkey') == new_key:
                        used_by = name
                        break
                if not used_by:
                    for cname, cinfo in self.collections.items():
                        if cinfo.get('hotkey') == new_key:
                            used_by = f"合集 '{cname}'"
                            break
                if used_by:
                    if QMessageBox.question(self, "快捷键冲突",
                                            f"快捷键已被 {used_by} 使用，是否仍要使用？",
                                            QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                        self.resume_key_listener()
                        return
                self.audio_files[file_name]['hotkey'] = new_key
                self.save_config()
                self.refresh_treeview()
                QMessageBox.information(self, "成功", f"已为 '{file_name}' 设置快捷键: {self.format_hotkey_for_display(new_key)}")
        self.resume_key_listener()

    def show_tree_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        self.tree.setCurrentItem(item)
        menu = QMenu()
        play_action = QAction("播放", self)
        play_action.triggered.connect(self.test_play)
        menu.addAction(play_action)
        set_hotkey_action = QAction("设置快捷键", self)
        set_hotkey_action.triggered.connect(self.set_hotkey)
        menu.addAction(set_hotkey_action)
        # 如果有快捷键，添加清除选项
        file_name = item.text(0)
        if self.audio_files.get(file_name, {}).get('hotkey'):
            clear_action = QAction("清除快捷键", self)
            clear_action.triggered.connect(lambda: self.clear_hotkey_for_file(file_name))
            menu.addAction(clear_action)
        menu.addSeparator()
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(self.remove_audio_file)
        menu.addAction(delete_action)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def clear_hotkey_for_file(self, file_name):
        if file_name in self.audio_files:
            self.audio_files[file_name]['hotkey'] = ''
            self.save_config()
            self.refresh_treeview()
            self.status_label.setText(f"已清除 '{file_name}' 的快捷键")

    # ------------------ 合集管理 ------------------
    def create_collection(self):
        name, ok = QInputDialog.getText(self, "新建合集", "请输入合集名称:")
        if ok and name:
            if name in self.collections:
                QMessageBox.warning(self, "警告", f"合集 '{name}' 已存在！")
                return
            self.collections[name] = {'files': [], 'hotkey': ''}
            if name not in self.collection_play_counts:
                self.collection_play_counts[name] = {}
            self.refresh_collection_treeview()
            self.save_config()
            self.save_play_counts()
            self.status_label.setText(f"已创建合集: {name}")

    def delete_collection(self):
        selected = self.collection_tree.currentItem()
        if not selected:
            return
        collection_name = selected.text(0)
        reply = QMessageBox.question(self, "确认删除", f"确定要删除合集 '{collection_name}' 吗？\n注意：播放计数也会被删除。",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if collection_name in self.collections:
                del self.collections[collection_name]
            if collection_name in self.collection_play_counts:
                del self.collection_play_counts[collection_name]
            self.refresh_collection_treeview()
            self.collection_detail_text.clear()
            self.save_config()
            self.save_play_counts()
            self.status_label.setText(f"已删除合集: {collection_name}")

    def add_files_to_collection_direct(self):
        selected = self.collection_tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择一个合集")
            return
        collection_name = selected.text(0)
        if collection_name not in self.collections:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, f"选择音频文件添加到合集 '{collection_name}'",
            "",
            "音频文件 (*.mp3 *.wav *.ogg *.flac *.m4a *.aac);;所有文件 (*.*)"
        )
        if not files:
            return
        added_count = 0
        for file_path in files:
            file_name = os.path.basename(file_path)
            if file_name in self.collections[collection_name]['files']:
                reply = QMessageBox.question(self, "文件已存在",
                                             f"'{file_name}' 已经在合集中，是否替换？",
                                             QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No:
                    continue
                # 替换：移除旧的，后面会重新添加
                self.collections[collection_name]['files'].remove(file_name)
            self.collections[collection_name]['files'].append(file_name)
            if collection_name not in self.collection_play_counts:
                self.collection_play_counts[collection_name] = {}
            if file_name not in self.collection_play_counts[collection_name]:
                self.collection_play_counts[collection_name][file_name] = 0
            # 如果文件不在 audio_files 中，也添加进去
            if file_name not in self.audio_files:
                file_ext = os.path.splitext(file_path)[1].lower()
                duration = "未知"
                try:
                    if file_ext == '.wav':
                        with wave.open(file_path, 'rb') as wf:
                            frames = wf.getnframes()
                            rate = wf.getframerate()
                            duration = f"{frames / rate:.2f}秒"
                    elif PYDUB_AVAILABLE:
                        audio = AudioSegment.from_file(file_path)
                        duration = f"{len(audio) / 1000:.2f}秒"
                except Exception as e:
                    print(f"获取音频时长失败: {e}")
                self.audio_files[file_name] = {
                    'path': file_path,
                    'hotkey': '',
                    'duration': duration,
                    'format': file_ext.replace('.', '').upper(),
                    'source': '本地添加'
                }
            added_count += 1
        self.refresh_treeview()
        self.refresh_collection_treeview()
        self.save_config()
        self.save_play_counts()
        self.status_label.setText(f"已向合集 '{collection_name}' 添加 {added_count} 个音效")
        QMessageBox.information(self, "成功", f"已向合集 '{collection_name}' 添加 {added_count} 个音效")

    def remove_file_from_collection(self):
        selected = self.collection_tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择一个合集")
            return
        collection_name = selected.text(0)
        if collection_name not in self.collections:
            return
        files = self.collections[collection_name]['files']
        if not files:
            QMessageBox.information(self, "提示", f"合集 '{collection_name}' 中没有音效")
            return
        # 弹出一个多选列表对话框
        dialog = QDialog(self)
        dialog.setWindowTitle(f"从合集 '{collection_name}' 移除音效")
        dialog.resize(400, 500)
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        list_widget.setSelectionMode(QListWidget.MultiSelection)
        for f in files:
            list_widget.addItem(f)
        layout.addWidget(list_widget)
        btn_layout = QHBoxLayout()
        remove_btn = QPushButton("移除选中")
        cancel_btn = QPushButton("取消")
        btn_layout.addWidget(remove_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        def do_remove():
            selected_items = list_widget.selectedItems()
            if not selected_items:
                QMessageBox.warning(dialog, "提示", "请先选择音效")
                return
            for item in selected_items:
                file_name = item.text()
                if file_name in self.collections[collection_name]['files']:
                    self.collections[collection_name]['files'].remove(file_name)
                if collection_name in self.collection_play_counts:
                    if file_name in self.collection_play_counts[collection_name]:
                        del self.collection_play_counts[collection_name][file_name]
            self.refresh_collection_treeview()
            self.save_config()
            self.save_play_counts()
            dialog.accept()
            self.status_label.setText(f"已从合集 '{collection_name}' 移除 {len(selected_items)} 个音效")
            QMessageBox.information(self, "成功", f"已从合集 '{collection_name}' 移除 {len(selected_items)} 个音效")

        remove_btn.clicked.connect(do_remove)
        cancel_btn.clicked.connect(dialog.reject)
        dialog.exec()

    def view_collection_details(self):
        selected = self.collection_tree.currentItem()
        if not selected:
            self.collection_detail_text.clear()
            return
        collection_name = selected.text(0)
        if collection_name not in self.collections:
            return
        collection_info = self.collections[collection_name]
        files = collection_info.get('files', [])
        hotkey = collection_info.get('hotkey', '')
        text = f"合集名称: {collection_name}\n"
        text += f"快捷键: {self.format_hotkey_for_display(hotkey)}\n"
        text += f"音效数量: {len(files)}\n\n"
        if files:
            text += "包含音效:\n"
            for i, file_name in enumerate(files):
                audio_info = self.audio_files.get(file_name, {})
                duration = audio_info.get('duration', '未知')
                play_count = 0
                if collection_name in self.collection_play_counts:
                    play_count = self.collection_play_counts[collection_name].get(file_name, 0)
                text += f"  {i+1}. {file_name} ({duration}) - 播放{play_count}次\n"
        else:
            text += "合集为空，请添加音效。\n"
        self.collection_detail_text.setText(text)

    def reset_collection_play_counts(self):
        selected = self.collection_tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择一个合集")
            return
        collection_name = selected.text(0)
        if collection_name not in self.collections:
            return
        reply = QMessageBox.question(self, "确认重置", f"确定要重置合集 '{collection_name}' 的播放计数吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if collection_name in self.collection_play_counts:
                for f in self.collection_play_counts[collection_name]:
                    self.collection_play_counts[collection_name][f] = 0
            self.save_play_counts()
            self.view_collection_details()
            self.status_label.setText(f"已重置合集 '{collection_name}' 的播放计数")
            QMessageBox.information(self, "成功", f"已重置合集 '{collection_name}' 的播放计数")

    def set_collection_hotkey(self):
        selected = self.collection_tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "提示", "请先选择一个合集")
            return
        collection_name = selected.text(0)
        if collection_name not in self.collections:
            return
        self.pause_key_listener()
        dialog = KeyCaptureDialog(self, f"设置合集快捷键 - {collection_name}",
                                  "请按下您要设置的按键", self.collections[collection_name].get('hotkey', ''))
        if dialog.exec() == QDialog.Accepted:
            if dialog.captured_key is None and dialog.clear:
                self.collections[collection_name]['hotkey'] = ''
                self.save_config()
                self.refresh_collection_treeview()
                QMessageBox.information(self, "成功", f"已清除合集 '{collection_name}' 的快捷键")
            elif dialog.captured_key:
                new_key = dialog.captured_key
                if new_key == self.mic_key:
                    QMessageBox.warning(self, "错误", "开麦键不能用作快捷键")
                    self.resume_key_listener()
                    return
                if new_key == self.stop_key:
                    QMessageBox.warning(self, "错误", "停止键不能用作快捷键")
                    self.resume_key_listener()
                    return
                # 检查冲突
                used_by = None
                for name, info in self.audio_files.items():
                    if info.get('hotkey') == new_key:
                        used_by = name
                        break
                if not used_by:
                    for cname, cinfo in self.collections.items():
                        if cname != collection_name and cinfo.get('hotkey') == new_key:
                            used_by = f"合集 '{cname}'"
                            break
                if used_by:
                    if QMessageBox.question(self, "快捷键冲突",
                                            f"快捷键已被 {used_by} 使用，是否仍要使用？",
                                            QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                        self.resume_key_listener()
                        return
                self.collections[collection_name]['hotkey'] = new_key
                self.save_config()
                self.refresh_collection_treeview()
                QMessageBox.information(self, "成功", f"已为合集 '{collection_name}' 设置快捷键: {self.format_hotkey_for_display(new_key)}")
        self.resume_key_listener()

    # ------------------ 快捷键监听 ------------------
    def start_key_listener(self):
        def on_press(key):
            try:
                if key is None or self.listener_paused:
                    return
                key_str = self.pynput_key_to_string(key)
                if not key_str:
                    return
                print(f"检测到按键: {key_str}")

                if key_str == self.mic_key:
                    print(f"检测到开麦键 {self.mic_key.upper()}，忽略")
                    return

                if key_str == self.stop_key:
                    print("检测到停止快捷键，停止播放")
                    self.stop_playback()
                    return

                for file_name, info in self.audio_files.items():
                    hotkey = info.get('hotkey', '')
                    if hotkey == key_str and not self.is_playing:
                        print(f"匹配到音效: {file_name}")
                        self.play_from_hotkey(file_name, info['path'])
                        break

                for collection_name, collection_info in self.collections.items():
                    hotkey = collection_info.get('hotkey', '')
                    if hotkey == key_str and not self.is_playing:
                        print(f"匹配到合集: {collection_name}")
                        self.play_from_collection_smart(collection_name, collection_info)
                        break

            except Exception as e:
                print(f"快捷键监听错误: {e}")

        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.daemon = True
        self.listener.start()
        self.update_listener_status_signal.emit("正常", "green")
        print("快捷键监听已启动")

    def play_from_hotkey(self, file_name, file_path):
        if self.selected_device_index is None:
            self.after(0, lambda: QMessageBox.warning(self, "提示", "请先选择音频输出设备"))
            return
        if self.is_playing:
            self.after(0, lambda: QMessageBox.warning(self, "提示", "请等待当前音效播放完毕"))
            return
        print(f"启动播放线程: {file_name}")
        thread = threading.Thread(target=self.play_audio_thread, args=(file_name, file_path), daemon=True)
        thread.start()
        self.after(0, lambda: self.status_label.setText(f"快捷键播放: {file_name}"))

    def play_from_collection_smart(self, collection_name, collection_info):
        if self.selected_device_index is None:
            self.after(0, lambda: QMessageBox.warning(self, "提示", "请先选择音频输出设备"))
            return
        if self.is_playing:
            self.after(0, lambda: QMessageBox.warning(self, "提示", "请等待当前音效播放完毕"))
            return
        files = collection_info.get('files', [])
        if not files:
            self.after(0, lambda: QMessageBox.warning(self, "提示", f"合集 '{collection_name}' 中没有音效"))
            return
        if collection_name not in self.collection_play_counts:
            self.collection_play_counts[collection_name] = {}
        play_counts = self.collection_play_counts[collection_name]
        for file_name in files:
            if file_name not in play_counts:
                play_counts[file_name] = 0
        min_play_count = min(play_counts.values()) if play_counts else 0
        candidate_files = [file_name for file_name, count in play_counts.items() if count == min_play_count and file_name in files]
        if not candidate_files:
            candidate_files = files
        selected_file = random.choice(candidate_files)
        play_counts[selected_file] = play_counts.get(selected_file, 0) + 1
        self.save_play_counts()
        file_info = self.audio_files.get(selected_file)
        if not file_info:
            self.after(0, lambda: QMessageBox.warning(self, "提示", f"找不到音效文件: {selected_file}"))
            return
        file_path = file_info['path']
        thread = threading.Thread(
            target=self.play_audio_thread,
            args=(f"[{collection_name}] {selected_file} (播放{play_counts[selected_file]}次)", file_path),
            daemon=True
        )
        thread.start()
        self.after(0, lambda: self.status_label.setText(
            f"合集播放: {collection_name} - {selected_file} (第{play_counts[selected_file]}次播放)"))

    # ------------------ 配置保存与加载 ------------------
    def save_config(self):
        try:
            config = {
                'audio_files': dict(self.audio_files),
                'collections': dict(self.collections),
                'selected_device_index': self.selected_device_index,
                'web_server_enabled': self.web_server_enabled,
                'mic_key': self.mic_key,
                'stop_key': self.stop_key,
                'version': '6.4'
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"配置已保存到 {self.config_file}")
        except Exception as e:
            print(f"保存配置失败: {e}")

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'audio_files' in config:
                        self.audio_files = OrderedDict()
                        for file_name, file_info in config['audio_files'].items():
                            if isinstance(file_info, dict):
                                new_info = file_info.copy()
                                if 'duration' not in new_info:
                                    new_info['duration'] = '未知'
                                if 'hotkey' not in new_info:
                                    new_info['hotkey'] = ''
                                if 'format' not in new_info:
                                    file_path = new_info.get('path', '')
                                    if file_path:
                                        file_ext = os.path.splitext(file_path)[1].lower().replace('.', '')
                                        new_info['format'] = file_ext.upper() if file_ext else '未知'
                                    else:
                                        new_info['format'] = '未知'
                                if 'source' not in new_info:
                                    new_info['source'] = '本地添加'
                                self.audio_files[file_name] = new_info
                            else:
                                file_path = file_info if isinstance(file_info, str) else ''
                                file_ext = os.path.splitext(file_path)[1].lower().replace('.', '')
                                self.audio_files[file_name] = {
                                    'path': file_path,
                                    'hotkey': '',
                                    'duration': '未知',
                                    'format': file_ext.upper() if file_ext else '未知',
                                    'source': '本地添加'
                                }
                        print(f"加载了 {len(self.audio_files)} 个音频文件")
                    if 'collections' in config:
                        self.collections = OrderedDict()
                        for collection_name, collection_info in config['collections'].items():
                            if isinstance(collection_info, dict):
                                new_info = collection_info.copy()
                                if 'files' not in new_info:
                                    new_info['files'] = []
                                if 'hotkey' not in new_info:
                                    new_info['hotkey'] = ''
                                self.collections[collection_name] = new_info
                        print(f"加载了 {len(self.collections)} 个合集")
                    if 'selected_device_index' in config:
                        self.selected_device_index = config['selected_device_index']
                    if 'web_server_enabled' in config:
                        self.web_server_enabled = config['web_server_enabled']
                    if 'mic_key' in config:
                        self.mic_key = config['mic_key']
                    if 'stop_key' in config:
                        self.stop_key = config['stop_key']
            else:
                print("配置文件不存在，使用默认配置")
        except Exception as e:
            print(f"加载配置失败: {e}")
            self.audio_files = OrderedDict()
            self.collections = OrderedDict()
            self.selected_device_index = None
            self.web_server_enabled = False
            self.mic_key = 'c'
            self.stop_key = 'down'

    def load_play_counts(self):
        try:
            if os.path.exists(self.play_counts_file):
                with open(self.play_counts_file, 'r', encoding='utf-8') as f:
                    self.collection_play_counts = json.load(f)
                print(f"播放计数已从 {self.play_counts_file} 加载")
            else:
                self.collection_play_counts = {}
        except Exception as e:
            print(f"加载播放计数失败: {e}")
            self.collection_play_counts = {}

    def save_play_counts(self):
        try:
            with open(self.play_counts_file, 'w', encoding='utf-8') as f:
                json.dump(self.collection_play_counts, f, ensure_ascii=False, indent=2)
            print(f"播放计数已保存到 {self.play_counts_file}")
        except Exception as e:
            print(f"保存播放计数失败: {e}")

    # ------------------ 网页控制相关 ------------------
    def start_web_server(self):
        if self.web_server.running:
            QMessageBox.information(self, "提示", "Web服务器已经在运行中")
            return
        success = self.web_server.start()
        if success:
            self.web_server_enabled = True
            ip = self.web_server.get_local_ip()
            url = f"http://{ip}:{self.web_server.port}"
            self.web_status_label.setText("服务器状态: 运行中")
            self.web_address_label.setText(f"地址: {url}")
            self.web_start_btn.setEnabled(False)
            self.web_stop_btn.setEnabled(True)
            self.web_open_btn.setEnabled(True)
            self.save_config()
            QMessageBox.information(self, "成功", f"Web服务器已启动！\n\n请在手机浏览器中访问：\n{url}\n\n确保手机和电脑在同一WiFi网络下。")
            self.status_label.setText(f"Web服务器已启动: {url}")
        else:
            QMessageBox.critical(self, "错误", "启动Web服务器失败，请检查端口是否被占用。")

    def stop_web_server(self):
        if not self.web_server.running:
            return
        self.web_server.stop()
        self.web_server_enabled = False
        self.web_status_label.setText("服务器状态: 已停止")
        self.web_address_label.setText("地址: 未启动")
        self.web_start_btn.setEnabled(True)
        self.web_stop_btn.setEnabled(False)
        self.web_open_btn.setEnabled(False)
        self.save_config()
        self.status_label.setText("Web服务器已停止")

    def open_web_browser(self):
        if self.web_server.running:
            ip = self.web_server.get_local_ip()
            url = f"http://{ip}:{self.web_server.port}"
            webbrowser.open(url)
        else:
            QMessageBox.warning(self, "提示", "请先启动Web服务器")

    def play_from_web(self, file_name):
        if self.selected_device_index is None:
            return
        if self.is_playing:
            return
        file_info = self.audio_files.get(file_name)
        if not file_info:
            return
        file_path = file_info['path']
        self.play_thread = threading.Thread(target=self.play_audio_thread, args=(file_name, file_path), daemon=True)
        self.play_thread.start()
        self.status_label.setText(f"网页控制播放: {file_name}")

    def play_from_collection_web(self, collection_name):
        if self.selected_device_index is None:
            return
        if self.is_playing:
            return
        collection_info = self.collections.get(collection_name)
        if not collection_info:
            return
        self.play_from_collection_smart(collection_name, collection_info)
        self.status_label.setText(f"网页控制播放合集: {collection_name}")

    def add_uploaded_audio(self, filename, file_path):
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            file_name = os.path.basename(file_path)
            duration = "未知"
            try:
                if file_ext == '.wav':
                    with wave.open(file_path, 'rb') as wf:
                        frames = wf.getnframes()
                        rate = wf.getframerate()
                        duration = f"{frames / rate:.2f}秒"
                elif PYDUB_AVAILABLE:
                    audio = AudioSegment.from_file(file_path)
                    duration = f"{len(audio) / 1000:.2f}秒"
                else:
                    try:
                        import mutagen
                        audio_info = mutagen.File(file_path)
                        if audio_info is not None:
                            duration = f"{audio_info.info.length:.2f}秒"
                    except:
                        pass
            except Exception as e:
                print(f"获取时长异常: {e}")

            self.audio_files[file_name] = {
                'path': file_path,
                'hotkey': '',
                'duration': duration,
                'format': file_ext.replace('.', '').upper(),
                'source': '网页上传'
            }
            self.refresh_treeview()
            self.save_config()
            self.after(0, lambda: self.status_label.setText(f"已添加上传音频: {file_name}"))
            return True
        except Exception as e:
            print(f"添加上传音频失败: {e}")
            traceback.print_exc()
            return False

    # ------------------ 其他 ------------------
    def show_mp3_warning(self):
        reply = QMessageBox.question(
            self, "MP3支持",
            "未安装pydub，MP3格式支持受限。\n\n是否安装pydub以获得完整MP3支持？\n\n(安装命令: pip install pydub)",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            webbrowser.open("https://pypi.org/project/pydub/")

    def check_hotkeys(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("快捷键设置检查")
        dialog.resize(600, 500)
        layout = QVBoxLayout(dialog)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # 单个音效
        single_tab = QWidget()
        single_layout = QVBoxLayout(single_tab)
        single_text = QTextEdit()
        single_text.setReadOnly(True)
        single_layout.addWidget(single_text)
        tabs.addTab(single_tab, "单个音效")

        single_info = "=== 当前音效快捷键设置 ===\n\n"
        if not self.audio_files:
            single_info += "暂无音效文件\n"
        else:
            for file_name, info in self.audio_files.items():
                single_info += f"文件: {file_name}\n"
                single_info += f"  快捷键: {self.format_hotkey_for_display(info.get('hotkey', ''))}\n"
                single_info += f"  路径: {info.get('path', '未知')}\n"
                single_info += f"  时长: {info.get('duration', '未知')}\n"
                single_info += f"  格式: {info.get('format', '未知')}\n"
                single_info += "-" * 50 + "\n\n"
        single_text.setText(single_info)

        # 合集
        col_tab = QWidget()
        col_layout = QVBoxLayout(col_tab)
        col_text = QTextEdit()
        col_text.setReadOnly(True)
        col_layout.addWidget(col_text)
        tabs.addTab(col_tab, "音乐盒合集")

        col_info = "=== 当前合集快捷键设置 ===\n\n"
        if not self.collections:
            col_info += "暂无音乐盒合集\n"
        else:
            for collection_name, collection_info in self.collections.items():
                col_info += f"合集: {collection_name}\n"
                col_info += f"  快捷键: {self.format_hotkey_for_display(collection_info.get('hotkey', ''))}\n"
                files = collection_info.get('files', [])
                col_info += f"  音效数量: {len(files)}\n"
                if collection_name in self.collection_play_counts:
                    play_counts = self.collection_play_counts[collection_name]
                    col_info += "  播放计数:\n"
                    for file_name in files[:10]:
                        count = play_counts.get(file_name, 0)
                        col_info += f"    {file_name}: {count}次\n"
                    if len(files) > 10:
                        col_info += f"    ... 还有 {len(files)-10} 个\n"
                col_info += "-" * 50 + "\n\n"
        col_info += "\n=== 快捷键映射 ===\n"
        col_info += "字母键、功能键、小键盘等均可自定义\n"
        col_info += f"\n停止快捷键: {self.format_hotkey_for_display(self.stop_key)}\n"
        col_info += "\n=== 随机播放算法 ===\n"
        col_info += "智能随机: 优先播放次数最少的音频\n"
        col_text.setText(col_info)

        dialog.exec()

    def on_closing(self):
        if self.is_playing:
            self.stop_playback()
            time.sleep(0.5)
        self.stop_web_server()
        self.save_config()
        self.save_play_counts()
        if self.c_key_held:
            self.release_c_key()
        if self.listener:
            self.listener.stop()
        self.p.terminate()

    def closeEvent(self, event: QCloseEvent):
        self.on_closing()
        event.accept()


# ==================== 按键捕获对话框（修正版）====================
class KeyCaptureDialog(QDialog):
    def __init__(self, parent, title, prompt, current_key=''):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(350, 200)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: rgba(0,0,0,0.8); color: white;")
        self.setFocusPolicy(Qt.StrongFocus)

        layout = QVBoxLayout(self)

        label = QLabel(prompt)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        self.current_label = QLabel(f"当前: {parent.format_hotkey_for_display(current_key)}")
        self.current_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.current_label)

        self.key_display = QLabel("等待按键...")
        self.key_display.setAlignment(Qt.AlignCenter)
        self.key_display.setStyleSheet("font-size: 20px; color: #00fff9; font-weight: bold;")
        layout.addWidget(self.key_display)

        self.stored_key = None
        self.clear_flag = False

        btn_layout = QHBoxLayout()
        self.clear_btn = QPushButton("清除")
        self.clear_btn.clicked.connect(self.on_clear)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def showEvent(self, event):
        super().showEvent(event)
        # 确保对话框获得焦点
        self.setFocus()
        self.activateWindow()
        self.raise_()
        self.grabKeyboard()

    def keyPressEvent(self, event: QKeyEvent):
        parent = self.parent()
        if not parent:
            return
        key_str = parent.qt_key_to_string(event)
        if not key_str:
            return
        self.key_display.setText(f"按下了: {key_str.upper()}")
        self.stored_key = key_str
        self.accept()

    def on_clear(self):
        self.stored_key = None
        self.clear_flag = True
        self.accept()

    @property
    def captured_key(self):
        return self.stored_key

    @property
    def clear(self):
        return self.clear_flag

# ==================== 主程序入口 ====================
def main():
    if sys.platform == 'win32':
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if not is_admin:
                print("需要管理员权限，正在请求...")
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
                os._exit(0)
        except Exception as e:
            print(f"管理员权限检查失败: {e}")

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = CS2MusicBox()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()