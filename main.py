#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NetStreamPlayer — 网络视频流播放器
- Supports Motion / MJPG-Streamer video streams
- HTTP Basic Auth, pinch-to-zoom, screenshot, recording
- 简体中文界面
"""

import os
import json
import io
import time
import threading
from datetime import datetime

from kivy.config import Config
Config.set('kivy', 'log_level', 'debug')
Config.set('kivy', 'exit_on_escape', '0')

from kivy.app import App
from kivy.lang import Builder
from kivy.animation import Animation
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.scatter import Scatter
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.properties import ObjectProperty, NumericProperty, StringProperty, BooleanProperty
from kivy.metrics import dp
from kivy.utils import platform
from kivy.core.text import LabelBase
from kivy.vector import Vector

import requests

# ═══════════════════════════════════════════════════════════════════════════════
# 简体中文国际化
# ═══════════════════════════════════════════════════════════════════════════════

_STRINGS = {
    'app_name': 'NetStreamPlayer',
    'version': '1.1.2',
    'add_source': '+ 添加源',
    'edit_source': '编辑源',
    'save_source': '保存源',
    'update_source': '更新源',
    'source_name': '源名称:',
    'source_name_hint': '例如：前门摄像头',
    'stream_url': '流地址:',
    'stream_url_hint': 'http://192.168.1.100:8080/video.mjpg',
    'username': '用户名:',
    'username_hint': '（可选）',
    'password': '密码:',
    'password_hint': '（可选）',
    'common_url_patterns': '常用地址格式:',
    'motion_url': 'Motion: http://IP:PORT/',
    'mjpg_url': 'MJPG-Streamer: http://IP:PORT/?action=stream',
    'cancel': '取消',
    'back': '← 返回',
    'play': '▶',
    'edit': '✎',
    'delete': '✕',
    'unnamed': '未命名',
    'connecting': '连接中...',
    'connected': '已连接',
    'no_stream': '无视频流',
    'fps': 'FPS',
    'recording': '● 录制中',
    'screenshot': '📷 截图',
    'record': '⏺ 录像',
    'stop': '⏹ 停止',
    'fullscreen': '⛶ 全屏',
    'exit_fullscreen': '⛶ 退出',
    'orientation': '◉ 方向',
    'orientation_auto': '◉ 自动',
    'orientation_portrait': '◉ 竖屏',
    'orientation_landscape': '◉ 横屏',
    'reset_zoom': '⊞ 复位',
    'settings': '⚙',
    'save_dir': '保存目录:',
    'save': '保存',
    'error': '错误',
    'screenshot_saved': '截图已保存',
    'saved_to': '保存至:',
    'no_frame': '无可用帧',
    'recording_stopped': '录像已停止',
    'recording_timeout': '录像已停止（10分钟超时）',
    'frames': '帧数',
    'duration': '时长',
    'directory': '目录',
    'please_enter_name': '请输入源名称',
    'please_enter_url': '请输入流地址',
    'footer': 'Motion / MJPG-Streamer 播放器 v1.1',
    'source_list_empty': '暂无视频源，点击上方按钮添加',
    'backup_config': '备份配置',
    'restore_config': '恢复配置',
    'backup_ok': '备份成功',
    'restore_ok': '恢复成功',
    'backup_fail': '备份失败',
    'restore_fail': '恢复失败，文件无效',
}

def _(key):
    """简体中文翻译函数"""
    return _STRINGS.get(key, key)


# ─── 注册中文字体（内置 wqy-microhei） ────────────────────────────────
_font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wqy-microhei.ttc')
if os.path.exists(_font_path):
    try:
        LabelBase.register(name='Roboto', fn_regular=_font_path)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════════════════

APP_NAME = _('app_name')
VERSION = _('version')
SOURCES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sources.json')
DEFAULT_SAVE_DIR = '/sdcard/Download' if platform == 'android' else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'captures')
os.makedirs(DEFAULT_SAVE_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MJPEG 流读取器
# ═══════════════════════════════════════════════════════════════════════════════

class MjpegReader(threading.Thread):
    """在后台线程读取 MJPEG 流，通过回调发送帧数据。"""

    def __init__(self, url, username='', password='', on_frame=None, on_error=None, **kwargs):
        super().__init__(daemon=True)
        self.url = url
        self.username = username
        self.password = password
        self.on_frame = on_frame
        self.on_error = on_error
        self._running = False
        self._paused = False
        self._frame_count = 0
        self._lock = threading.Lock()
        self._latest_frame = None
        self._frame_ready = threading.Event()
        # 帧率限制：避免高分辨率（如 1080p）流以满帧率冲击主线程 UI
        # 当显示器跟不上时自动丢帧，保持流畅而非卡顿
        self._target_framerate = 15.0
        self._last_frame_time = 0.0

    def run(self):
        self._running = True
        auth = None
        if self.username and self.password:
            auth = (self.username, self.password)

        headers = {
            'User-Agent': f'{APP_NAME}/{VERSION}',
            'Accept': 'image/jpeg,*/*',
        }

        retry_delay = 1.0
        max_retry_delay = 10.0

        while self._running:
            try:
                resp = requests.get(
                    self.url, auth=auth, headers=headers,
                    stream=True, timeout=30
                )
                resp.raise_for_status()
                content_type = resp.headers.get('Content-Type', '')
                retry_delay = 1.0

                if 'multipart/x-mixed-replace' in content_type:
                    self._read_multipart(resp)
                elif 'image/jpeg' in content_type:
                    self._read_single_jpeg(resp)
                else:
                    self._read_raw_jpeg(resp)

            except requests.exceptions.RequestException as e:
                err_msg = f"连接错误: {e}"
                if self.on_error:
                    Clock.schedule_once(lambda dt, m=err_msg: self.on_error(m))
            except Exception as e:
                err_msg = f"流错误: {e}"
                if self.on_error:
                    Clock.schedule_once(lambda dt, m=err_msg: self.on_error(m))

            if self._running:
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)

    def _read_multipart(self, resp):
        """解析 multipart/x-mixed-replace MJPEG 流。"""
        boundary = None
        content_type = resp.headers.get('Content-Type', '')
        if 'boundary=' in content_type:
            boundary = content_type.split('boundary=')[1].strip().strip('"').strip("'")
            if isinstance(boundary, str):
                boundary = boundary.encode('utf-8')

        if not boundary:
            boundary = b'--'

        buffer = b''
        while self._running:
            try:
                chunk = resp.raw.read(4096)
                if not chunk:
                    break
                buffer += chunk

                while True:
                    start = buffer.find(b'\xff\xd8')
                    if start < 0:
                        break
                    end = buffer.find(b'\xff\xd9', start)
                    if end < 0:
                        break
                    end += 2

                    jpeg_data = buffer[start:end]
                    buffer = buffer[end:]

                    if len(jpeg_data) > 100:
                        self._process_frame(jpeg_data)

            except Exception as e:
                if self._running:
                    raise

    def _read_single_jpeg(self, resp):
        """读取单帧 JPEG 响应。"""
        data = resp.content
        if data and len(data) > 100:
            self._process_frame(data)
            while self._running:
                try:
                    more = resp.raw.read(4096)
                    if not more:
                        break
                    self._process_frame(more)
                except Exception:
                    break

    def _read_raw_jpeg(self, resp):
        """从原始字节流中提取 JPEG 帧。"""
        buffer = b''
        for chunk in resp.iter_content(chunk_size=4096):
            if not chunk or not self._running:
                break
            buffer += chunk
            while len(buffer) > 0:
                start = buffer.find(b'\xff\xd8')
                if start < 0:
                    if len(buffer) > 1048576:
                        buffer = buffer[-4096:]
                    break
                end = buffer.find(b'\xff\xd9', start)
                if end < 0:
                    break
                end += 2
                jpeg_data = buffer[start:end]
                buffer = buffer[end:]
                if len(jpeg_data) > 100:
                    self._process_frame(jpeg_data)

    def _process_frame(self, jpeg_data):
        now = time.time()
        # 帧率限制：丢弃超出目标帧率的帧，避免高分辨率流冲击 UI
        interval = 1.0 / self._target_framerate
        if now - self._last_frame_time < interval:
            # 仍更新最新帧缓存（截图/录像可用），但不触发 UI 回调
            with self._lock:
                self._latest_frame = jpeg_data
                self._frame_count += 1
            return
        self._last_frame_time = now
        with self._lock:
            self._latest_frame = jpeg_data
            self._frame_count += 1
            self._frame_ready.set()

        if self.on_frame and not self._paused:
            Clock.schedule_once(lambda dt: self.on_frame(jpeg_data))

    def get_latest_frame(self):
        with self._lock:
            return self._latest_frame

    def get_frame_count(self):
        with self._lock:
            return self._frame_count

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop(self):
        self._running = False


# ═══════════════════════════════════════════════════════════════════════════════
# 视频源管理器
# ═══════════════════════════════════════════════════════════════════════════════

class SourceManager:
    """管理视频源配置，存储于 JSON 文件。"""

    def __init__(self, filepath=SOURCES_FILE):
        self.filepath = filepath
        self.sources = []
        self.load()

    def load(self):
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.sources = data.get('sources', [])
        except Exception as e:
            print(f"加载源失败: {e}")
            self.sources = []

    def save(self):
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump({'sources': self.sources, 'version': VERSION},
                          f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存源失败: {e}")

    def add(self, source):
        source['id'] = str(int(time.time() * 1000))
        source['created'] = datetime.now().isoformat()
        self.sources.append(source)
        self.save()

    def update(self, source_id, updated_source):
        for i, s in enumerate(self.sources):
            if s.get('id') == source_id:
                updated_source['id'] = source_id
                updated_source['created'] = s.get('created', datetime.now().isoformat())
                self.sources[i] = updated_source
                self.save()
                return True
        return False

    def delete(self, source_id):
        self.sources = [s for s in self.sources if s.get('id') != source_id]
        self.save()

    def get(self, source_id):
        for s in self.sources:
            if s.get('id') == source_id:
                return s
        return None

    def get_all(self):
        return self.sources

    def backup(self, dst_dir=None):
        """复制 sources.json 到 Download 目录，返回目标路径或 None。"""
        if dst_dir is None:
            if platform == 'android':
                dst_dir = '/sdcard/Download'
            else:
                dst_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backup')
        try:
            os.makedirs(dst_dir, exist_ok=True)
            date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            dst = os.path.join(dst_dir, f'netstreamplayer_backup_{date_str}.json')
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = f.read()
            with open(dst, 'w', encoding='utf-8') as f:
                f.write(data)
            return dst
        except Exception as e:
            print(f'备份失败: {e}')
            return None

    def restore_from(self, src_path):
        """从外部 JSON 文件导入配置，返回 (True, 'ok') 或 (False, '原因')。

        兼容两种备份格式：
          1) {"sources": [...], "version": "..."}  （程序原生备份）
          2) [...]                                  （裸数组，部分导出方式）
        并自动补齐每条源缺失的 name/url/id/created 默认值，避免导入后显示或操作异常。
        """
        try:
            with open(src_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            return False, f'文件不存在: {src_path}'
        except json.JSONDecodeError as e:
            return False, f'JSON 解析失败: {e}'
        except Exception as e:
            return False, f'读取失败: {e}'

        # 兼容裸数组格式
        if isinstance(data, dict):
            new_sources = data.get('sources')
        elif isinstance(data, list):
            new_sources = data
        else:
            return False, '顶层不是 JSON 对象或数组'

        if not isinstance(new_sources, list):
            return False, 'sources 不是列表'
        if not new_sources:
            return False, 'sources 列表为空'

        # 补齐每条源的必要字段，防止导入后编辑/播放出错
        normalized = []
        for s in new_sources:
            if not isinstance(s, dict):
                continue
            src = {
                'name': (s.get('name') or '').strip() or '未命名',
                'url': (s.get('url') or '').strip(),
                'username': s.get('username') or '',
                'password': s.get('password') or '',
            }
            # 缺少 id 或 created 时补生成（保留原有的）
            src['id'] = s.get('id') or str(int(time.time() * 1000) + len(normalized))
            src['created'] = s.get('created') or datetime.now().isoformat()
            normalized.append(src)

        if not normalized:
            return False, '没有可用的视频源条目'

        self.sources = normalized
        try:
            self.save()
        except Exception as e:
            return False, f'保存失败: {e}'
        return True, f'导入 {len(normalized)} 个视频源'

    def _validate_source_entry(self, source):
        """为单条源补齐缺失字段（add/update 前兜底）。"""
        for key in ('name', 'url', 'username', 'password'):
            if key not in source:
                source[key] = ''
        return source


# ═══════════════════════════════════════════════════════════════════════════════
# 截图 / 录像管理器
# ═══════════════════════════════════════════════════════════════════════════════

class CaptureManager:
    """管理视频帧的截图和录像（支持纯 Python MP4 编码）。"""

    def __init__(self, save_dir=None):
        self.save_dir = save_dir or DEFAULT_SAVE_DIR
        self._recording = False
        self._recording_frames = []  # 存储 JPEG 字节
        self._recording_start_time = None
        self._last_recording_info = None  # 最近一次录像结果
        os.makedirs(self.save_dir, exist_ok=True)

    def take_screenshot(self, jpeg_data):
        if not jpeg_data:
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"screenshot_{timestamp}.jpg"
        filepath = os.path.join(self.save_dir, filename)
        try:
            with open(filepath, 'wb') as f:
                f.write(jpeg_data)
            return filepath
        except Exception as e:
            print(f"截图错误: {e}")
            return None

    def start_recording(self):
        if self._recording:
            return False
        self._recording = True
        self._recording_frames = []
        self._recording_start_time = time.time()
        return True

    def stop_recording(self):
        if not self._recording:
            return None
        self._recording = False
        frame_count = len(self._recording_frames)
        duration = time.time() - self._recording_start_time
        # 如果时间太短（测试场景），根据帧数估算时长
        if duration < 0.1 and frame_count > 0:
            duration = frame_count / 15.0  # 假设 15fps

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mp4_path = None

        # 尝试编码为 MP4（ffmpeg 或 Android MediaCodec）
        if frame_count > 5:
            try:
                mp4_path = self._encode_mp4(timestamp)
            except Exception as e:
                print(f"MP4 编码失败: {e}")
                mp4_path = None

        # 如果 MP4 编码失败，则记录错误信息，但不再回退到 JPG 帧文件
        if not mp4_path:
            # 如果帧数太少（≤5 帧），也尝试编码（可能产生短文件）
            if frame_count <= 5 and frame_count > 0:
                try:
                    mp4_path = self._encode_mp4(timestamp)
                except Exception as e:
                    print(f"MP4 编码失败: {e}")
                    mp4_path = None
            if not mp4_path:
                print("错误: 录像编码失败，无法输出 MP4 文件")

        info = {
            'path': mp4_path,
            'frames': frame_count,
            'duration': duration,
            'fps': frame_count / duration if duration > 0 else 0,
        }
        self._recording_frames = []  # 清空帧缓存
        return info

    def _encode_mp4(self, timestamp):
        """将 JPEG 帧编码为 MP4 视频文件。
        优先用 ffmpeg 命令行输出 H.264（Android 原生可播放）；
        不可用时回退到纯 Python MJPEG 封装。"""
        try:
            mp4_path = self._encode_mp4_h264_ffmpeg_cli(timestamp)
            if mp4_path:
                return mp4_path
        except Exception as e:
            print(f"H.264 编码失败，尝试 MJPEG: {e}")
        return self._encode_mp4_pure_python(timestamp)

    def _find_ffmpeg(self):
        """在 Android 上定位 p4a 打包的 ffmpeg 二进制。"""
        import shutil
        # 桌面端 / 普通环境
        p = shutil.which('ffmpeg')
        if p:
            return p
        # Android: p4a ffmpeg recipe 把 ffmpeg 二进制装到 dist/lib/python/ 下
        # 同时常见路径也搜一下
        if platform == 'android':
            from kivy.utils import platform as _p
            candidates = []
            try:
                from kivy.core.window import Window
            except Exception:
                pass
            # dist 私有的 ffmpeg: 通过 python 模块目录向上找
            import __main__
            root = getattr(__main__, '__file__', None)
            if root:
                for _ in range(8):
                    base = os.path.dirname(root)
                    for sub in ('bin', 'lib', ''):
                        try:
                            from os import listdir
                        except Exception:
                            listdir = os.listdir
                        if base:
                            for d in listdir(base):
                                c = os.path.join(base, d, sub, 'ffmpeg')
                                if os.path.isfile(c):
                                    candidates.append(c)
                    if base and os.path.isdir(os.path.join(base, '..')):
                        root = os.path.join(base, '..')
                    else:
                        break
            for c in candidates:
                if os.path.isfile(c):
                    return c
        return None

    def _encode_mp4_h264_ffmpeg_cli(self, timestamp):
        """用 ffmpeg 命令行将 JPEG 帧解码并编码为 H.264 MP4。"""
        import subprocess
        frames = self._recording_frames
        if not frames or len(frames) < 3:
            return None
        w, h = self._get_jpeg_size(frames[0])
        elapsed = time.time() - self._recording_start_time
        if elapsed < 0.1:
            elapsed = len(frames) / 15.0
        fps = max(5, min(30, len(frames) / max(1, elapsed)))
        outpath = os.path.join(self.save_dir, f"recording_{timestamp}.mp4")
        # 临时目录放 JPEG 帧
        tmpdir = os.path.join(self.save_dir, '.rec_tmp')
        os.makedirs(tmpdir, exist_ok=True)
        try:
            for i, jpeg in enumerate(frames):
                with open(os.path.join(tmpdir, f'frame_{i:05d}.jpg'), 'wb') as f:
                    f.write(jpeg)
            ff = self._find_ffmpeg()
            if not ff:
                raise RuntimeError("ffmpeg 不可用")
            pattern = os.path.join(tmpdir, 'frame_%05d.jpg')
            cmd = [
                ff, '-y', '-framerate', str(int(fps)),
                '-i', pattern,
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                '-preset', 'ultrafast', '-crf', '23',
                '-movflags', '+faststart',
                '-threads', '2',
                outpath,
            ]
            subprocess.run(cmd, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=300)
            if os.path.isfile(outpath) and os.path.getsize(outpath) > 1000:
                return outpath
            return None
        finally:
            # 清理临时帧文件
            try:
                import shutil as _shutil
                _shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    def _get_jpeg_size(self, jpeg_data):
        """从 JPEG 二进制数据中解析宽高，无需 PIL 等外部库。"""
        import struct
        data = jpeg_data
        pos = 0
        while pos < len(data) - 1:
            if data[pos] != 0xFF:
                break
            marker = data[pos + 1]
            if marker == 0xC0 or marker == 0xC1 or marker == 0xC2:
                # SOF0/SOF1/SOF2: 包含图像尺寸
                h = struct.unpack('>H', data[pos + 5:pos + 7])[0]
                w = struct.unpack('>H', data[pos + 7:pos + 9])[0]
                return w, h
            if marker == 0xD9 or marker == 0xDA:
                break  # EOI / SOS
            if marker == 0xD0 or marker == 0xD1 or marker == 0xD2 or \
               marker == 0xD3 or marker == 0xD4 or marker == 0xD5 or \
               marker == 0xD6 or marker == 0xD7 or marker == 0xD8:
                pos += 2  # RST/标记无长度
                continue
            if len(data) < pos + 4:
                break
            seg_len = struct.unpack('>H', data[pos + 2:pos + 4])[0]
            pos += 2 + seg_len
        return 640, 480  # 保底值

    def _encode_mp4_pure_python(self, timestamp):
        """
        纯 Python MJPEG → MP4 封装器。
        直接将 JPEG 帧写入 MP4 容器（MJPEG 格式），无需 ffmpeg。
        使用 ISO 14496-12 / ISO 14496-14 标准。
        """
        import struct
        from io import BytesIO

        frames = self._recording_frames
        if not frames or len(frames) < 3:
            return None

        w, h = self._get_jpeg_size(frames[0])

        # 计算 FPS 和时间戳
        elapsed = time.time() - self._recording_start_time
        if elapsed < 0.1:
            elapsed = len(frames) / 15.0  # 估算
        fps = max(5, min(30, len(frames) / max(1, elapsed)))
        # 时间尺度 = fps * 100，每个帧的持续时间为 100 个时间单位
        timescale = int(fps * 100)
        frame_duration = timescale // int(fps)

        outpath = os.path.join(self.save_dir, f"recording_{timestamp}.mp4")

        def make_box(box_type, data):
            """创建 ISOBMFF 盒子。"""
            size = 8 + len(data)
            return struct.pack('>I', size) + box_type.encode('ascii') + data

        def make_full_box(box_type, data, version=0, flags=0):
            """创建 FullBox（带版本和标志位）。"""
            inner = struct.pack('>I', (version << 24) | flags) + data
            size = 8 + len(inner)
            return struct.pack('>I', size) + box_type.encode('ascii') + inner

        # ── ftyp ──
        ftyp_data = struct.pack('>I', 0x6D703432)  # major brand 'mp42'
        ftyp_data += struct.pack('>I', 0)           # minor version
        ftyp_data += b'mp42mp41'                    # compatible brands
        ftyp_box = make_box('ftyp', ftyp_data)

        # ── mvhd ──
        mvhd_data = struct.pack('>I', int(time.time() - 3600 * 24 * 365 * 30))
        mvhd_data += struct.pack('>I', int(time.time()))
        mvhd_data += struct.pack('>I', timescale)
        mvhd_data += struct.pack('>I', int(len(frames) * frame_duration))
        mvhd_data += struct.pack('>I', 0x00010000)  # rate 1.0 (16.16 fixed)
        mvhd_data += struct.pack('>H', 0x0100)      # volume 1.0
        mvhd_data += struct.pack('>H', 0)           # reserved
        mvhd_data += struct.pack('>I', 0) * 2       # reserved
        mvhd_data += struct.pack('>I', 0x00010000) * 9  # matrix (identity)
        mvhd_data += struct.pack('>I', 0) * 6       # pre-defined
        mvhd_data += struct.pack('>I', 2)           # next track id
        mvhd_box = make_full_box('mvhd', mvhd_data)

        # ── tkhd ──
        tkhd_data = struct.pack('>I', int(time.time() - 3600 * 24 * 365 * 30))
        tkhd_data += struct.pack('>I', int(time.time()))
        tkhd_data += struct.pack('>I', 1)           # track id
        tkhd_data += struct.pack('>I', 0)           # reserved
        tkhd_data += struct.pack('>I', int(len(frames) * frame_duration))
        tkhd_data += struct.pack('>I', 0) * 2       # reserved
        tkhd_data += struct.pack('>H', 0)           # layer
        tkhd_data += struct.pack('>H', 0)           # alternate group
        tkhd_data += struct.pack('>H', 0x0100)      # volume 1.0
        tkhd_data += struct.pack('>H', 0)           # reserved
        tkhd_data += struct.pack('>I', 0x00010000) * 9  # matrix
        tkhd_data += struct.pack('>I', w << 16)     # width 16.16
        tkhd_data += struct.pack('>I', h << 16)     # height 16.16
        tkhd_box = make_full_box('tkhd', tkhd_data, flags=0x0003)

        # ── mdhd ──
        mdhd_data = struct.pack('>I', int(time.time() - 3600 * 24 * 365 * 30))
        mdhd_data += struct.pack('>I', int(time.time()))
        mdhd_data += struct.pack('>I', timescale)
        mdhd_data += struct.pack('>I', int(len(frames) * frame_duration))
        mdhd_data += struct.pack('>H', 0x55C4)      # language: und
        mdhd_data += struct.pack('>H', 0)           # quality
        mdhd_box = make_full_box('mdhd', mdhd_data)

        # ── hdlr ──
        hdlr_data = struct.pack('>I', 0)            # pre-defined
        hdlr_data += b'vide'                        # handler type
        hdlr_data += struct.pack('>I', 0) * 3       # reserved
        hdlr_data += b'VideoHandler\x00'            # name (null-terminated)
        hdlr_box = make_full_box('hdlr', hdlr_data)

        # ── vmhd ──
        vmhd_data = struct.pack('>H', 0)            # graphics mode
        vmhd_data += struct.pack('>H', 0) * 3       # opcolor
        vmhd_box = make_full_box('vmhd', vmhd_data, flags=0x0001)

        # ── dref → url ──
        url_data = struct.pack('>I', 0x0001)        # version=0, flags=self-contained
        url_box = make_full_box('url ', url_data)
        dref_data = struct.pack('>I', 1)            # entry count
        dref_data += url_box
        dref_box = make_full_box('dref', dref_data)
        dinf_box = make_box('dinf', dref_box)

        # ── stsd (mjpeg) ──
        # VisualSampleEntry for MJPEG (ISO 14496-12 full box)
        stsd_entry = struct.pack('>I', 0)             # version/flags
        stsd_entry += struct.pack('>H', 0) * 3        # reserved (6 bytes)
        stsd_entry += struct.pack('>H', 1)            # data reference index
        stsd_entry += struct.pack('>H', w)            # width
        stsd_entry += struct.pack('>H', h)            # height
        stsd_entry += struct.pack('>I', 0x00480000)   # h_res 72 dpi 16.16
        stsd_entry += struct.pack('>I', 0x00480000)   # v_res 72 dpi 16.16
        stsd_entry += struct.pack('>I', 0)            # reserved
        stsd_entry += struct.pack('>H', 1)            # frame count
        stsd_entry += struct.pack('>B', 0)            # compressor name length
        stsd_entry += b'\x00' * 31                    # compressor name
        stsd_entry += struct.pack('>H', 0x0018)       # depth 24
        stsd_entry += struct.pack('>H', 0xFFFF)       # pre-defined
        stsd_entry_box = struct.pack('>I', 8 + len(stsd_entry)) + b'mjpe' + stsd_entry
        stsd_data = struct.pack('>I', 1) + stsd_entry_box  # entry_count = 1
        stsd_box = make_full_box('stsd', stsd_data)

        # ── stts ──
        stts_data = struct.pack('>I', 1)            # entry count
        stts_data += struct.pack('>I', len(frames)) # sample count
        stts_data += struct.pack('>I', frame_duration)  # sample duration
        stts_box = make_full_box('stts', stts_data)

        # ── stsc ──
        stsc_data = struct.pack('>I', 1)            # entry count
        stsc_data += struct.pack('>I', 1)           # first chunk
        stsc_data += struct.pack('>I', len(frames)) # samples per chunk
        stsc_data += struct.pack('>I', 1)           # sample description index
        stsc_box = make_full_box('stsc', stsc_data)

        # ── stsz ──
        frame_sizes = [len(f) for f in frames]
        total_mdat_size = sum(frame_sizes)
        stsz_data = struct.pack('>I', 0)            # sample size (0 = variable)
        stsz_data += struct.pack('>I', len(frames)) # sample count
        for sz in frame_sizes:
            stsz_data += struct.pack('>I', sz)
        stsz_box = make_full_box('stsz', stsz_data)

        # ── stco ──
        # 先创建一个占位 stco 计算其大小，用于准确计算 moov 总尺寸
        stco_placeholder = struct.pack('>I', 1) + struct.pack('>I', 0)
        stco_box_placeholder = make_full_box('stco', stco_placeholder)
        # 用占位 stco 算出最终 moov 大小
        stbl_inner = (stsd_box + stts_box + stsc_box + stsz_box + stco_box_placeholder)
        stbl_box = make_box('stbl', stbl_inner)
        minf_inner = vmhd_box + dinf_box + stbl_box
        minf_box = make_box('minf', minf_inner)
        mdia_inner = mdhd_box + hdlr_box + minf_box
        mdia_box = make_box('mdia', mdia_inner)
        trak_inner = tkhd_box + mdia_box
        trak_box = make_box('trak', trak_inner)
        moov_inner = mvhd_box + trak_box
        moov_box = make_box('moov', moov_inner)

        # mdat 数据偏移 = ftyp + moov 总大小 + 8 (mdat 头)
        mdat_offset = len(ftyp_box) + len(moov_box) + 8

        # 用正确的偏移创建 stco box
        stco_data = struct.pack('>I', 1)            # entry count
        stco_data += struct.pack('>I', mdat_offset) # chunk offset
        stco_box = make_full_box('stco', stco_data)

        # 用正确的 stco 组装最终 moov
        stbl_inner = stsd_box + stts_box + stsc_box + stsz_box + stco_box
        stbl_box = make_box('stbl', stbl_inner)
        minf_inner = vmhd_box + dinf_box + stbl_box
        minf_box = make_box('minf', minf_inner)
        mdia_inner = mdhd_box + hdlr_box + minf_box
        mdia_box = make_box('mdia', mdia_inner)
        trak_inner = tkhd_box + mdia_box
        trak_box = make_box('trak', trak_inner)
        moov_inner = mvhd_box + trak_box
        moov_box = make_box('moov', moov_inner)

        # ── 写入文件 ──
        try:
            with open(outpath, 'wb') as f:
                f.write(ftyp_box)
                f.write(moov_box)
                # mdat box
                mdat_header = struct.pack('>I', 8 + total_mdat_size) + b'mdat'
                f.write(mdat_header)
                for frame_data in frames:
                    f.write(frame_data)

            if os.path.isfile(outpath) and os.path.getsize(outpath) > 100:
                return outpath
        except Exception as e:
            print(f"纯 Python MP4 编码失败: {e}")
            try:
                os.remove(outpath)
            except Exception:
                pass
        return None

    MAX_RECORDING_DURATION = 600  # 最长录像时间：10分钟

    def record_frame(self, jpeg_data):
        if not self._recording or not jpeg_data:
            return None
        # 检查是否超时，超时自动停止
        elapsed = time.time() - self._recording_start_time
        if elapsed >= self.MAX_RECORDING_DURATION:
            info = self.stop_recording()
            self._last_recording_info = info  # 保存供上层获取
            return 'TIMEOUT_STOPPED'
        self._recording_frames.append(jpeg_data)
        return 'RECORDING'

    @property
    def is_recording(self):
        return self._recording

    def set_save_dir(self, new_dir):
        self.save_dir = new_dir
        os.makedirs(self.save_dir, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MJPEG 显示控件
# ═══════════════════════════════════════════════════════════════════════════════

class MjpegDisplay(Image):
    """显示 MJPEG 视频帧的控件。"""

    reader = ObjectProperty(None, allownone=True)
    source_url = StringProperty('')
    source_username = StringProperty('')
    source_password = StringProperty('')
    is_connected = BooleanProperty(False)
    frame_rate = NumericProperty(0)
    error_message = StringProperty('')
    recording_timeout = BooleanProperty(False)

    __events__ = ('on_recording_finished',)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            self.fit_mode = 'contain'
        except AttributeError:
            self.keep_ratio = True
            self.allow_stretch = True
        self._capture_manager = CaptureManager()
        self._frame_times = []
        self._fps_update_clock = None

    def connect(self, url, username='', password=''):
        self.disconnect()
        self.source_url = url
        self.source_username = username
        self.source_password = password
        self.error_message = ''
        self.is_connected = False

        self.reader = MjpegReader(
            url, username, password,
            on_frame=self._on_frame,
            on_error=self._on_error
        )
        self.reader.start()
        self._fps_update_clock = Clock.schedule_interval(self._update_fps, 1.0)

    def disconnect(self):
        if self.reader:
            self.reader.stop()
            self.reader = None
        if self._fps_update_clock:
            self._fps_update_clock.cancel()
            self._fps_update_clock = None
        self.is_connected = False
        self.frame_rate = 0
        self._frame_times = []

    def _on_frame(self, jpeg_data):
        try:
            now = time.time()
            self._frame_times.append(now)
            while len(self._frame_times) > 30:
                self._frame_times.pop(0)

            data = io.BytesIO(jpeg_data)
            core_img = CoreImage(data, ext='jpeg')
            self.texture = core_img.texture

            if not self.is_connected:
                self.is_connected = True
                self.error_message = ''

            if self._capture_manager and self._capture_manager.is_recording:
                result = self._capture_manager.record_frame(jpeg_data)
                if result == 'TIMEOUT_STOPPED':
                    self.recording_timeout = True
                    # 超时自动停止 → 通知上层更新 UI 并弹窗
                    info = self._capture_manager._last_recording_info
                    Clock.schedule_once(
                        lambda dt, i=info: self.dispatch('on_recording_finished', i))

        except Exception:
            pass

    def on_recording_finished(self, info):
        """超时自动停止后被子类或绑定函数调用。"""
        pass

    def _on_error(self, error_msg):
        self.error_message = error_msg
        self.is_connected = False

    def _update_fps(self, dt):
        now = time.time()
        cutoff = now - 3.0
        recent = [t for t in self._frame_times if t > cutoff]
        if recent:
            fps = len(recent) / 3.0
            self.frame_rate = round(fps, 1)
        else:
            self.frame_rate = 0

    def take_screenshot(self):
        if self.reader:
            frame = self.reader.get_latest_frame()
            return self._capture_manager.take_screenshot(frame)
        return None

    def start_recording(self):
        self.recording_timeout = False
        return self._capture_manager.start_recording()

    def stop_recording(self):
        return self._capture_manager.stop_recording()

    @property
    def is_recording(self):
        return self._capture_manager.is_recording

    def set_save_dir(self, path):
        self._capture_manager.set_save_dir(path)

    def get_save_dir(self):
        return self._capture_manager.save_dir


# ═══════════════════════════════════════════════════════════════════════════════
# 可缩放图像控件（基于 Scatter，流畅平滑）
# ═══════════════════════════════════════════════════════════════════════════════

class ZoomableImage(RelativeLayout):
    """
    可缩放、平移的图像查看器。
    使用 Kivy Scatter 实现流畅的捏合缩放和拖拽平移。
    """

    _min_scale = 0.5
    _max_scale = 8.0

    def __init__(self, mjpeg_display, **kwargs):
        super().__init__(**kwargs)
        self.mjpeg_display = mjpeg_display

        # 使用 Scatter 实现原生手势支持
        self.scatter = Scatter(
            do_rotation=False,
            do_scale=True,
            do_translation=True,
            scale_min=self._min_scale,
            scale_max=self._max_scale,
            auto_bring_to_front=False,
        )
        # 将视频显示控件放入 Scatter
        self.scatter.add_widget(mjpeg_display)
        self.add_widget(self.scatter)

        # 绑定 Scatter 变化以更新控件大小
        mjpeg_display.bind(texture=self._on_texture)
        self._smooth_anim = None

    def _on_texture(self, instance, texture):
        """当视频帧到达时，调整 Scatter 和显示控件的尺寸。"""
        if texture:
            self.mjpeg_display.size = texture.size
            self.scatter.size = texture.size
            # 居中显示
            self.scatter.center = self.center

    def on_size(self, *args):
        """父容器大小变化时保持居中。"""
        if hasattr(self, 'scatter'):
            self.scatter.center = self.center

    def reset_transform(self, animated=True):
        """平滑复位缩放和平移。"""
        if animated:
            anim = Animation(
                scale=1.0, x=0, y=0,
                duration=0.25,
                t='out_quad'
            )
            anim.start(self.scatter)
        else:
            self.scatter.scale = 1.0
            self.scatter.pos = (0, 0)
        self.scatter.center = self.center


# ═══════════════════════════════════════════════════════════════════════════════
# 界面 — 视频源列表
# ═══════════════════════════════════════════════════════════════════════════════

class SourceListScreen(Screen):
    """主屏幕，显示视频源列表。"""

    def on_enter(self):
        self.refresh_list()

    def refresh_list(self):
        app = App.get_running_app()
        if app is None:
            return
        sources = app.source_manager.get_all()
        list_view = self.ids.source_list if hasattr(self, 'ids') and 'source_list' in self.ids else None
        if list_view:
            list_view.clear_widgets()
            if not sources:
                list_view.add_widget(Label(
                    text=_('source_list_empty'),
                    color=(0.5, 0.5, 0.5, 1),
                    size_hint_y=None, height=dp(60)
                ))
            for src in sources:
                item = SourceListItem(src=src)
                item.bind(on_play=lambda btn, s=src: self.play_source(s))
                item.bind(on_edit=lambda btn, s=src: self.edit_source(s))
                item.bind(on_delete=lambda btn, s=src: self.delete_source(s))
                list_view.add_widget(item)

    def play_source(self, source):
        app = App.get_running_app()
        player_screen = self.manager.get_screen('player')
        player_screen.connect_to(source)
        self.manager.current = 'player'

    def edit_source(self, source):
        edit_screen = self.manager.get_screen('edit_source')
        edit_screen.load_source(source)
        self.manager.current = 'edit_source'

    def delete_source(self, source):
        app = App.get_running_app()
        app.source_manager.delete(source['id'])
        self.refresh_list()

    def add_new_source(self):
        self.manager.current = 'edit_source'

    def backup_config(self):
        """备份 sources.json 到 Download 目录。"""
        app = App.get_running_app()
        dst = app.source_manager.backup()
        if dst:
            Popup(title=_('backup_ok'),
                  content=Label(text=f'已保存:\n{dst}', font_size=dp(14)),
                  size_hint=(0.7, 0.3)).open()
        else:
            Popup(title=_('backup_fail'),
                  content=Label(text='无法写入文件，请检查权限', font_size=dp(14)),
                  size_hint=(0.7, 0.3)).open()

    def restore_config(self):
        """弹出文件选择器，导入外部 sources.json。"""
        fc = FileChooserListView(
            filters=['*.json'],
            path='/sdcard/Download' if platform == 'android' else os.getcwd(),
            dirselect=False,
            multiselect=False,
        )
        box = BoxLayout(orientation='vertical', spacing=dp(5))
        box.add_widget(fc)

        def _pick(*args):
            sel = fc.selection
            if not sel:
                return
            app = App.get_running_app()
            ok, msg = app.source_manager.restore_from(sel[0])
            if ok:
                self.refresh_list()
                Popup(title=_('restore_ok'),
                      content=Label(text=f'{msg}\n{sel[0]}', font_size=dp(14)),
                      size_hint=(0.7, 0.3)).open()
            else:
                Popup(title=_('restore_fail'),
                      content=Label(text=msg, font_size=dp(14)),
                      size_hint=(0.7, 0.3)).open()

        btn_ok = Button(text=_('restore_config'), size_hint_y=None, height=dp(40))
        btn_ok.bind(on_release=_pick)
        box.add_widget(btn_ok)

        Popup(title=_('restore_config'), content=box,
              size_hint=(0.9, 0.8)).open()


class SourceListItem(BoxLayout):
    """视频源列表中的单个条目。"""
    src = ObjectProperty(None)

    __events__ = ('on_play', 'on_edit', 'on_delete')

    def __init__(self, src=None, **kwargs):
        super().__init__(**kwargs)
        self.src = src
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = dp(60)
        self.spacing = dp(5)
        self.padding = dp(5)

        info = BoxLayout(orientation='vertical', size_hint_x=0.55)
        name = self.src.get('name', _('unnamed'))
        url = self.src.get('url', '')
        info.add_widget(Label(
            text=name, halign='left', valign='middle',
            text_size=(dp(200), None), bold=True, size_hint_y=0.6
        ))
        info.add_widget(Label(
            text=url[:50] + ('...' if len(url) > 50 else ''),
            halign='left', valign='middle',
            text_size=(dp(200), None), font_size=dp(10), size_hint_y=0.4
        ))

        btn_play = Button(text=_('play'), size_hint_x=0.15, background_color=(0, 0.7, 0, 1))
        btn_play.bind(on_release=lambda btn: self.dispatch('on_play'))

        btn_edit = Button(text=_('edit'), size_hint_x=0.15, background_color=(0.2, 0.4, 0.8, 1))
        btn_edit.bind(on_release=lambda btn: self.dispatch('on_edit'))

        btn_delete = Button(text=_('delete'), size_hint_x=0.15, background_color=(0.8, 0.2, 0.2, 1))
        btn_delete.bind(on_release=lambda btn: self.dispatch('on_delete'))

        self.add_widget(info)
        self.add_widget(btn_play)
        self.add_widget(btn_edit)
        self.add_widget(btn_delete)

    def on_play(self): pass
    def on_edit(self): pass
    def on_delete(self): pass


# ═══════════════════════════════════════════════════════════════════════════════
# 界面 — 编辑视频源
# ═══════════════════════════════════════════════════════════════════════════════

class EditSourceScreen(Screen):
    """添加或编辑视频源的界面。"""

    _editing_id = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._editing_id = None

    def load_source(self, source):
        self._editing_id = source.get('id')
        self.ids.source_name.text = source.get('name', '')
        self.ids.source_url.text = source.get('url', '')
        self.ids.source_username.text = source.get('username', '')
        self.ids.source_password.text = source.get('password', '')
        self.ids.save_btn.text = _('update_source')

    def clear_form(self):
        self._editing_id = None
        self.ids.source_name.text = ''
        self.ids.source_url.text = ''
        self.ids.source_username.text = ''
        self.ids.source_password.text = ''
        self.ids.save_btn.text = _('save_source')

    def on_enter(self):
        if not self._editing_id:
            self.clear_form()

    def save_source(self):
        name = self.ids.source_name.text.strip()
        url = self.ids.source_url.text.strip()
        username = self.ids.source_username.text.strip()
        password = self.ids.source_password.text.strip()

        if not name:
            self.show_error(_('please_enter_name'))
            return
        if not url:
            self.show_error(_('please_enter_url'))
            return

        app = App.get_running_app()
        source_data = {
            'name': name,
            'url': url,
            'username': username,
            'password': password,
        }

        if self._editing_id:
            app.source_manager.update(self._editing_id, source_data)
        else:
            app.source_manager.add(source_data)

        self.manager.current = 'main'

    def cancel(self):
        self.manager.current = 'main'

    def show_error(self, msg):
        popup = Popup(title=_('error'),
                       content=Label(text=msg),
                       size_hint=(0.8, 0.3))
        popup.open()


# ═══════════════════════════════════════════════════════════════════════════════
# 界面 — 视频播放器
# ═══════════════════════════════════════════════════════════════════════════════

class PlayerScreen(Screen):
    """视频播放界面，含控制栏。"""

    mjpeg_display = ObjectProperty(None)
    _is_fullscreen = False
    _orientation = 'auto'
    _recording = False
    _control_bar_visible = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_source = None
        self._mjpeg_display = None
        self._pending_timeout_info = None
        self._event_bound = False

    def on_enter(self):
        if self._current_source:
            self._start_stream()
            # 绑定超时自动停止事件（只绑一次）
            if not self._event_bound:
                mjpeg = self.get_mjpeg_display()
                mjpeg.bind(on_recording_finished=self._on_recording_finished)
                self._event_bound = True

    def _on_recording_finished(self, instance, info):
        """超时自动停止时：复位按钮、弹窗显示结果。"""
        self._recording = False
        self._pending_timeout_info = info
        self.ids.record_btn.text = _('record')
        self.ids.record_btn.background_color = (0.8, 0.2, 0.2, 0.7)
        self._show_recording_result(info, _('recording_timeout'))

    def on_leave(self):
        self._stop_stream()
        self._mjpeg_display = None

    def connect_to(self, source):
        self._current_source = source

    def _start_stream(self):
        if not self._current_source:
            return

        src = self._current_source
        url = src.get('url', '')
        username = src.get('username', '')
        password = src.get('password', '')

        mjpeg = self.get_mjpeg_display()
        mjpeg.connect(url, username, password)

    def _stop_stream(self):
        mjpeg = self.get_mjpeg_display()
        mjpeg.disconnect()

    def get_mjpeg_display(self):
        """Get or create the MJPEG display widget (cached)."""
        if self._mjpeg_display is not None:
            return self._mjpeg_display
        zoom_container = self.ids.zoom_container
        for child in zoom_container.children:
            if isinstance(child, MjpegDisplay):
                self._mjpeg_display = child
                return child
            if isinstance(child, ZoomableImage):
                self._mjpeg_display = child.mjpeg_display
                return child.mjpeg_display
        mjpeg = MjpegDisplay()
        zoom = ZoomableImage(mjpeg)
        zoom_container.clear_widgets()
        zoom_container.add_widget(zoom)
        self._mjpeg_display = mjpeg
        return mjpeg

    def toggle_fullscreen(self):
        self._is_fullscreen = not self._is_fullscreen
        if self._is_fullscreen:
            Window.fullscreen = 'auto'
            self.ids.fullscreen_btn.text = _('exit_fullscreen')
            self.ids.player_controls.opacity = 0.4
        else:
            Window.fullscreen = False
            self.ids.fullscreen_btn.text = _('fullscreen')
            self.ids.player_controls.opacity = 1.0

    def toggle_orientation(self):
        orientations = ['auto', 'landscape', 'portrait']
        current_idx = orientations.index(self._orientation) if self._orientation in orientations else 0
        self._orientation = orientations[(current_idx + 1) % len(orientations)]

        labels = {
            'auto': _('orientation_auto'),
            'landscape': _('orientation_landscape'),
            'portrait': _('orientation_portrait'),
        }
        self.ids.orientation_btn.text = labels.get(self._orientation, _('orientation_auto'))

        # 在 Android 上通过系统请求横竖屏
        if platform == 'android':
            try:
                import jnius
                PythonActivity = jnius.autoclass('org.kivy.android.PythonActivity')
                activity = PythonActivity.mActivity
                if self._orientation == 'landscape':
                    activity.setRequestedOrientation(0)
                elif self._orientation == 'portrait':
                    activity.setRequestedOrientation(1)
                else:
                    activity.setRequestedOrientation(4)
            except Exception:
                pass

    def take_screenshot(self):
        mjpeg = self.get_mjpeg_display()
        filepath = mjpeg.take_screenshot()
        if filepath:
            popup = Popup(
                title=_('screenshot_saved'),
                content=Label(text=f"{_('saved_to')}\n{filepath}"),
                size_hint=(0.8, 0.3)
            )
            popup.open()
        else:
            popup = Popup(
                title=_('error'),
                content=Label(text=_('no_frame')),
                size_hint=(0.8, 0.2)
            )
            popup.open()

    def toggle_recording(self):
        mjpeg = self.get_mjpeg_display()

        if not mjpeg.is_recording:
            # 如果有未展示的超时结果，直接弹窗
            if self._pending_timeout_info:
                self._show_recording_result(self._pending_timeout_info, _('recording_timeout'))
                self._pending_timeout_info = None
                return
            mjpeg.recording_timeout = False
            result = mjpeg.start_recording()
            if result:
                self._recording = True
                self.ids.record_btn.text = _('stop')
                self.ids.record_btn.background_color = (0.8, 0.1, 0.1, 1)
        else:
            info = mjpeg.stop_recording()
            self._recording = False
            self.ids.record_btn.text = _('record')
            self.ids.record_btn.background_color = (0.8, 0.2, 0.2, 0.7)

            if mjpeg.recording_timeout:
                mjpeg.recording_timeout = False
                title = _('recording_timeout')
            else:
                title = _('recording_stopped')

            if info:
                self._show_recording_result(info, title)
            else:
                popup = Popup(
                    title=_('error'),
                    content=Label(text="录像编码失败，无法输出 MP4 文件"),
                    size_hint=(0.8, 0.3)
                )
                popup.open()

    def _show_recording_result(self, info, title):
        """显示录像结果的弹窗。"""
        if info and info.get('path'):
            ext = 'MP4'
            popup = Popup(
                title=title,
                content=Label(
                    text=(
                        f"{_('frames')}: {info['frames']}\n"
                        f"{_('duration')}: {info['duration']:.1f}s\n"
                        f"{_('fps')}: {info['fps']:.1f}\n"
                        f"格式: {ext}\n"
                        f"{_('directory')}:\n{info['path']}"
                    )
                ),
                size_hint=(0.8, 0.4)
            )
            popup.open()
        else:
            popup = Popup(
                title=_('error'),
                content=Label(text="录像编码失败，无法输出 MP4 文件"),
                size_hint=(0.8, 0.3)
            )
            popup.open()

    def reset_zoom(self):
        zoom_container = self.ids.zoom_container
        for child in zoom_container.children:
            if isinstance(child, ZoomableImage):
                child.reset_transform(animated=True)
                break

    def show_settings(self):
        mjpeg = self.get_mjpeg_display()
        current_path = mjpeg.get_save_dir()

        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(text=_('save_dir'), size_hint_y=0.2))

        path_input = TextInput(
            text=current_path, multiline=False,
            size_hint_y=0.15
        )
        content.add_widget(path_input)

        btn_layout = BoxLayout(size_hint_y=0.2, spacing=10)
        btn_cancel = Button(text=_('cancel'))
        btn_save = Button(text=_('save'), background_color=(0, 0.7, 0, 1))

        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_save)
        content.add_widget(btn_layout)

        popup = Popup(title=_('settings'), content=content,
                       size_hint=(0.9, 0.4), auto_dismiss=False)

        btn_cancel.bind(on_release=popup.dismiss)
        btn_save.bind(on_release=lambda btn: self._save_settings(path_input.text, popup))

        popup.open()

    def _save_settings(self, new_path, popup):
        if new_path.strip():
            mjpeg = self.get_mjpeg_display()
            mjpeg.set_save_dir(new_path.strip())
            popup.dismiss()

    def go_back(self):
        self._stop_stream()
        self.manager.current = 'main'


# ═══════════════════════════════════════════════════════════════════════════════
# 主应用
# ═══════════════════════════════════════════════════════════════════════════════

class NetStreamPlayerApp(App):
    """Kivy 主应用。"""

    source_manager = ObjectProperty(None)

    def build(self):
        self.title = APP_NAME
        self.icon = ''
        self.source_manager = SourceManager()

        kv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'videostreamer.kv')
        Builder.load_file(kv_path)

        sm = ScreenManager(transition=SlideTransition(duration=0.3))

        main_screen = SourceListScreen(name='main')
        edit_screen = EditSourceScreen(name='edit_source')
        player_screen = PlayerScreen(name='player')

        sm.add_widget(main_screen)
        sm.add_widget(edit_screen)
        sm.add_widget(player_screen)

        if platform == 'android':
            from kivy.core.window import Window
            Window.bind(on_keyboard=self._on_keyboard)

        return sm

    def _on_keyboard(self, window, key, scancode, codepoint, modifier):
        if key == 27:  # ESC/Back
            current = self.root.current
            if current == 'player':
                self.root.get_screen('player').go_back()
            elif current == 'edit_source':
                self.root.get_screen('edit_source').cancel()
            else:
                return False
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    NetStreamPlayerApp().run()