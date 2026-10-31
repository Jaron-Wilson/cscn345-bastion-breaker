# Bastion Breaker (Lab 8 - Python Game)

Two-player paddle game in pygame. Each player defends a brick wall with a
paddle. Smash an enemy brick for +1, break through to the enemy core for +5.
First to the target score (chosen on the menu, 5-99) wins.

## Run

    pip install pygame
    python bastion_breaker.py

Left: W/S, hold D for a power shot. Right: Up/Down, hold Left arrow.
P pauses, Esc quits. Match results are appended to `results.txt`.

## Where each requirement lives

| Requirement | Where |
|---|---|
| Loops | `Game.run` main loop, `build_wall` nested loops, `check_bricks`, `handle_events` |
| Conditionals | `Game.update` collision/scoring rules, `handle_events` state machine, `check_winner` |
| Naming conventions | `UPPER_CASE` constants, `snake_case` functions/variables, `CapWords` classes |
| Comments | Module docstring, a docstring on every function, inline notes on the rules |
| Two players | Two `Paddle` objects sharing one keyboard |
| Scoring + winner | `BRICK_POINTS` / `CORE_POINTS` in `update`, `check_winner`, game-over screen |
| Error handling | `validate_target` (ValueError on bad menu input), `save_result` (OSError), window start-up (`pygame.error`), font fallback, `main` try/finally |

## Teammates: how to make changes

You don't need to be added to this repo. Any GitHub account can contribute:

1. Click **Fork** (top right of this page) to make your own copy.
2. Edit `bastion_breaker.py` in your fork. You can use the pencil icon on GitHub,
   or clone your fork and edit locally:

       git clone https://github.com/YOUR_USERNAME/cscn345-bastion-breaker.git

3. Commit your changes, then on your fork click **Contribute -> Open pull request**.
4. Describe what you changed. Jaron reviews and merges it.

Test before opening the pull request: `pip install pygame`, then
`python bastion_breaker.py` and play a full match.
