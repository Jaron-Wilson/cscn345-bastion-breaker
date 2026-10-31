"""
Bastion Breaker - a two-player paddle game built with pygame.

Each player guards a wall of bricks with a paddle. Behind the wall is the
player's core. Knock the ball into the other player's bricks to smash them,
and break through to their core for a big score.

Scoring:
    Smash an enemy brick   -> +1 point
    Hit the enemy core      -> +5 points (ball is re-served)
    First player to reach the target score wins.

Controls:
    Left player:   W / S to move, D to hold a power shot
    Right player:  Up / Down to move, Left arrow to hold a power shot
    P pauses, Esc quits.
"""

import random
import sys
from datetime import datetime

import pygame

# ---------------------------------------------------------------------------
# Game settings (constants are in UPPER_CASE so they stand out)
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 960, 600
FPS = 60

CORE_WIDTH = 16            # width of the glowing core strip at each edge
BRICK_ROWS = 8
BRICK_COLUMNS = 2
BRICK_WIDTH = 18
BRICK_GAP = 6

PADDLE_WIDTH = 12
PADDLE_HEIGHT = 100
PADDLE_SPEED = 7
PADDLE_OFFSET = 110        # distance from the screen edge to the paddle

BALL_SIZE = 14
BALL_START_SPEED = 6.0
BALL_MAX_SPEED = 14.0
SPEED_UP_PER_HIT = 0.25    # the ball gets a little faster on every paddle hit
POWER_MULTIPLIER = 1.4     # extra speed from a power shot
POWER_COOLDOWN_MS = 3000   # how long before a power shot can be used again
SERVE_DELAY_MS = 1000      # pause before the ball is served
BANNER_MS = 1200           # how long a scoring message stays on screen

BRICK_POINTS = 1
CORE_POINTS = 5
DEFAULT_TARGET_SCORE = 20
MIN_TARGET_SCORE = 5
MAX_TARGET_SCORE = 99

RESULTS_FILE = "results.txt"

# Colors (red, green, blue)
BACKGROUND = (14, 16, 28)
WHITE = (235, 235, 245)
GRAY = (120, 125, 145)
LEFT_COLOR = (80, 170, 255)
RIGHT_COLOR = (255, 120, 90)
POWER_COLOR = (255, 220, 80)
ERROR_COLOR = (255, 90, 90)


class Paddle:
    """A player's paddle. It moves up and down and can store a power shot."""

    def __init__(self, x, color, up_key, down_key, power_key):
        self.rect = pygame.Rect(x, HEIGHT // 2 - PADDLE_HEIGHT // 2,
                                PADDLE_WIDTH, PADDLE_HEIGHT)
        self.color = color
        self.up_key = up_key
        self.down_key = down_key
        self.power_key = power_key
        self.last_power_time = -POWER_COOLDOWN_MS  # ready at the start

    def move(self, keys):
        """Move the paddle based on which keys are held, staying on screen."""
        if keys[self.up_key]:
            self.rect.y -= PADDLE_SPEED
        if keys[self.down_key]:
            self.rect.y += PADDLE_SPEED
        # Clamp keeps the paddle from leaving the screen
        self.rect.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))

    def power_ready(self, now):
        """True if the cooldown has finished since the last power shot."""
        return now - self.last_power_time >= POWER_COOLDOWN_MS

    def power_charge(self, now):
        """How full the power meter is, from 0.0 (empty) to 1.0 (ready)."""
        return min(1.0, (now - self.last_power_time) / POWER_COOLDOWN_MS)

    def reset(self):
        """Center the paddle and refill the power meter for a new match."""
        self.rect.centery = HEIGHT // 2
        self.last_power_time = -POWER_COOLDOWN_MS


