"""Меловые рисунки сырья для витрины: static/images/sketches/<slug>.svg.

Запуск из корня проекта: python scripts/draw_sketches.py — перерисует все файлы.
Холст 200×200. Левый верхний угол (x < 122, y < 155) закрыт фото бутылки,
поэтому главное — справа, а семена рассыпаны по нижней полосе.
"""
import math
import random
import sys
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / 'static' / 'images' / 'sketches'

W = '#f1ede3'      # мел
O = '#f0a04b'      # оранжевый
Y = '#f2d46b'      # жёлтый
G = '#a9cf86'      # зелёный
B = '#a9c8ec'      # голубой
K = '#c9a274'      # крафт, орех
L = '#c7a2e6'      # сиреневый
R = '#e98aa6'      # розовый
RU = '#e0904f'     # рыжий
DARK = '#0f0f0e'   # чёрные семена на доске

HEAD = '''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 200 200" width="200" height="200">
<defs>
<filter id="c" filterUnits="userSpaceOnUse" x="-10" y="-10" width="220" height="220">
<feTurbulence type="fractalNoise" baseFrequency="0.07" numOctaves="2" seed="{seed}" result="w"/>
<feDisplacementMap in="SourceGraphic" in2="w" scale="2.2" xChannelSelector="R" yChannelSelector="G" result="d"/>
<feTurbulence type="fractalNoise" baseFrequency="1.25" numOctaves="2" seed="11" result="g"/>
<feColorMatrix in="g" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 3.4 0 0 0 -0.75" result="m"/>
<feComposite in="d" in2="m" operator="in"/>
</filter>
{defs}
</defs>
<g filter="url(#c)" fill="none" stroke-linecap="round" stroke-linejoin="round" opacity="0.94">
{body}
</g>
</svg>
'''


def f(n):
    return f'{n:.2f}'.rstrip('0').rstrip('.')


def attrs(c, w, fill, fo):
    out = f'stroke="{c}" stroke-width="{f(w)}"' if c else 'stroke="none"'
    if fill:
        out += f' fill="{fill}" fill-opacity="{f(fo) if fo < 1 else 1}"'
    return out


def path(d, c=W, w=2, fill=None, fo=0.2, extra=''):
    return f'<path d="{d}" {attrs(c, w, fill, fo)}{extra}/>'


def ellipse(cx, cy, rx, ry, c=W, w=2, fill=None, fo=0.2, rot=0):
    tr = f' transform="rotate({f(rot)} {f(cx)} {f(cy)})"' if rot else ''
    return f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}" {attrs(c, w, fill, fo)}{tr}/>'


def circle(cx, cy, r, c=W, w=2, fill=None, fo=0.2):
    return f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" {attrs(c, w, fill, fo)}/>'


def use(ref, x, y, rot=0, s=1):
    return f'<use xlink:href="#{ref}" transform="translate({f(x)} {f(y)}) rotate({f(rot)}) scale({f(s)})"/>'


def symbol(ref, content):
    return f'<g id="{ref}">{content}</g>'


def scatter(rng, ref, n, x0=24, x1=194, y0=162, y1=194, s0=0.85, s1=1.15):
    return ''.join(use(ref, rng.uniform(x0, x1), rng.uniform(y0, y1), rng.uniform(0, 360), rng.uniform(s0, s1))
                   for _ in range(n))


def heap(rng, ref, n, cx, cy, rx, ry, s0=0.85, s1=1.1):
    items = []
    for _ in range(n):
        a = rng.uniform(0, math.tau)
        r = math.sqrt(rng.random())
        x, y = cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r
        # горка: выше к середине
        y -= (1 - r) * ry * 0.9
        items.append((y, use(ref, x, y, rng.uniform(0, 360), rng.uniform(s0, s1))))
    return ''.join(item for _, item in sorted(items))


def bezier(p0, p1, p2, p3, t):
    u = 1 - t
    return tuple(u ** 3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t ** 3 * d for a, b, c, d in zip(p0, p1, p2, p3))


def leaf_shape(length, width):
    """Лист от черешка (0,0) вверх до (0,-length)."""
    return (f'M0 0 C{f(width)} {f(-length * 0.25)} {f(width)} {f(-length * 0.7)} 0 {f(-length)} '
            f'C{f(-width)} {f(-length * 0.7)} {f(-width)} {f(-length * 0.25)} 0 0Z')


def leaf(x, y, rot, length, width, c=G, fo=0.18, vein=True):
    d = leaf_shape(length, width)
    v = path(f'M0 0 L0 {f(-length * 0.85)}', c, 1.1) if vein else ''
    return f'<g transform="translate({f(x)} {f(y)}) rotate({f(rot)})">{path(d, c, 1.6, c, fo)}{v}</g>'


