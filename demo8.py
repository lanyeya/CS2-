import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import pyaudio
import wave
import threading
import time
import json
import os
import sys
import random
from pynput import keyboard
from pynput.keyboard import Controller, Key
from collections import OrderedDict
import traceback
import math
import audioop  # 用于无pydub时调节WAV音量

# 尝试导入pydub用于MP3支持
try:
    from pydub import AudioSegment
    from pydub.playback import play
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("警告: pydub未安装，MP3支持受限。请运行: pip install pydub")

# 导入Web服务器相关模块
import http.server
import socketserver
import urllib.parse
import socket
import webbrowser


class WebServer:
    """简单的HTTP服务器，用于手机控制"""

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
            <footer style="text-align:center; margin-top:30px; color:#666;">CS2音乐盒控制器 v5.8 | 手机控制端</footer>
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
                        print("收到文件上传请求")
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
                            result = [False]
                            def add_to_music_box():
                                try:
                                    success = self.webserver.music_box.add_uploaded_audio(safe_filename, file_path)
                                    result[0] = success
                                except Exception as e:
                                    print(f"添加音频到音乐盒时出错: {e}")
                            self.webserver.music_box.root.after(0, add_to_music_box)
                            import time
                            for _ in range(30):
                                time.sleep(0.1)
                                if result[0]:
                                    break
                            if result[0]:
                                self.send_json({'success': True, 'message': f'音频 {safe_filename} 上传成功', 'filename': safe_filename})
                            else:
                                try:
                                    if os.path.exists(file_path):
                                        os.remove(file_path)
                                except:
                                    pass
                                self.send_json({'success': False, 'message': '添加音频到音乐盒失败'}, 500)
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
                        self.webserver.music_box.root.after(0, lambda n=name: self.webserver.music_box.play_from_web(n))
                    self.send_json({'status': 'ok'})
                elif path == '/play_collection':
                    name = query.get('name', [''])[0]
                    if name and name in self.webserver.music_box.collections:
                        self.webserver.music_box.root.after(0, lambda n=name: self.webserver.music_box.play_from_collection_web(n))
                    self.send_json({'status': 'ok'})
                elif path == '/stop':
                    self.webserver.music_box.root.after(0, self.webserver.music_box.stop_playback)
                    self.send_json({'status': 'ok'})
                elif path == '/test_c_key':
                    hold = query.get('hold', [''])[0] == 'true'
                    if hold:
                        self.webserver.music_box.root.after(0, lambda: self.webserver.music_box.hold_c_key(True))
                        threading.Timer(2.0, lambda: self.webserver.music_box.root.after(0, lambda: self.webserver.music_box.release_c_key(True))).start()
                    else:
                        self.webserver.music_box.root.after(0, lambda: self.webserver.music_box.release_c_key(True))
                    self.send_json({'status': 'ok'})
                elif path == '/toggle_c_key':
                    current = self.webserver.music_box.c_key_held
                    if current:
                        self.webserver.music_box.root.after(0, lambda: self.webserver.music_box.release_c_key(False))
                    else:
                        self.webserver.music_box.root.after(0, lambda: self.webserver.music_box.hold_c_key(False))
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
                        'mic_key_display': self.webserver.music_box.format_hotkey_for_display(self.webserver.music_box.mic_key),
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


