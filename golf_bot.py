"""
Play fun_game's Golf against a bot.

    python golf_bot.py                 you vs the bot (bot is player 2)
    python golf_bot.py --level easy    bot sometimes plays badly
    python golf_bot.py --bot-seat 0    bot is player 1 and moves first
    python golf_bot.py --bot-vs-bot    two bots play each other
"""
import argparse
import random

import pygame

import fun_game as g

EXPECTED = 5.5       # average value of an unknown (face-down) card
HIDDEN_BONUS = 0.2   # small push to turn face-down cards up


def estimate_grid(cards):
    """Estimated score of a grid: face-down cards count EXPECTED."""
    total = 0.0
    for top, bottom in g.GRID_COLUMNS:
        upper, lower = cards[top], cards[bottom]
        if (upper is not None and lower is not None
                and upper["face_up"] and lower["face_up"]
                and upper["rank"] == lower["rank"]):
            continue
        for card in (upper, lower):
            if card is None:
                continue
            total += g.card_value(card) if card["face_up"] else EXPECTED
    return total


def best_slot(grid, incoming):
    """Returns (slot, gain): where `incoming` lowers the estimated score most."""
    now = estimate_grid(grid)
    best_index, best_gain = 0, None
    for slot in range(len(grid)):
        trial = list(grid)
        trial[slot] = incoming
        gain = now - estimate_grid(trial)
        if grid[slot] is not None and not grid[slot]["face_up"]:
            gain += HIDDEN_BONUS
        if best_gain is None or gain > best_gain:
            best_index, best_gain = slot, gain
    return best_index, best_gain


def settled(state):
    """True when no card is moving, flipping, being dealt or dragged."""
    if state["queue"]:
        return False
    for card in state["cards"]:
        if card["motion"] is not None or card["flipping"] or card["dragging"]:
            return False
    return True


class GolfBot:
    """A computer player in seat 0 or 1."""

    # take_gain: how much a discard card must help to take it over the deck
    # keep_gain: how much a deck card must help to keep it over discarding
    # mistakes:  chance per move of a random choice
    LEVELS = {"easy":   {"take_gain": 4.0, "keep_gain": 0.0, "mistakes": 0.3},
              "normal": {"take_gain": 2.5, "keep_gain": 0.5, "mistakes": 0.0}}

    def __init__(self, seat, level="normal", think_time=(0.6, 1.2),
                 auto_continue=False, rng=None):
        self.seat = seat
        self.cfg = self.LEVELS[level]
        self.think_time = think_time
        self.auto_continue = auto_continue
        self.rng = rng or random.Random()
        self._key = None
        self._wait = 0.0

    def update(self, state, dt, sfx):
        """Call once per frame, after input and before g.update."""
        if not state.get("rules_on"):
            return
        phase = state["phase"]

        # a new situation restarts the thinking timer
        key = (state["current"], phase, state["hole"], tuple(state["revealed"]),
               state["drawn_from"], len(state["discard"]))
        if key != self._key:
            self._key = key
            self._wait = self.rng.uniform(*self.think_time)

        if phase == "scored":
            if not self.auto_continue:
                return
        elif state["current"] != self.seat or phase == "round_over":
            return

        if not settled(state):
            return
        self._wait -= dt
        if self._wait > 0:
            return

        if phase == "scored":
            g.continue_after_hole(state, sfx)
        elif phase == "reveal":
            self._reveal(state, sfx)
        elif phase == "draw":
            self._draw(state, sfx)
        elif phase == "place":
            self._place(state)

    def _reveal(self, state, sfx):
        grid = state["players"][self.seat]["grid_occ"]
        hidden = [c for c in grid if c is not None and not c["face_up"]]
        if hidden:
            g.reveal_card(state, self.rng.choice(hidden), sfx)

    def _draw(self, state, sfx):
        grid = state["players"][self.seat]["grid_occ"]
        take = False
        if state["discard"]:
            _, gain = best_slot(grid, state["discard"][-1])
            take = gain >= self.cfg["take_gain"]
            if self.rng.random() < self.cfg["mistakes"]:
                take = self.rng.random() < 0.5
        if take:
            g.draw_from_discard(state, sfx)
        elif g.draw_from_deck(state, sfx) is None and state["discard"]:
            g.draw_from_discard(state, sfx)

    def _place(self, state):
        player = state["players"][self.seat]
        held = [c for c in player["hand_occ"] if c is not None]
        if not held:
            return
        held = held[0]
        grid = player["grid_occ"]
        slot, gain = best_slot(grid, held)
        from_deck = state["drawn_from"] == "deck"
        discard = from_deck and gain < self.cfg["keep_gain"]
        if self.rng.random() < self.cfg["mistakes"]:
            slot = self.rng.randrange(len(grid))
            discard = from_deck and self.rng.random() < 0.3
        target = (g.DISCARD_POS if discard
                  else g.PLAYER_GRID_SLOTS[self.seat][slot])
        # release_card needs a press position to tell a drag from a click
        held["press_pos"] = tuple(held["pos"])
        g.release_card(held, target, state)