def petals(cx, cy, n, dist, rx, ry, c, fo=0.22, w=1.6, offset=0, vein=None):
    out = []
    for k in range(n):
        a = offset + k * 360 / n
        out.append(ellipse(cx, cy - dist, rx, ry, c, w, c, fo, 0) .replace('/>', f' transform="rotate({f(a)} {f(cx)} {f(cy)})"/>'))
        if vein:
            out.append(path(f'M{f(cx)} {f(cy - 3)} L{f(cx)} {f(cy - dist - ry * 0.6)}', vein, 0.9)
                       .replace('/>', f' transform="rotate({f(a)} {f(cx)} {f(cy)})"/>'))
    return ''.join(out)


# ── рисунки ──────────────────────────────────────────────────────────────────

def pumpkin(rng):
    seed = symbol('s', path('M-8 0C-6-4.6 4-5.2 8-1.2C8.6-.2 8.6.6 8 1.2C4 5.2-6 4.6-8 0Z', G, 1.3, G, 0.4)
                  + path('M-4.5 0C-1-1.3 3-1.3 5.5-.4', '#d7ecc4', 0.8))
    body = [
        # лист и усик
        path('M160 60C150 52 146 38 153 31C151 22 160 16 168 21C172 11 185 10 189 20C197 21 200 31 195 39'
             'C200 47 193 57 183 55C176 61 166 63 160 60Z', G, 1.8, G, 0.16),
        path('M160 60L154 32M160 60L169 21M160 60L187 22M160 60L195 40M160 60L183 55', G, 1),
        path('M151 82C150 72 154 64 160 60', G, 2),
        path('M152 70C141 67 135 58 140 51C145 46 151 51 146 55', G, 1.2),
        # тыква — дольки от задних к передним
        ellipse(123, 121, 20, 29, O, 1.8, O, 0.14),
        ellipse(177, 121, 20, 29, O, 1.8, O, 0.14),
        ellipse(137, 119, 22, 34, O, 1.8, O, 0.16),
        ellipse(163, 119, 22, 34, O, 1.8, O, 0.16),
        ellipse(150, 118, 15, 36, O, 2, O, 0.18),
        path('M141 128C143 136 146 142 150 146M163 100C165 106 166 112 166 118', '#f6c58a', 0.9),
        # хвостик
        path('M146 85C145 77 147 71 152 66L158 69C154 74 153 79 154 85Z', K, 1.6, K, 0.45),
    ]
    body.append(scatter(rng, 's', 9))
    body.append(heap(rng, 's', 12, 158, 186, 22, 7))
    return seed, body


def nigella(rng):
    seed = symbol('s', path('M-2.8-1.6C-1-2.6 2-2.8 3-1.8C3.2 0 2 2.2.6 2.6C-1 2.4-2.6 0-2.8-1.6Z', W, 0.8, DARK, 0.95))
    cx, cy = 152, 76
    body = []
    # перистые прицветники за цветком
    for k in range(11):
        a = math.radians(k * 360 / 11 + 8)
        x1, y1 = cx + math.cos(a) * 20, cy + math.sin(a) * 20
        x2, y2 = cx + math.cos(a) * 44, cy + math.sin(a) * 44
        mx, my = cx + math.cos(a + 0.18) * 33, cy + math.sin(a + 0.18) * 33
        body.append(path(f'M{f(x1)} {f(y1)}Q{f(mx)} {f(my)} {f(x2)} {f(y2)}', G, 1.1))
        bx, by = cx + math.cos(a) * 32, cy + math.sin(a) * 32
        body.append(path(f'M{f(bx)} {f(by)}l{f(math.cos(a - 0.7) * 9)} {f(math.sin(a - 0.7) * 9)}', G, 0.9))
    body += [
        path('M150 100C147 126 154 160 150 198', G, 1.8),
        petals(cx, cy, 5, 16, 11, 17, B, 0.22, 1.7, 12, vein='#d3e3f6'),
        circle(cx, cy, 6, G, 1.4, G, 0.3),
    ]
    for k in range(14):
        a = math.radians(k * 360 / 14)
        body.append(path(f'M{f(cx + math.cos(a) * 6)} {f(cy + math.sin(a) * 6)}L{f(cx + math.cos(a) * 10)} '
                         f'{f(cy + math.sin(a) * 10)}', W, 0.9))
    for k in range(5):
        body.append(path(f'M{cx} {cy}c3-7 10-10 13-6', '#cfe5b5', 1.1)
                    .replace('/>', f' transform="rotate({k * 72} {cx} {cy})"/>'))
    # коробочка с рожками
    body += [
        path('M181 150C183 166 179 182 177 198', G, 1.6),
        ellipse(181, 134, 13, 17, G, 1.7, G, 0.14),
        path('M181 117C178 128 178 140 181 151M181 117C185 128 186 140 181 151', G, 1),
        path('M171 124C166 118 163 112 166 107M176 119C174 112 174 106 178 102M181 117C182 110 184 105 188 103'
             'M186 119C190 113 194 111 197 112M191 124C195 121 197 118 197 115', G, 1.2),
    ]
    body.append(scatter(rng, 's', 20, s0=0.7, s1=0.95))
    body.append(heap(rng, 's', 22, 104, 186, 16, 6, 0.7, 0.9))
    return seed, body