class CS2MusicBox:
    def __init__(self, root):
        self.root = root
        self.root.title("CS2 音乐盒控制器 v5.8")
        self.root.geometry("1000x750")

        # 初始化变量
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
        self.hotkey_window = None
        self.collection_hotkey_window = None
        self.volume = 1.0
        self.mic_key = 'c'  # 默认开麦键
        self.mic_key_window = None
        self.temp_mic_key = None
        self.stop_key = 'down'  # 默认停止快捷键
        self.stop_key_window = None
        self.temp_stop_key = None

        self.c_key_lock = threading.Lock()

        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        print(f"基础目录: {self.base_dir}")

        self.web_server = WebServer(self, port=54188)
        self.web_server_enabled = False

        try:
            self.p = pyaudio.PyAudio()
        except Exception as e:
            messagebox.showerror("错误", f"无法初始化音频系统: {str(e)}\n请确保音频设备正常工作。")
            raise

        self.keyboard_controller = Controller()

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

        self.config_file = "music_box_config.json"
        self.play_counts_file = "play_counts.json"
        self.load_config()
        self.load_play_counts()

        self.create_widgets()
        self.start_key_listener()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ------------------ 快捷键辅助函数 ------------------
    def key_event_to_string(self, event):
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

    # ------------------ GUI 创建 ------------------
    def create_widgets(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True)

        # 标签页1: 单个音效
        single_frame = ttk.Frame(notebook)
        notebook.add(single_frame, text="单个音效")
        self._create_single_tab(single_frame)

        # 标签页2: 音乐盒合集
        collection_frame = ttk.Frame(notebook)
        notebook.add(collection_frame, text="音乐盒合集")
        self._create_collection_tab(collection_frame)

        # 标签页3: 网页控制
        web_frame = ttk.Frame(notebook)
        notebook.add(web_frame, text="网页控制")
        self._create_web_tab(web_frame)

        # 标签页4: 关于
        about_frame = ttk.Frame(notebook)
        notebook.add(about_frame, text="关于")
        self._create_about_tab(about_frame)

        # 底部状态栏
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(side="bottom", fill="x", padx=10, pady=5)
        self.status_label = tk.Label(bottom_frame, text="就绪", relief=tk.SUNKEN, anchor="w")
        self.status_label.pack(fill="x")

        self.refresh_device_list()
        self.refresh_treeview()
        self.refresh_collection_treeview()

        if not PYDUB_AVAILABLE:
            self.root.after(1000, self.show_mp3_warning)

    def _create_single_tab(self, parent):
        # 左侧框架
        left_frame = ttk.Frame(parent)
        left_frame.pack(side="left", fill="both", expand=True)

        # 设备选择部分
        device_frame = ttk.LabelFrame(left_frame, text="音频输出设备", padding=10)
        device_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(device_frame, text="选择输出设备:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.device_var = tk.StringVar()
        self.device_combobox = ttk.Combobox(device_frame, textvariable=self.device_var, state="readonly", width=60)
        self.device_combobox.grid(row=1, column=0, sticky="ew", columnspan=2)

        device_button_frame = ttk.Frame(device_frame)
        device_button_frame.grid(row=2, column=0, columnspan=2, pady=(5, 0))
        ttk.Button(device_button_frame, text="刷新设备列表", command=self.refresh_device_list).pack(side="left", padx=2)
        ttk.Button(device_button_frame, text="测试设备", command=self.test_device).pack(side="left", padx=2)

        self.device_info_label = ttk.Label(device_frame, text="未选择设备", font=('Arial', 9))
        self.device_info_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(5, 0))

        # 音效列表部分
        sound_frame = ttk.LabelFrame(left_frame, text="音效列表", padding=10)
        sound_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(sound_frame, columns=('文件名', '快捷键', '时长', '格式', '来源'), show='headings')
        self.tree.heading('文件名', text='文件名')
        self.tree.heading('快捷键', text='快捷键')
        self.tree.heading('时长', text='时长')
        self.tree.heading('格式', text='格式')
        self.tree.heading('来源', text='来源')
        self.tree.column('文件名', width=160)
        self.tree.column('快捷键', width=100)
        self.tree.column('时长', width=60)
        self.tree.column('格式', width=50)
        self.tree.column('来源', width=80)

        scrollbar = ttk.Scrollbar(sound_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind('<Double-Button-1>', self.on_item_double_click)
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)

        # 右键菜单
        self.tree_menu = tk.Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="播放", command=self.test_play)
        self.tree_menu.add_command(label="设置快捷键", command=self.set_hotkey)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="删除", command=self.remove_audio_file)
        self.tree.bind("<Button-3>", self.show_tree_menu)

        # 右侧框架
        right_frame = ttk.Frame(parent)
        right_frame.pack(side="right", fill="y", padx=(10, 0))

        control_frame = ttk.LabelFrame(right_frame, text="控制面板", padding=15, width=250)
        control_frame.pack(fill="x", pady=(0, 10))

        ttk.Button(control_frame, text="添加音效文件", command=self.add_audio_file, width=25).pack(pady=5)
        self.delete_button = ttk.Button(control_frame, text="删除选中音效", command=self.remove_audio_file, width=25, state="disabled")
        self.delete_button.pack(pady=5)
        self.hotkey_button = ttk.Button(control_frame, text="设置快捷键", command=self.set_hotkey, width=25, state="disabled")
        self.hotkey_button.pack(pady=5)

        play_frame = ttk.Frame(control_frame)
        play_frame.pack(pady=10)
        self.play_button = ttk.Button(play_frame, text="▶ 播放", command=self.test_play, width=10, state="disabled")
        self.play_button.pack(side="left", padx=2)
        self.stop_button = ttk.Button(play_frame, text="■ 停止", command=self.stop_playback, width=10, state="disabled")
        self.stop_button.pack(side="left", padx=2)

        status_frame = ttk.LabelFrame(right_frame, text="状态信息", padding=15)
        status_frame.pack(fill="x", pady=(0, 10))

        self.play_status_label = ttk.Label(status_frame, text="状态: 空闲", font=('Arial', 10))
        self.play_status_label.pack(anchor="w", pady=(0, 5))
        self.current_file_label = ttk.Label(status_frame, text="当前: 无", font=('Arial', 9))
        self.current_file_label.pack(anchor="w", pady=(0, 10))

        ckey_frame = ttk.Frame(status_frame)
        ckey_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(ckey_frame, text="开麦键状态:", font=('Arial', 10)).pack(side="left")
        self.c_key_indicator = tk.Label(ckey_frame, text="释放", bg="red", fg="white", width=8, font=('Arial', 10, 'bold'))
        self.c_key_indicator.pack(side="left", padx=(5, 0))
        self.mic_key_display_label = ttk.Label(ckey_frame, text=f"键位: {self.format_hotkey_for_display(self.mic_key)}", font=('Arial', 9))
        self.mic_key_display_label.pack(side="left", padx=(10,0))

        stop_key_frame = ttk.Frame(status_frame)
        stop_key_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(stop_key_frame, text="停止快捷键:", font=('Arial', 10)).pack(side="left")
        self.stop_key_display_label = ttk.Label(stop_key_frame, text=f"{self.format_hotkey_for_display(self.stop_key)}", font=('Arial', 10, 'bold'))
        self.stop_key_display_label.pack(side="left", padx=(5,0))

        listener_frame = ttk.Frame(status_frame)
        listener_frame.pack(fill="x")
        ttk.Label(listener_frame, text="快捷键监听:", font=('Arial', 10)).pack(side="left")
        self.listener_status = tk.Label(listener_frame, text="正常", fg="green", font=('Arial', 10, 'bold'))
        self.listener_status.pack(side="left", padx=(5, 0))

        debug_frame = ttk.LabelFrame(right_frame, text="调试工具", padding=15)
        debug_frame.pack(fill="x")

        ttk.Button(debug_frame, text="测试开麦键按下", command=lambda: self.hold_c_key(True)).pack(pady=2, fill="x")
        ttk.Button(debug_frame, text="测试开麦键释放", command=lambda: self.release_c_key(True)).pack(pady=2, fill="x")
        ttk.Button(debug_frame, text="设置开麦键", command=self.set_mic_key).pack(pady=2, fill="x")
        ttk.Button(debug_frame, text="设置停止快捷键", command=self.set_stop_key).pack(pady=2, fill="x")
        ttk.Button(debug_frame, text="播放测试音", command=self.play_test_tone).pack(pady=2, fill="x")
        ttk.Button(debug_frame, text="查看设备信息", command=self.show_device_info).pack(pady=2, fill="x")
        ttk.Button(debug_frame, text="检查快捷键", command=self.check_hotkeys).pack(pady=2, fill="x")

        stop_frame = ttk.Frame(debug_frame)
        stop_frame.pack(fill="x", pady=5)
        ttk.Label(stop_frame, text="停止播放:", font=('Arial', 9)).pack(side="left")
        self.stop_key_hint = tk.Label(stop_frame, text=self.format_hotkey_for_display(self.stop_key), fg="blue", font=('Arial', 9, 'bold'))
        self.stop_key_hint.pack(side="left", padx=(5, 0))

        format_frame = ttk.Frame(debug_frame)
        format_frame.pack(fill="x", pady=2)
        format_status = "支持MP3" if PYDUB_AVAILABLE else "不支持MP3(需安装pydub)"
        format_color = "green" if PYDUB_AVAILABLE else "orange"
        ttk.Label(format_frame, text="音频格式:", font=('Arial', 9)).pack(side="left")
        tk.Label(format_frame, text=format_status, fg=format_color, font=('Arial', 9, 'bold')).pack(side="left", padx=(5, 0))

    def _create_collection_tab(self, parent):
        collection_manage_frame = ttk.LabelFrame(parent, text="合集管理", padding=15)
        collection_manage_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.collection_tree = ttk.Treeview(collection_manage_frame, columns=('合集名称', '快捷键', '音效数量'), show='headings')
        self.collection_tree.heading('合集名称', text='合集名称')
        self.collection_tree.heading('快捷键', text='快捷键')
        self.collection_tree.heading('音效数量', text='音效数量')
        self.collection_tree.column('合集名称', width=200)
        self.collection_tree.column('快捷键', width=100)
        self.collection_tree.column('音效数量', width=80)

        scrollbar = ttk.Scrollbar(collection_manage_frame, orient=tk.VERTICAL, command=self.collection_tree.yview)
        self.collection_tree.configure(yscrollcommand=scrollbar.set)
        self.collection_tree.pack(side=tk.LEFT, fill="both", expand=True, padx=(0, 5))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        button_frame = ttk.Frame(collection_manage_frame)
        button_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        ttk.Button(button_frame, text="新建合集", command=self.create_collection, width=15).pack(pady=5)
        ttk.Button(button_frame, text="删除合集", command=self.delete_collection, width=15).pack(pady=5)
        ttk.Button(button_frame, text="添加音效到合集", command=self.add_files_to_collection_direct, width=15).pack(pady=5)
        ttk.Button(button_frame, text="移除音效", command=self.remove_file_from_collection, width=15).pack(pady=5)
        ttk.Button(button_frame, text="查看详情", command=self.view_collection_details, width=15).pack(pady=5)
        ttk.Button(button_frame, text="重置播放计数", command=self.reset_collection_play_counts, width=15).pack(pady=5)
        ttk.Button(button_frame, text="设置快捷键", command=self.set_collection_hotkey, width=15).pack(pady=5)

        detail_frame = ttk.LabelFrame(parent, text="合集详情", padding=15)
        detail_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.collection_detail_text = tk.Text(detail_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        scroll = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL, command=self.collection_detail_text.yview)
        self.collection_detail_text.configure(yscrollcommand=scroll.set)
        self.collection_detail_text.pack(side=tk.LEFT, fill="both", expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _create_web_tab(self, parent):
        web_control_frame = ttk.LabelFrame(parent, text="Web服务器控制", padding=15)
        web_control_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.web_status_label = ttk.Label(web_control_frame, text="服务器状态: 未启动", font=('Arial', 12))
        self.web_status_label.pack(pady=(0, 10))
        self.web_address_label = ttk.Label(web_control_frame, text="地址: 未启动", font=('Arial', 10))
        self.web_address_label.pack(pady=(0, 20))

        btn_frame = ttk.Frame(web_control_frame)
        btn_frame.pack(pady=10)
        self.web_start_button = ttk.Button(btn_frame, text="启动Web服务器", command=self.start_web_server, width=20)
        self.web_start_button.pack(side="left", padx=5)
        self.web_stop_button = ttk.Button(btn_frame, text="停止Web服务器", command=self.stop_web_server, width=20, state="disabled")
        self.web_stop_button.pack(side="left", padx=5)

        self.web_open_button = ttk.Button(web_control_frame, text="在浏览器中打开", command=self.open_web_browser, width=20, state="disabled")
        self.web_open_button.pack(pady=10)

        instruction_frame = ttk.LabelFrame(parent, text="使用说明", padding=15)
        instruction_frame.pack(fill="x", padx=10, pady=(0, 10))

        instructions = """
        1. 启动Web服务器后，在同一局域网内的手机或电脑浏览器中访问上述地址
        2. 网页将显示所有音效和合集，点击即可播放
        3. 播放时会自动按下开麦键，播放完成后自动释放开麦键
        4. 网页会自动更新播放状态和开麦键状态
        5. 确保手机和电脑连接在同一WiFi网络下
        6. 如有防火墙提示，请允许Python通过防火墙
        """
        text = tk.Text(instruction_frame, height=8, wrap=tk.WORD, font=('Arial', 10))
        text.insert(1.0, instructions)
        text.config(state=tk.DISABLED)
        text.pack(fill="both", expand=True)

        qr_frame = ttk.LabelFrame(parent, text="手机访问二维码（可选）", padding=15)
        qr_frame.pack(fill="x", padx=10, pady=(0, 10))
        try:
            import qrcode
            from PIL import Image, ImageTk
            self.qr_available = True
            self.qr_label = ttk.Label(qr_frame, text="启动服务器后生成二维码")
            self.qr_label.pack()
        except ImportError:
            self.qr_available = False
            ttk.Label(qr_frame, text="安装qrcode和Pillow库可生成二维码:\npip install qrcode[pil] Pillow").pack()

    def _create_about_tab(self, parent):
        """创建关于标签页，包含详细教程、版权信息和联系作者按钮"""
        main_frame = ttk.Frame(parent, padding=15)
        main_frame.pack(fill="both", expand=True)

        # 使用Text控件显示详细教程和版权信息，便于滚动
        text_widget = tk.Text(main_frame, wrap=tk.WORD, font=('Arial', 10), height=20)
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        text_widget.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 插入详细教程
        tutorial = """
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
"""

        copyright_text = """
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
"""
        text_widget.insert(tk.END, tutorial)
        text_widget.insert(tk.END, "\n" + "="*60 + "\n\n")
        text_widget.insert(tk.END, copyright_text)
        text_widget.config(state=tk.DISABLED)

        # 联系作者按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="📞 联系作者 (QQ群)", command=lambda: webbrowser.open("https://qm.qq.com/q/XOza7RQt2Y")).pack()

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
            if not self.devices_info:
                self.device_combobox['values'] = ["未找到音频输出设备"]
                self.device_var.set("未找到音频输出设备")
                self.device_info_label.config(text="错误: 没有可用的音频输出设备")
                return
            device_names = [f"{info['index']}: {info['name']}" for info in self.devices_info]
            self.device_combobox['values'] = device_names
            self.device_combobox.bind('<<ComboboxSelected>>', self.on_device_select)
            if self.selected_device_index is not None:
                found = False
                for i, info in enumerate(self.devices_info):
                    if info['index'] == self.selected_device_index:
                        self.device_combobox.current(i)
                        self.update_device_info_label()
                        found = True
                        break
                if not found and device_names:
                    self.device_combobox.current(0)
                    self.selected_device_index = self.devices_info[0]['index']
                    self.update_device_info_label()
            elif device_names:
                self.device_combobox.current(0)
                self.selected_device_index = self.devices_info[0]['index']
                self.update_device_info_label()
            self.status_label.config(text=f"找到 {len(self.devices_info)} 个音频设备")
        except Exception as e:
            print(f"刷新设备列表失败: {e}")

    def on_device_select(self, event=None):
        try:
            selected_idx = self.device_combobox.current()
            if selected_idx >= 0 and selected_idx < len(self.devices_info):
                self.selected_device_index = self.devices_info[selected_idx]['index']
                self.update_device_info_label()
                self.save_config()
        except Exception as e:
            print(f"设备选择事件错误: {e}")

    def update_device_info_label(self):
        if self.selected_device_index is not None:
            for info in self.devices_info:
                if info['index'] == self.selected_device_index:
                    self.device_info_label.config(
                        text=f"设备ID: {info['index']} | 通道: {info['channels']} | 采样率: {info['defaultSampleRate']}Hz"
                    )
                    break

    def show_device_info(self):
        info_window = tk.Toplevel(self.root)
        info_window.title("音频设备信息")
        info_window.geometry("700x500")
        text_frame = ttk.Frame(info_window)
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        text = tk.Text(text_frame, wrap=tk.WORD, font=('Consolas', 9))
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.insert(tk.END, "=== 所有音频设备 ===\n\n")
        for i in range(self.p.get_device_count()):
            try:
                info = self.p.get_device_info_by_index(i)
                text.insert(tk.END, f"[设备 {i}]\n")
                text.insert(tk.END, f"  名称: {info.get('name', 'Unknown')}\n")
                text.insert(tk.END, f"  输入通道: {info.get('maxInputChannels', 0)}\n")
                text.insert(tk.END, f"  输出通道: {info.get('maxOutputChannels', 0)}\n")
                text.insert(tk.END, f"  默认采样率: {info.get('defaultSampleRate', 0)} Hz\n")
                text.insert(tk.END, "-" * 50 + "\n\n")
            except:
                text.insert(tk.END, f"[设备 {i}] 无法获取信息\n\n")
        text.config(state=tk.DISABLED)

    def test_device(self):
        if self.selected_device_index is None:
            messagebox.showwarning("提示", "请先选择音频设备")
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
            self.status_label.config(text="设备测试完成")
            messagebox.showinfo("测试成功", "音频设备工作正常！")
        except Exception as e:
            messagebox.showerror("测试失败", f"无法播放测试音: {str(e)}")

    def play_test_tone(self):
        self.test_device()

    # ------------------ 音频文件管理 ------------------
    def add_audio_file(self):
        filetypes = [
            ('音频文件', '*.mp3 *.wav *.ogg *.flac *.m4a *.aac'),
            ('MP3文件', '*.mp3'),
            ('WAV文件', '*.wav'),
            ('所有文件', '*.*')
        ]
        file_path = filedialog.askopenfilename(title="选择音频文件", filetypes=filetypes)
        if file_path:
            file_name = os.path.basename(file_path)
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_name in self.audio_files:
                response = messagebox.askyesno("文件已存在", f"'{file_name}' 已经存在于列表中。\n是否替换？")
                if not response:
                    return
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
            self.refresh_treeview()
            self.save_config()
            self.status_label.config(text=f"已添加: {file_name}")
            messagebox.showinfo("成功", f"已添加音效: {file_name}\n您可以在列表中为其设置快捷键。")

    def remove_audio_file(self):
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        file_name = self.tree.item(item, 'values')[0]
        response = messagebox.askyesno("确认删除", f"确定要删除 '{file_name}' 吗？")
        if response:
            if self.is_playing and self.current_playing == file_name:
                self.stop_playback()
            if file_name in self.audio_files:
                del self.audio_files[file_name]
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
            self.status_label.config(text=f"已删除: {file_name}")

    def refresh_treeview(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for file_name, info in self.audio_files.items():
            hotkey = info.get('hotkey', '')
            hotkey_display = self.format_hotkey_for_display(hotkey)
            duration = info.get('duration', '未知')
            file_format = info.get('format', '未知')
            source = info.get('source', '本地添加')
            self.tree.insert('', 'end', values=(file_name, hotkey_display, duration, file_format, source))

    def refresh_collection_treeview(self):
        for item in self.collection_tree.get_children():
            self.collection_tree.delete(item)
        for collection_name, collection_info in self.collections.items():
            hotkey = collection_info.get('hotkey', '')
            hotkey_display = self.format_hotkey_for_display(hotkey)
            files_count = len(collection_info.get('files', []))
            self.collection_tree.insert('', 'end', values=(
                collection_name,
                hotkey_display,
                files_count
            ))

    def on_tree_select(self, event):
        selection = self.tree.selection()
        if selection:
            self.delete_button.config(state="normal")
            self.hotkey_button.config(state="normal")
            self.play_button.config(state="normal")
            self.stop_button.config(state="normal")
        else:
            self.delete_button.config(state="disabled")
            self.hotkey_button.config(state="disabled")
            self.play_button.config(state="disabled")
            self.stop_button.config(state="disabled")

    def on_item_double_click(self, event):
        selection = self.tree.selection()
        if selection:
            self.test_play()

    def test_play(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个音效")
            return
        if self.selected_device_index is None:
            messagebox.showwarning("提示", "请先选择音频输出设备")
            return
        if self.is_playing:
            messagebox.showwarning("提示", "请等待当前音效播放完毕")
            return
        item = selection[0]
        file_name = self.tree.item(item, 'values')[0]
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
            self.root.after(0, self.update_play_status, True, file_name)
            with self.c_key_lock:
                was_c_key_held = self.c_key_held
            self.hold_c_key(False)
            self.play_audio_file(file_path)
        except Exception as e:
            print(f"播放错误: {traceback.format_exc()}")
            self.root.after(0, lambda: messagebox.showerror("播放错误", str(e)))
        finally:
            if not was_c_key_held:
                self.release_c_key(False)
            self.is_playing = False
            self.current_playing = None
            self.root.after(0, self.update_play_status, False, None)

    def play_audio_file(self, file_path):
        """播放音频文件，支持音量调节（无论是否有pydub，WAV文件都能调节）"""
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
            self.play_status_label.config(text="状态: 播放中")
            self.current_file_label.config(text=f"当前: {file_name}")
            self.play_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.status_label.config(text=f"正在播放: {file_name}")
        else:
            self.play_status_label.config(text="状态: 空闲")
            self.current_file_label.config(text="当前: 无")
            self.play_button.config(state="normal")
            self.stop_button.config(state="disabled")
            self.status_label.config(text="播放完成")

    def stop_playback(self):
        if self.is_playing:
            print("停止播放...")
            self.stop_flag = True
            self.status_label.config(text="播放已停止")

    # ------------------ 开麦键控制 ------------------
    def hold_c_key(self, manual=False):
        with self.c_key_lock:
            if not self.c_key_held:
                try:
                    print(f"按下{self.mic_key.upper()}键...")
                    self.keyboard_controller.press(self.mic_key)
                    self.c_key_held = True
                    self.root.after(0, lambda: self.c_key_indicator.config(text="按下", bg="green", fg="white"))
                    if manual:
                        self.root.after(0, lambda: self.status_label.config(text=f"{self.mic_key.upper()}键已按下 (手动测试)"))
                        threading.Timer(1.0, lambda: self.release_c_key(True)).start()
                except Exception as e:
                    print(f"按下{self.mic_key.upper()}键失败: {e}")

    def release_c_key(self, manual=False):
        with self.c_key_lock:
            if self.c_key_held:
                try:
                    print(f"释放{self.mic_key.upper()}键...")
                    self.keyboard_controller.release(self.mic_key)
                    self.c_key_held = False
                    self.root.after(0, lambda: self.c_key_indicator.config(text="释放", bg="red", fg="white"))
                    if manual:
                        self.root.after(0, lambda: self.status_label.config(text=f"{self.mic_key.upper()}键已释放 (手动测试)"))
                except Exception as e:
                    print(f"释放{self.mic_key.upper()}键失败: {e}")

    def set_mic_key(self):
        """弹出窗口设置开麦键"""
        if self.mic_key_window and self.mic_key_window.winfo_exists():
            self.mic_key_window.destroy()

        self.mic_key_window = tk.Toplevel(self.root)
        self.mic_key_window.title("设置开麦键")
        self.mic_key_window.geometry("350x200")
        self.mic_key_window.resizable(False, False)
        self.mic_key_window.transient(self.root)
        self.mic_key_window.grab_set()

        main_frame = ttk.Frame(self.mic_key_window, padding=20)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text="设置开麦键（播放时自动按下）", font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        current_display = self.format_hotkey_for_display(self.mic_key)
        ttk.Label(main_frame, text=f"当前开麦键: {current_display}", font=('Arial', 10)).pack(pady=(0, 10))

        ttk.Label(main_frame, text="请按下您要设置为开麦键的按键", font=('Arial', 9)).pack(pady=5)

        self.mic_pressed_key_var = tk.StringVar(value="等待按键...")
        key_display = ttk.Label(main_frame, textvariable=self.mic_pressed_key_var,
                                font=('Arial', 14, 'bold'), foreground="blue")
        key_display.pack(pady=10)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="取消", command=self.mic_key_window.destroy, width=10).pack(side="left", padx=5)

        self.mic_key_window.focus_set()
        self.mic_key_window.bind('<KeyPress>', self.on_mic_key_press)
        self.mic_key_window.bind('<Return>', lambda e: self.save_mic_key())
        self.mic_key_window.bind('<Escape>', lambda e: self.mic_key_window.destroy())

        self.temp_mic_key = None

    def on_mic_key_press(self, event):
        if event.keysym in ('Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Caps_Lock', 'Num_Lock'):
            return
        key_str = self.key_event_to_string(event)
        if not key_str:
            return
        self.mic_pressed_key_var.set(f"按下了: {self.format_hotkey_for_display(key_str)}")
        self.temp_mic_key = key_str

    def save_mic_key(self):
        if not self.temp_mic_key:
            messagebox.showwarning("警告", "请先按下一个按键")
            return
        conflicts = []
        for name, info in self.audio_files.items():
            if info.get('hotkey') == self.temp_mic_key:
                conflicts.append(f"音效: {name}")
        for cname, cinfo in self.collections.items():
            if cinfo.get('hotkey') == self.temp_mic_key:
                conflicts.append(f"合集: {cname}")
        if conflicts:
            conflict_msg = "以下快捷键将被覆盖（因为它们将无法使用）：\n" + "\n".join(conflicts)
            if not messagebox.askyesno("警告", conflict_msg + "\n\n是否仍然设置？"):
                return

        self.mic_key = self.temp_mic_key
        self.save_config()
        self.mic_key_display_label.config(text=f"键位: {self.format_hotkey_for_display(self.mic_key)}")
        self.mic_key_window.destroy()
        messagebox.showinfo("成功", f"开麦键已设置为: {self.format_hotkey_for_display(self.mic_key)}")
        self.status_label.config(text=f"开麦键已更新为: {self.format_hotkey_for_display(self.mic_key)}")

    def set_stop_key(self):
        """弹出窗口设置停止快捷键"""
        if self.stop_key_window and self.stop_key_window.winfo_exists():
            self.stop_key_window.destroy()

        self.stop_key_window = tk.Toplevel(self.root)
        self.stop_key_window.title("设置停止快捷键")
        self.stop_key_window.geometry("350x200")
        self.stop_key_window.resizable(False, False)
        self.stop_key_window.transient(self.root)
        self.stop_key_window.grab_set()

        main_frame = ttk.Frame(self.stop_key_window, padding=20)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text="设置停止播放的快捷键", font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        current_display = self.format_hotkey_for_display(self.stop_key)
        ttk.Label(main_frame, text=f"当前停止键: {current_display}", font=('Arial', 10)).pack(pady=(0, 10))

        ttk.Label(main_frame, text="请按下您要设置为停止的按键", font=('Arial', 9)).pack(pady=5)

        self.stop_pressed_key_var = tk.StringVar(value="等待按键...")
        key_display = ttk.Label(main_frame, textvariable=self.stop_pressed_key_var,
                                font=('Arial', 14, 'bold'), foreground="blue")
        key_display.pack(pady=10)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="取消", command=self.stop_key_window.destroy, width=10).pack(side="left", padx=5)

        self.stop_key_window.focus_set()
        self.stop_key_window.bind('<KeyPress>', self.on_stop_key_press)
        self.stop_key_window.bind('<Return>', lambda e: self.save_stop_key())
        self.stop_key_window.bind('<Escape>', lambda e: self.stop_key_window.destroy())

        self.temp_stop_key = None

    def on_stop_key_press(self, event):
        if event.keysym in ('Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Caps_Lock', 'Num_Lock'):
            return
        key_str = self.key_event_to_string(event)
        if not key_str:
            return
        if key_str == self.mic_key:
            self.stop_pressed_key_var.set(f"开麦键 {self.format_hotkey_for_display(key_str)} 不能作为停止键")
            return
        self.stop_pressed_key_var.set(f"按下了: {self.format_hotkey_for_display(key_str)}")
        self.temp_stop_key = key_str

    def save_stop_key(self):
        if not self.temp_stop_key:
            messagebox.showwarning("警告", "请先按下一个按键")
            return
        conflicts = []
        for name, info in self.audio_files.items():
            if info.get('hotkey') == self.temp_stop_key:
                conflicts.append(f"音效: {name}")
        for cname, cinfo in self.collections.items():
            if cinfo.get('hotkey') == self.temp_stop_key:
                conflicts.append(f"合集: {cname}")
        if conflicts:
            conflict_msg = "以下快捷键将与停止键冲突（它们将无法触发播放）：\n" + "\n".join(conflicts)
            if not messagebox.askyesno("警告", conflict_msg + "\n\n是否仍然设置？"):
                return

        self.stop_key = self.temp_stop_key
        self.save_config()
        self.stop_key_display_label.config(text=self.format_hotkey_for_display(self.stop_key))
        self.stop_key_hint.config(text=self.format_hotkey_for_display(self.stop_key))
        self.stop_key_window.destroy()
        messagebox.showinfo("成功", f"停止快捷键已设置为: {self.format_hotkey_for_display(self.stop_key)}")
        self.status_label.config(text=f"停止键已更新为: {self.format_hotkey_for_display(self.stop_key)}")

    # ------------------ 快捷键设置 ------------------
    def set_hotkey(self):
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        file_name = self.tree.item(item, 'values')[0]
        if file_name not in self.audio_files:
            messagebox.showerror("错误", f"找不到文件: {file_name}")
            return

        if self.hotkey_window and self.hotkey_window.winfo_exists():
            self.hotkey_window.destroy()

        self.hotkey_window = tk.Toplevel(self.root)
        self.hotkey_window.title(f"设置快捷键 - {file_name}")
        self.hotkey_window.geometry("400x300")
        self.hotkey_window.resizable(False, False)
        self.hotkey_window.transient(self.root)
        self.hotkey_window.grab_set()

        main_frame = ttk.Frame(self.hotkey_window, padding=20)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text=f"为 '{file_name}' 设置快捷键", font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        current_hotkey = self.audio_files[file_name].get('hotkey', '')
        current_display = self.format_hotkey_for_display(current_hotkey)
        ttk.Label(main_frame, text=f"当前快捷键: {current_display}", font=('Arial', 10)).pack(pady=(0, 10))

        ttk.Label(main_frame, text="请按下您要设置的按键（ESC取消，回车确认）", font=('Arial', 9)).pack(pady=5)

        self.pressed_key_var = tk.StringVar(value="等待按键...")
        key_display = ttk.Label(main_frame, textvariable=self.pressed_key_var, font=('Arial', 14, 'bold'), foreground="blue")
        key_display.pack(pady=10)

        preview_frame = ttk.Frame(main_frame)
        preview_frame.pack(pady=5)
        ttk.Label(preview_frame, text="存储值:").pack(side="left")
        self.stored_key_var = tk.StringVar(value="")
        ttk.Label(preview_frame, textvariable=self.stored_key_var, font=('Arial', 9, 'bold')).pack(side="left", padx=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        ttk.Button(button_frame, text="清除", command=self.clear_hotkey, width=10).pack(side="left", padx=5)
        ttk.Button(button_frame, text="取消", command=self.hotkey_window.destroy, width=10).pack(side="left", padx=5)

        self.hotkey_window.focus_set()
        self.hotkey_window.bind('<KeyPress>', self.on_hotkey_key_press)
        self.hotkey_window.bind('<Return>', lambda e: self.save_hotkey(file_name))
        self.hotkey_window.bind('<Escape>', lambda e: self.hotkey_window.destroy())

        self.temp_hotkey = None

    def on_hotkey_key_press(self, event):
        if event.keysym in ('Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Caps_Lock', 'Num_Lock'):
            return
        key_str = self.key_event_to_string(event)
        if not key_str:
            return
        if key_str == self.mic_key:
            self.pressed_key_var.set(f"开麦键 {self.format_hotkey_for_display(key_str)} 不能用作快捷键")
            return
        if key_str == self.stop_key:
            self.pressed_key_var.set(f"停止键 {self.format_hotkey_for_display(key_str)} 不能用作快捷键")
            return
        self.pressed_key_var.set(f"按下了: {self.format_hotkey_for_display(key_str)}")
        self.stored_key_var.set(key_str)
        self.temp_hotkey = key_str

    def save_hotkey(self, file_name):
        if not self.temp_hotkey:
            messagebox.showwarning("警告", "请先按下一个按键")
            return
        used_by = None
        for name, info in self.audio_files.items():
            if name != file_name and info.get('hotkey') == self.temp_hotkey:
                used_by = name
                break
        if not used_by:
            for cname, cinfo in self.collections.items():
                if cinfo.get('hotkey') == self.temp_hotkey:
                    used_by = f"合集 '{cname}'"
                    break
        if used_by:
            if not messagebox.askyesno("快捷键冲突", f"快捷键已被 {used_by} 使用，是否仍要使用？"):
                return
        self.audio_files[file_name]['hotkey'] = self.temp_hotkey
        self.save_config()
        self.refresh_treeview()
        self.hotkey_window.destroy()
        self.hotkey_window = None
        messagebox.showinfo("成功", f"已为 '{file_name}' 设置快捷键: {self.format_hotkey_for_display(self.temp_hotkey)}")

    def clear_hotkey(self):
        selection = self.tree.selection()
        if not selection:
            return
        item = selection[0]
        file_name = self.tree.item(item, 'values')[0]
        if file_name in self.audio_files:
            self.audio_files[file_name]['hotkey'] = ''
            self.save_config()
            self.refresh_treeview()
        if self.hotkey_window:
            self.hotkey_window.destroy()

    # ------------------ 合集管理 ------------------
    def create_collection(self):
        collection_name = simpledialog.askstring("新建合集", "请输入合集名称:")
        if collection_name:
            if collection_name in self.collections:
                messagebox.showwarning("警告", f"合集 '{collection_name}' 已存在！")
                return
            self.collections[collection_name] = {'files': [], 'hotkey': ''}
            if collection_name not in self.collection_play_counts:
                self.collection_play_counts[collection_name] = {}
            self.refresh_collection_treeview()
            self.save_config()
            self.save_play_counts()
            self.status_label.config(text=f"已创建合集: {collection_name}")

    def delete_collection(self):
        selection = self.collection_tree.selection()
        if not selection:
            return
        item = selection[0]
        collection_name = self.collection_tree.item(item, 'values')[0]
        response = messagebox.askyesno("确认删除", f"确定要删除合集 '{collection_name}' 吗？\n注意：播放计数也会被删除。")
        if response:
            if collection_name in self.collections:
                del self.collections[collection_name]
            if collection_name in self.collection_play_counts:
                del self.collection_play_counts[collection_name]
            self.refresh_collection_treeview()
            self.clear_collection_details()
            self.save_config()
            self.save_play_counts()
            self.status_label.config(text=f"已删除合集: {collection_name}")

    def add_files_to_collection_direct(self):
        selection = self.collection_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个合集")
            return
        item = selection[0]
        collection_name = self.collection_tree.item(item, 'values')[0]
        if collection_name not in self.collections:
            return
        filetypes = [('音频文件', '*.mp3 *.wav *.ogg *.flac *.m4a *.aac'), ('MP3文件', '*.mp3'), ('WAV文件', '*.wav'), ('所有文件', '*.*')]
        file_paths = filedialog.askopenfilenames(title=f"选择音频文件添加到合集 '{collection_name}'", filetypes=filetypes)
        if not file_paths:
            return
        added_count = 0
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            if file_name in self.collections[collection_name]['files']:
                response = messagebox.askyesno("文件已存在", f"'{file_name}' 已经在合集中，是否替换？")
                if not response:
                    continue
                if file_name in self.collections[collection_name]['files']:
                    self.collections[collection_name]['files'].remove(file_name)
            self.collections[collection_name]['files'].append(file_name)
            if collection_name not in self.collection_play_counts:
                self.collection_play_counts[collection_name] = {}
            if file_name not in self.collection_play_counts[collection_name]:
                self.collection_play_counts[collection_name][file_name] = 0
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
        self.status_label.config(text=f"已向合集 '{collection_name}' 添加 {added_count} 个音效")
        messagebox.showinfo("成功", f"已向合集 '{collection_name}' 添加 {added_count} 个音效")

    def remove_file_from_collection(self):
        selection = self.collection_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个合集")
            return
        item = selection[0]
        collection_name = self.collection_tree.item(item, 'values')[0]
        if collection_name not in self.collections:
            return
        collection_files = self.collections[collection_name]['files']
        if not collection_files:
            messagebox.showinfo("提示", f"合集 '{collection_name}' 中没有音效")
            return
        select_window = tk.Toplevel(self.root)
        select_window.title(f"从合集 '{collection_name}' 移除音效")
        select_window.geometry("400x500")
        main_frame = ttk.Frame(select_window, padding=10)
        main_frame.pack(fill="both", expand=True)
        ttk.Label(main_frame, text=f"选择要从合集 '{collection_name}' 移除的音效:", font=('Arial', 11, 'bold')).pack(pady=(0, 10))
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill="both", expand=True, pady=(0, 10))
        listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, font=('Arial', 10))
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        for file_name in collection_files:
            listbox.insert(tk.END, file_name)
        listbox.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def remove_selected():
            selected_indices = listbox.curselection()
            if not selected_indices:
                messagebox.showwarning("提示", "请先选择音效")
                return
            selected_files = [listbox.get(index) for index in selected_indices]
            for file_name in selected_files:
                if file_name in self.collections[collection_name]['files']:
                    self.collections[collection_name]['files'].remove(file_name)
                if collection_name in self.collection_play_counts:
                    if file_name in self.collection_play_counts[collection_name]:
                        del self.collection_play_counts[collection_name][file_name]
            self.refresh_collection_treeview()
            self.save_config()
            self.save_play_counts()
            select_window.destroy()
            self.status_label.config(text=f"已从合集 '{collection_name}' 移除 {len(selected_files)} 个音效")
            messagebox.showinfo("成功", f"已从合集 '{collection_name}' 移除 {len(selected_files)} 个音效")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack()
        ttk.Button(button_frame, text="移除选中", command=remove_selected, width=15).pack(side="left", padx=5)
        ttk.Button(button_frame, text="取消", command=select_window.destroy, width=15).pack(side="left", padx=5)

    def view_collection_details(self):
        selection = self.collection_tree.selection()
        if not selection:
            return
        item = selection[0]
        collection_name = self.collection_tree.item(item, 'values')[0]
        if collection_name not in self.collections:
            return
        collection_info = self.collections[collection_name]
        files = collection_info.get('files', [])
        hotkey = collection_info.get('hotkey', '')
        self.collection_detail_text.config(state=tk.NORMAL)
        self.collection_detail_text.delete(1.0, tk.END)
        self.collection_detail_text.insert(tk.END, f"合集名称: {collection_name}\n")
        self.collection_detail_text.insert(tk.END, f"快捷键: {self.format_hotkey_for_display(hotkey)}\n")
        self.collection_detail_text.insert(tk.END, f"音效数量: {len(files)}\n\n")
        if files:
            self.collection_detail_text.insert(tk.END, "包含音效:\n")
            for i, file_name in enumerate(files):
                audio_info = self.audio_files.get(file_name, {})
                duration = audio_info.get('duration', '未知')
                play_count = 0
                if collection_name in self.collection_play_counts:
                    play_count = self.collection_play_counts[collection_name].get(file_name, 0)
                self.collection_detail_text.insert(tk.END, f"  {i+1}. {file_name} ({duration}) - 播放{play_count}次\n")
        else:
            self.collection_detail_text.insert(tk.END, "合集为空，请添加音效。\n")
        self.collection_detail_text.config(state=tk.DISABLED)

    def clear_collection_details(self):
        self.collection_detail_text.config(state=tk.NORMAL)
        self.collection_detail_text.delete(1.0, tk.END)
        self.collection_detail_text.config(state=tk.DISABLED)

    def reset_collection_play_counts(self):
        selection = self.collection_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个合集")
            return
        item = selection[0]
        collection_name = self.collection_tree.item(item, 'values')[0]
        if collection_name not in self.collections:
            return
        response = messagebox.askyesno("确认重置", f"确定要重置合集 '{collection_name}' 的播放计数吗？")
        if response:
            if collection_name in self.collection_play_counts:
                for file_name in self.collection_play_counts[collection_name]:
                    self.collection_play_counts[collection_name][file_name] = 0
            self.save_play_counts()
            self.view_collection_details()
            self.status_label.config(text=f"已重置合集 '{collection_name}' 的播放计数")
            messagebox.showinfo("成功", f"已重置合集 '{collection_name}' 的播放计数")

    def set_collection_hotkey(self):
        selection = self.collection_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个合集")
            return
        item = selection[0]
        collection_name = self.collection_tree.item(item, 'values')[0]
        if collection_name not in self.collections:
            return

        if self.collection_hotkey_window and self.collection_hotkey_window.winfo_exists():
            self.collection_hotkey_window.destroy()

        self.collection_hotkey_window = tk.Toplevel(self.root)
        self.collection_hotkey_window.title(f"设置合集快捷键 - {collection_name}")
        self.collection_hotkey_window.geometry("400x300")
        self.collection_hotkey_window.transient(self.root)
        self.collection_hotkey_window.grab_set()

        main_frame = ttk.Frame(self.collection_hotkey_window, padding=20)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text=f"为合集 '{collection_name}' 设置快捷键", font=('Arial', 11, 'bold')).pack(pady=(0, 10))

        current_hotkey = self.collections[collection_name].get('hotkey', '')
        current_display = self.format_hotkey_for_display(current_hotkey)
        ttk.Label(main_frame, text=f"当前快捷键: {current_display}", font=('Arial', 10)).pack(pady=(0, 10))

        ttk.Label(main_frame, text="请按下您要设置的按键（ESC取消，回车确认）", font=('Arial', 9)).pack(pady=5)

        self.pressed_key_var_col = tk.StringVar(value="等待按键...")
        key_display = ttk.Label(main_frame, textvariable=self.pressed_key_var_col, font=('Arial', 14, 'bold'), foreground="blue")
        key_display.pack(pady=10)

        preview_frame = ttk.Frame(main_frame)
        preview_frame.pack(pady=5)
        ttk.Label(preview_frame, text="存储值:").pack(side="left")
        self.stored_key_var_col = tk.StringVar(value="")
        ttk.Label(preview_frame, textvariable=self.stored_key_var_col, font=('Arial', 9, 'bold')).pack(side="left", padx=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        ttk.Button(button_frame, text="清除", command=lambda: self.clear_collection_hotkey(collection_name), width=10).pack(side="left", padx=5)
        ttk.Button(button_frame, text="取消", command=self.collection_hotkey_window.destroy, width=10).pack(side="left", padx=5)

        self.collection_hotkey_window.focus_set()
        self.collection_hotkey_window.bind('<KeyPress>', self.on_collection_hotkey_key_press)
        self.collection_hotkey_window.bind('<Return>', lambda e: self.save_collection_hotkey(collection_name))
        self.collection_hotkey_window.bind('<Escape>', lambda e: self.collection_hotkey_window.destroy())

        self.temp_collection_hotkey = None

    def on_collection_hotkey_key_press(self, event):
        if event.keysym in ('Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Caps_Lock', 'Num_Lock'):
            return
        key_str = self.key_event_to_string(event)
        if not key_str:
            return
        if key_str == self.mic_key:
            self.pressed_key_var_col.set(f"开麦键 {self.format_hotkey_for_display(key_str)} 不能用作快捷键")
            return
        if key_str == self.stop_key:
            self.pressed_key_var_col.set(f"停止键 {self.format_hotkey_for_display(key_str)} 不能用作快捷键")
            return
        self.pressed_key_var_col.set(f"按下了: {self.format_hotkey_for_display(key_str)}")
        self.stored_key_var_col.set(key_str)
        self.temp_collection_hotkey = key_str

    def save_collection_hotkey(self, collection_name):
        if not self.temp_collection_hotkey:
            messagebox.showwarning("警告", "请先按下一个按键")
            return
        used_by = None
        for name, info in self.audio_files.items():
            if info.get('hotkey') == self.temp_collection_hotkey:
                used_by = name
                break
        if not used_by:
            for cname, cinfo in self.collections.items():
                if cname != collection_name and cinfo.get('hotkey') == self.temp_collection_hotkey:
                    used_by = f"合集 '{cname}'"
                    break
        if used_by:
            if not messagebox.askyesno("快捷键冲突", f"快捷键已被 {used_by} 使用，是否仍要使用？"):
                return
        self.collections[collection_name]['hotkey'] = self.temp_collection_hotkey
        self.save_config()
        self.refresh_collection_treeview()
        self.collection_hotkey_window.destroy()
        self.collection_hotkey_window = None
        messagebox.showinfo("成功", f"已为合集 '{collection_name}' 设置快捷键: {self.format_hotkey_for_display(self.temp_collection_hotkey)}")

    def clear_collection_hotkey(self, collection_name):
        self.collections[collection_name]['hotkey'] = ''
        self.save_config()
        self.refresh_collection_treeview()
        if self.collection_hotkey_window:
            self.collection_hotkey_window.destroy()

    # ------------------ 快捷键监听 ------------------
    def start_key_listener(self):
        def on_press(key):
            try:
                if key is None:
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
                    self.root.after(0, self.stop_playback)
                    return

                for file_name, info in self.audio_files.items():
                    hotkey = info.get('hotkey', '')
                    if hotkey == key_str and not self.is_playing:
                        print(f"匹配到音效: {file_name}")
                        self.root.after(0, lambda fn=file_name, fp=info['path']: self.play_from_hotkey(fn, fp))
                        break

                for collection_name, collection_info in self.collections.items():
                    hotkey = collection_info.get('hotkey', '')
                    if hotkey == key_str and not self.is_playing:
                        print(f"匹配到合集: {collection_name}")
                        self.root.after(0, lambda cn=collection_name, ci=collection_info: self.play_from_collection_smart(cn, ci))
                        break

            except Exception as e:
                print(f"快捷键监听错误: {e}")

        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.daemon = True
        self.listener.start()
        self.listener_status.config(text="正常", foreground="green")
        print("快捷键监听已启动")

    def play_from_hotkey(self, file_name, file_path):
        if self.selected_device_index is None:
            self.root.after(0, lambda: messagebox.showwarning("提示", "请先选择音频输出设备"))
            return
        if self.is_playing:
            self.root.after(0, lambda: messagebox.showwarning("提示", "请等待当前音效播放完毕"))
            return
        thread = threading.Thread(target=self.play_audio_thread, args=(file_name, file_path), daemon=True)
        thread.start()
        self.root.after(0, lambda: self.status_label.config(text=f"快捷键播放: {file_name}"))

    def play_from_collection_smart(self, collection_name, collection_info):
        if self.selected_device_index is None:
            self.root.after(0, lambda: messagebox.showwarning("提示", "请先选择音频输出设备"))
            return
        if self.is_playing:
            self.root.after(0, lambda: messagebox.showwarning("提示", "请等待当前音效播放完毕"))
            return
        files = collection_info.get('files', [])
        if not files:
            self.root.after(0, lambda: messagebox.showwarning("提示", f"合集 '{collection_name}' 中没有音效"))
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
            self.root.after(0, lambda: messagebox.showwarning("提示", f"找不到音效文件: {selected_file}"))
            return
        file_path = file_info['path']
        thread = threading.Thread(
            target=self.play_audio_thread,
            args=(f"[{collection_name}] {selected_file} (播放{play_counts[selected_file]}次)", file_path),
            daemon=True
        )
        thread.start()
        self.root.after(0, lambda: self.status_label.config(
            text=f"合集播放: {collection_name} - {selected_file} (第{play_counts[selected_file]}次播放)"))

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
                'version': '5.8'
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
                        if self.web_server_enabled:
                            self.root.after(1000, self.start_web_server)
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
            messagebox.showinfo("提示", "Web服务器已经在运行中")
            return
        success = self.web_server.start()
        if success:
            self.web_server_enabled = True
            ip = self.web_server.get_local_ip()
            url = f"http://{ip}:{self.web_server.port}"
            self.web_status_label.config(text="服务器状态: 运行中")
            self.web_address_label.config(text=f"地址: {url}")
            self.web_start_button.config(state="disabled")
            self.web_stop_button.config(state="normal")
            self.web_open_button.config(state="normal")
            if hasattr(self, 'qr_available') and self.qr_available:
                self.update_qr_code(url)
            self.save_config()
            messagebox.showinfo("成功", f"Web服务器已启动！\n\n请在手机浏览器中访问：\n{url}\n\n确保手机和电脑在同一WiFi网络下。")
            self.status_label.config(text=f"Web服务器已启动: {url}")
        else:
            messagebox.showerror("错误", "启动Web服务器失败，请检查端口是否被占用。")

    def stop_web_server(self):
        if not self.web_server.running:
            return
        self.web_server.stop()
        self.web_server_enabled = False
        self.web_status_label.config(text="服务器状态: 已停止")
        self.web_address_label.config(text="地址: 未启动")
        self.web_start_button.config(state="normal")
        self.web_stop_button.config(state="disabled")
        self.web_open_button.config(state="disabled")
        self.save_config()
        self.status_label.config(text="Web服务器已停止")

    def open_web_browser(self):
        if self.web_server.running:
            ip = self.web_server.get_local_ip()
            url = f"http://{ip}:{self.web_server.port}"
            webbrowser.open(url)
        else:
            messagebox.showwarning("提示", "请先启动Web服务器")

    def update_qr_code(self, url):
        try:
            import qrcode
            from PIL import Image, ImageTk
            qr = qrcode.QRCode(version=1, box_size=4, border=4)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            photo = ImageTk.PhotoImage(img)
            self.qr_label.config(image=photo)
            self.qr_label.image = photo
        except Exception as e:
            print(f"生成二维码失败: {e}")

    def play_from_web(self, file_name):
        if self.selected_device_index is None:
            messagebox.showwarning("提示", "请先选择音频输出设备")
            return
        if self.is_playing:
            messagebox.showwarning("提示", "请等待当前音效播放完毕")
            return
        file_info = self.audio_files.get(file_name)
        if not file_info:
            messagebox.showerror("错误", f"找不到音效文件: {file_name}")
            return
        file_path = file_info['path']
        self.play_thread = threading.Thread(target=self.play_audio_thread, args=(file_name, file_path), daemon=True)
        self.play_thread.start()
        self.status_label.config(text=f"网页控制播放: {file_name}")

    def play_from_collection_web(self, collection_name):
        if self.selected_device_index is None:
            messagebox.showwarning("提示", "请先选择音频输出设备")
            return
        if self.is_playing:
            messagebox.showwarning("提示", "请等待当前音效播放完毕")
            return
        collection_info = self.collections.get(collection_name)
        if not collection_info:
            messagebox.showerror("错误", f"找不到合集: {collection_name}")
            return
        self.play_from_collection_smart(collection_name, collection_info)
        self.status_label.config(text=f"网页控制播放合集: {collection_name}")

    # ------------------ 其他 ------------------
    def show_tree_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.tree_menu.post(event.x_root, event.y_root)

    def show_mp3_warning(self):
        response = messagebox.askyesno(
            "MP3支持",
            "未安装pydub，MP3格式支持受限。\n\n是否安装pydub以获得完整MP3支持？\n\n(安装命令: pip install pydub)"
        )
        if response:
            try:
                import webbrowser
                webbrowser.open("https://pypi.org/project/pydub/")
            except:
                pass

    def check_hotkeys(self):
        hotkey_window = tk.Toplevel(self.root)
        hotkey_window.title("快捷键设置检查")
        hotkey_window.geometry("600x500")
        notebook = ttk.Notebook(hotkey_window)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        single_frame = ttk.Frame(notebook)
        notebook.add(single_frame, text="单个音效")
        single_text_frame = ttk.Frame(single_frame)
        single_text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        single_text = tk.Text(single_text_frame, wrap=tk.WORD, font=('Consolas', 10))
        single_scrollbar = ttk.Scrollbar(single_text_frame, orient="vertical", command=single_text.yview)
        single_text.configure(yscrollcommand=single_scrollbar.set)
        single_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        single_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        single_text.insert(tk.END, "=== 当前音效快捷键设置 ===\n\n")
        if not self.audio_files:
            single_text.insert(tk.END, "暂无音效文件\n")
        else:
            for file_name, info in self.audio_files.items():
                single_text.insert(tk.END, f"文件: {file_name}\n")
                hotkey = info.get('hotkey', '')
                single_text.insert(tk.END, f"  快捷键: {self.format_hotkey_for_display(hotkey)}\n")
                single_text.insert(tk.END, f"  路径: {info.get('path', '未知')}\n")
                single_text.insert(tk.END, f"  时长: {info.get('duration', '未知')}\n")
                single_text.insert(tk.END, f"  格式: {info.get('format', '未知')}\n")
                single_text.insert(tk.END, "-" * 50 + "\n\n")
        single_text.config(state=tk.DISABLED)

        collection_frame = ttk.Frame(notebook)
        notebook.add(collection_frame, text="音乐盒合集")
        collection_text_frame = ttk.Frame(collection_frame)
        collection_text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        collection_text = tk.Text(collection_text_frame, wrap=tk.WORD, font=('Consolas', 10))
        collection_scrollbar = ttk.Scrollbar(collection_text_frame, orient="vertical", command=collection_text.yview)
        collection_text.configure(yscrollcommand=collection_scrollbar.set)
        collection_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        collection_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        collection_text.insert(tk.END, "=== 当前合集快捷键设置 ===\n\n")
        if not self.collections:
            collection_text.insert(tk.END, "暂无音乐盒合集\n")
        else:
            for collection_name, collection_info in self.collections.items():
                collection_text.insert(tk.END, f"合集: {collection_name}\n")
                hotkey = collection_info.get('hotkey', '')
                collection_text.insert(tk.END, f"  快捷键: {self.format_hotkey_for_display(hotkey)}\n")
                files = collection_info.get('files', [])
                collection_text.insert(tk.END, f"  音效数量: {len(files)}\n")
                if collection_name in self.collection_play_counts:
                    play_counts = self.collection_play_counts[collection_name]
                    collection_text.insert(tk.END, "  播放计数:\n")
                    for file_name in files[:10]:
                        count = play_counts.get(file_name, 0)
                        collection_text.insert(tk.END, f"    {file_name}: {count}次\n")
                    if len(files) > 10:
                        collection_text.insert(tk.END, f"    ... 还有 {len(files)-10} 个\n")
                collection_text.insert(tk.END, "-" * 50 + "\n\n")
        collection_text.insert(tk.END, "\n=== 快捷键映射 ===\n")
        collection_text.insert(tk.END, "字母键、功能键、小键盘等均可自定义\n")
        collection_text.insert(tk.END, "\n停止快捷键: {}\n".format(self.format_hotkey_for_display(self.stop_key)))
        collection_text.insert(tk.END, "\n=== 随机播放算法 ===\n")
        collection_text.insert(tk.END, "智能随机: 优先播放次数最少的音频\n")
        collection_text.config(state=tk.DISABLED)

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
            except:
                pass
            self.audio_files[file_name] = {
                'path': file_path,
                'hotkey': '',
                'duration': duration,
                'format': file_ext.replace('.', '').upper(),
                'source': '网页上传'
            }
            self.refresh_treeview()
            self.save_config()
            self.root.after(0, lambda: self.status_label.config(text=f"已添加上传音频: {file_name}"))
            print(f"已添加上传音频: {file_name} ({duration}, {file_ext})")
            return True
        except Exception as e:
            print(f"添加上传音频失败: {e}")
            traceback.print_exc()
            return False

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
        self.root.destroy()


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

    root = tk.Tk()
    app = CS2MusicBox(root)
    root.mainloop()


if __name__ == "__main__":
    main()