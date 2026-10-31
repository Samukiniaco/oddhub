"""CaVo — labirinto procedural SEMPRE possível: gera perfeito (DFS) e resolve (BFS).

Labirinto perfeito = exatamente 1 caminho entre dois pontos -> impossível de
ser impossível. Paredes viram rects (colisão círculo), caminho viram
checkpoints, orbes patrulham células (sem atravessar parede).
"""
import math
import random
from collections import deque

import pygame

from . import config as C
from .graphics import draw


class Orb:
    """Patrulheiro que manda de volta ao checkpoint (ou começo)."""

    def __init__(self, cx, cy, speed):
        self.c = pygame.Vector2(cx, cy)
        self.p = self.c.copy()
        self.axis = random.choice([(1, 0), (0, 1)])
        self.range = C.MAZE_CELL / 2 - 34
        self.t = random.uniform(0, 6.28)
        self.speed = speed
        self.r = 16

    def update(self, dt):
        self.t += dt * self.speed / max(1.0, self.range)
        k = math.sin(self.t)
        self.p.x = self.c.x + self.axis[0] * k * self.range
        self.p.y = self.c.y + self.axis[1] * k * self.range

    def draw(self, s, off=(0, 0)):
        x, y = int(self.p.x - off[0]), int(self.p.y - off[1])
        pulse = 1.0 + 0.15 * math.sin(self.t * 3)
        draw.circle(s, (255, 70, 70), (x, y), int(self.r * pulse + 4))
        draw.circle(s, (255, 200, 200), (x, y), int(self.r * pulse - 3))