def hemp(rng):
    seed = symbol('s', ellipse(0, 0, 4.4, 3.4, '#ddd1b6', 1, K, 0.32) + path('M-4 .2C-1 -1 1.5 -1 4 .1', '#ddd1b6', 0.7))
    body = [
        # мешочек
        path('M121 166C108 141 113 113 132 100L170 100C188 113 194 141 184 166C172 175 134 175 121 166Z',
             K, 2, K, 0.14),
        path('M128 120L136 160M140 112L146 166M156 110L158 168M170 114L168 166M180 126L176 160', K, 0.8),
        path('M124 140C140 144 168 144 188 138M122 154C142 158 166 158 186 152', K, 0.8),
        # горловина и завязка
        path('M132 100C123 92 119 84 123 76M170 100C181 92 184 84 180 76', K, 1.8),
        ellipse(151, 76, 29, 7, K, 1.8, K, 0.1),
        path('M130 101C142 106 160 106 172 101', W, 1.6),
        path('M150 105C142 112 136 112 138 106C140 102 146 104 150 105C156 112 164 113 162 106C160 101 154 103 150 105',
             W, 1.2),
        path('M149 106L144 120M151 106L157 119', W, 1.1),
    ]
    # горка семян в мешке
    body.append(heap(rng, 's', 22, 151, 74, 24, 6, 0.8, 1.0))
    body.append(scatter(rng, 's', 10))
    body.append(heap(rng, 's', 14, 182, 184, 16, 7))
    return seed, body


def flax(rng):
    seed = symbol('s', path('M-4.6 0C-3-2.5 3-2.7 4.6-.4C3 2.1-3 2.3-4.6 0Z', K, 0.9, K, 0.55)
                  + path('M-2.5-.6C-.5-1.2 1.5-1.2 3-.6', '#ecd9b6', 0.6))
    boll = symbol('b', path('M0-9C5-7 7-2 6 2C5 6-5 6-6 2C-7-2-5-7 0-9Z', '#d9bd78', 1.3, '#d9bd78', 0.22)
                  + path('M-6 2L-3 7M0 6V9M6 2L3 7', G, 1))

    def flower(x, y, rot=0):
        return (f'<g transform="rotate({rot} {x} {y})">'
                + petals(x, y, 5, 8, 7.5, 8.5, B, 0.25, 1.5, 0, vein='#d3e3f6')
                + circle(x, y, 2.6, Y, 1, Y, 0.6) + '</g>')

    body = [
        path('M156 198C154 160 150 110 148 66', G, 1.6),
        path('M151 132C162 120 174 110 182 106', G, 1.3),
        path('M149 94C158 78 168 62 177 54', G, 1.3),
        path('M152 160C164 150 176 146 190 146', G, 1.2),
    ]
    for x, y, rot in ((154, 176, -18), (152, 150, 24), (150, 120, -26), (149, 104, 28), (166, 119, 64),
                      (164, 72, 52), (172, 150, 78), (148, 80, -24)):
        body.append(leaf(x, y, rot, 15, 2.8, G, 0.2, vein=False))
    body += [flower(148, 56, 8), flower(184, 100, -14), use('b', 178, 46, 20), use('b', 192, 142, 70, 0.9)]
    body.append(scatter(rng, 's', 16))
    body.append(heap(rng, 's', 22, 112, 186, 18, 6))
    return seed + boll, body


