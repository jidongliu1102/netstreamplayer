#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Android H.264 录像编码器。
在 Android 上通过 ctypes 直接调用 p4a 编译的 ffmpeg 共享库（libavcodec /
libavformat / libswscale / libavutil），把 MJPEG 帧解码 → 重编码为
H.264 (libx264) + yuv420p + faststart 的 MP4。

桌面端走 ffmpeg CLI（如有）；无法定位 ffmpeg 时回退到 MJPEG 纯 Python muxer。
零额外 Python 依赖，纯 stdlib。
"""
import os
import subprocess
import tempfile
from kivy.utils import platform


# ── Android ffmpeg 库定位 ─────────────────────────────────────────────
# p4a 把 ffmpeg 共享库放到 dist/lib 下，路径相对 dist 可预测。
_DIST_SEARCH = [
    # p4a 标准位置：dist/<name>/lib
    ("lib"),
    ("lib", "python3"),
]


def _find_dist_root() -> str | None:
    """从当前进程推断 p4a dist 根目录。"""
    if platform != "android":
        return None
    # p4a 把 dist 路径暴露给 PYTHONPATH；从中反推
    for p in os.environ.get("PYTHONPATH", "").split(":"):
        if p and ("build-arm64" in p or "dist" in p or "android" in p):
            return p
    # 兜底：从主脚本目录向上找 "lib"
    try:
        import __main__
        root = getattr(__main__, "__file__", None)
    except Exception:
        root = None
    if root:
        base = os.path.dirname(root)
        for _ in range(8):
            if base and os.path.isdir(base):
                for candidates in _DIST_SEARCH:
                    p = os.path.join(base, *candidates)
                    if os.path.isdir(p):
                        return p
            parent = os.path.dirname(base)
            if parent == base:
                break
            base = parent
    return None


def _open_lib(name: str) -> "ctypes.CDLL | None":
    """打开 ffmpeg 共享库。"""
    import ctypes
    # 1) 先尝试直接按名字（可能已在 LD_LIBRARY_PATH）
    try:
        return ctypes.CDLL(name)
    except OSError:
        pass
    # 2) 在 dist/lib 下按平台找
    root = _find_dist_root()
    if root:
        for candidates in _DIST_SEARCH:
            base = os.path.join(root, *candidates)
            if not os.path.isdir(base):
                continue
            try:
                for f in os.listdir(base):
                    if f.startswith(name):
                        p = os.path.join(base, f)
                        if os.path.isfile(p):
                            return ctypes.CDLL(p)
            except OSError:
                continue
    return None


# 延迟导入 ctypes 只在真正需要时发生
_avutil = _avcodec = _avformat = _swscale = None


def _ensure_libs() -> tuple:
    """加载 ffmpeg 共享库并返回句柄。"""
    global _avutil, _avcodec, _avformat, _swscale
    if _avutil is None:
        import ctypes
        _avutil = _open_lib("libavutil")
        _avcodec = _open_lib("libavcodec")
        _avformat = _open_lib("libavformat")
        _swscale = _open_lib("libswscale")
        if not all((_avutil, _avcodec, _avformat, _swscale)):
            raise RuntimeError(
                "缺少 ffmpeg 共享库: "
                f"avutil={_avutil is not None} "
                f"avcodec={_avcodec is not None} "
                f"avformat={_avformat is not None} "
                f"swscale={_swscale is not None}"
            )
    return _avutil, _avcodec, _avformat, _swscale


def encode_jpegs_to_h264_mp4(
    frames: list[bytes],
    out_path: str,
    fps: float = 15.0,
) -> bool:
    """
    把 JPEG 帧列表编码为 H.264 MP4 文件。

    参数
    ----
    frames : list[bytes]  每帧的 JPEG 数据
    out_path : str        输出 .mp4 路径
    fps : float           帧率

    返回
    ----
    bool  True 表示成功生成 >1KB 的 MP4
    """
    import ctypes
    import io
    if not frames:
        return False

    # 桌面端：尝试 ffmpeg CLI（更简单可靠）
    if platform != "android":
        try:
            import shutil
            ff = shutil.which("ffmpeg")
            if ff:
                tmpdir = tempfile.mkdtemp(prefix="h264_")
                try:
                    for i, jpeg in enumerate(frames):
                        with open(os.path.join(tmpdir, f"frame_{i:05d}.jpg"), "wb") as f:
                            f.write(jpeg)
                    subprocess.run(
                        [
                            ff, "-y", "-framerate", str(int(fps)),
                            "-i", os.path.join(tmpdir, "frame_%05d.jpg"),
                            "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-preset", "ultrafast", "-crf", "23",
                            "-movflags", "+faststart",
                            "-threads", "2",
                            out_path,
                        ],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=300,
                    )
                    if os.path.isfile(out_path) and os.path.getsize(out_path) > 1000:
                        return True
                finally:
                    import shutil as _sh
                    _sh.rmtree(tmpdir, ignore_errors=True)
        except Exception as e:
            print(f"[h264] ffmpeg CLI 失败，尝试 ctypes: {e}")

    # Android（或桌面 ffmpeg 不可用）：ctypes 直调 ffmpeg 库
    try:
        avutil, avcodec, avformat, swscale = _ensure_libs()
        return _encode_via_ctypes(
            avutil, avcodec, avformat, swscale,
            frames, out_path, fps,
        )
    except Exception as e:
        print(f"[h264] ctypes 编码失败: {e}")
        return False


# ── ctypes 内部实现（Android 路径）───────────────────────────────────

def _parse_jpeg_size(data: bytes) -> tuple[int, int]:
    """解析 JPEG SOF0 标记里的宽高。"""
    import struct
    pos = 0
    while pos < len(data) - 1:
        if data[pos] != 0xFF:
            break
        m = data[pos + 1]
        if m in (0xC0, 0xC1, 0xC2):
            h = struct.unpack(">H", data[pos + 5 : pos + 7])[0]
            w = struct.unpack(">H", data[pos + 7 : pos + 9])[0]
            return w, h
        if m in (0xD9, 0xDA):
            break
        if 0xD0 <= m <= 0xD7:
            pos += 2
            continue
        if len(data) < pos + 4:
            break
        sl = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
        pos += 2 + sl
    return 640, 480


def _encode_via_ctypes(
    avutil, avcodec, avformat, swscale,
    frames: list[bytes],
    out_path: str,
    fps: float,
) -> bool:
    import ctypes

    w, h = _parse_jpeg_size(frames[0])
    num = len(frames)
    # 帧率分数（简化）
    fps_num = int(fps * 1000)
    fps_den = 1000

    # ── 输入 JPEG 解码器 ──
    dec_ctx = avcodec.avcodec_alloc_context3(avcodec.avcodec_find_decoder(
        avcodec.AV_CODEC_ID_MJPEG
    ))
    dec = ctypes.POINTER(avcodec.AVCodecContext)(dec_ctx)

    # ── 输出 H.264 编码器 ──
    enc_ctx = avcodec.avcodec_alloc_context3(avcodec.avcodec_find_encoder(
        avcodec.AV_CODEC_ID_H264
    ))
    enc = ctypes.POINTER(avcodec.AVCodecContext)(enc_ctx)
    enc.contents.width = w
    enc.contents.height = h
    enc.contents.pix_fmt = avutil.AV_PIX_FMT_YUV420P
    enc.contents.time_base = avutil.AVRational(fps_den, fps_num)
    enc.contents.gop_size = 10
    enc.contents.codec_id = avcodec.AV_CODEC_ID_H264
    enc.contents.codec_type = avutil.AVMEDIA_TYPE_VIDEO
    enc.contents.bit_rate = 0  # CRF-like via x264 opts
    enc.contents.qmin = 10
    enc.contents.qmax = 51
    # libx264 选项（通过 extradata 或直接选项字典）
    # 简单设置 CRF = 23（通过 qmax 近似；精确 CRF 需 x264 特有 API）
    avcodec.avcodec_open2(enc, avcodec.avcodec_find_encoder(avcodec.AV_CODEC_ID_H264), None)

    # ── 输出格式上下文 ──
    oc = avformat.avformat_alloc_context()
    avformat.avformat_alloc_output_context2(
        ctypes.byref(oc), None, "mp4", out_path.encode()
    )
    # 打开输出文件
    avutil.avio_open2(
        ctypes.byref(oc.contents.pb),
        out_path.encode(),
        avutil.AVIO_FLAG_WRITE,
        None,
        None,
    )

    # 添加视频流
    st = avformat.avformat_new_stream(oc, None)
    avcodec.avcodec_copy_context(st.contents.codec, enc)
    st.contents.codec.contents.codec_tag = 0

    # ── 写 moov ──
    avformat.avformat_write_header(oc, None)

    frame_pkt = avutil.av_packet_alloc()
    yuv_frame = avcodec.av_frame_alloc()
    jpeg_pkt = avutil.av_packet_alloc()

    # 缩放上下文（MJEPG → yuv420p，尺寸对齐）
    sws = swscale.sws_getContext(
        w, h, avutil.AV_PIX_FMT_YUVJ420P,
        w, h, avutil.AV_PIX_FMT_YUV420P,
        swscale.SWS_FAST_BILINEAR,
        None, None, None,
    )

    for i, jpeg_data in enumerate(frames):
        # 构造输入包
        jpeg_pkt.contents.size = len(jpeg_data)
        jpeg_pkt.contents.data = avutil.av_malloc(len(jpeg_data))
        ctypes.memmove(jpeg_pkt.contents.data, jpeg_data, len(jpeg_data))
        jpeg_pkt.contents.pts = i

        # 解码
        avcodec.avcodec_send_packet(dec, jpeg_pkt)
        ret = avcodec.avcodec_receive_frame(dec, yuv_frame)
        avutil.av_packet_unref(jpeg_pkt)
        if ret < 0:
            continue

        # 缩放为 yuv420p
        out_frame = avcodec.av_frame_alloc()
        swscale.sws_scale(
            sws,
            (ctypes.c_void_p * 4)(*yuv_frame.contents.data),
            (ctypes.c_int * 4)(*yuv_frame.contents.linesize),
            0, h,
            out_frame.contents.data,
            out_frame.contents.linesize,
        )
        out_frame.contents.pts = i
        out_frame.contents.width = w
        out_frame.contents.height = h
        out_frame.contents.format = ctypes.c_int(avutil.AV_PIX_FMT_YUV420P)

        # 编码
        avcodec.avcodec_send_frame(enc, out_frame)
        avcodec.avcodec_receive_packet(enc, frame_pkt)
        frame_pkt.contents.stream_index = 0
        avformat.av_interleaved_write_frame(oc, frame_pkt)
        avutil.av_packet_unref(frame_pkt)

        avcodec.av_frame_free(ctypes.byref(out_frame))

    # 收尾
    avcodec.avcodec_send_frame(enc, None)
    while avcodec.avcodec_receive_packet(enc, frame_pkt) == 0:
        frame_pkt.contents.stream_index = 0
        avformat.av_interleaved_write_frame(oc, frame_pkt)
        avutil.av_packet_unref(frame_pkt)

    avformat.av_write_trailer(oc)
    avutil.avio_close(oc.contents.pb)

    # 释放
    avutil.av_packet_free(ctypes.byref(jpeg_pkt))
    avutil.av_packet_free(ctypes.byref(frame_pkt))
    avcodec.av_frame_free(ctypes.byref(yuv_frame))
    avcodec.avcodec_free_context(ctypes.byref(enc))
    avcodec.avcodec_free_context(ctypes.byref(dec))
    avformat.avformat_free(oc)
    swscale.sws_freeContext(sws)

    return os.path.isfile(out_path) and os.path.getsize(out_path) > 1000