class Maze:
    def __init__(self, diff="normal", seed=None):
        self.diff = diff
        self.rng = random.Random(seed)
        self.cols, self.rows, self.cell = C.MAZE_COLS, C.MAZE_ROWS, C.MAZE_CELL
        w, h = self.cols * self.cell, self.rows * self.cell
        self.x0 = (C.WORLD_W - w) / 2
        self.y0 = (C.WORLD_H - h) / 2
        self._gen()
        self._solve()
        self._populate()

    # ---------- geração (backtracker iterativo) ----------
    def _gen(self):
        cols, rows = self.cols, self.rows
        # open[e] = parede aberta? N,E,S,W por célula
        self.open = [[[False] * 4 for _ in range(cols)] for _ in range(rows)]
        seen = [[False] * cols for _ in range(rows)]
        stack = [(0, 0)]
        seen[0][0] = True
        DIRS = [(0, -1, 0, 2), (1, 0, 1, 3), (0, 1, 2, 0), (-1, 0, 3, 1)]
        while stack:
            x, y = stack[-1]
            opts = []
            for dx, dy, d, back in DIRS:
                nx, ny = x + dx, y + dy
                if 0 <= nx < cols and 0 <= ny < rows and not seen[ny][nx]:
                    opts.append((nx, ny, d, back))
            if not opts:
                stack.pop()
                continue
            nx, ny, d, back = self.rng.choice(opts)
            self.open[y][x][d] = True
            self.open[ny][nx][back] = True
            seen[ny][nx] = True
            stack.append((nx, ny))

    def cell_center(self, cx, cy):
        return pygame.Vector2(self.x0 + (cx + 0.5) * self.cell,
                              self.y0 + (cy + 0.5) * self.cell)

    # ---------- paredes em rects ----------
    def _solve(self):
        t = C.MAZE_WALL
        self.walls = []
        # borda externa
        w, h = self.cols * self.cell, self.rows * self.cell
        self.walls += [pygame.Rect(self.x0 - t, self.y0 - t, w + 2 * t, t),
                       pygame.Rect(self.x0 - t, self.y0 + h, w + 2 * t, t),
                       pygame.Rect(self.x0 - t, self.y0, t, h),
                       pygame.Rect(self.x0 + w, self.y0, t, h)]
        # internas: parede N e W fechada de cada célula (S/E saem das vizinhas)
        for y in range(self.rows):
            for x in range(self.cols):
                cx, cy = self.x0 + x * self.cell, self.y0 + y * self.cell
                if not self.open[y][x][0]:
                    self.walls.append(pygame.Rect(cx - t / 2, cy - t / 2, self.cell + t, t))
                if not self.open[y][x][3]:
                    self.walls.append(pygame.Rect(cx - t / 2, cy - t / 2, t, self.cell + t))
        # resolve (BFS no caminho único) p/ checkpoints
        start, goal = (0, 0), (self.cols - 1, self.rows - 1)
        prev = {start: None}
        dq = deque([start])
        DIRS = [(0, -1, 0), (1, 0, 1), (0, 1, 2), (-1, 0, 3)]
        while dq:
            x, y = dq.popleft()
            if (x, y) == goal:
                break
            for dx, dy, d in DIRS:
                nx, ny = x + dx, y + dy
                if (0 <= nx < self.cols and 0 <= ny < self.rows
                        and self.open[y][x][d] and (nx, ny) not in prev):
                    prev[(nx, ny)] = (x, y)
                    dq.append((nx, ny))
        path, cur = [], goal
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        assert path[0] == start and path[-1] == goal, "labirinto sem caminho?!"
        self.path = path
        self.start = self.cell_center(*start)
        self.goal = self.cell_center(*goal)

    # ---------- checkpoints + orbes ----------
    def _populate(self):
        cfg = C.MAZE_DIFFS[self.diff]
        every = cfg["cp_every"]
        picks = self.path[::every]
        if picks[-1] != self.path[-1]:
            picks.append(self.path[-1])
        self.checkpoints = [self.cell_center(*c) for c in picks]
        used = set(self.path[:2])
        self.orbs = []
        for _ in range(cfg["orbs"]):
            for _try in range(30):
                cx = self.rng.randrange(self.cols)
                cy = self.rng.randrange(self.rows)
                if (cx, cy) not in used:
                    used.add((cx, cy))
                    self.orbs.append(Orb(*self.cell_center(cx, cy), cfg["speed"]))
                    break

    # ---------- física ----------
    def collide(self, p, r, v):
        """Empurra o círculo p/ fora das paredes; zera a velocidade normal."""
        hit = False
        for w in self.walls:
            nx = max(w.left, min(p.x, w.right))
            ny = max(w.top, min(p.y, w.bottom))
            dx, dy = p.x - nx, p.y - ny
            d2 = dx * dx + dy * dy
            if d2 < r * r:
                hit = True
                if d2 > 1e-6:
                    d = math.sqrt(d2)
                    n = (dx / d, dy / d)
                    p.x, p.y = nx + n[0] * r, ny + n[1] * r
                    vn = v.x * n[0] + v.y * n[1]
                    if vn < 0:
                        v.x -= vn * n[0]
                        v.y -= vn * n[1]
                else:  # centro dentro da parede: empurra pelo eixo menor
                    left, right = p.x - w.left, w.right - p.x
                    top, bottom = p.y - w.top, w.bottom - p.y
                    m = min(left, right, top, bottom)
                    if m == left:
                        p.x = w.left - r
                        v.x = min(0, v.x)
                    elif m == right:
                        p.x = w.right + r
                        v.x = max(0, v.x)
                    elif m == top:
                        p.y = w.top - r
                        v.y = min(0, v.y)
                    else:
                        p.y = w.bottom + r
                        v.y = max(0, v.y)
        return hit

    def update(self, dt):
        for o in self.orbs:
            o.update(dt)

    # ---------- desenho ----------
    def draw(self, s, off=(0, 0), cp_idx=0):
        for w in self.walls:
            r = pygame.Rect(w.left - off[0], w.top - off[1], w.width, w.height)
            if not s.get_clip().inflate(100, 100).colliderect(r):
                continue
            draw.rect(s, (52, 60, 92), r, border_radius=6)
            draw.rect(s, (95, 110, 160), r, 1, border_radius=6)
        for i, cp in enumerate(self.checkpoints[:-1]):
            x, y = int(cp.x - off[0]), int(cp.y - off[1])
            done = i < cp_idx
            draw.circle(s, (120, 255, 170) if done else (90, 100, 140), (x, y), 10, 3)
            if done:
                draw.circle(s, (120, 255, 170), (x, y), 4)
        gx, gy = int(self.goal.x - off[0]), int(self.goal.y - off[1])
        for k in range(3):
            draw.rect(s, (255, 215, 90) if k % 2 == 0 else (30, 32, 50),
                             (gx - 18 + k * 12, gy - 18, 12, 36))
        draw.rect(s, (255, 215, 90), (gx - 18, gy - 18, 36, 36), 3)
        for o in self.orbs:
            o.draw(s, off)