class Ball:
    """The ball. Position is stored as floats so slow angles move smoothly."""

    def __init__(self):
        self.rect = pygame.Rect(0, 0, BALL_SIZE, BALL_SIZE)
        self.x = 0.0
        self.y = 0.0
        self.dx = 0.0
        self.dy = 0.0
        self.powered = False   # True right after a power shot (drawn yellow)

    def serve(self, direction):
        """Place the ball in the center and launch it left (-1) or right (1)."""
        self.x = WIDTH / 2 - BALL_SIZE / 2
        self.y = HEIGHT / 2 - BALL_SIZE / 2
        self.dx = BALL_START_SPEED * direction
        self.dy = random.uniform(-3.0, 3.0)
        self.powered = False
        self.sync_rect()

    def speed(self):
        """Current speed of the ball (length of its velocity)."""
        return (self.dx ** 2 + self.dy ** 2) ** 0.5

    def set_speed(self, new_speed):
        """Keep the ball's direction but change how fast it moves."""
        new_speed = min(new_speed, BALL_MAX_SPEED)
        current = self.speed()
        if current > 0:
            self.dx = self.dx / current * new_speed
            self.dy = self.dy / current * new_speed

    def sync_rect(self):
        """Copy the float position into the pygame Rect used for collisions."""
        self.rect.x = round(self.x)
        self.rect.y = round(self.y)