def amaranth(rng):
    seed = symbol('s', circle(0, 0, 1.4, '#efe2c2', 0.6, '#efe2c2', 0.8))
    body = [
        path('M160 198C161 160 159 120 156 76', G, 2.2),
        path('M157 140C168 126 190 128 197 141C186 152 167 152 157 140Z', G, 1.6, G, 0.16),
        path('M157 140L195 141M168 136L172 131M176 139L182 133M168 144L173 148M180 143L186 148', G, 0.9),
        path('M157 112C146 99 129 97 120 103C130 116 146 119 157 112Z', G, 1.6, G, 0.16),
        path('M157 112L122 103', G, 0.9),
    ]
    plume = [((156, 80), (150, 28), (198, 16), (192, 82), 9, 3), ((157, 92), (180, 76), (198, 104), (186, 130), 6, 2.4)]
    # пушистая метёлка: много мелких бусин вокруг изогнутой оси
    for p0, p1, p2, p3, r0, r1 in plume:
        steps = 34
        body.append(path(f'M{p0[0]} {p0[1]}C{p1[0]} {p1[1]} {p2[0]} {p2[1]} {p3[0]} {p3[1]}', R, r0 * 1.6, R, 0)
                    .replace('stroke-width', 'stroke-opacity="0.18" stroke-width'))
        for i in range(steps + 1):
            t = i / steps
            x, y = bezier(p0, p1, p2, p3, t)
            r = r0 + (r1 - r0) * t
            for _ in range(3):
                a = rng.uniform(0, math.tau)
                d = rng.uniform(0, r * 0.8)
                body.append(circle(x + math.cos(a) * d, y + math.sin(a) * d, r * 0.42, R, 1, R, 0.25))
    body.append(scatter(rng, 's', 36, s0=0.9, s1=1.3))
    body.append(heap(rng, 's', 40, 176, 188, 16, 6, 0.9, 1.2))
    return seed, body


def cedar(rng):
    nut = symbol('s', path('M0-6C3.5-4 4.5 2 2.6 5C1 6.6-1 6.6-2.6 5C-4.5 2-3.5-4 0-6Z', K, 1, K, 0.45)
                 + path('M0-5.6L0-3', '#e9d3ae', 0.9))
    kernel = symbol('k', ellipse(0, 0, 2.2, 4.2, W, 0.8, '#f4ead3', 0.45) + circle(0, -3.4, 0.8, K, 0.5, K, 1))
    cone = 'M160 64C182 66 194 96 190 122C186 146 172 160 160 160C148 160 134 146 130 122C126 96 138 66 160 64Z'
    lattice = []
    for i in range(-5, 7):
        lattice.append(f'M{100 + i * 13} 170Q{150 + i * 13} 125 {170 + i * 13} 55')
        lattice.append(f'M{220 - i * 13} 170Q{170 - i * 13} 125 {150 - i * 13} 55')
    body = [
        # ветка с иглами
        path('M200 24C186 27 170 34 157 45', K, 2),
    ]
    for t in (0.15, 0.4, 0.65, 0.9):
        x, y = 200 - 43 * t, 24 + 21 * t
        for k in range(6):
            a = math.radians(-160 + k * 22)
            body.append(path(f'M{f(x)} {f(y)}l{f(math.cos(a) * 24)} {f(math.sin(a) * 24)}', G, 1.1))
    body += [
        path(cone, K, 2, K, 0.16),
        f'<clipPath id="cone"><path d="{cone}"/></clipPath>',
        f'<g clip-path="url(#cone)">{path("".join(lattice), K, 1.3)}</g>',
        path('M160 65C160 58 163 53 168 50', K, 2.2),
    ]
    body.append(scatter(rng, 's', 12))
    body.append(heap(rng, 's', 16, 110, 186, 16, 6))
    body.append(scatter(rng, 'k', 5, x0=150, x1=192))
    return nut + kernel, body


def almond(rng):
    shape = 'M0-22C10-16 14 2 10 12C7 19-7 19-10 12C-14 2-10-16 0-22Z'
    pores = ''.join(path(f'M{f(rng.uniform(-7, 7))} {f(rng.uniform(-13, 13))}l{f(rng.uniform(-1, 1))} 2', K, 0.8)
                    for _ in range(12))
    nut = symbol('a', path(shape, K, 1.8, K, 0.28) + path('M0-21C3-10 3 6 0 17', '#e2c69d', 0.9) + pores)
    small = symbol('s', path(shape, K, 1.8, K, 0.3).replace('<path', '<path transform="scale(.4)"'))

    def blossom(x, y, rot):
        return (f'<g transform="rotate({rot} {x} {y})">' + petals(x, y, 5, 6.5, 5.5, 6.5, '#f6d8e2', 0.3, 1.3)
                + circle(x, y, 2.2, R, 1, R, 0.8) + '</g>')

    body = [
        path('M200 30C186 34 170 44 158 52C150 56 142 58 134 58', K, 2.4),
        path('M178 41C182 34 184 28 182 22', K, 1.6),
        blossom(176, 46, 10), blossom(146, 52, -20), blossom(186, 20, 30),
        ellipse(164, 40, 3, 4.6, '#f6d8e2', 1.2, R, 0.3, 30),
        leaf(160, 50, 140, 16, 4.5, G, 0.18),
        use('a', 150, 118, -24), use('a', 178, 110, 18), use('a', 166, 144, 78),
    ]
    body.append(scatter(rng, 's', 7, s0=0.9, s1=1.1))
    body.append(heap(rng, 's', 6, 104, 184, 14, 5))
    return nut + small, body