def filter_events(events, state, bot_seats):
    """Ignore clicks and SPACE while it is a bot's turn."""
    if (not state.get("rules_on") or state["phase"] == "scored"
            or state["current"] not in bot_seats):
        return events
    kept = []
    for event in events:
        if event.type == pygame.MOUSEBUTTONDOWN:
            continue
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            continue
        kept.append(event)
    return kept


def draw_bot_labels(screen, font, bot_seats):
    """Write "(BOT)" under the label of each bot seat."""
    for seat in bot_seats:
        slots = g.PLAYER_GRID_SLOTS[seat]
        mid_y = (slots[0][1] + slots[2][1]) // 2 + 24
        label = font.render("(BOT)", True, g.TEXT_COLOR)
        if seat == 0:
            screen.blit(label, label.get_rect(midright=(635, mid_y)))
        else:
            screen.blit(label, label.get_rect(midleft=(365, mid_y)))


def main(frames=None, bot_seats=(1,), level="normal"):
    pygame.init()
    screen, refresh_hz, _ = g.create_display()
    both = len(bot_seats) == g.NUM_PLAYERS
    pygame.display.set_caption("Golf - bot vs bot" if both
                               else "Golf - you vs the bot")
    g._bring_window_to_front()
    font = pygame.font.Font(None, 26)
    faces = g.load_deck_faces()
    back = g.load_card_back()
    sfx = g.load_sfx()

    state = g.make_state(g.NUM_PLAYERS)
    state["sfx"] = sfx
    state["rules_on"] = True
    g.reset_table(state, sfx)
    bots = [GolfBot(seat, level, auto_continue=both) for seat in bot_seats]

    clock = pygame.time.Clock()
    frame_count = 0
    running = True
    while running:
        dt = min(clock.tick(refresh_hz or 60) / 1000.0, g.MAX_DT)
        mouse_pos = pygame.mouse.get_pos()
        events = filter_events(pygame.event.get(), state, bot_seats)
        running = g.handle_input(events, state, sfx, mouse_pos)
        for bot in bots:
            bot.update(state, dt, sfx)
        g.update(state, dt, mouse_pos, sfx)

        g.render(screen, state, font, faces, back)
        draw_bot_labels(screen, font, bot_seats)
        g.draw_hud(screen, font, state["message"])
        g.draw_golf_hud(screen, font, g.golf_hud_lines(state))
        pygame.display.flip()

        frame_count += 1
        if frames is not None and frame_count >= frames:
            running = False
    pygame.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Golf against a bot")
    parser.add_argument("--level", choices=sorted(GolfBot.LEVELS),
                        default="normal", help="how well the bot plays")
    parser.add_argument("--bot-seat", type=int, choices=(0, 1), default=1,
                        help="0 = bottom right (moves first), 1 = top left")
    parser.add_argument("--bot-vs-bot", "--selfplay", dest="selfplay",
                        action="store_true", help="two bots play each other")
    args = parser.parse_args()
    seats = (0, 1) if args.selfplay else (args.bot_seat,)
    main(bot_seats=seats, level=args.level)
