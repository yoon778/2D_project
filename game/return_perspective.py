"""Optional screen-space perspective for an already-rendered world frame."""
import ctypes

import pico2d.pico2d as p


_MESH_COLUMNS = 8
_MESH_ROWS = 16


def project(x, y, width, height, strength):
    """Warp SDL coordinates. The top edge keeps its size and the bottom widens."""
    if not strength:
        return x, y
    half_width, half_height = width / 2, height / 2
    v = y / half_height - 1
    divisor = 1 - strength * v
    return (half_width + (x - half_width) * (1 + strength) / divisor,
            half_height * (1 + (v - strength) / divisor))


def unproject(x, y, width, height, strength):
    """Recover the source SDL point sampled by the warped destination."""
    if not strength:
        return x, y
    half_width, half_height = width / 2, height / 2
    warped_v = y / half_height - 1
    v = (warped_v + strength) / (1 + strength * warped_v)
    return (half_width + (x - half_width) * (1 - strength * v) / (1 + strength),
            half_height * (1 + v))


class PerspectiveTarget:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self._renderer = p.renderer
        self._texture = None
        self._previous = None
        self._active = False
        self._mesh_strength = None
        if not p.SDL_RenderTargetSupported(self._renderer):
            return
        self._texture = p.SDL_CreateTexture(self._renderer, p.SDL_PIXELFORMAT_ARGB8888,
                                            p.SDL_TEXTUREACCESS_TARGET, width, height)
        if not self._texture:
            return
        if (p.SDL_SetTextureBlendMode(self._texture, p.SDL_BLENDMODE_NONE) != 0
                or p.SDL_SetTextureScaleMode(self._texture, p.SDL_ScaleModeNearest) != 0):
            self.close()
            return

        columns = _MESH_COLUMNS + 1
        self._vertices = (p.SDL_Vertex * (columns * (_MESH_ROWS + 1)))()
        for i, vertex in enumerate(self._vertices):
            row, column = divmod(i, columns)
            vertex.color = p.SDL_Color(255, 255, 255, 255)
            vertex.tex_coord = p.SDL_FPoint(column / _MESH_COLUMNS, row / _MESH_ROWS)
        triangles = []
        for row in range(_MESH_ROWS):
            for column in range(_MESH_COLUMNS):
                nw = row * columns + column
                sw = nw + columns
                triangles.extend((nw, nw + 1, sw + 1, nw, sw + 1, sw))
        self._indices = (ctypes.c_int * len(triangles))(*triangles)

    @property
    def available(self):
        return bool(self._texture)

    def begin(self):
        """Redirect drawing, returning false when the caller should draw directly."""
        if not self.available or self._active:
            return False
        self._previous = p.SDL_GetRenderTarget(self._renderer)
        if p.SDL_SetRenderTarget(self._renderer, self._texture) != 0:
            self.close()
            return False
        self._active = True
        return True

    def cancel(self):
        """Restore the previous target without compositing the captured world."""
        if self._active:
            if p.SDL_SetRenderTarget(self._renderer, self._previous) != 0:
                raise RuntimeError(f"Perspective render target restoration failed: {p.SDL_GetError()!r}")
            self._active = False
            self._previous = None

    def present(self, strength):
        """Composite into the previous target and report whether the warp applied."""
        if not self._active:
            return False
        self.cancel()
        if strength != self._mesh_strength:
            for vertex in self._vertices:
                source = vertex.tex_coord
                x, y = project(source.x * self.width, source.y * self.height,
                               self.width, self.height, strength)
                vertex.position = p.SDL_FPoint(x, y)
            self._mesh_strength = strength
        if p.SDL_RenderGeometry(self._renderer, self._texture, self._vertices, len(self._vertices),
                                self._indices, len(self._indices)) == 0:
            return True
        try:
            if p.SDL_RenderCopy(self._renderer, self._texture, None, None) != 0:
                raise RuntimeError(f"Perspective frame copy failed: {p.SDL_GetError()!r}")
        finally:
            # Input must go back to unwarped coordinates alongside the retained frame.
            self.close()
        return False

    def close(self):
        try:
            self.cancel()
        finally:
            if self._texture:
                p.SDL_DestroyTexture(self._texture)
                self._texture = None