def thistle(rng):
    seed = symbol('s', path('M-6 0C-4-2.8 4-2.8 6-.6C4 2.6-4 2.6-6 0Z', K, 0.9, K, 0.45)
                  + circle(-1.5, -0.5, 0.5, W, 0.4, W, 1) + circle(2, 0.6, 0.5, W, 0.4, W, 1))
    cx, cy = 160, 100
    body = [
        # лист с колючками и белыми прожилками
        path('M140 176C150 161 158 160 162 151C170 149 172 141 180 141C186 135 190 135 198 128'
             'C194 138 190 142 188 151C180 153 178 161 170 163C164 171 156 171 148 177Z', G, 1.7, G, 0.16),
        path('M144 175C160 162 178 148 196 130', W, 1),
        path('M162 162C164 156 166 152 170 150M176 152C176 147 178 144 182 142M156 168C152 162 152 158 154 154',
             W, 0.7),
        path('M162 151l-2-4M180 141l1-5M198 128l2-1M188 151l5 1M170 163l2 5M148 177l-3 2', '#e7f2d9', 1),
        path('M160 120C160 138 161 156 164 168', G, 1.8),
        ellipse(cx, cy, 21, 18, G, 1.7, G, 0.18),
    ]
    # колючие прицветники
    for k in range(13):
        a = math.radians(160 + k * 220 / 12)
        x1, y1 = cx + math.cos(a) * 19, cy + math.sin(a) * 16
        x2, y2 = cx + math.cos(a) * 34, cy + math.sin(a) * 30
        body.append(path(f'M{f(x1)} {f(y1)}L{f(x2)} {f(y2)}', '#e7f2d9', 1.1))
    body.append(path('M146 96Q153 104 160 96Q167 104 174 96M148 108Q154 115 160 108Q166 115 172 108', G, 1))
    # сиреневая кисточка
    body.append(ellipse(cx, 70, 17, 14, None, 0, L, 0.14))
    for k in range(19):
        dx = -16 + k * 32 / 18
        x2 = cx + dx * 1.5 + rng.uniform(-2, 2)
        y2 = 46 + abs(dx) * 0.7 + rng.uniform(-3, 3)
        body.append(path(f'M{f(cx + dx * 0.8)} 84L{f(x2)} {f(y2)}', L, 1.3))
        body.append(circle(x2, y2, 1, L, 0.8, L, 0.8))
    body.append(scatter(rng, 's', 9))
    body.append(heap(rng, 's', 12, 110, 186, 16, 6))
    return seed, body


def sunflower(rng):
    seed = symbol('s', path('M-7.5 0C-5-3.8 5-3.6 7.5-.3C5 3.4-5 3.8-7.5 0Z', W, 1, '#2b2a26', 0.95)
                  + path('M-5-1.2C-1-2.2 3-2 6-1M-5 1.4C-1 2.4 3 2.2 6 1', W, 0.6))
    cx, cy = 152, 78
    body = [
        path('M156 122C158 150 156 175 158 198', G, 2.6),
        path('M158 154C168 138 196 140 196 156C194 170 176 172 158 154Z', G, 1.7, G, 0.16),
        path('M158 154C172 152 184 154 194 157M170 153L176 144M180 155L188 146M172 155L178 165', G, 0.9),
    ]
    for k in range(18):
        a = k * 20
        body.append(path('M0-24C6-32 6-40 0-45C-6-40-6-32 0-24Z', Y, 1.5, Y, 0.24)
                    .replace('<path', f'<path transform="translate({cx} {cy}) rotate({a})"'))
    for k in range(9):
        a = k * 40 + 10
        body.append(path('M0-22C4-28 4-33 0-37C-4-33-4-28 0-22Z', '#e9b649', 1.2, '#e9b649', 0.25)
                    .replace('<path', f'<path transform="translate({cx} {cy}) rotate({a})"'))
    body.append(circle(cx, cy, 25, K, 2, '#6b4a2b', 0.55))
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(1, 110):
        r = 23 * math.sqrt(i / 110)
        body.append(circle(cx + math.cos(i * golden) * r, cy + math.sin(i * golden) * r, 0.9, None, 0,
                           '#e8c98d', 0.55))
    body.append(scatter(rng, 's', 8))
    body.append(heap(rng, 's', 5, 110, 186, 12, 5))
    return seed, body


