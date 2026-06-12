"""Game tunables and constants (no pygame import — safe for tests)."""

# Display
SCREEN_WIDTH = 960
SCREEN_HEIGHT = 600
FPS = 60
TITLE = "Slasher Survivors"

# Player
PLAYER_SPEED = 220.0          # pixels / second
PLAYER_RADIUS = 14
PLAYER_MAX_HP = 100
PLAYER_CONTACT_COOLDOWN = 0.5  # seconds of i-frames after a hit

# Auto-attack
ATTACK_INTERVAL = 0.35        # seconds between shots
ATTACK_RANGE = 320.0          # only fire if an enemy is within this range
BULLET_SPEED = 460.0          # pixels / second
BULLET_RADIUS = 5
BULLET_DAMAGE = 25
BULLET_LIFETIME = 1.5         # seconds

# Enemies
ENEMY_SPEED = 95.0            # pixels / second
ENEMY_RADIUS = 13
ENEMY_HP = 50
ENEMY_CONTACT_DAMAGE = 12
SPAWN_INTERVAL_START = 1.1    # seconds between spawns at t=0
SPAWN_INTERVAL_MIN = 0.25     # fastest spawn rate
SPAWN_RAMP = 0.015            # how much the interval shrinks per second survived
SCORE_PER_KILL = 10

# Colors (R, G, B)
COLOR_BG = (18, 18, 24)
COLOR_PLAYER = (90, 200, 250)
COLOR_ENEMY = (235, 90, 90)
COLOR_BULLET = (250, 230, 120)
COLOR_TEXT = (235, 235, 235)
COLOR_HP_BACK = (70, 30, 30)
COLOR_HP_FRONT = (90, 220, 120)