class Game:
    """Holds all game objects and runs the menu, play and game-over screens."""

    def __init__(self):
        # Error handling: pygame can fail to open a window (no display, bad
        # drivers). Report it clearly instead of crashing with a traceback.
        try:
            pygame.init()
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        except pygame.error as error:
            print(f"Could not start the game window: {error}")
            sys.exit(1)

        pygame.display.set_caption("Bastion Breaker")
        self.clock = pygame.time.Clock()
        self.big_font = self.load_font(64)
        self.font = self.load_font(28)
        self.small_font = self.load_font(20)

        self.left_paddle = Paddle(PADDLE_OFFSET, LEFT_COLOR,
                                  pygame.K_w, pygame.K_s, pygame.K_d)
        self.right_paddle = Paddle(WIDTH - PADDLE_OFFSET - PADDLE_WIDTH,
                                   RIGHT_COLOR, pygame.K_UP, pygame.K_DOWN,
                                   pygame.K_LEFT)
        self.ball = Ball()

        self.state = "menu"        # one of: menu, playing, paused, game_over
        self.target_text = str(DEFAULT_TARGET_SCORE)
        self.target_score = DEFAULT_TARGET_SCORE
        self.menu_error = ""
        self.save_message = ""
        self.winner = ""
        self.banner_text = ""     # big message such as "CORE HIT! +5"
        self.banner_color = WHITE
        self.banner_until = 0     # time (ms) when the banner disappears
        self.new_match()

    @staticmethod
    def load_font(size):
        """Load the default font, falling back to a system font if needed."""
        try:
            return pygame.font.Font(None, size)
        except (pygame.error, OSError):
            return pygame.font.SysFont("arial", size)

    # ------------------------------------------------------------------
    # Match setup
    # ------------------------------------------------------------------
    @staticmethod
    def build_wall(side):
        """Create the bricks for one side ("left" or "right")."""
        bricks = []
        brick_height = HEIGHT // BRICK_ROWS
        for column in range(BRICK_COLUMNS):
            offset = CORE_WIDTH + BRICK_GAP + column * (BRICK_WIDTH + BRICK_GAP)
            if side == "left":
                x = offset
            else:
                x = WIDTH - offset - BRICK_WIDTH
            for row in range(BRICK_ROWS):
                y = row * brick_height + BRICK_GAP // 2
                bricks.append(pygame.Rect(x, y, BRICK_WIDTH,
                                          brick_height - BRICK_GAP))
        return bricks

    def new_match(self):
        """Reset scores, walls, paddles and the ball for a fresh match."""
        self.left_score = 0
        self.right_score = 0
        self.left_bricks = self.build_wall("left")
        self.right_bricks = self.build_wall("right")
        self.left_paddle.reset()
        self.right_paddle.reset()
        self.winner = ""
        self.save_message = ""
        self.banner_until = 0
        self.start_serve(random.choice([-1, 1]))

    def start_serve(self, direction):
        """Freeze the ball in the center, then serve after a short delay."""
        self.ball.serve(direction)
        self.serve_time = pygame.time.get_ticks() + SERVE_DELAY_MS

    def show_banner(self, text, color, duration=BANNER_MS):
        """Flash a message in the middle of the field so players see why
        the score changed."""
        self.banner_text = text
        self.banner_color = color
        self.banner_until = pygame.time.get_ticks() + duration

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def validate_target(self, text):
        """Turn the typed target score into a number, or raise ValueError."""
        if text == "":
            raise ValueError("Please type a target score.")
        value = int(text)   # raises ValueError if text is not a whole number
        if value < MIN_TARGET_SCORE or value > MAX_TARGET_SCORE:
            raise ValueError(f"Target must be between {MIN_TARGET_SCORE} "
                             f"and {MAX_TARGET_SCORE}.")
        return value

    def handle_menu_key(self, event):
        """Typing on the menu screen: digits edit the target, Enter starts."""
        if event.key == pygame.K_RETURN:
            try:
                self.target_score = self.validate_target(self.target_text)
            except ValueError as error:
                # int() gives a technical message, so replace it with ours
                if "invalid literal" in str(error):
                    self.menu_error = "Numbers only, please."
                else:
                    self.menu_error = str(error)
                return
            self.menu_error = ""
            self.new_match()
            self.state = "playing"
        elif event.key == pygame.K_BACKSPACE:
            self.target_text = self.target_text[:-1]
        elif event.unicode and len(self.target_text) < 3:
            # Accept the character for now; validation happens on Enter
            self.target_text += event.unicode

    def handle_events(self):
        """Process window and keyboard events. Returns False to quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_ESCAPE:
                return False

            if self.state == "menu":
                self.handle_menu_key(event)
            elif self.state == "playing" and event.key == pygame.K_p:
                self.state = "paused"
            elif self.state == "paused" and event.key == pygame.K_p:
                self.state = "playing"
            elif self.state == "game_over":
                if event.key == pygame.K_r:
                    self.new_match()
                    self.state = "playing"
                elif event.key == pygame.K_m:
                    self.state = "menu"
        return True

    # ------------------------------------------------------------------
    # Game rules
    # ------------------------------------------------------------------
    def hit_paddle(self, paddle, direction):
        """Bounce the ball off a paddle, aiming it by where it hit."""
        now = pygame.time.get_ticks()
        keys = pygame.key.get_pressed()

        # Where on the paddle did the ball land? -1 = top edge, 1 = bottom
        offset = (self.ball.rect.centery - paddle.rect.centery) / (PADDLE_HEIGHT / 2)
        offset = max(-1.0, min(1.0, offset))

        new_speed = self.ball.speed() + SPEED_UP_PER_HIT
        self.ball.dx = direction * new_speed
        self.ball.dy = offset * new_speed * 0.75
        self.ball.powered = False

        # Power shot: holding the power key at the moment of impact
        if keys[paddle.power_key] and paddle.power_ready(now):
            new_speed *= POWER_MULTIPLIER
            paddle.last_power_time = now
            self.ball.powered = True
            self.show_banner("POWER SHOT!", POWER_COLOR, 700)

        self.ball.set_speed(new_speed)

    def check_bricks(self, bricks):
        """Remove the first brick the ball touches. Returns True on a hit."""
        for brick in bricks:
            if self.ball.rect.colliderect(brick):
                bricks.remove(brick)
                return True
        return False

    def update(self):
        """Move everything and apply the scoring rules for one frame."""
        keys = pygame.key.get_pressed()
        self.left_paddle.move(keys)
        self.right_paddle.move(keys)

        # Wait for the serve delay before the ball starts moving
        if pygame.time.get_ticks() < self.serve_time:
            return

        ball = self.ball

        # Move horizontally first, then check for side-on collisions
        ball.x += ball.dx
        ball.sync_rect()
        if ball.dx < 0 and ball.rect.colliderect(self.left_paddle.rect):
            ball.x = self.left_paddle.rect.right
            self.hit_paddle(self.left_paddle, 1)
        elif ball.dx > 0 and ball.rect.colliderect(self.right_paddle.rect):
            ball.x = self.right_paddle.rect.left - BALL_SIZE
            self.hit_paddle(self.right_paddle, -1)
        elif self.check_bricks(self.left_bricks):
            self.right_score += BRICK_POINTS
            ball.dx = -ball.dx
        elif self.check_bricks(self.right_bricks):
            self.left_score += BRICK_POINTS
            ball.dx = -ball.dx

        # Then move vertically and bounce off the top and bottom walls
        ball.y += ball.dy
        if ball.y <= 0:
            ball.y = 0
            ball.dy = abs(ball.dy)
        elif ball.y >= HEIGHT - BALL_SIZE:
            ball.y = HEIGHT - BALL_SIZE
            ball.dy = -abs(ball.dy)
        ball.sync_rect()
        if self.check_bricks(self.left_bricks):
            self.right_score += BRICK_POINTS
            ball.dy = -ball.dy
        elif self.check_bricks(self.right_bricks):
            self.left_score += BRICK_POINTS
            ball.dy = -ball.dy

        # Core hits: the ball reached the far edge behind a wall
        if ball.rect.left <= CORE_WIDTH:
            self.right_score += CORE_POINTS
            self.show_banner(f"CORE HIT!  Right +{CORE_POINTS}", RIGHT_COLOR)
            self.start_serve(-1)      # serve toward the player who was hit
        elif ball.rect.right >= WIDTH - CORE_WIDTH:
            self.left_score += CORE_POINTS
            self.show_banner(f"CORE HIT!  Left +{CORE_POINTS}", LEFT_COLOR)
            self.start_serve(1)

        self.check_winner()

    def check_winner(self):
        """End the match when a player reaches the target score."""
        if self.left_score >= self.target_score:
            self.winner = "Left player"
        elif self.right_score >= self.target_score:
            self.winner = "Right player"
        else:
            return
        self.state = "game_over"
        self.save_result()

    def save_result(self):
        """Append the match result to a text file. Errors are shown, not fatal."""
        line = (f"{datetime.now():%Y-%m-%d %H:%M}  Left {self.left_score} - "
                f"Right {self.right_score}  Winner: {self.winner}\n")
        try:
            with open(RESULTS_FILE, "a", encoding="utf-8") as results:
                results.write(line)
            self.save_message = f"Result saved to {RESULTS_FILE}"
        except OSError as error:
            self.save_message = f"Could not save result: {error.strerror}"

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw_text(self, text, font, color, center):
        """Draw a line of text centered on a point."""
        surface = font.render(text, True, color)
        self.screen.blit(surface, surface.get_rect(center=center))

    def draw_power_meter(self, paddle, x):
        """Draw a small bar that fills up as the power shot recharges."""
        now = pygame.time.get_ticks()
        width = 120
        outline = pygame.Rect(x - width // 2, 52, width, 8)
        fill = outline.copy()
        fill.width = int(width * paddle.power_charge(now))
        color = POWER_COLOR if paddle.power_ready(now) else GRAY
        pygame.draw.rect(self.screen, color, fill)
        pygame.draw.rect(self.screen, WHITE, outline, 1)

    def draw_field(self):
        """Draw the cores, bricks, paddles, ball and scoreboard."""
        self.screen.fill(BACKGROUND)

        # Dashed center line
        for y in range(0, HEIGHT, 30):
            pygame.draw.rect(self.screen, (40, 44, 64), (WIDTH // 2 - 2, y, 4, 16))

        # Cores at each edge
        pygame.draw.rect(self.screen, LEFT_COLOR, (0, 0, CORE_WIDTH, HEIGHT))
        pygame.draw.rect(self.screen, RIGHT_COLOR,
                         (WIDTH - CORE_WIDTH, 0, CORE_WIDTH, HEIGHT))

        for brick in self.left_bricks:
            pygame.draw.rect(self.screen, LEFT_COLOR, brick, border_radius=3)
        for brick in self.right_bricks:
            pygame.draw.rect(self.screen, RIGHT_COLOR, brick, border_radius=3)

        pygame.draw.rect(self.screen, self.left_paddle.color, self.left_paddle.rect,
                         border_radius=4)
        pygame.draw.rect(self.screen, self.right_paddle.color,
                         self.right_paddle.rect, border_radius=4)

        ball_color = POWER_COLOR if self.ball.powered else WHITE
        pygame.draw.ellipse(self.screen, ball_color, self.ball.rect)

        # Scoreboard
        self.draw_text(str(self.left_score), self.font, LEFT_COLOR, (WIDTH // 4, 30))
        self.draw_text(str(self.right_score), self.font, RIGHT_COLOR,
                       (WIDTH * 3 // 4, 30))
        self.draw_text(f"First to {self.target_score}", self.small_font, GRAY,
                       (WIDTH // 2, 20))
        self.draw_power_meter(self.left_paddle, WIDTH // 4)
        self.draw_power_meter(self.right_paddle, WIDTH * 3 // 4)

        # Messages: "Get ready" before a serve, and the latest scoring banner.
        # Hidden on the pause and game-over screens so they don't clutter them.
        if self.state != "playing":
            return
        now = pygame.time.get_ticks()
        if now < self.serve_time:
            self.draw_text("Get ready...", self.small_font, GRAY,
                           (WIDTH // 2, HEIGHT // 2 + 40))
        if now < self.banner_until:
            self.draw_text(self.banner_text, self.font, self.banner_color,
                           (WIDTH // 2, HEIGHT // 2 - 60))

    def draw_menu(self):
        """Title screen with controls and the target score input."""
        self.screen.fill(BACKGROUND)
        self.draw_text("BASTION BREAKER", self.big_font, WHITE, (WIDTH // 2, 110))
        self.draw_text("Smash their bricks (+1). Hit their core (+5).",
                       self.font, GRAY, (WIDTH // 2, 180))

        self.draw_text("Left:  W / S move,  hold D for a power shot",
                       self.small_font, LEFT_COLOR, (WIDTH // 2, 250))
        self.draw_text("Right:  Up / Down move,  hold Left arrow for a power shot",
                       self.small_font, RIGHT_COLOR, (WIDTH // 2, 280))
        self.draw_text("P pauses and shows the rules,  Esc quits",
                       self.small_font, GRAY,
                       (WIDTH // 2, 310))

        self.draw_text(f"Target score: {self.target_text}_", self.font, WHITE,
                       (WIDTH // 2, 390))
        self.draw_text(f"Type a number from {MIN_TARGET_SCORE} to "
                       f"{MAX_TARGET_SCORE}, then press Enter",
                       self.small_font, GRAY, (WIDTH // 2, 425))
        if self.menu_error:
            self.draw_text(self.menu_error, self.small_font, ERROR_COLOR,
                           (WIDTH // 2, 465))

    def draw_overlay(self, title, lines):
        """Darken the field and show a message box on top of it."""
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 215))
        self.screen.blit(shade, (0, 0))
        self.draw_text(title, self.big_font, WHITE, (WIDTH // 2, HEIGHT // 2 - 60))
        for index, line in enumerate(lines):
            self.draw_text(line, self.small_font, GRAY,
                           (WIDTH // 2, HEIGHT // 2 + index * 30))

    def draw(self):
        """Draw whichever screen matches the current state."""
        if self.state == "menu":
            self.draw_menu()
        else:
            self.draw_field()
            if self.state == "paused":
                self.draw_overlay("PAUSED", [
                    f"Smash a brick: +{BRICK_POINTS}     Hit the core: "
                    f"+{CORE_POINTS}     First to {self.target_score} wins",
                    "Left: W / S, hold D for a power shot",
                    "Right: Up / Down, hold Left arrow for a power shot",
                    f"Power shots recharge in {POWER_COOLDOWN_MS // 1000} seconds "
                    "(yellow bar = ready)",
                    "Press P to resume,  Esc to quit",
                ])
            elif self.state == "game_over":
                self.draw_overlay(f"{self.winner} wins!", [
                    f"Final score  {self.left_score} - {self.right_score}",
                    self.save_message,
                    "R for a rematch,  M for the menu,  Esc to quit",
                ])
        pygame.display.flip()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self):
        """The main game loop: input, update, draw, repeat."""
        running = True
        while running:
            running = self.handle_events()
            if self.state == "playing":
                self.update()
            self.draw()
            self.clock.tick(FPS)


def main():
    """Start the game and make sure pygame always shuts down cleanly."""
    try:
        Game().run()
    except KeyboardInterrupt:
        pass   # Ctrl+C in the terminal: just exit quietly
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