def camelina(rng):
    seed = symbol('s', ellipse(0, 0, 2.3, 1.4, RU, 0.7, RU, 0.7))
    pod = symbol('p', path('M0 0L0-6', G, 0.9) + path('M0-6C-4-7-5-13-3-16C-1.5-18 1.5-18 3-16C5-13 4-7 0-6Z',
                                                       '#d8c86a', 1.1, '#d8c86a', 0.22)
                 + path('M0-17.5V-19.5', '#d8c86a', 0.9))
    body = [
        path('M160 198C160 160 158 110 156 36', G, 1.7),
        path('M158 146C168 128 178 114 190 102', G, 1.3),
        path('M157 112C150 100 140 92 128 86', G, 1.3),
        path('M156 82C164 70 172 60 182 50', G, 1.3),
        leaf(160, 176, -14, 22, 4, G, 0.18),
        leaf(159, 164, 30, 20, 3.6, G, 0.18),
    ]
    stems = [((158, 146), (190, 102)), ((157, 112), (128, 86)), ((156, 82), (182, 50)), ((159, 140), (156, 40))]
    for (x0, y0), (x1, y1) in stems:
        for i in range(1, 6):
            t = i / 6
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            side = 1 if i % 2 else -1
            body.append(use('p', x, y, side * rng.uniform(30, 55), rng.uniform(0.8, 1)))
    for x, y in ((190, 100), (182, 48), (156, 36)):
        body.append(petals(x, y - 3, 4, 2.6, 2, 2.8, Y, 0.5, 1, 45))
    body.append(scatter(rng, 's', 30, s0=0.9, s1=1.3))
    body.append(heap(rng, 's', 40, 116, 186, 18, 6, 0.9, 1.2))
    return seed + pod, body


def sesame_pod(c='#dcc68c'):
    return symbol('p', path('M0 4V0', G, 1.2)
                  + path('M-6.5 0C-8-10-7.5-22-3.5-28L0-31L3.5-28C7.5-22 8-10 6.5 0C4 2.5-4 2.5-6.5 0Z', c, 1.5, c, 0.2)
                  + path('M-2.6 0C-3.6-10-3.4-20-1.2-28M2.6 0C3.6-10 3.4-20 1.2-28', c, 0.9))


def sesame_black(rng):
    seed = symbol('s', path('M0-2.9C1.9-1.6 2.1 1.6 0 2.9C-2.1 1.6-1.9-1.6 0-2.9Z', W, 0.7, DARK, 0.95))
    body = [
        path('M162 198C161 160 160 110 158 40', G, 1.8),
        leaf(160, 150, 52, 40, 7, G, 0.16),
        leaf(159, 112, -40, 34, 6, G, 0.16),
        leaf(158, 76, 48, 28, 5, G, 0.16),
        use('p', 168, 132, 18), use('p', 150, 122, -16), use('p', 167, 96, 22), use('p', 152, 74, -14),
        use('p', 159, 48, 4, 0.8),
    ]
    # раскрытая коробочка: семена у створок
    body.append(heap(rng, 's', 60, 172, 186, 22, 9, 0.95, 1.25))
    body.append(scatter(rng, 's', 18, x0=30, x1=150, s0=0.95, s1=1.25))
    return seed + sesame_pod(), body


def sesame_light(rng):
    seed = symbol('s', path('M0-2.9C1.9-1.6 2.1 1.6 0 2.9C-2.1 1.6-1.9-1.6 0-2.9Z', K, 0.7, '#e6d3a8', 0.75))
    bell = symbol('f', path('M0 0C-2-3-3-9-4-13C-7-15-7-19-4-19C-2-21 2-21 4-19C7-19 7-15 4-13C3-9 2-3 0 0Z',
                            '#f6e4ec', 1.3, '#f6d8e2', 0.25) + path('M-3-16C-1-14 1-14 3-16', R, 0.8))
    body = [
        path('M164 160C163 130 161 90 158 36', G, 1.8),
        leaf(162, 128, 54, 34, 6, G, 0.16),
        leaf(160, 96, -44, 30, 5.5, G, 0.16),
        use('p', 168, 112, 20, 0.9), use('p', 150, 104, -18, 0.9),
        use('f', 167, 72, 160), use('f', 152, 60, -150), use('f', 162, 42, 175, 0.85),
        # деревянная ложка
        path('M138 182C120 186 80 190 40 193', K, 4.5),
        path('M138 182C120 186 80 190 40 193', '#e2c69d', 1),
        ellipse(162, 179, 25, 12, K, 2, K, 0.2, -6),
    ]
    body.append(heap(rng, 's', 46, 162, 180, 20, 7, 0.95, 1.2))
    body.append(scatter(rng, 's', 14, x0=40, x1=196, y0=160, y1=176))
    return seed + bell + sesame_pod(), body


