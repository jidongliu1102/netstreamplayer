#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Network Video Stream Player for Android
- Supports Motion / MJPG-Streamer video streams
- HTTP Basic Auth support
- Pinch-to-zoom, pan gestures
- Screenshot and video recording
- Fullscreen and orientation modes
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
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, PushMatrix, PopMatrix, Scale, Translate
from kivy.properties import ObjectProperty, NumericProperty, StringProperty, BooleanProperty
from kivy.metrics import dp
from kivy.utils import platform

import requests

# ─── Constants ────────────────────────────────────────────────────────────────
APP_NAME = "NetStreamPlayer"
VERSION = "1.0.0"
SOURCES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources.json")
DEFAULT_SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")

# Ensure save directory exists
os.makedirs(DEFAULT_SAVE_DIR, exist_ok=True)

# ─── MJPEG Stream Reader ─────────────────────────────────────────────────────

class MjpegReader(threading.Thread):
    """Reads MJPEG stream in a background thread, emits frames via callback."""

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
                retry_delay = 1.0  # reset on success

                if 'multipart/x-mixed-replace' in content_type:
                    self._read_multipart(resp)
                elif 'image/jpeg' in content_type:
                    self._read_single_jpeg(resp)
                else:
                    # Try reading raw bytes as JPEG anyway
                    self._read_raw_jpeg(resp)

            except requests.exceptions.RequestException as e:
                err_msg = f"Connection error: {e}"
                if self.on_error:
                    Clock.schedule_once(lambda dt, m=err_msg: self.on_error(m))
            except Exception as e:
                err_msg = f"Stream error: {e}"
                if self.on_error:
                    Clock.schedule_once(lambda dt, m=err_msg: self.on_error(m))

            if self._running:
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)

    def _read_multipart(self, resp):
        """Parse multipart/x-mixed-replace MJPEG stream."""
        boundary = None
        content_type = resp.headers.get('Content-Type', '')
        if 'boundary=' in content_type:
            boundary = content_type.split('boundary=')[1].strip().strip('"').strip("'")
            # Ensure proper boundary format
            if isinstance(boundary, str):
                boundary = boundary.encode('utf-8')

        if not boundary:
            # Try to detect from first bytes
            boundary = b'--'

        buffer = b''
        while self._running:
            try:
                chunk = resp.raw.read(4096)
                if not chunk:
                    break
                buffer += chunk

                # Try to extract JPEG frames
                while True:
                    # Find JPEG start marker
                    start = buffer.find(b'\xff\xd8')
                    if start < 0:
                        break
                    # Find JPEG end marker
                    end = buffer.find(b'\xff\xd9', start)
                    if end < 0:
                        break
                    end += 2  # include the end marker

                    jpeg_data = buffer[start:end]
                    buffer = buffer[end:]

                    if len(jpeg_data) > 100:  # sanity check
                        self._process_frame(jpeg_data)

            except Exception as e:
                if self._running:
                    raise

    def _read_single_jpeg(self, resp):
        """Read a single JPEG response (for non-multipart streams)."""
        data = resp.content
        if data and len(data) > 100:
            self._process_frame(data)
            # Some streams continuously send JPEGs, keep reading
            while self._running:
                try:
                    more = resp.raw.read(4096)
                    if not more:
                        break
                    # Try to find JPEG boundaries in the stream
                    self._process_frame(more)
                except Exception:
                    break

    def _read_raw_jpeg(self, resp):
        """Read raw bytes, try to extract JPEG frames."""
        buffer = b''
        for chunk in resp.iter_content(chunk_size=4096):
            if not chunk or not self._running:
                break
            buffer += chunk
            while len(buffer) > 0:
                start = buffer.find(b'\xff\xd8')
                if start < 0:
                    if len(buffer) > 1048576:  # 1MB limit
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
        """Process a JPEG frame - store it and call callback."""
        with self._lock:
            self._latest_frame = jpeg_data
            self._frame_count += 1
            self._frame_ready.set()

        if self.on_frame and not self._paused:
            Clock.schedule_once(lambda dt: self.on_frame(jpeg_data))

    def get_latest_frame(self):
        """Get the most recent frame (for recording/screenshot)."""
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


# ─── Source Manager ──────────────────────────────────────────────────────────

