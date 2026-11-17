"""Desktop fullscreen and the fixed game canvas."""
from contextlib import contextmanager
import ctypes
import sys

import pico2d.pico2d as p


_canvas = None


def configure(fullscreen):
    global _canvas
    cursor = p.SDL_Point()
    x, y = ctypes.c_int(), ctypes.c_int()
    p.SDL_GetGlobalMouseState(ctypes.byref(x), ctypes.byref(y))
    cursor.x, cursor.y = x.value, y.value
    display = p.SDL_GetPointDisplayIndex(ctypes.byref(cursor))
    center = p.SDL_WINDOWPOS_CENTERED_DISPLAY(max(0, display))
    p.SDL_SetWindowPosition(p.window, center, center)
    if fullscreen and p.SDL_SetWindowFullscreen(p.window, p.SDL_WINDOW_FULLSCREEN_DESKTOP) != 0:
        print(f"Fullscreen unavailable: {p.SDL_GetError()!r}", file=sys.stderr)
    p.SDL_SetHint(p.SDL_HINT_RENDER_LOGICAL_SIZE_MODE, b"letterbox")
    if p.SDL_RenderSetLogicalSize(p.renderer, p.canvas_width, p.canvas_height) != 0:
        raise RuntimeError(f"SDL logical size initialization failed: {p.SDL_GetError()!r}")
    _canvas = p.SDL_CreateTexture(p.renderer, p.SDL_PIXELFORMAT_ARGB8888, p.SDL_TEXTUREACCESS_TARGET,
                                  p.canvas_width, p.canvas_height)
    if not _canvas or p.SDL_SetTextureScaleMode(_canvas, p.SDL_ScaleModeNearest) != 0:
        raise RuntimeError(f"SDL game canvas initialization failed: {p.SDL_GetError()!r}")


def clear(color=(0, 0, 0)):
    p.SDL_SetRenderDrawColor(p.renderer, *color, 255)
    p.SDL_RenderClear(p.renderer)


@contextmanager
def frame():
    # Keep one-pixel lighting masks intact before the final display scale.
    if p.SDL_SetRenderTarget(p.renderer, _canvas) != 0:
        raise RuntimeError(f"SDL game canvas binding failed: {p.SDL_GetError()!r}")
    try:
        yield
    finally:
        if p.SDL_SetRenderTarget(p.renderer, None) != 0:
            raise RuntimeError(f"SDL display binding failed: {p.SDL_GetError()!r}")
    clear()
    if p.SDL_RenderCopy(p.renderer, _canvas, None, None) != 0:
        raise RuntimeError(f"SDL display copy failed: {p.SDL_GetError()!r}")
    p.update_canvas()


def close():
    global _canvas
    if _canvas:
        p.SDL_DestroyTexture(_canvas)
        _canvas = None


def cursor_in_canvas(x, y):
    if 0 <= x < p.canvas_width and 0 <= y < p.canvas_height:
        return int(x), int(y)
    return None