def mustard(rng):
    seed = symbol('s', circle(0, 0, 2, '#e2b55a', 0.8, '#e2b55a', 0.45))
    flower = symbol('f', petals(0, 0, 4, 3.8, 2.8, 3.8, Y, 0.4, 1.1, 45) + circle(0, 0, 1, '#f6e7a6', 0.6, '#f6e7a6', 1))
    body = [
        path('M160 198C160 160 158 110 156 50', G, 1.8),
        path('M158 128C166 110 176 96 186 84', G, 1.3),
        path('M159 162C170 160 182 156 194 150C186 162 174 168 159 162Z', G, 1.5, G, 0.16),
        path('M159 162C172 162 184 158 194 150', G, 0.8),
    ]
    for x, y, a in ((157, 120, -28), (158, 104, 30), (157, 92, -32), (156, 80, 26), (170, 108, -10),
                    (176, 100, 40), (182, 92, -6), (158, 140, 34)):
        r = math.radians(a - 90)
        x2, y2 = x + math.cos(r) * 22, y + math.sin(r) * 22
        body.append(path(f'M{x} {y}L{f(x2)} {f(y2)}', '#c9d27a', 2.4))
        body.append(path(f'M{f(x2)} {f(y2)}l{f(math.cos(r) * 4)} {f(math.sin(r) * 4)}', '#c9d27a', 1))
    for x, y, s in ((156, 46, 1.1), (146, 52, 1), (166, 50, 1), (152, 36, 0.9), (162, 34, 0.9), (172, 42, 0.95),
                    (140, 42, 0.85), (186, 82, 1), (192, 72, 0.9), (180, 74, 0.85), (157, 26, 0.7), (196, 84, 0.7)):
        body.append(use('f', x, y, rng.uniform(0, 90), s * 1.3))
    body.append(scatter(rng, 's', 26))
    body.append(heap(rng, 's', 34, 112, 186, 17, 6))
    return seed + flower, body


def walnut(rng):
    shell = 'M164 80C180 80 192 96 191 114C190 133 178 146 164 146C149 146 137 133 137 114C137 96 148 80 164 80Z'

    def ridges():
        """Извилистые бороздки скорлупы сверху вниз, по обе стороны от шва."""
        out = []
        for x0 in (142, 149, 156, 172, 179, 186):
            d = f'M{x0} 82'
            y = 82
            while y < 146:
                step = rng.uniform(6, 10)
                d += f'q{f(rng.uniform(-6, 6))} {f(step / 2)} {f(rng.uniform(-3, 3))} {f(step)}'
                y += step
            out.append(d)
        return (f'<clipPath id="shell"><path d="{shell}"/></clipPath>'
                f'<g clip-path="url(#shell)">{path("".join(out), "#e2c69d", 1)}</g>')

    piece = symbol('s', path('M-4-3C-1-5 2-5 4-3C6 0 4 4 1 4C-1 5-4 4-5 1C-6 0-5-2-4-3Z', W, 0.8, '#efe2c2', 0.4)
                   + path('M-3 0C-1-2 1 1 3-1', W, 0.6))
    body = [path('M200 72C190 57 178 41 162 27', G, 1.6)]
    for t, side in ((0.2, 1), (0.2, -1), (0.45, 1), (0.45, -1), (0.7, 1), (0.7, -1)):
        x, y = 200 - 38 * t, 72 - 45 * t
        body.append(leaf(x, y, -40 + side * 62, 20, 5, G, 0.16))
    body.append(leaf(162, 27, -38, 20, 5, G, 0.16))
    body += [
        path(shell, K, 2, K, 0.24),
        path('M164 80C160 98 168 126 164 146', K, 1.8),
        path('M164 80C162 76 164 73 167 72', K, 1.6),
        ridges(),
        # половинка с ядром
        ellipse(150, 170, 22, 14, K, 2, K, 0.22),
        path('M132 168C136 158 146 158 150 166C154 158 164 158 168 168C164 180 154 180 150 174C146 180 136 180 132 168Z',
             W, 1.2, '#efe2c2', 0.35),
        path('M138 166C141 163 144 166 146 169M154 169C157 165 160 165 162 168M140 172C143 174 146 172 148 175'
             'M152 175C156 173 159 174 162 172', W, 0.8),
    ]
    body.append(scatter(rng, 's', 7, x0=24, x1=120))
    body.append(scatter(rng, 's', 4, x0=176, x1=196))
    return piece, body


