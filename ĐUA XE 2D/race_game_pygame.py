import os
import math
import wave
import struct
import pygame
import random
import sys

# Better audio init: pre-initialize mixer before pygame.init
pygame.mixer.pre_init(44100, -16, 1, 512)

# --- Configuration ---
SCREEN_W = 600
SCREEN_H = 800
FPS = 60
LANE_COUNT = 3
ROAD_RATIO = 0.56  # portion of width occupied by road

# Player (motorcycle)
PLAYER_COLOR = (0, 200, 255)  # neon cyan for motorcycle body
PLAYER_SPEED = 520  # base px/s (affects some calculations but physics uses accel/vx)

# Enemy colors
ENEMY_COLORS = [(229, 57, 53), (76, 175, 80), (33, 150, 243), (255, 152, 0), (156, 39, 176)]

# Gameplay tuning
INITIAL_ENEMY_SPEED = 220.0
SPEED_INCREASE_PER_SEC = 2.0
INITIAL_SPAWN_INTERVAL = 1100  # ms
MIN_SPAWN_INTERVAL = 420
SPAWN_DECREASE_PER_SCORE = 5  # how spawn interval shrinks per score unit

# Fonts
pygame.font.init()
FONT_LARGE = pygame.font.SysFont(None, 48)
FONT_MED = pygame.font.SysFont(None, 28)
FONT_SMALL = pygame.font.SysFont(None, 20)

# --- Helper functions ---

def clamp(v, a, b):
    return max(a, min(b, v))


# Axis-aligned bounding box collision
def aabb(ax, ay, aw, ah, bx, by, bw, bh):
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def ellipse_rect_collision(cx, cy, rx, ry, rx_x, rx_y, rw, rh):
    """
    Check collision between an axis-aligned ellipse centered at (cx,cy) with radii rx,ry
    and an axis-aligned rectangle at (rx_x, rx_y) with size rw x rh.
    Uses closest-point test: find closest point on rect to ellipse center, then test
    whether that point lies within the normalized ellipse equation.
    """
    # closest point on rectangle to ellipse center
    closest_x = clamp(cx, rx_x, rx_x + rw)
    closest_y = clamp(cy, rx_y, rx_y + rh)

    # compute normalized distance to ellipse center
    if rx == 0 or ry == 0:
        return False
    nx = (closest_x - cx) / rx
    ny = (closest_y - cy) / ry
    return (nx * nx + ny * ny) <= 1.0


