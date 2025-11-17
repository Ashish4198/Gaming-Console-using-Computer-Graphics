# arcade_fixed_all.py
# Single-file arcade collection — Tetris + Brick Breaker + Car Avoid + Snake + Space Shooter
# Fixed so every game runs reliably; modular, pygame-based.
# Controls shown in menu and per-game. Install pygame first: pip install pygame

import pygame, sys, random, json
from pathlib import Path
import time, math

pygame.init()
WIDTH, HEIGHT = 900, 720
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Arcade - Fixed Collection")
CLOCK = pygame.time.Clock()
FPS = 60

DATA_DIR = Path(".")
SCORES_FILE = DATA_DIR / "arcade_scores.json"
SETTINGS_FILE = DATA_DIR / "arcade_settings.json"

# defaults
DEFAULT_KEYS = {
    "left": pygame.K_LEFT,
    "right": pygame.K_RIGHT,
    "up": pygame.K_UP,
    "down": pygame.K_DOWN,
    "shoot": pygame.K_SPACE,
    "pause": pygame.K_p,
    "enter": pygame.K_RETURN,
    "escape": pygame.K_ESCAPE
}
DEFAULT_SETTINGS = {"difficulty":"Normal","keys":DEFAULT_KEYS}
# load / save helpers
def load_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default
def save_json(path, data):
    try:
        path.write_text(json.dumps(data, indent=2))
    except Exception:
        pass

SETTINGS = load_json(SETTINGS_FILE, DEFAULT_SETTINGS.copy())
HIGH_SCORES = load_json(SCORES_FILE, {})

# fonts & colors
FONT = pygame.font.SysFont("consolas", 18)
BIG = pygame.font.SysFont("consolas", 34)
XL = pygame.font.SysFont("consolas", 44)
COLS = {
    "bg":(12,14,24),"panel":(24,28,44),"accent":(245,188,66),
    "white":(235,235,235),"muted":(150,150,160),"danger":(220,80,80),
    "good":(80,200,120)
}

def draw_text(surf, txt, x, y, font=FONT, color=None, center=False):
    color = color or COLS["white"]
    r = font.render(txt, True, color)
    rect = r.get_rect()
    if center:
        rect.center = (x,y)
    else:
        rect.topleft = (x,y)
    surf.blit(r, rect)
    return rect

# particle system (tiny)
class Particle:
    def __init__(self,x,y,vx,vy,life,size,color):
        self.x=x; self.y=y; self.vx=vx; self.vy=vy; self.life=life; self.max=life
        self.size=size; self.color=color
    def update(self,dt):
        self.x += self.vx*dt
        self.y += self.vy*dt
        self.life -= dt
    def draw(self,surf):
        if self.life<=0: return
        a = max(0, self.life/self.max)
        col = (int(self.color[0]*a), int(self.color[1]*a), int(self.color[2]*a))
        pygame.draw.circle(surf, col, (int(self.x),int(self.y)), max(1,int(self.size*a)))

class Particles:
    def __init__(self): self.ps=[]
    def emit(self,x,y,n=12,color=(245,188,66)):
        for _ in range(n):
            ang = random.random()*2*math.pi
            sp = random.uniform(40,300)
            vx = math.cos(ang)*sp
            vy = math.sin(ang)*sp
            self.ps.append(Particle(x,y,vx,vy,random.uniform(0.3,0.9),random.uniform(1.8,4.5),color))
    def update(self,dt):
        for p in self.ps: p.update(dt)
        self.ps = [p for p in self.ps if p.life>0]
    def draw(self,surf):
        for p in self.ps: p.draw(surf)

particles = Particles()

