"""Comprehensive test for NetStreamPlayer application."""
import os
import sys
import json
import tempfile

os.environ['KIVY_NO_ARGS'] = '1'
from kivy.config import Config
Config.set('graphics', 'width', 400)
Config.set('graphics', 'height', 800)
Config.set('kivy', 'log_level', 'warning')

import kivy
kivy.require('2.0.0')

from main import (
    NetStreamPlayerApp, SourceManager, CaptureManager,
    MjpegReader, MjpegDisplay, SourceListScreen,
    EditSourceScreen, PlayerScreen, ZoomableImage
)

print("=" * 60)
print("NetStreamPlayer - Test Suite")
print("=" * 60)

# Test 1: SourceManager
print("\n[TEST 1] SourceManager...")
sm = SourceManager()
assert len(sm.get_all()) == 0, "Should start empty"

# Test adding
sm.add({'name': 'Test Cam', 'url': 'http://192.168.1.1:8080/?action=stream', 
        'username': 'admin', 'password': 'pass123'})
assert len(sm.get_all()) == 1, "Should have 1 source"
src = sm.get_all()[0]
assert src['name'] == 'Test Cam'
assert 'id' in src
print("  ✓ Add source OK")

# Test get
src_id = src['id']
retrieved = sm.get(src_id)
assert retrieved is not None
assert retrieved['name'] == 'Test Cam'
print("  ✓ Get source OK")

# Test update
sm.update(src_id, {'name': 'Updated Cam', 'url': 'http://10.0.0.1:8080/'})
updated = sm.get(src_id)
assert updated['name'] == 'Updated Cam'
assert updated['id'] == src_id
print("  ✓ Update source OK")

# Test delete
sm.delete(src_id)
assert len(sm.get_all()) == 0
print("  ✓ Delete source OK")

# Test persistence
sm.add({'name': 'Persist Test', 'url': 'http://localhost:8080/'})
sm2 = SourceManager()
assert len(sm2.get_all()) == 1
assert sm2.get_all()[0]['name'] == 'Persist Test'
sm2.delete(sm2.get_all()[0]['id'])
print("  ✓ Persistence OK")

print("  ✓ SourceManager ALL PASSED")

# Test 2: CaptureManager
print("\n[TEST 2] CaptureManager...")
with tempfile.TemporaryDirectory() as tmpdir:
    cm = CaptureManager(save_dir=tmpdir)
    assert cm.save_dir == tmpdir
    assert not cm.is_recording

    # Test with a simple JPEG (minimal valid file)
    minimal_jpeg = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x11\x04\x12\x21\x31\x41\x05\x13\x51\x61\x07\x22\x71\x14\x32\x81\x91\xa1\x08\x23\x42\xb1\xc1\x15\x52\xd1\xf0\x24\x33\x62\x72\x82\x09\x0a\x16\x17\x18\x19\x1a\x25\x26\x27\x28\x29\x2a\x34\x35\x36\x37\x38\x39\x3a\x43\x44\x45\x46\x47\x48\x49\x4a\x53\x54\x55\x56\x57\x58\x59\x5a\x63\x64\x65\x66\x67\x68\x69\x6a\x73\x74\x75\x76\x77\x78\x79\x7a\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xc4\x00\x1f\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\xff\xc4\x00\xb5\x11\x00\x02\x01\x02\x04\x04\x03\x04\x07\x05\x04\x04\x00\x01\x02\x77\x00\x01\x02\x03\x11\x04\x05\x21\x31\x06\x12\x41\x51\x07\x61\x71\x13\x22\x32\x81\x08\x14\x42\x91\xa1\xb1\xc1\x09\x23\x33\x52\xf0\x15\x62\x72\xd1\x0a\x16\x24\x34\xe1\x25\xf1\x17\x18\x19\x1a\x26\x27\x28\x29\x2a\x35\x36\x37\x38\x39\x3a\x43\x44\x45\x46\x47\x48\x49\x4a\x53\x54\x55\x56\x57\x58\x59\x5a\x63\x64\x65\x66\x67\x68\x69\x6a\x73\x74\x75\x76\x77\x78\x79\x7a\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00\x7b\x94\x7a\x82\xae\xa0\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xd9'

    # Screenshot
    path = cm.take_screenshot(minimal_jpeg)
    assert path is not None, "Screenshot should return path"
    assert os.path.exists(path)
    assert os.path.getsize(path) > 0
    print(f"  ✓ Screenshot saved to: {path}")

    # Recording
    assert cm.start_recording()
    assert cm.is_recording
    for _ in range(5):
        cm.record_frame(minimal_jpeg)
    info = cm.stop_recording()
    assert info is not None
    assert info['frames'] == 5
    assert info['duration'] > 0
    assert os.path.isdir(info['directory'])
    print(f"  ✓ Recording OK: {info['frames']} frames in {info['directory']}")

    cm.set_save_dir(os.path.join(tmpdir, 'new_dir'))
    assert 'new_dir' in cm.save_dir
    print("  ✓ Set save dir OK")

print("  ✓ CaptureManager ALL PASSED")

# Test 3: MjpegReader
print("\n[TEST 3] MjpegReader...")
# We can't test actual network streaming, but we can test the instantiation
reader = MjpegReader(
    url='http://localhost/test.mjpg',
    username='test',
    password='test',
    on_frame=lambda data: None,
    on_error=lambda msg: None
)
assert reader.url == 'http://localhost/test.mjpg'
assert reader.username == 'test'
assert reader.password == 'test'
assert not reader._running
print("  ✓ MjpegReader creation OK")
print("  ✓ MjpegReader ALL PASSED")

# Test 4: Kivy widget creation
print("\n[TEST 4] Kivy Widgets...")
from kivy.uix.screenmanager import ScreenManager
from kivy.lang import Builder

# Load KV
kv_path = os.path.join(os.path.abspath('.'), 'videostreamer.kv')
Builder.load_file(kv_path)

# Create screen manager
sm_widget = ScreenManager()
main_screen = SourceListScreen(name='main')
edit_screen = EditSourceScreen(name='edit_source')
player_screen = PlayerScreen(name='player')
sm_widget.add_widget(main_screen)
sm_widget.add_widget(edit_screen)
sm_widget.add_widget(player_screen)
print("  ✓ All screens created OK")

# Test MjpegDisplay
display = MjpegDisplay()
assert display is not None
assert display.is_connected == False
assert display.frame_rate == 0
print("  ✓ MjpegDisplay created OK")

# Test ZoomableImage
zoom = ZoomableImage(display)
assert zoom._scale == 1.0
zoom.reset_transform()
assert zoom._scale == 1.0
assert zoom._translate.x == 0
assert zoom._translate.y == 0
print("  ✓ ZoomableImage created OK")

print("  ✓ Kivy Widgets ALL PASSED")

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)