class SourceManager:
    """Manages video source configurations stored in JSON."""

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
            print(f"Error loading sources: {e}")
            self.sources = []

    def save(self):
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump({'sources': self.sources, 'version': VERSION},
                          f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving sources: {e}")

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


# ─── Screenshot / Recording Helpers ──────────────────────────────────────────

class CaptureManager:
    """Manages screenshots and recording of video frames."""

    def __init__(self, save_dir=None):
        self.save_dir = save_dir or DEFAULT_SAVE_DIR
        self._recording = False
        self._recording_dir = None
        self._recording_frames = []
        self._recording_start_time = None
        os.makedirs(self.save_dir, exist_ok=True)

    def take_screenshot(self, jpeg_data):
        """Save a single JPEG frame as screenshot (PNG format)."""
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
            print(f"Screenshot error: {e}")
            return None

    def start_recording(self):
        """Start recording - creates a timestamped directory for frames."""
        if self._recording:
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_name = f"recording_{timestamp}"
        self._recording_dir = os.path.join(self.save_dir, dir_name)
        os.makedirs(self._recording_dir, exist_ok=True)

        self._recording = True
        self._recording_frames = []
        self._recording_start_time = time.time()
        return True

    def stop_recording(self):
        """Stop recording and return info about the recording."""
        if not self._recording:
            return None

        self._recording = False
        duration = time.time() - self._recording_start_time
        frame_count = len(self._recording_frames)

        info = {
            'directory': self._recording_dir,
            'frames': frame_count,
            'duration': duration,
            'fps': frame_count / duration if duration > 0 else 0,
        }

        self._recording_dir = None
        self._recording_frames = []
        return info

    def record_frame(self, jpeg_data):
        """Save a frame during recording. Called per-frame."""
        if not self._recording or not jpeg_data:
            return None

        timestamp = int(time.time() * 1000)
        filename = f"frame_{timestamp:016d}.jpg"
        filepath = os.path.join(self._recording_dir, filename)

        try:
            with open(filepath, 'wb') as f:
                f.write(jpeg_data)
            self._recording_frames.append(filepath)
            return filepath
        except Exception as e:
            print(f"Record frame error: {e}")
            return None

    @property
    def is_recording(self):
        return self._recording

    def set_save_dir(self, new_dir):
        self.save_dir = new_dir
        os.makedirs(self.save_dir, exist_ok=True)


# ─── MJPEG Display Widget ────────────────────────────────────────────────────

class MjpegDisplay(Image):
    """Widget that displays MJPEG frames from a stream reader."""

    reader = ObjectProperty(None, allownone=True)
    source_url = StringProperty('')
    source_username = StringProperty('')
    source_password = StringProperty('')
    is_connected = BooleanProperty(False)
    frame_rate = NumericProperty(0)
    error_message = StringProperty('')

    _capture_manager = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # For Kivy 2.3+ compatibility: keep_ratio/allow_stretch deprecated
        try:
            self.fit_mode = 'contain'
        except AttributeError:
            self.keep_ratio = True
            self.allow_stretch = True
        self._capture_manager = CaptureManager()
        self._frame_times = []
        self._fps_update_clock = None

    def connect(self, url, username='', password=''):
        """Connect to an MJPEG stream."""
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
        """Disconnect from the stream."""
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
        """Called by MjpegReader when a new frame arrives."""
        try:
            # Track framerate
            now = time.time()
            self._frame_times.append(now)
            # Keep last 30 timestamps
            while len(self._frame_times) > 30:
                self._frame_times.pop(0)

            # Convert JPEG bytes to texture
            data = io.BytesIO(jpeg_data)
            core_img = CoreImage(data, ext='jpeg')
            self.texture = core_img.texture

            if not self.is_connected:
                self.is_connected = True
                self.error_message = ''

            # Handle recording
            if self._capture_manager and self._capture_manager.is_recording:
                self._capture_manager.record_frame(jpeg_data)

        except Exception as e:
            pass

    def _on_error(self, error_msg):
        self.error_message = error_msg
        self.is_connected = False

    def _update_fps(self, dt):
        """Calculate and update frame rate display."""
        now = time.time()
        # Count frames in last 3 seconds
        cutoff = now - 3.0
        recent = [t for t in self._frame_times if t > cutoff]
        if recent:
            fps = len(recent) / 3.0
            self.frame_rate = round(fps, 1)
        else:
            self.frame_rate = 0

    def take_screenshot(self):
        """Take a screenshot of the current frame."""
        if self.reader:
            frame = self.reader.get_latest_frame()
            return self._capture_manager.take_screenshot(frame)
        return None

    def start_recording(self):
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


# ─── Zoomable Image Widget ────────────────────────────────────────────────────

class ZoomableImage(RelativeLayout):
    """A zoomable and pannable image viewer with pinch-to-zoom."""

    image = ObjectProperty(None)
    _min_scale = 0.5
    _max_scale = 8.0
    _scale = 1.0
    _touches = []
    _pinch_start_dist = 0
    _pinch_start_scale = 1.0

    def __init__(self, mjpeg_display, **kwargs):
        super().__init__(**kwargs)
        self.mjpeg_display = mjpeg_display
        self.add_widget(mjpeg_display)
        self._touches = []
        self._last_pan_pos = None

        # For zoom/pan using canvas transforms
        with self.canvas.before:
            PushMatrix()
            self._translate = Translate()
            self._scale_mat = Scale()
        with self.canvas.after:
            PopMatrix()

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        self._touches.append(touch)
        touch.grab(self)

        if len(self._touches) == 1:
            self._last_pan_pos = list(touch.pos)
        elif len(self._touches) == 2:
            t1, t2 = self._touches[0], self._touches[1]
            self._pinch_start_dist = self._calc_distance(t1.pos, t2.pos)
            self._pinch_start_scale = self._scale

        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return False

        if len(self._touches) >= 2:
            # Pinch zoom
            t1, t2 = self._touches[0], self._touches[1]
            current_dist = self._calc_distance(t1.pos, t2.pos)
            if self._pinch_start_dist > 5:
                ratio = current_dist / self._pinch_start_dist
                new_scale = max(min(self._pinch_start_scale * ratio,
                                    self._max_scale), self._min_scale)
                self._scale = new_scale
                self._apply_transform()
        else:
            # Single finger pan
            if self._last_pan_pos:
                dx = touch.x - self._last_pan_pos[0]
                dy = touch.y - self._last_pan_pos[1]
                self._translate.x += dx
                self._translate.y += dy
            self._last_pan_pos = list(touch.pos)

        return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            if touch in self._touches:
                self._touches.remove(touch)
            touch.ungrab(self)
            return True
        return False

    def _calc_distance(self, p1, p2):
        return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5

    def _apply_transform(self):
        """Apply zoom transform centered on the view center."""
        self._scale_mat.x = self._scale
        self._scale_mat.y = self._scale

    def reset_transform(self):
        """Reset zoom and pan to default."""
        self._scale = 1.0
        self._translate.x = 0
        self._translate.y = 0
        self._scale_mat.x = 1.0
        self._scale_mat.y = 1.0


# ─── Screens ──────────────────────────────────────────────────────────────────

# We'll define screens in the KV language file, with Python bindings below


class SourceListScreen(Screen):
    """Main screen showing list of video sources."""

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


class SourceListItem(BoxLayout):
    """A single item in the source list."""
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

        # Source info label
        info = BoxLayout(orientation='vertical', size_hint_x=0.55)
        name = self.src.get('name', 'Unnamed')
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

        # Buttons
        btn_play = Button(text='▶', size_hint_x=0.15, background_color=(0, 0.7, 0, 1))
        btn_play.bind(on_release=lambda btn: self.dispatch('on_play'))

        btn_edit = Button(text='✎', size_hint_x=0.15, background_color=(0.2, 0.4, 0.8, 1))
        btn_edit.bind(on_release=lambda btn: self.dispatch('on_edit'))

        btn_delete = Button(text='✕', size_hint_x=0.15, background_color=(0.8, 0.2, 0.2, 1))
        btn_delete.bind(on_release=lambda btn: self.dispatch('on_delete'))

        self.add_widget(info)
        self.add_widget(btn_play)
        self.add_widget(btn_edit)
        self.add_widget(btn_delete)

    def on_play(self):
        pass

    def on_edit(self):
        pass

    def on_delete(self):
        pass


class EditSourceScreen(Screen):
    """Screen for adding or editing a video source."""

    _editing_id = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._editing_id = None

    def load_source(self, source):
        """Load an existing source for editing."""
        self._editing_id = source.get('id')
        self.ids.source_name.text = source.get('name', '')
        self.ids.source_url.text = source.get('url', '')
        self.ids.source_username.text = source.get('username', '')
        self.ids.source_password.text = source.get('password', '')
        self.ids.save_btn.text = 'Update Source'

    def clear_form(self):
        """Clear form for new source."""
        self._editing_id = None
        self.ids.source_name.text = ''
        self.ids.source_url.text = ''
        self.ids.source_username.text = ''
        self.ids.source_password.text = ''
        self.ids.save_btn.text = 'Save Source'

    def on_enter(self):
        if not self._editing_id:
            self.clear_form()

    def save_source(self):
        name = self.ids.source_name.text.strip()
        url = self.ids.source_url.text.strip()
        username = self.ids.source_username.text.strip()
        password = self.ids.source_password.text.strip()

        if not name:
            self.show_error("Please enter a source name.")
            return
        if not url:
            self.show_error("Please enter a stream URL.")
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
        popup = Popup(title='Error',
                       content=Label(text=msg),
                       size_hint=(0.8, 0.3))
        popup.open()


class PlayerScreen(Screen):
    """Screen for video playback with controls."""

    mjpeg_display = ObjectProperty(None)
    _is_fullscreen = False
    _orientation = 'auto'
    _recording = False
    _control_bar_visible = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_source = None

    def on_enter(self):
        """When entering player screen, start the stream."""
        if self._current_source:
            self._start_stream()

    def on_leave(self):
        """When leaving player screen, stop the stream."""
        self._stop_stream()

    def connect_to(self, source):
        """Prepare to connect to a source."""
        self._current_source = source

    def _start_stream(self):
        """Actually start the MJPEG stream."""
        if not self._current_source:
            return

        src = self._current_source
        url = src.get('url', '')
        username = src.get('username', '')
        password = src.get('password', '')

        # Get or create MjpegDisplay
        mjpeg = self.get_mjpeg_display()
        mjpeg.connect(url, username, password)

        # Update info display
        self.ids.stream_info.text = src.get('name', 'Stream')

        # Update FPS periodically
        if hasattr(self, '_fps_clock') and self._fps_clock:
            self._fps_clock.cancel()
        self._fps_clock = Clock.schedule_interval(self._update_info, 0.5)

    def _stop_stream(self):
        """Stop the stream."""
        if hasattr(self, '_fps_clock') and self._fps_clock:
            self._fps_clock.cancel()
            self._fps_clock = None

        mjpeg = self.get_mjpeg_display()
        mjpeg.disconnect()

    def get_mjpeg_display(self):
        """Get or create the MJPEG display widget in the zoom container."""
        zoom_container = self.ids.zoom_container
        # Find existing MjpegDisplay
        for child in zoom_container.children:
            if isinstance(child, MjpegDisplay):
                return child
            if isinstance(child, ZoomableImage):
                return child.mjpeg_display

        # Create new ones
        mjpeg = MjpegDisplay()
        zoom = ZoomableImage(mjpeg)
        zoom_container.clear_widgets()
        zoom_container.add_widget(zoom)
        return mjpeg

    def _update_info(self, dt):
        """Update info display (FPS, connection status, recording)."""
        try:
            mjpeg = self.get_mjpeg_display()
            status = "Connected" if mjpeg.is_connected else "Connecting..."
            fps = mjpeg.frame_rate
            rec = "● REC" if mjpeg.is_recording else ""
            self.ids.stream_info.text = (
                f"{self._current_source.get('name', '')} | {status} | {fps:.1f} FPS {rec}"
            )
        except Exception:
            pass

    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode."""
        self._is_fullscreen = not self._is_fullscreen
        if self._is_fullscreen:
            Window.fullscreen = 'auto'
            self.ids.fullscreen_btn.text = '⛶ Exit'
            self.ids.player_controls.opacity = 0.3
        else:
            Window.fullscreen = False
            self.ids.fullscreen_btn.text = '⛶ Full'
            self.ids.player_controls.opacity = 1.0

    def toggle_orientation(self):
        """Toggle between portrait, landscape, and auto."""
        orientations = ['auto', 'portrait', 'landscape']
        current_idx = orientations.index(self._orientation) if self._orientation in orientations else 0
        self._orientation = orientations[(current_idx + 1) % len(orientations)]

        if self._orientation == 'portrait':
            Window.rotation = 0
        elif self._orientation == 'landscape':
            Window.rotation = 0
        # Auto = use system sensor

        self.ids.orientation_btn.text = f'◉ {self._orientation.capitalize()}'

    def take_screenshot(self):
        """Capture current frame as screenshot."""
        mjpeg = self.get_mjpeg_display()
        filepath = mjpeg.take_screenshot()
        if filepath:
            app = App.get_running_app()
            popup = Popup(
                title='Screenshot Saved',
                content=Label(text=f'Saved to:\n{filepath}'),
                size_hint=(0.8, 0.3)
            )
            popup.open()
        else:
            popup = Popup(
                title='Error',
                content=Label(text='No frame available.'),
                size_hint=(0.8, 0.2)
            )
            popup.open()

    def toggle_recording(self):
        """Start or stop video recording."""
        mjpeg = self.get_mjpeg_display()

        if not mjpeg.is_recording:
            # Start recording
            result = mjpeg.start_recording()
            if result:
                self._recording = True
                self.ids.record_btn.text = '⏹ Stop'
                self.ids.record_btn.background_color = (0.8, 0.1, 0.1, 1)
        else:
            # Stop recording
            info = mjpeg.stop_recording()
            self._recording = False
            self.ids.record_btn.text = '⏺ Rec'
            self.ids.record_btn.background_color = (0.8, 0.2, 0.2, 0.7)

            if info:
                popup = Popup(
                    title='Recording Stopped',
                    content=Label(
                        text=(f'Frames: {info["frames"]}\n'
                              f'Duration: {info["duration"]:.1f}s\n'
                              f'FPS: {info["fps"]:.1f}\n'
                              f'Directory:\n{info["directory"]}')
                    ),
                    size_hint=(0.8, 0.4)
                )
                popup.open()

    def reset_zoom(self):
        """Reset zoom and pan to default."""
        zoom_container = self.ids.zoom_container
        for child in zoom_container.children:
            if isinstance(child, ZoomableImage):
                child.reset_transform()
                break

    def show_settings(self):
        """Show settings popup for save path configuration."""
        mjpeg = self.get_mjpeg_display()
        current_path = mjpeg.get_save_dir()

        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(text='Save Directory:', size_hint_y=0.2))

        path_input = TextInput(
            text=current_path, multiline=False,
            size_hint_y=0.15
        )
        content.add_widget(path_input)

        btn_layout = BoxLayout(size_hint_y=0.2, spacing=10)
        btn_cancel = Button(text='Cancel')
        btn_save = Button(text='Save', background_color=(0, 0.7, 0, 1))

        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_save)
        content.add_widget(btn_layout)

        popup = Popup(title='Settings', content=content,
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
        """Return to source list."""
        self._stop_stream()
        self.manager.current = 'main'


# ─── Main Application ─────────────────────────────────────────────────────────

class NetStreamPlayerApp(App):
    """Main Kivy application."""

    source_manager = ObjectProperty(None)

    def build(self):
        self.title = APP_NAME
        self.icon = ''
        self.source_manager = SourceManager()

        # Load KV file
        kv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'videostreamer.kv')
        Builder.load_file(kv_path)

        # Build screen manager
        sm = ScreenManager(transition=SlideTransition(duration=0.3))

        # Create screens
        main_screen = SourceListScreen(name='main')
        edit_screen = EditSourceScreen(name='edit_source')
        player_screen = PlayerScreen(name='player')

        sm.add_widget(main_screen)
        sm.add_widget(edit_screen)
        sm.add_widget(player_screen)

        # Bind back button (Android)
        if platform == 'android':
            from kivy.core.window import Window
            Window.bind(on_keyboard=self._on_keyboard)

        return sm

    def _on_keyboard(self, window, key, scancode, codepoint, modifier):
        """Handle Android back button."""
        if key == 27:  # ESC/Back
            current = self.root.current
            if current == 'player':
                self.root.get_screen('player').go_back()
            elif current == 'edit_source':
                self.root.get_screen('edit_source').cancel()
            else:
                # Exit app
                return False
            return True
        return False


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    NetStreamPlayerApp().run()