# BaseGame with run() loop
class BaseGame:
    name = "Base"
    def __init__(self, difficulty="Normal"):
        self.difficulty = difficulty
        self.paused = False
        self.game_over = False
        self.score = 0
    def handle_event(self, ev): pass
    def update(self, dt): pass
    def draw(self, surf): pass
    def run(self):
        # blocking run loop until user returns to menu
        last = pygame.time.get_ticks()
        while True:
            dt_ms = CLOCK.tick(FPS)
            dt = dt_ms / 1000.0
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT:
                    save_json(SCORES_FILE, HIGH_SCORES)
                    save_json(SETTINGS_FILE, SETTINGS)
                    pygame.quit(); sys.exit()
                # universal escape returns to menu (if game_over or paused)
                if ev.type==pygame.KEYDOWN and ev.key == SETTINGS["keys"]["escape"]:
                    # save score if any
                    if self.score:
                        arr = HIGH_SCORES.get(self.name, []); arr.append(int(self.score)); HIGH_SCORES[self.name] = sorted(arr, reverse=True)[:5]
                        save_json(SCORES_FILE, HIGH_SCORES)
                    return
                self.handle_event(ev)
            if not self.paused and not self.game_over:
                self.update(dt_ms)
            self.draw(SCREEN)
            particles.update(dt)
            particles.draw(SCREEN)
            pygame.display.flip()

