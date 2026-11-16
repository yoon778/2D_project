"""Temporary truck art for the in-world arrival and return flow."""
import ctypes

import pico2d.pico2d as p


TRUCK_HEIGHT = 48


def truck_bounds(project, footprint):
    x, y, width, depth = footprint
    left, bottom = project(x, y)
    right, top = project(x + width, y + depth)
    return left - 2, bottom - 2, right - left + 4, top - bottom + TRUCK_HEIGHT + 4


def draw_truck(project, footprint, *, door="closed", dimmed=False):
    left, bottom, width, rise = truck_bounds(project, footprint)
    x, y = left + 2, bottom + 2
    width -= 4
    depth = rise - TRUCK_HEIGHT - 4
    reach = lambda u: x + u * width

    def shade(rgb):
        return tuple(round(channel * .26) for channel in rgb) if dimmed else rgb

    def box(lo, bottom, hi, top, rgb):
        p.draw_rectangle(reach(lo), y + bottom, reach(hi), y + top, *shade(rgb), filled=True)

    def face(points, rgb):
        color = p.SDL_Color(*shade(rgb), 255)
        verts = (p.SDL_Vertex * len(points))(*(
            p.SDL_Vertex(p.SDL_FPoint(reach(u), p.canvas_height - y - v), color, p.SDL_FPoint())
            for u, v in points))
        quad = (ctypes.c_int * 6)(0, 1, 2, 0, 2, 3)
        if p.SDL_RenderGeometry(p.renderer, None, verts, len(verts), quad, len(quad)) != 0:
            raise RuntimeError(f"Truck geometry failed: {p.SDL_GetError()!r}")

    ink = (30, 33, 32)
    box(.03, 6, .98, 13, ink)
    face(((.35, 47), (.96, 47), (.99, 47 + depth), (.38, 47 + depth)), (148, 144, 124))
    face(((.96, 11), (.99, 11 + depth), (.99, 47 + depth), (.96, 47)), (96, 91, 77))
    box(.35, 11, .96, 47, (121, 117, 100))
    box(.38, 42, .93, 44, (170, 160, 131))
    box(.38, 15, .93, 17, (96, 91, 77))

    face(((.12, 30), (.35, 33), (.38, 33 + depth), (.15, 30 + depth)), (135, 109, 77))
    face(((.03, 10), (.35, 10), (.35, 33), (.12, 30)), (102, 83, 61))
    face(((.13, 22), (.32, 23), (.32, 30), (.16, 28)), (61, 81, 82))
    box(.04, 13, .09, 17, (230, 192, 118))
    box(.92, 13, .96, 17, (167, 86, 64))

    if door == "cab":
        box(.18, 11, .34, 30, ink)
        face(((.14, 10), (.24, 12), (.24, 28), (.14, 26)), (119, 99, 68))
    elif door == "cargo":
        box(.75, 18, .94, 42, ink)
        box(.77, 19, .91, 24, (171, 122, 78))

    for axle in (.17, .80):
        p.draw_circle(reach(axle), y + 7, 8, *shade(ink), filled=True)
        p.draw_circle(reach(axle), y + 7, 3, *shade((114, 112, 101)), filled=True)