def coconut(rng):
    chip = symbol('s', path('M-4.5-2C-1-3.4 2.5-3 4.6-1.4C5.4.6 3.6 2.6.8 3C-2 3.2-4.6 1.6-5 .2Z', W, 0.9, W, 0.55))
    body = [path('M200 18C180 20 162 32 148 54', '#b9a06a', 2)]
    for i in range(1, 12):
        t = i / 12
        x, y = bezier((200, 18), (186, 19), (162, 32), (148, 54), t)
        for side in (1, -1):
            a = math.radians(100 + side * 38 + i * 3)
            ln = 30 - i * 1.3
            body.append(path(f'M{f(x)} {f(y)}q{f(math.cos(a) * ln * 0.5 + side * 4)} {f(math.sin(a) * ln * 0.3)} '
                             f'{f(math.cos(a) * ln)} {f(math.sin(a) * ln)}', G, 1.3))
    hair = ''.join(f'M{f(x)} {f(y)}l{f(rng.uniform(-3, 3))} {f(rng.uniform(2, 5))}'
                   for x, y in ((rng.uniform(136, 188), rng.uniform(118, 150)) for _ in range(40)))
    body += [
        path('M132 112C132 140 146 158 162 158C178 158 192 140 192 112', K, 2, '#6b4a2b', 0.5),
        path(hair, '#d9b98c', 0.9),
        ellipse(162, 112, 30, 11, K, 2, W, 0.85),
        ellipse(162, 113, 22, 7, W, 0.8, '#3a332a', 0.9),
        # вторая половинка — кусок мякоти
        path('M176 182C182 170 196 168 198 178C196 186 184 190 176 182Z', K, 1.6, '#6b4a2b', 0.5),
        path('M178 180C184 172 194 171 196 177', W, 2),
    ]
    body.append(scatter(rng, 's', 14, x0=24, x1=168))
    return chip, body


def sea_buckthorn(rng):
    berry = symbol('s', circle(0, 0, 4, O, 1.2, O, 0.5) + circle(-1.3, -1.4, 0.9, '#fde2b8', 0.6, '#fde2b8', 1))
    silver = '#bcd3ae'
    twigs = [((200, 12), (184, 44), (170, 92), (162, 158)), ((176, 70), (186, 80), (194, 96), (198, 116)),
             ((166, 116), (152, 104), (140, 100), (128, 100))]
    body = []
    for p0, p1, p2, p3 in twigs:
        body.append(path(f'M{p0[0]} {p0[1]}C{p1[0]} {p1[1]} {p2[0]} {p2[1]} {p3[0]} {p3[1]}', K, 2.2))
    # узкие серебристые листья — пучками у веток
    for (p0, p1, p2, p3), spots in zip(twigs, ((0.08, 0.3, 0.55, 0.98), (0.6, 1.0), (0.7, 1.0))):
        for t in spots:
            x, y = bezier(p0, p1, p2, p3, t)
            for rot in (rng.uniform(-70, -30), rng.uniform(30, 70), rng.uniform(-15, 15) + (180 if t > 0.9 else 0)):
                body.append(leaf(x, y, rot, rng.uniform(20, 27), 2.8, silver, 0.18))
    # ягоды облепляют ветку плотно
    for (p0, p1, p2, p3), (t0, t1, n) in zip(twigs, ((0.18, 0.92, 26), (0.1, 0.55, 9), (0.1, 0.6, 7))):
        for i in range(n):
            t = t0 + (t1 - t0) * i / max(1, n - 1)
            x, y = bezier(p0, p1, p2, p3, t)
            body.append(use('s', x + rng.uniform(-5, 5), y + rng.uniform(-4, 4), rng.uniform(0, 360),
                            rng.uniform(0.85, 1.15)))
    body.append(scatter(rng, 's', 8, s0=0.9, s1=1.1))
    body.append(heap(rng, 's', 9, 108, 186, 14, 5))
    return berry, body


DRAWINGS = {
    'tykvy-shtiriyskoy': pumpkin,
    'chernogo-tmina': nigella,
    'konoplyanoe': hemp,
    'lnyanoe': flax,
    'amarantovoe': amaranth,
    'kedrovoe': cedar,
    'mindalnoe': almond,
    'rastoropshi': thistle,
    'podsolnechnoe': sunflower,
    'ryzhikovoe': camelina,
    'kunzhut-chernyy': sesame_black,
    'kunzhut-neshlifovannyy': sesame_light,
    'gorchichnoe': mustard,
    'gretskogo-oreha': walnut,
    'kokosovoe': coconut,
    'oblepihovoe': sea_buckthorn,
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for index, (slug, draw) in enumerate(DRAWINGS.items()):
        rng = random.Random(slug)
        defs, body = draw(rng)
        svg = HEAD.format(seed=index + 3, defs=defs, body='\n'.join(body))
        (OUT / f'{slug}.svg').write_text(svg, encoding='utf-8')
        print(slug, len(svg))


if __name__ == '__main__':
    main()