def synth_tone(filename, freq=440.0, duration=1.0, volume=0.2):
    """Create a simple sine wave WAV file if it doesn't exist."""
    if os.path.exists(filename):
        return
    framerate = 44100
    amplitude = int(32767 * volume)
    nframes = int(duration * framerate)
    with wave.open(filename, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        for i in range(nframes):
            t = float(i) / framerate
            sample = int(amplitude * math.sin(2.0 * math.pi * freq * t))
            wf.writeframesraw(struct.pack('<h', sample))


def find_audio(basename):
    """Look for user-provided audio file (wav/ogg/mp3) in project root or assets/audio.
    Returns path if found, otherwise None.
    """
    exts = ['.wav', '.ogg', '.mp3']
    candidates = []
    # check root
    for e in exts:
        candidates.append(basename + e)
    # check assets/audio
    for e in exts:
        candidates.append(os.path.join('assets', 'audio', basename + e))
    for p in candidates:
        if os.path.exists(p):
            return p
    return None



# --- Game classes ---
class Road:
    def __init__(self, screen_w, screen_h, lane_count):
        self.w = int(screen_w * ROAD_RATIO)
        self.h = screen_h
        self.x = (screen_w - self.w) // 2
        self.y = 0
        self.lane_count = lane_count
        self.lane_w = self.w / self.lane_count
        self.mark_offset = 0.0
        self.theme = 'city'

    def lane_center(self, i):
        return self.x + self.lane_w * i + self.lane_w / 2

    def update(self, cam_speed, dt):
        # cam_speed in px/s, dt in seconds
        self.mark_offset = (self.mark_offset + cam_speed * dt) % 50

    def draw(self, surf):
        # background by theme
        if getattr(self, 'theme', 'city') == 'desert':
            surf.fill((200, 180, 120))
        elif getattr(self, 'theme', 'city') == 'snow':
            surf.fill((220, 235, 245))
        else:
            surf.fill((43, 122, 43))
        # road
        pygame.draw.rect(surf, (85, 85, 85), (self.x, self.y, self.w, self.h))
        # shoulder
        pygame.draw.rect(surf, (46,46,46), (self.x - 10, 0, 10, self.h))
        pygame.draw.rect(surf, (46,46,46), (self.x + self.w, 0, 10, self.h))
        # lane dashed lines
        dash_h = 30
        gap = 20
        for i in range(1, self.lane_count):
            lx = int(self.x + self.lane_w * i - 3)
            y = -int(self.mark_offset)
            while y < self.h:
                pygame.draw.rect(surf, (255,255,255), (lx, y, 6, dash_h))
                y += dash_h + gap

        # roadside decorations: neon poles and signs
        pole_x_left = self.x - 6
        pole_x_right = self.x + self.w + 6
        pole_y = 20 - int(self.mark_offset % 40)
        while pole_y < self.h:
            # left pole
            if getattr(self, 'theme', 'city') == 'desert':
                pygame.draw.rect(surf, (90,50,20), (pole_x_left-8, pole_y, 6, 40), border_radius=3)
                pygame.draw.rect(surf, (180,160,100), (pole_x_left-12, pole_y+8, 12, 8), border_radius=3)
                pygame.draw.rect(surf, (90,50,20), (pole_x_right+2, pole_y, 6, 40), border_radius=3)
                pygame.draw.rect(surf, (200,200,160), (pole_x_right+2, pole_y+8, 12, 8), border_radius=3)
            elif getattr(self, 'theme', 'city') == 'snow':
                pygame.draw.rect(surf, (40,40,60), (pole_x_left-8, pole_y, 6, 40), border_radius=3)
                pygame.draw.rect(surf, (200,220,240), (pole_x_left-12, pole_y+8, 12, 8), border_radius=3)
                pygame.draw.rect(surf, (40,40,60), (pole_x_right+2, pole_y, 6, 40), border_radius=3)
                pygame.draw.rect(surf, (200,220,240), (pole_x_right+2, pole_y+8, 12, 8), border_radius=3)
            else:
                pygame.draw.rect(surf, (10,10,30), (pole_x_left-8, pole_y, 6, 40), border_radius=3)
                pygame.draw.rect(surf, (0,180,255), (pole_x_left-12, pole_y+8, 12, 8), border_radius=3)
                # right pole
                pygame.draw.rect(surf, (10,10,30), (pole_x_right+2, pole_y, 6, 40), border_radius=3)
                pygame.draw.rect(surf, (255,120,200), (pole_x_right+2, pole_y+8, 12, 8), border_radius=3)
            pole_y += 80


class Player:
    def __init__(self, road: Road):
        # Motorcycle is slimmer and lower than a car
        self.w = int(road.lane_w * 0.45)
        self.h = int(self.w * 0.9)
        self.x = road.lane_center(1) - self.w / 2
        # place lower on screen (closer to bottom)
        self.y = int(SCREEN_H * 0.82 - self.h / 2)

        # Physics properties tuned for a nimble motorcycle
        self.speed = PLAYER_SPEED
        self.color = PLAYER_COLOR
        self.vx = 0.0           # current horizontal velocity
        self.accel = 3000.0     # stronger acceleration for nimble control
        self.friction = 6.0     # slightly less friction for light vehicle
        self.max_vx = 900.0     # higher max horizontal speed

    def move(self, hdir, vdir, dt, road: Road):
        """
        Move the motorcycle with separate horizontal and vertical directions.
        hdir: -1 left, +1 right, 0 none
        vdir: -1 up (forward), +1 down (back), 0 none
        """
        # Horizontal physics
        if hdir != 0:
            self.vx += hdir * self.accel * dt
        # apply friction (exponential) horizontally
        self.vx -= self.vx * min(self.friction * dt, 1)
        # clamp horizontal velocity
        self.vx = clamp(self.vx, -self.max_vx, self.max_vx)

        # Vertical physics - simpler tuned values so bike is nimble
        # reuse accel and friction but scaled
        if not hasattr(self, 'vy'):
            self.vy = 0.0
            self.accel_v = self.accel * 0.7
            self.friction_v = self.friction * 0.9
            self.max_vy = self.max_vx * 0.6

        if vdir != 0:
            self.vy += vdir * self.accel_v * dt
        # vertical friction
        self.vy -= self.vy * min(self.friction_v * dt, 1)
        self.vy = clamp(self.vy, -self.max_vy, self.max_vy)

        # integrate position
        self.x += self.vx * dt
        self.y += self.vy * dt

        # clamp to road bounds (prevent leaving road area vertically and horizontally)
        left_bound = road.x + 6
        right_bound = road.x + road.w - self.w - 6
        top_bound = road.y + 30
        bottom_bound = road.y + road.h - self.h - 18
        if self.x < left_bound:
            self.x = left_bound
            self.vx = 0
        if self.x > right_bound:
            self.x = right_bound
            self.vx = 0
        if self.y < top_bound:
            self.y = top_bound
            self.vy = 0
        if self.y > bottom_bound:
            self.y = bottom_bound
            self.vy = 0

    def draw(self, surf):
        # Top-down motorcycle rendering that matches elliptical hitbox
        # Use the hitbox center and radii for placement so visuals align with collision
        cx, cy, rx, ry = self.get_hitbox()

        # glow/halo matching hitbox
        glow_surf = pygame.Surface((int(rx*2+20), int(ry*2+20)), pygame.SRCALPHA)
        pygame.draw.ellipse(glow_surf, (self.color[0], self.color[1], self.color[2], 38), (10,10, int(rx*2), int(ry*2)))
        glow_rect = glow_surf.get_rect(center=(int(cx), int(cy)))
        surf.blit(glow_surf, glow_rect.topleft, special_flags=pygame.BLEND_RGBA_ADD)

        # body: vertical slim rectangle within ellipse
        body_w = int(rx * 0.9)
        body_h = int(ry * 1.6)
        body_rect = pygame.Rect(int(cx - body_w/2), int(cy - body_h/2), body_w, body_h)
        # darker base
        pygame.draw.rect(surf, (6,6,6), body_rect, border_radius=8)
        # neon body
        pygame.draw.rect(surf, self.color, body_rect.inflate(-4, -6), border_radius=6)

        # wheels (top-down: front and rear small circles centered horizontally)
        wheel_r = max(3, int(min(rx, ry) * 0.28))
        front_y = int(cy - body_h*0.42)
        rear_y = int(cy + body_h*0.42)
        pygame.draw.circle(surf, (20,20,20), (int(cx), front_y), wheel_r)
        pygame.draw.circle(surf, (20,20,20), (int(cx), rear_y), wheel_r)
        pygame.draw.circle(surf, (90,90,90), (int(cx), front_y), max(1, wheel_r-3))
        pygame.draw.circle(surf, (90,90,90), (int(cx), rear_y), max(1, wheel_r-3))

        # handlebars (small line near front)
        hb_len = int(rx * 0.9)
        pygame.draw.line(surf, (200,200,200), (cx - hb_len/2, front_y - int(wheel_r*0.6)), (cx + hb_len/2, front_y - int(wheel_r*0.6)), 2)

        # rider helmet (small circle near center)
        pygame.draw.circle(surf, (220,40,80), (int(cx), int(cy - body_h*0.12)), max(4, int(body_w*0.22)))

        # subtle headlight (front)
        pygame.draw.circle(surf, (255,240,200,120), (int(cx), front_y - int(wheel_r*1.2)), max(4, int(wheel_r*0.8)))

    def get_hitbox(self):
        """Return ellipse center and radii representing vertical ellipse hitbox smaller than sprite."""
        cx = self.x + self.w / 2
        cy = self.y + self.h / 2
        # make vertical ellipse (taller than wide) but overall smaller than a car hitbox
        rx = self.w * 0.42  # horizontal radius
        ry = self.h * 0.6   # vertical radius
        return (cx, cy, rx, ry)


class Particle:
    def __init__(self, x, y, vx, vy, life, color):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.color = color

    def update(self, dt):
        self.life -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt

    def draw(self, surf):
        if self.life <= 0: return
        alpha = int(255 * (self.life / self.max_life))
        s = max(1, int(6 * (self.life / self.max_life)))
        col = (self.color[0], self.color[1], self.color[2], alpha)
        surf_part = pygame.Surface((s*2, s*2), pygame.SRCALPHA)
        pygame.draw.circle(surf_part, col, (s, s), s)
        surf.blit(surf_part, (int(self.x)-s, int(self.y)-s), special_flags=pygame.BLEND_RGBA_ADD)


class Enemy:
    def __init__(self, lane_idx, road: Road, base_speed):
        self.w = int(road.lane_w * 0.72)
        self.h = int(self.w * 1.4)
        self.x = road.lane_center(lane_idx) - self.w / 2
        self.y = -self.h - random.uniform(0, 120)
        self.lane = lane_idx
        self.color = random.choice(ENEMY_COLORS)
        # vary speed a bit
        self.speed = base_speed * random.uniform(0.9, 1.5)

    def update(self, dt, speed_scale=1.0):
        self.y += self.speed * dt * speed_scale

    def draw(self, surf):
        r = pygame.Rect(int(self.x), int(self.y), self.w, self.h)
        pygame.draw.rect(surf, self.color, r, border_radius=8)
        # small wheels
        wheel_w = self.w // 6
        wheel_h = self.h // 6
        pygame.draw.rect(surf, (20,20,20), (r.left+6, r.bottom-wheel_h-4, wheel_w, wheel_h), border_radius=3)
        pygame.draw.rect(surf, (20,20,20), (r.right-6-wheel_w, r.bottom-wheel_h-4, wheel_w, wheel_h), border_radius=3)


class Pickup:
    """Simple pickup object (chicken drumstick) that moves down the screen in a lane."""
    def __init__(self, lane_idx, road: Road, base_speed):
        self.w = int(road.lane_w * 0.42)
        self.h = int(self.w * 0.9)
        self.x = road.lane_center(lane_idx) - self.w / 2
        self.y = -self.h - random.uniform(0, 80)
        self.lane = lane_idx
        self.speed = base_speed * random.uniform(0.9, 1.2)

    def update(self, dt, speed_scale=1.0):
        self.y += self.speed * dt * speed_scale

    def draw(self, surf):
        # draw a stylized drumstick: brown meat circle + bone stem
        cx = int(self.x + self.w/2)
        cy = int(self.y + self.h/2)
        meat_r = max(6, int(min(self.w, self.h) * 0.45))
        # meat
        pygame.draw.circle(surf, (160, 80, 30), (cx - meat_r//4, cy), meat_r)
        # highlight
        pygame.draw.circle(surf, (210, 140, 70), (cx - meat_r//4, cy - meat_r//3), max(2, meat_r//3))
        # bone (stem)
        bone_w = max(4, self.w//6)
        bone_h = max(8, int(self.h*0.5))
        bone_rect = pygame.Rect(cx + meat_r//2 - 4, cy - bone_h//2, bone_w, bone_h)
        pygame.draw.rect(surf, (240,240,230), bone_rect, border_radius=3)
        # bone cap
        pygame.draw.circle(surf, (240,240,230), (bone_rect.centerx, bone_rect.top), bone_w//2)


class Boss(Enemy):
    def __init__(self, lane_idx, road: Road, base_speed, kind='truck'):
        super().__init__(lane_idx, road, base_speed)
        self.kind = kind
        # make boss larger and slower
        self.w = int(road.lane_w * 1.0)
        self.h = int(self.w * 1.6)
        self.x = road.lane_center(lane_idx) - self.w / 2
        self.y = -self.h - 40
        self.speed = base_speed * random.uniform(0.6, 0.95)
        if kind == 'helicopter':
            self.color = (200, 200, 50)
        elif kind == 'police':
            self.color = (30, 60, 220)
        else:
            self.color = (100, 60, 40)


# --- Main game class ---
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption('Đua Xe 2D - Top-down Racing (Pygame)')
        self.clock = pygame.time.Clock()
        self.road = Road(SCREEN_W, SCREEN_H, LANE_COUNT)
        self.player = Player(self.road)
        self.enemies = []
        # particle system (exhaust, flames, dust)
        self.particles = []
        # pickups (chicken drumsticks)
        self.pickups = []

        # schedule next pickup spawn when score reaches this threshold (every 30 points)
        self.next_pickup_score = 30
        # coin popup state and coin threshold for awarding
        self.coins = 0
        self.coin_popups = []  # transient on-screen coin notifications
        self.next_coin_score = 50

        # coins and upgrades (ensure available before reset is called)
        self.coins = 0
        self.upgrades_file = 'upgrades.json'
        self.upgrades = {
            'speed_level': 0,
            'nitro_level': 0,
            'hp_level': 0,
            'selected_map': 'city'
        }
        # try load saved coins and upgrades so shop shows correct coins on start screen
        try:
            import json
            if os.path.exists(self.upgrades_file):
                with open(self.upgrades_file, 'r') as f:
                    data = json.load(f)
                    self.upgrades.update(data.get('upgrades', {}))
                    self.coins = int(data.get('coins', self.coins))
        except Exception:
            pass

        # Audio: generate simple sounds if missing and load
        try:
            # Prefer user-provided audio files if available
            engine_file = find_audio('engine') or 'engine.wav'
            nitro_file = find_audio('nitro') or 'nitro.wav'
            crash_file = find_audio('crash') or 'crash.wav'
            # generate fallback tones only when no user file exists
            if not os.path.exists(engine_file):
                synth_tone('engine.wav', freq=220.0, duration=1.0, volume=0.12)
            if not os.path.exists(nitro_file):
                synth_tone('nitro.wav', freq=440.0, duration=0.6, volume=0.18)
            if not os.path.exists(crash_file):
                synth_tone('crash.wav', freq=80.0, duration=0.8, volume=0.6)
            self.snd_engine = pygame.mixer.Sound(engine_file)
            self.snd_nitro = pygame.mixer.Sound(nitro_file)
            self.snd_crash = pygame.mixer.Sound(crash_file)
            # pickup sound
            pickup_file = find_audio('pickup') or 'pickup.wav'
            if not os.path.exists(pickup_file):
                synth_tone('pickup.wav', freq=660.0, duration=0.25, volume=0.2)
            self.snd_pickup = pygame.mixer.Sound(pickup_file)
            self.engine_channel = pygame.mixer.Channel(3)

            self.nitro_channel = pygame.mixer.Channel(4)
        except Exception:
            self.snd_engine = None
            self.snd_nitro = None
            self.snd_crash = None
            self.engine_channel = None
            self.nitro_channel = None

        # Nitro (boost) state
        self.nitro = False
        self.nitro_multiplier = 2.0  # score multiplier
        self.nitro_speed_boost = 1.7  # speed multiplier while nitro active

        # Screen shake state
        self.shake_time = 0.0
        self.shake_magnitude = 0.0

        # Highscore persistence
        self.highscore_file = 'highscore.txt'
        self.highscore = self.load_highscore()
        self.leaderboard_file = 'leaderboard.txt'
        self.entering_name = False
        self.entered_name = ''

        self.running = True
        self.state = 'start'  # 'start', 'playing', 'gameover'

        self.spawn_timer = 0.0
        self.spawn_interval = INITIAL_SPAWN_INTERVAL
        self.base_enemy_speed = INITIAL_ENEMY_SPEED
        self.score = 0.0
        self.score_rate = 1.0  # multiplier for score gain

        # invulnerability (pickup) state
        self.invulnerable = False
        self.invul_timer = 0.0

        # health
        self.max_hp = 3
        self.hp = self.max_hp

        self.keys = {'left': False, 'right': False}
        # allow up/down for forward/back movement
        self.keys.update({'up': False, 'down': False})

    def reset(self):
        self.player = Player(self.road)
        self.enemies = []
        self.pickups = []
        self.spawn_timer = 0.0
        self.spawn_interval = INITIAL_SPAWN_INTERVAL
        self.base_enemy_speed = INITIAL_ENEMY_SPEED
        self.score = 0.0
        self.state = 'playing'
        self.particles = []
        self.nitro = False
        # reset invulnerability and pickup schedule
        self.invulnerable = False
        self.invul_timer = 0.0
        self.next_pickup_score = 30
        # reset hp
        self.hp = self.max_hp

        # coins and upgrades
        self.coins = 0
        self.upgrades = {
            'speed_level': 0,
            'nitro_level': 0,
            'hp_level': 0,
            'selected_map': 'city'
        }
        self.upgrades_file = 'upgrades.json'
        # reset coin popup state and coin award schedule on new run
        self.coin_popups = []
        self.next_coin_score = 50
        # try load upgrades
        try:
            import json
            if os.path.exists(self.upgrades_file):
                with open(self.upgrades_file, 'r') as f:
                    data = json.load(f)
                    self.upgrades.update(data.get('upgrades', {}))
                    self.coins = int(data.get('coins', self.coins))
        except Exception:
            pass

        # boss spawn schedule
        self.next_boss_score = 500

    def spawn(self):
        # decide whether to spawn 1 or 2 enemies
        desired = 1 if random.random() < 0.7 else 2
        lanes = list(range(self.road.lane_count))

        # determine lanes currently occupied by enemies near the player's area
        threshold_y = self.player.y  # consider enemies above the player's y as occupying
        occupied = set(e.lane for e in self.enemies if e.y < threshold_y)

        free_lanes = [l for l in lanes if l not in occupied]

        # compute maximum new enemies we can spawn while leaving at least one lane free
        max_new = min(desired, len(free_lanes))
        allowed_new = max(0, min(max_new, self.road.lane_count - len(occupied) - 1))

        if allowed_new <= 0:
            # No safe spawn that guarantees a free lane; pick the lane with the farthest nearest enemy to minimize blockage
            lane_gaps = {}
            for l in lanes:
                ys = [e.y for e in self.enemies if e.lane == l]
                # if no enemies in lane, treat as infinite gap
                lane_gaps[l] = min(ys) if ys else float('inf')
            best_lane = max(lane_gaps.items(), key=lambda x: x[1])[0]
            self.enemies.append(Enemy(best_lane, self.road, self.base_enemy_speed))
            return


        if allowed_new == 1:
            lane = random.choice(free_lanes)
            self.enemies.append(Enemy(lane, self.road, self.base_enemy_speed))
            return

        # allowed_new >= 2
        # choose two free lanes
        pair = random.sample(free_lanes, 2)
        self.enemies.append(Enemy(pair[0], self.road, self.base_enemy_speed))
        self.enemies.append(Enemy(pair[1], self.road, self.base_enemy_speed))

        # pickups are spawned on score thresholds elsewhere (every 30 points)

    # Emit particles from the player's exhaust. Called each update.
    def emit_particles(self, dt):
        if self.state != 'playing':
            return
        # spawn rate (particles per second)
        base_rate = 80 if self.nitro else 30
        # expected number to spawn this frame
        expected = base_rate * dt
        count = int(expected)
        if random.random() < (expected - count):
            count += 1

        for _ in range(count):
            # spawn position roughly at rear-center of motorcycle using hitbox
            cx, cy, rx, ry = self.player.get_hitbox()
            px = cx + random.uniform(-rx*0.25, rx*0.25)
            py = cy + ry * 0.7 + random.uniform(0, 6)
            # nitro: flame particles fast and colorful, else grey smoke
            if self.nitro:
                angle = math.radians(random.uniform(85, 95))
                speed = random.uniform(180, 420)
                vx = math.cos(angle) * speed + (self.player.vx * 0.05)
                vy = math.sin(angle) * speed
                life = random.uniform(0.25, 0.6)
                col = (random.randint(30, 80), random.randint(160, 255), random.randint(200,255)) if random.random() < 0.5 else (255,120,20)
            else:
                angle = math.radians(random.uniform(85, 95))
                speed = random.uniform(30, 120)
                vx = math.cos(angle) * speed + (self.player.vx * 0.02)
                vy = math.sin(angle) * speed
                life = random.uniform(0.6, 1.2)
                grey = random.randint(40, 140)
                col = (grey, grey, grey)

            self.particles.append(Particle(px, py, vx, vy, life, col))

    # Load highscore from file, return 0 if missing or invalid
    def load_highscore(self):
        try:
            if os.path.exists(self.highscore_file):
                with open(self.highscore_file, 'r') as f:
                    return int(f.read().strip() or 0)
        except Exception:
            pass
        return 0

    # Save highscore to file
    def save_highscore(self):
        try:
            with open(self.highscore_file, 'w') as f:
                f.write(str(int(self.highscore)))
        except Exception:
            pass

    def update(self, dt):
        if self.state != 'playing':
            return

        # difficulty scaling
        self.base_enemy_speed += SPEED_INCREASE_PER_SEC * dt
        self.spawn_interval = max(MIN_SPAWN_INTERVAL, INITIAL_SPAWN_INTERVAL - (self.score * SPAWN_DECREASE_PER_SCORE))

        # Nitro modifies speed and scoring
        speed_mul = self.nitro_speed_boost if self.nitro else 1.0
        score_mul = self.nitro_multiplier if self.nitro else 1.0

        # update road (visual speed tied to enemy speed)
        self.road.update(self.base_enemy_speed * 0.9 * speed_mul, dt)

        # handle player movement (horizontal and vertical)
        hdir = 0
        if self.keys['left'] and not self.keys['right']:
            hdir = -1
        elif self.keys['right'] and not self.keys['left']:
            hdir = 1
        vdir = 0
        if self.keys.get('up') and not self.keys.get('down'):
            vdir = -1
        elif self.keys.get('down') and not self.keys.get('up'):
            vdir = 1
        # always call move to apply friction even when no input
        self.player.move(hdir, vdir, dt, self.road)

        # audio: engine sound when moving
        try:
            moving = abs(self.player.vx) > 1 or abs(getattr(self.player, 'vy', 0)) > 1
            if self.snd_engine and self.engine_channel:
                if moving and not self.engine_channel.get_busy():
                    self.engine_channel.play(self.snd_engine, loops=-1)
                    self.engine_channel.set_volume(0.22)
                if not moving and self.engine_channel.get_busy():
                    self.engine_channel.fadeout(120)
            # nitro sound
            if self.nitro and self.snd_nitro and self.nitro_channel:
                if not self.nitro_channel.get_busy():
                    self.nitro_channel.play(self.snd_nitro, loops=-1)
                    self.nitro_channel.set_volume(0.28)
            elif not self.nitro and self.nitro_channel and self.nitro_channel.get_busy():
                self.nitro_channel.fadeout(120)
        except Exception:
            pass

        # update enemies
        for e in self.enemies:
            e.update(dt, speed_scale=(1.0 + self.score * 0.0008) * speed_mul)

        # update pickups
        for pk in self.pickups:
            pk.update(dt, speed_scale=(1.0 + self.score * 0.0008) * speed_mul)

        # remove off-screen enemies
        self.enemies = [e for e in self.enemies if e.y <= SCREEN_H + 200]

        # spawn logic
        self.spawn_timer += dt * 1000
        if self.spawn_timer >= self.spawn_interval:
            self.spawn_timer = 0
            self.spawn()

        # spawn pickup every time score crosses next_pickup_score (every 30 points)
        if int(self.score) >= self.next_pickup_score:
            # pick a free lane to place pickup
            lanes = list(range(self.road.lane_count))
            occupied = set(e.lane for e in self.enemies if e.y < self.player.y)
            free = [l for l in lanes if l not in occupied]
            if not free:
                free = lanes
            pl = random.choice(free)
            self.pickups.append(Pickup(pl, self.road, self.base_enemy_speed * 0.9))
            # schedule next
            self.next_pickup_score += 30

        # spawn boss every time score crosses next_boss_score
        if int(self.score) >= self.next_boss_score:
            lanes = list(range(self.road.lane_count))
            lane = random.choice(lanes)
            kind = random.choice(['truck', 'helicopter', 'police'])
            self.enemies.append(Boss(lane, self.road, self.base_enemy_speed * 0.7, kind=kind))
            self.next_boss_score += 500

        # collision detection using player's elliptical hitbox vs enemy rectangles
        px, py, prx, pry = self.player.get_hitbox()

        # pickup collisions first
        for pk in list(self.pickups):
            if aabb(px-prx, py-pry, prx*2, pry*2, pk.x, pk.y, pk.w, pk.h):
                # collect pickup -> invulnerable for 2 seconds
                self.invulnerable = True
                self.invul_timer = 2.0
                try:
                    if self.snd_pickup:
                        pygame.mixer.find_channel().play(self.snd_pickup)
                except Exception:
                    pass
                try:
                    # small visual shake
                    self.shake_time = 0.12
                    self.shake_magnitude = 6.0
                except Exception:
                    pass
                try:
                    self.pickups.remove(pk)
                except ValueError:
                    pass

        for e in self.enemies:
            # shrink enemy rect slightly so hitbox is smaller than a car
            margin_w = e.w * 0.14
            margin_h = e.h * 0.12
            ex = e.x + margin_w/2
            ey = e.y + margin_h/2
            ew = e.w - margin_w
            eh = e.h - margin_h
            if self.invulnerable:
                # if invulnerable, skip collision with enemies
                continue
            if ellipse_rect_collision(px, py, prx, pry, ex, ey, ew, eh):
                # if invulnerable we skip earlier; here take damage
                self.hp -= 1
                # small hit shake and sound
                self.shake_time = 0.28
                self.shake_magnitude = 10.0
                try:
                    if self.snd_crash:
                        pygame.mixer.find_channel().play(self.snd_crash)
                except Exception:
                    pass
                # remove collided enemy to avoid repeated hits
                try:
                    self.enemies.remove(e)
                except ValueError:
                    pass
                # check hp
                if self.hp <= 0:
                    self.state = 'gameover'
                    # stop engine/nitro
                    try:
                        if self.engine_channel: self.engine_channel.fadeout(200)
                        if self.nitro_channel: self.nitro_channel.fadeout(200)
                    except Exception:
                        pass
                    # update highscore
                    if int(self.score) > self.highscore:
                        self.highscore = int(self.score)
                        self.save_highscore()
                    break

        # spawn exhaust / particle effects behind the player
        self.emit_particles(dt)

        # update invulnerability timer
        if self.invulnerable:
            self.invul_timer -= dt
            if self.invul_timer <= 0:
                self.invulnerable = False
                self.invul_timer = 0.0

        # update particles
        for p in self.particles:
            p.update(dt)
        # remove dead particles
        self.particles = [p for p in self.particles if p.life > 0]

        # score increases with time and base_enemy_speed to reflect distance
        self.score += (self.base_enemy_speed * dt * 0.02) * self.score_rate * score_mul

        # award coins every time score crosses next_coin_score
        try:
            if int(self.score) >= self.next_coin_score:
                # award 10 coins and create a popup lasting 0.5s
                self.coins += 10
                self.coin_popups.append({'timer': 0.5, 'text': '+10 Coins'})
                # schedule next award
                self.next_coin_score += 50
                # persist coins and upgrades
                try:
                    import json
                    with open(self.upgrades_file, 'w') as f:
                        json.dump({'upgrades': self.upgrades, 'coins': self.coins}, f)
                except Exception:
                    pass
        except Exception:
            pass

        # update coin popup timers and remove expired
        for cp in list(self.coin_popups):
            cp['timer'] -= dt
            if cp['timer'] <= 0:
                try:
                    self.coin_popups.remove(cp)
                except ValueError:
                    pass

    def draw_text_center(self, surf, text, font, color, y):
        txt = font.render(text, True, color)
        rect = txt.get_rect(center=(SCREEN_W//2, y))
        surf.blit(txt, rect)

    def draw(self):
        # Use an offscreen surface to allow screen-shake offset when blitting
        surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

        # draw scene to surf
        self.road.draw(surf)
        # draw enemies first (behind)
        for e in self.enemies:
            e.draw(surf)
        # draw pickups (behind player but above enemies)
        for pk in self.pickups:
            pk.draw(surf)
        # draw particles behind and above
        for p in self.particles:
            p.draw(surf)
        # draw player on top
        self.player.draw(surf)

        # HUD
        hud_surf = pygame.Surface((210, 48), pygame.SRCALPHA)
        hud_surf.fill((0,0,0,140))
        surf.blit(hud_surf, (12,12))
        score_txt = FONT_MED.render(f"Score: {int(self.score)}", True, (255,255,255))
        surf.blit(score_txt, (18, 22))
        hs_txt = FONT_SMALL.render(f"Best: {int(self.highscore)}", True, (200,200,255))
        surf.blit(hs_txt, (130, 18))

        # HP display
        hp_txt = FONT_SMALL.render(f"HP: {self.hp}/{self.max_hp}", True, (255,180,180))
        surf.blit(hp_txt, (18, 4))

        # invulnerability timer indicator
        if self.invulnerable:
            inv_txt = FONT_SMALL.render(f"Invul: {int(math.ceil(self.invul_timer))}s", True, (255, 200, 80))
            surf.blit(inv_txt, (18, 46))

        # coin popups (transient notifications) - draw stacked under HUD
        if getattr(self, 'coin_popups', None):
            base_y = 72
            for i, cp in enumerate(self.coin_popups):
                t = max(0.0, min(0.5, cp.get('timer', 0.0)))
                alpha = int(255 * (t / 0.5))
                txt_surf = FONT_SMALL.render(cp.get('text', ''), True, (255, 220, 120))
                try:
                    txt_surf.set_alpha(alpha)
                except Exception:
                    pass
                surf.blit(txt_surf, (18, base_y + i * 20))

        # top-right controls hint and nitro indicator
        ctrl_surf = FONT_SMALL.render('Arrows/WASD  •  Hold SPACE = NITRO  •  Diagonal OK', True, (200,200,200))
        surf.blit(ctrl_surf, (SCREEN_W - 420, 18))

        # overlays
        if self.state == 'start':
            overlay = pygame.Surface((420, 180), pygame.SRCALPHA)
            overlay.fill((0,0,0,200))
            rect = overlay.get_rect(center=(SCREEN_W//2, SCREEN_H//2))
            surf.blit(overlay, rect.topleft)
            self.draw_text_center(surf, 'Đua Xe 2D - Neon Arcade', FONT_LARGE, (180,255,255), SCREEN_H//2 - 20)
            self.draw_text_center(surf, 'Press ENTER to Start  •  SPACE for Nitro', FONT_MED, (200,200,200), SCREEN_H//2 + 30)
            # shop removed
            # map selection hints
            self.draw_text_center(surf, "Map: 1)City  2)Desert  3)Snow - Press 1/2/3 to select", FONT_SMALL, (200,200,200), SCREEN_H//2 + 90)

            # shop removed - purchases handled automatically via coins

        if self.state == 'leaderboard':
            overlay = pygame.Surface((560, 540), pygame.SRCALPHA)
            overlay.fill((0,0,0,220))
            rect = overlay.get_rect(center=(SCREEN_W//2, SCREEN_H//2))
            surf.blit(overlay, rect.topleft)
            self.draw_text_center(surf, 'Leaderboard (most recent)', FONT_LARGE, (220,220,220), SCREEN_H//2 - 220)
            try:
                lines = []
                if os.path.exists(self.leaderboard_file):
                    with open(self.leaderboard_file, 'r', encoding='utf-8') as f:
                        lines = f.read().strip().splitlines()[-12:]
                y = SCREEN_H//2 - 170
                for ln in reversed(lines):
                    parts = ln.split(',')
                    if len(parts) >= 3:
                        n, s, d = parts[0], parts[1], parts[2]
                        self.draw_text_center(surf, f"{n} - {s} - {d[:10]}", FONT_SMALL, (200,200,200), y)
                        y += 26
            except Exception:
                pass

        if self.state == 'gameover':
            overlay = pygame.Surface((420, 220), pygame.SRCALPHA)
            overlay.fill((0,0,0,220))
            rect = overlay.get_rect(center=(SCREEN_W//2, SCREEN_H//2))
            surf.blit(overlay, rect.topleft)
            self.draw_text_center(surf, 'Game Over', FONT_LARGE, (255,80,80), SCREEN_H//2 - 50)
            self.draw_text_center(surf, f'Your Score: {int(self.score)}', FONT_MED, (255,255,255), SCREEN_H//2 - 6)
            self.draw_text_center(surf, f'Best: {int(self.highscore)}', FONT_MED, (180,200,255), SCREEN_H//2 + 30)
            self.draw_text_center(surf, 'Press ENTER to Restart', FONT_MED, (200,200,200), SCREEN_H//2 + 80)
            if not self.entering_name:
                self.draw_text_center(surf, "Press 'N' to enter name and save score", FONT_SMALL, (200,200,200), SCREEN_H//2 + 110)
            else:
                self.draw_text_center(surf, f"Enter name: {self.entered_name}_", FONT_SMALL, (220,220,220), SCREEN_H//2 + 110)

        # apply screen shake when present
        if self.shake_time > 0:
            shake_dx = int((random.random() * 2 - 1) * self.shake_magnitude)
            shake_dy = int((random.random() * 2 - 1) * self.shake_magnitude)
        else:
            shake_dx = 0
            shake_dy = 0

        # blit final surface to screen with shake offset
        self.screen.fill((8,8,12))
        self.screen.blit(surf, (shake_dx, shake_dy))

        # decrease shake timer
        if self.shake_time > 0:
            self.shake_time -= 1.0 / FPS
            # decay magnitude
            self.shake_magnitude = max(0.0, self.shake_magnitude * 0.92)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.keys['left'] = True
            if event.key in (pygame.K_RIGHT, pygame.K_d):
                self.keys['right'] = True
            if event.key in (pygame.K_UP, pygame.K_w):
                self.keys['up'] = True
            if event.key in (pygame.K_DOWN, pygame.K_s):
                self.keys['down'] = True
            if event.key == pygame.K_SPACE:
                # enable nitro while space is held
                if self.state == 'playing':
                    self.nitro = True
                    # small shake when nitro engages
                    self.shake_time = 0.18
                    self.shake_magnitude = 6.0
            # shop key removed
            # shop functionality removed (no-op)
            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                if self.state == 'start':
                    self.reset()
                elif self.state == 'gameover':
                    self.reset()
            if self.state == 'gameover' and event.key == pygame.K_n:
                # start entering name
                self.entering_name = True
                self.entered_name = ''
            if self.entering_name:
                if event.key == pygame.K_BACKSPACE:
                    self.entered_name = self.entered_name[:-1]
                elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    # finalize and save leaderboard entry
                    name = (self.entered_name or 'Player')[:32]
                    try:
                        from datetime import datetime
                        with open(self.leaderboard_file, 'a', encoding='utf-8') as f:
                            f.write(f"{name},{int(self.score)},{datetime.utcnow().isoformat()}\n")
                    except Exception:
                        pass
                    self.entering_name = False
                else:
                    # accept printable characters
                    ch = event.unicode
                    if ch and len(self.entered_name) < 32 and ch.isprintable():
                        self.entered_name += ch
            # show leaderboard on start
            if self.state == 'start' and event.key == pygame.K_l:
                # toggle display by temporarily setting state
                self.state = 'leaderboard'
            # map selection on start
            if self.state == 'start' and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                if event.key == pygame.K_1:
                    self.upgrades['selected_map'] = 'city'
                elif event.key == pygame.K_2:
                    self.upgrades['selected_map'] = 'desert'
                else:
                    self.upgrades['selected_map'] = 'snow'
                # apply to road
                self.road.theme = self.upgrades['selected_map']
                # persist
                try:
                    import json
                    with open(self.upgrades_file, 'w') as f:
                        json.dump({'upgrades': self.upgrades, 'coins': self.coins}, f)
                except Exception:
                    pass
            # shop purchases removed
            # shop functionality removed (purchases disabled)
        elif event.type == pygame.KEYUP:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.keys['left'] = False
            if event.key in (pygame.K_RIGHT, pygame.K_d):
                self.keys['right'] = False
            if event.key in (pygame.K_UP, pygame.K_w):
                self.keys['up'] = False
            if event.key in (pygame.K_DOWN, pygame.K_s):
                self.keys['down'] = False
            if event.key == pygame.K_SPACE:
                # disable nitro on release
                self.nitro = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            # support clicking overlay buttons areas (approximate)
            if self.state == 'start':
                mx, my = event.pos
                # if clicked roughly on overlay, start
                ox, oy = SCREEN_W//2 - 180, SCREEN_H//2 - 80
                if ox <= mx <= ox + 360 and oy <= my <= oy + 160:
                    self.reset()
            elif self.state == 'leaderboard':
                # click to return
                self.state = 'start'
            elif self.state == 'gameover':
                mx, my = event.pos
                ox, oy = SCREEN_W//2 - 180, SCREEN_H//2 - 100
                if ox <= mx <= ox + 360 and oy <= my <= oy + 200:
                    self.reset()

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()
        sys.exit()


if __name__ == '__main__':
    game = Game()
    game.run()