# ---------- TETRIS (works already) ----------
class Tetris(BaseGame):
    """
    Tetris - Left/Right/Up/Down, Space hard drop, P pause
    """
    name = "Tetris"
    def __init__(self,difficulty="Normal"):
        super().__init__(difficulty)
        self.cols, self.rows = 10, 20
        self.cell = 28
        self.gx = (WIDTH - self.cols*self.cell)//2
        self.gy = 90
        self.board = [[0]*self.cols for _ in range(self.rows)]
        self.pieces = [
            [[1,1,1,1]], [[1,1],[1,1]], [[0,1,0],[1,1,1]],
            [[0,1,1],[1,1,0]], [[1,1,0],[0,1,1]],
            [[1,0,0],[1,1,1]], [[0,0,1],[1,1,1]]
        ]
        self.colors = [(80,200,250),(240,200,60),(200,120,240),(100,240,120),(240,100,100),(80,120,240),(240,150,60)]
        self.spawn()
        base = {"Easy":700,"Normal":450,"Hard":260}
        self.gravity = base.get(difficulty,450)
        self.lastfall = pygame.time.get_ticks()
        self.score = 0; self.level = 1

    def spawn(self):
        shape = [row[:] for row in random.choice(self.pieces)]
        val = random.randint(1,7)
        self.cur = {"shape":shape,"x":self.cols//2 - len(shape[0])//2,"y":-1,"val":val}

    def rotate(self,s):
        return [list(row) for row in zip(*s[::-1])]

    def valid(self,shape,x,y):
        for r,row in enumerate(shape):
            for c,v in enumerate(row):
                if v:
                    xx,yy = x+c,y+r
                    if xx<0 or xx>=self.cols or yy>=self.rows: return False
                    if yy>=0 and self.board[yy][xx]: return False
        return True

    def lock(self):
        s=self.cur
        for r,row in enumerate(s["shape"]):
            for c,v in enumerate(row):
                if v:
                    yy = s["y"]+r; xx = s["x"]+c
                    if 0<=yy<self.rows: self.board[yy][xx]=s["val"]
                    else: self.game_over=True
        # clear lines
        cleared=0
        new=[]
        for row in self.board:
            if all(row): cleared+=1
            else: new.append(row)
        for _ in range(cleared): new.insert(0,[0]*self.cols)
        self.board=new
        if cleared:
            self.score += cleared*100
            self.level = 1 + self.score//700
            particles.emit(WIDTH//2, self.gy+40, n=18)
        self.spawn()

    def handle_event(self, ev):
        k = SETTINGS["keys"]
        if ev.type==pygame.KEYDOWN:
            if ev.key==k["pause"]:
                self.paused = not self.paused
            if self.paused or self.game_over: return
            if ev.key==k["left"] and self.valid(self.cur["shape"], self.cur["x"]-1, self.cur["y"]): self.cur["x"]-=1
            if ev.key==k["right"] and self.valid(self.cur["shape"], self.cur["x"]+1, self.cur["y"]): self.cur["x"]+=1
            if ev.key==k["up"]:
                r = self.rotate(self.cur["shape"])
                if self.valid(r, self.cur["x"], self.cur["y"]): self.cur["shape"] = r
            if ev.key==k["down"] and self.valid(self.cur["shape"], self.cur["x"], self.cur["y"]+1): 
                self.cur["y"] += 1; self.score += 1
            if ev.key==k["shoot"]: # hard drop
                while self.valid(self.cur["shape"], self.cur["x"], self.cur["y"]+1):
                    self.cur["y"] += 1
                self.lock()

    def update(self, dt):
        now = pygame.time.get_ticks()
        if now - self.lastfall >= self.gravity:
            if self.valid(self.cur["shape"], self.cur["x"], self.cur["y"]+1):
                self.cur["y"] += 1
            else:
                self.lock()
            self.lastfall = now

    def draw(self,surf):
        surf.fill(COLS["bg"])
        draw_text(surf, f"TETRIS  Score:{self.score}  Level:{self.level}", WIDTH//2, 34, BIG, COLS["white"], center=True)
        gx,gy = self.gx,self.gy
        pygame.draw.rect(surf, COLS["panel"], (gx-6,gy-6,self.cols*self.cell+12,self.rows*self.cell+12), border_radius=6)
        for r in range(self.rows):
            for c in range(self.cols):
                v = self.board[r][c]
                rect = pygame.Rect(gx + c*self.cell, gy + r*self.cell, self.cell-1, self.cell-1)
                if v: pygame.draw.rect(surf, self.colors[v-1], rect)
                else: pygame.draw.rect(surf, (8,10,18), rect)
        if self.cur:
            for r,row in enumerate(self.cur["shape"]):
                for c,v in enumerate(row):
                    if v:
                        rect = pygame.Rect(gx + (self.cur["x"]+c)*self.cell, gy + (self.cur["y"]+r)*self.cell, self.cell-1, self.cell-1)
                        pygame.draw.rect(surf, self.colors[self.cur["val"]-1], rect)
        if self.paused:
            draw_text(surf, "PAUSED - press P", WIDTH//2, HEIGHT-40, FONT, COLS["accent"], center=True)
        if self.game_over:
            draw_text(surf, "GAME OVER - press Esc to return to menu", WIDTH//2, HEIGHT-40, FONT, COLS["danger"], center=True)

# ---------- Brick Breaker ----------
class BrickBreaker(BaseGame):
    """
    Brick Breaker - Left/Right move, Space to launch, P pause
    """
    name = "Brick Breaker"
    def __init__(self,difficulty="Normal"):
        super().__init__(difficulty)
        self.pw, self.ph = 120, 14
        self.px = WIDTH//2 - self.pw//2
        self.py = HEIGHT - 90
        self.ball = [WIDTH//2, self.py - 12]
        self.ball_r = 9
        self.ball_v = [4, -5] if difficulty!="Hard" else [5, -7]
        self.launch = False
        self.lives = 3
        self.score = 0
        self.make_level()

    def make_level(self):
        self.bricks=[]
        cols,rows = 9,6
        margin = 80
        bw = (WIDTH - 2*margin)//cols - 6
        for r in range(rows):
            for c in range(cols):
                x = margin + c*(bw+6)
                y = 80 + r*28
                self.bricks.append(pygame.Rect(int(x), int(y), int(bw), 20))

    def handle_event(self, ev):
        k = SETTINGS["keys"]
        if ev.type==pygame.KEYDOWN:
            if ev.key==k["pause"]: self.paused = not self.paused
            if ev.key==k["shoot"] and not self.launch: self.launch = True
            # escape handled by BaseGame.run()

    def update(self, dt):
        if self.paused or self.game_over: return
        k = SETTINGS["keys"]
        keys = pygame.key.get_pressed()
        if keys[k["left"]]: self.px -= 8
        if keys[k["right"]]: self.px += 8
        self.px = max(8, min(WIDTH - self.pw - 8, self.px))
        if not self.launch:
            self.ball[0] = self.px + self.pw//2
            self.ball[1] = self.py - 12
            return
        # move ball
        self.ball[0] += self.ball_v[0]
        self.ball[1] += self.ball_v[1]
        if self.ball[0] <= self.ball_r or self.ball[0] >= WIDTH - self.ball_r:
            self.ball_v[0] *= -1
        if self.ball[1] <= self.ball_r:
            self.ball_v[1] *= -1
        # paddle collision
        paddle = pygame.Rect(self.px, self.py, self.pw, self.ph)
        if paddle.collidepoint(self.ball[0], self.ball[1] + self.ball_r):
            offset = (self.ball[0] - (self.px + self.pw/2)) / (self.pw/2)
            self.ball_v[0] = offset * 6
            self.ball_v[1] = -abs(self.ball_v[1])
        # bricks collision
        hit = None
        for b in self.bricks:
            if b.collidepoint(self.ball[0], self.ball[1]):
                hit = b; break
        if hit:
            self.bricks.remove(hit)
            self.ball_v[1] *= -1
            self.score += 50
            particles.emit(hit.centerx, hit.centery, n=12, color=(200,120,100))
        # bottom
        if self.ball[1] > HEIGHT + 20:
            self.lives -= 1
            if self.lives <= 0:
                self.game_over = True
            else:
                self.launch = False
                self.ball_v = [4 * random.choice((-1,1)), -5]

    def draw(self,surf):
        surf.fill((6,12,20))
        draw_text(surf, f"Brick Breaker  Score:{self.score}  Lives:{self.lives}", WIDTH//2, 34, BIG, COLS["white"], center=True)
        pygame.draw.rect(surf, COLS["accent"], (self.px, self.py, self.pw, self.ph), border_radius=6)
        pygame.draw.circle(surf, COLS["white"], (int(self.ball[0]), int(self.ball[1])), self.ball_r)
        for i,b in enumerate(self.bricks):
            color = (180 - (i%6)*10, 80 + (i%6)*12, 100 + (i%6)*6)
            pygame.draw.rect(surf, color, b, border_radius=6)
        if self.paused:
            draw_text(surf, "PAUSED - press P", WIDTH//2, HEIGHT-40, FONT, COLS["accent"], center=True)
        if self.game_over:
            draw_text(surf, "GAME OVER - press Esc to return to menu", WIDTH//2, HEIGHT-40, FONT, COLS["danger"], center=True)

# ---------- Car Avoid ----------
class CarAvoid(BaseGame):
    """
    Car Avoid - Left/Right to change lanes, avoid obstacles
    """
    name = "Car Avoid"
    def __init__(self,difficulty="Normal"):
        super().__init__(difficulty)
        self.lanes = 3
        self.lw = WIDTH // self.lanes
        self.player_lane = 1
        self.player_y = HEIGHT - 160
        self.obstacles = []
        self.spawn_ms = 800 if difficulty=="Normal" else (1100 if difficulty=="Easy" else 520)
        self.last_spawn = pygame.time.get_ticks()
        self.speed = 4 if difficulty!="Hard" else 6
        self.score = 0

    def spawn(self):
        lane = random.randrange(self.lanes)
        w = self.lw - 60
        x = lane*self.lw + (self.lw - w)//2
        self.obstacles.append(pygame.Rect(int(x), -90, int(w), 70))

    def handle_event(self, ev):
        k = SETTINGS["keys"]
        if ev.type==pygame.KEYDOWN:
            if ev.key==k["pause"]: self.paused = not self.paused
            if ev.key==k["left"]: self.player_lane = max(0, self.player_lane-1)
            if ev.key==k["right"]: self.player_lane = min(self.lanes-1, self.player_lane+1)

    def update(self, dt):
        if self.paused or self.game_over: return
        now = pygame.time.get_ticks()
        if now - self.last_spawn > self.spawn_ms:
            self.spawn(); self.last_spawn = now
            self.spawn_ms = max(250, int(self.spawn_ms*0.98))
            self.speed = min(12, self.speed + 0.05)
        for o in self.obstacles:
            o.y += self.speed
        self.obstacles = [o for o in self.obstacles if o.y < HEIGHT+200]
        px = self.player_lane*self.lw + self.lw//2
        player_rect = pygame.Rect(px-28, self.player_y, 56, 100)
        for o in self.obstacles:
            if player_rect.colliderect(o):
                particles.emit(player_rect.centerx, player_rect.centery, n=20, color=(220,80,80))
                self.game_over = True
        self.score += 1

    def draw(self,surf):
        surf.fill((10,20,10))
        draw_text(surf, f"Car Avoid  Score:{self.score}", WIDTH//2, 34, BIG, COLS["white"], center=True)
        for i in range(1,self.lanes):
            pygame.draw.line(surf, COLS["panel"], (i*self.lw,0), (i*self.lw,HEIGHT), 6)
        px = self.player_lane*self.lw + self.lw//2
        pygame.draw.rect(surf, COLS["accent"], (px-28, self.player_y, 56, 100), border_radius=8)
        for o in self.obstacles:
            pygame.draw.rect(surf, COLS["danger"], o, border_radius=6)
        if self.paused:
            draw_text(surf, "PAUSED - press P", WIDTH//2, HEIGHT-40, FONT, COLS["accent"], center=True)
        if self.game_over:
            draw_text(surf, "CRASHED! Press Esc to menu", WIDTH//2, HEIGHT-40, FONT, COLS["danger"], center=True)

# ---------- Snake ----------
class Snake(BaseGame):
    """
    Snake - Arrow keys to move, eat food to grow
    """
    name = "Snake"
    def __init__(self, difficulty="Normal"):
        super().__init__(difficulty)
        self.grid = 20
        self.cols = WIDTH // self.grid
        self.rows = (HEIGHT - 100) // self.grid
        self.reset()

    def reset(self):
        self.snake = [(self.cols//2, self.rows//2)]
        self.dir = (1,0)
        self.spawn_food()
        self.score = 0
        self.speed = 8 if self.difficulty!="Hard" else 12
        self.last_move = pygame.time.get_ticks()

    def spawn_food(self):
        while True:
            p = (random.randrange(self.cols), random.randrange(self.rows))
            if p not in self.snake:
                self.food = p; break

    def handle_event(self, ev):
        k = SETTINGS["keys"]
        if ev.type==pygame.KEYDOWN:
            if ev.key==k["pause"]: self.paused = not self.paused
            if ev.key==k["left"] and self.dir!=(1,0): self.dir = (-1,0)
            if ev.key==k["right"] and self.dir!=(-1,0): self.dir = (1,0)
            if ev.key==k["up"] and self.dir!=(0,1): self.dir = (0,-1)
            if ev.key==k["down"] and self.dir!=(0,-1): self.dir = (0,1)

    def update(self, dt):
        if self.paused or self.game_over: return
        now = pygame.time.get_ticks()
        if now - self.last_move > 1000//self.speed:
            head = self.snake[0]
            nxt = ((head[0]+self.dir[0])%self.cols, (head[1]+self.dir[1])%self.rows)
            if nxt in self.snake:
                self.game_over = True
            else:
                self.snake.insert(0,nxt)
                if nxt == self.food:
                    self.score += 10
                    self.spawn_food()
                else:
                    self.snake.pop()
            self.last_move = now

    def draw(self,surf):
        surf.fill((6,32,6))
        draw_text(surf, f"Snake  Score:{self.score}", WIDTH//2, 34, BIG, COLS["white"], center=True)
        oy = 90
        for i,(x,y) in enumerate(self.snake):
            color = COLS["accent"] if i>0 else (40,120,200)
            pygame.draw.rect(surf, color, (x*self.grid, oy + y*self.grid, self.grid-2, self.grid-2), border_radius=4)
        pygame.draw.rect(surf, COLS["danger"], (self.food[0]*self.grid, oy + self.food[1]*self.grid, self.grid-2, self.grid-2))
        if self.paused:
            draw_text(surf, "PAUSED - press P", WIDTH//2, HEIGHT-40, FONT, COLS["accent"], center=True)
        if self.game_over:
            draw_text(surf, "GAME OVER - press Esc to return to menu", WIDTH//2, HEIGHT-40, FONT, COLS["danger"], center=True)

# ---------- Space Shooter ----------
class SpaceShooter(BaseGame):
    """
    Space Shooter - Left/Right to move, Space to shoot
    """
    name = "Space Shooter"
    def __init__(self, difficulty="Normal"):
        super().__init__(difficulty)
        self.player = pygame.Rect(WIDTH//2 - 20, HEIGHT-120, 40, 40)
        self.bullets = []
        self.enemies = []
        self.enemy_ms = 800 if difficulty!="Hard" else 420
        self.last_enemy = pygame.time.get_ticks()
        self.score = 0
        self.lives = 3

    def spawn_enemy(self):
        x = random.randint(40, WIDTH-80)
        self.enemies.append(pygame.Rect(x, -40, 36, 36))

    def handle_event(self, ev):
        k = SETTINGS["keys"]
        if ev.type==pygame.KEYDOWN:
            if ev.key==k["pause"]: self.paused = not self.paused
            if ev.key==k["shoot"]:
                self.bullets.append(pygame.Rect(self.player.centerx-4, self.player.top-10, 8, 14))

    def update(self, dt):
        if self.paused or self.game_over: return
        k = SETTINGS["keys"]
        keys = pygame.key.get_pressed()
        speed = 280
        if keys[k["left"]]: self.player.x -= int(speed * dt / 1000.0)
        if keys[k["right"]]: self.player.x += int(speed * dt / 1000.0)
        self.player.x = max(8, min(WIDTH - self.player.width - 8, self.player.x))
        now = pygame.time.get_ticks()
        if now - self.last_enemy > self.enemy_ms:
            self.spawn_enemy(); self.last_enemy = now; self.enemy_ms = max(240, int(self.enemy_ms*0.98))
        # bullets & enemies movement
        for b in self.bullets: b.y -= 10
        for e in self.enemies: e.y += 3
        # collisions
        remove_b=[]; remove_e=[]
        for e in self.enemies:
            if e.colliderect(self.player):
                remove_e.append(e)
                self.lives -= 1
                if self.lives <= 0:
                    self.game_over = True
            for b in self.bullets:
                if e.colliderect(b):
                    remove_e.append(e); remove_b.append(b); self.score += 50
                    particles.emit(e.centerx, e.centery, n=8)
        self.bullets = [b for b in self.bullets if b not in remove_b and b.y > -30]
        self.enemies = [e for e in self.enemies if e not in remove_e and e.y < HEIGHT+40]

    def draw(self,surf):
        surf.fill((2,6,20))
        draw_text(surf, f"Space Shooter  Score:{self.score}  Lives:{self.lives}", WIDTH//2, 34, BIG, COLS["white"], center=True)
        pygame.draw.rect(surf, COLS["good"], self.player)
        for b in self.bullets: pygame.draw.rect(surf, COLS["accent"], b)
        for e in self.enemies: pygame.draw.rect(surf, COLS["danger"], e)
        if self.paused:
            draw_text(surf, "PAUSED - press P", WIDTH//2, HEIGHT-40, FONT, COLS["accent"], center=True)
        if self.game_over:
            draw_text(surf, "GAME OVER - press Esc to return to menu", WIDTH//2, HEIGHT-40, FONT, COLS["danger"], center=True)

# ---------- Menu / Manager ----------
GAMES = [("Tetris", Tetris), ("Brick Breaker", BrickBreaker), ("Car Avoid", CarAvoid), ("Snake", Snake), ("Space Shooter", SpaceShooter)]
menu_idx = 0

def draw_menu():
    SCREEN.fill(COLS["bg"])
    draw_text(SCREEN, "Arcade - Fixed Collection", WIDTH//2, 44, XL, COLS["accent"], center=True)
    draw_text(SCREEN, "Use Up/Down, Enter to pick a game. H:High Scores  S:Settings  Esc:Quit", WIDTH//2, 88, FONT, COLS["muted"], center=True)
    start_y = 150
    for i,(label,cls) in enumerate(GAMES):
        y = start_y + i*78
        w,h = 760,60
        x = (WIDTH - w)//2
        rect = pygame.Rect(x,y,w,h)
        color = (36,46,66) if i==menu_idx else COLS["panel"]
        pygame.draw.rect(SCREEN, color, rect, border_radius=8)
        draw_text(SCREEN, label, x+20, y+8, BIG if i==menu_idx else XL, COLS["white"])
        # high score snippet
        hs = HIGH_SCORES.get(label, [])
        draw_text(SCREEN, f"Top: {hs[0] if hs else 0}", x+w-120, y+18, FONT, COLS["good"])

def settings_screen():
    # simple difficulty toggle
    diffs = ["Easy","Normal","Hard"]
    idx = diffs.index(SETTINGS.get("difficulty","Normal"))
    running = True
    while running:
        SCREEN.fill(COLS["bg"])
        draw_text(SCREEN, "Settings", WIDTH//2, 44, XL, COLS["accent"], center=True)
        draw_text(SCREEN, f"Difficulty: {diffs[idx]} (press Left/Right to change)", WIDTH//2, 120, FONT, COLS["muted"], center=True)
        draw_text(SCREEN, "Press ESC to return", WIDTH//2, HEIGHT-40, FONT, COLS["muted"], center=True)
        pygame.display.flip()
        ev = pygame.event.wait()
        if ev.type==pygame.QUIT:
            save_json(SCORES_FILE, HIGH_SCORES); save_json(SETTINGS_FILE, SETTINGS); pygame.quit(); sys.exit()
        if ev.type==pygame.KEYDOWN:
            if ev.key==pygame.K_ESCAPE:
                SETTINGS["difficulty"] = diffs[idx]; save_json(SETTINGS_FILE, SETTINGS); return
            if ev.key==pygame.K_LEFT:
                idx = (idx - 1) % len(diffs)
            if ev.key==pygame.K_RIGHT:
                idx = (idx + 1) % len(diffs)

def scores_screen():
    running = True
    while running:
        SCREEN.fill(COLS["bg"])
        draw_text(SCREEN, "High Scores", WIDTH//2, 44, XL, COLS["accent"], center=True)
        y = 120
        for name,cls in GAMES:
            draw_text(SCREEN, name, 120, y, BIG, COLS["white"])
            arr = HIGH_SCORES.get(name, [])
            s = ", ".join(str(x) for x in arr) if arr else "—"
            draw_text(SCREEN, s, 420, y, FONT, COLS["muted"])
            y += 48
        draw_text(SCREEN, "Press ESC to return", WIDTH//2, HEIGHT-40, FONT, COLS["muted"], center=True)
        pygame.display.flip()
        ev = pygame.event.wait()
        if ev.type==pygame.QUIT:
            save_json(SCORES_FILE, HIGH_SCORES); save_json(SETTINGS_FILE, SETTINGS); pygame.quit(); sys.exit()
        if ev.type==pygame.KEYDOWN and ev.key==pygame.K_ESCAPE:
            return

def main_loop():
    global menu_idx
    while True:
        draw_menu()
        particles.update(1/60.0)
        particles.draw(SCREEN)
        pygame.display.flip()
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT:
                save_json(SCORES_FILE, HIGH_SCORES); save_json(SETTINGS_FILE, SETTINGS); pygame.quit(); sys.exit()
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_DOWN:
                    menu_idx = (menu_idx + 1) % len(GAMES)
                elif ev.key==pygame.K_UP:
                    menu_idx = (menu_idx - 1) % len(GAMES)
                elif ev.key==pygame.K_RETURN:
                    # launch selected game
                    label, cls = GAMES[menu_idx]
                    game = cls(SETTINGS.get("difficulty","Normal"))
                    game.run()
                elif ev.key==pygame.K_h:
                    scores_screen()
                elif ev.key==pygame.K_s:
                    settings_screen()
                elif ev.key==pygame.K_ESCAPE:
                    save_json(SCORES_FILE, HIGH_SCORES); save_json(SETTINGS_FILE, SETTINGS); pygame.quit(); sys.exit()
            if ev.type==pygame.MOUSEBUTTONDOWN:
                mx,my = ev.pos
                start_y = 150
                for i,(label,cls) in enumerate(GAMES):
                    y = start_y + i*78
                    w,h = 760,60; x=(WIDTH-w)//2
                    if pygame.Rect(x,y,w,h).collidepoint(mx,my):
                        menu_idx = i
                        label, cls = GAMES[menu_idx]
                        game = cls(SETTINGS.get("difficulty","Normal"))
                        game.run()
        CLOCK.tick(FPS)

if __name__ == "__main__":
    # quick startup notice
    save_json(SETTINGS_FILE, SETTINGS)
    save_json(SCORES_FILE, HIGH_SCORES)
    # brief press-any-key screen
    SCREEN.fill(COLS["bg"])
    draw_text(SCREEN, "Arcade - Fixed Collection", WIDTH//2, HEIGHT//2 - 20, XL, COLS["accent"], center=True)
    draw_text(SCREEN, "Press any key to continue", WIDTH//2, HEIGHT//2 + 30, FONT, COLS["muted"], center=True)
    pygame.display.flip()
    ev = pygame.event.wait()
    main_loop()
