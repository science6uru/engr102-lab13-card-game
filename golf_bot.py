"""Play fun_game's Golf against a bot.

    python golf_bot.py                 you vs the bot (bot is player 2)
    python golf_bot.py --level easy    bot sometimes plays badly
    python golf_bot.py --bot-seat 0    bot is player 1 and moves first
    python golf_bot.py --bot-vs-bot    two bots play each other
"""
import argparse
import random

import pygame

import fun_game as g

EXPECTED = 5.5       # fallback average value of an unknown (face-down) card
HIDDEN_BONUS = 0.2   # small push to turn face-down cards up

# Statistics of a standard single 52-card deck used for inference.
# Scoring: A=1, 2=-2, 3-10=face, J=10, Q=10, K=0  →  4 suits × 71 = 284.
DECK_SIZE = 52
DECK_SUM = 284
RANKS_PER_DECK = 4


class BotContext:
    """Per-turn snapshot of what the bot can actually see.

    Counts every card visible to `seat` (both face-up grids, the whole discard
    pile, and the bot's own hand) so `estimate_grid` can use the true average
    value of the *unseen* cards instead of a fixed constant, and can reason
    about how likely a hidden card is to complete a column pair.
    """

    def __init__(self, state, seat):
        self.seat = seat
        self.rank_seen = {}
        self.seen_count = 0
        self.seen_sum = 0.0
        for player in state["players"]:
            for card in player["grid_occ"]:
                if card is not None and card["face_up"]:
                    self._observe(card)
        for card in state["discard"]:
            self._observe(card)
        for card in state["players"][seat]["hand_occ"]:
            if card is not None:
                self._observe(card)

        self.unseen_count = max(1, DECK_SIZE - self.seen_count)
        unseen_sum = DECK_SUM - self.seen_sum
        # Clamp to the legal value range so a damaged deck size can't blow up.
        self.avg = max(-2.0, min(10.0, unseen_sum / self.unseen_count))

    def _observe(self, card):
        self.seen_count += 1
        self.seen_sum += g.card_value(card)
        rank = card.get("rank")
        if rank is not None:
            self.rank_seen[rank] = self.rank_seen.get(rank, 0) + 1

    def remaining(self, rank):
        return max(0, RANKS_PER_DECK - self.rank_seen.get(rank, 0))

    def pair_prob(self, rank):
        """Probability a random unseen card has the given rank."""
        return self.remaining(rank) / self.unseen_count


def estimate_grid(cards, ctx=None):
    avg = ctx.avg if ctx is not None else EXPECTED
    total = 0.0
    for top, bottom in g.GRID_COLUMNS:
        upper, lower = cards[top], cards[bottom]
        if (upper is not None and lower is not None
                and upper["face_up"] and lower["face_up"]
                and upper["rank"] == lower["rank"]):
            continue
        if ctx is not None and upper is not None and lower is not None:
            u_up, l_up = upper["face_up"], lower["face_up"]
            if u_up and not l_up:
                p = ctx.pair_prob(upper["rank"])
                v = g.card_value(upper)
                # E[column] = (1 - p) * (V + avg) = V + avg*(1-p) - p*V
                total += v + avg * (1.0 - p) - p * v
                continue
            if l_up and not u_up:
                p = ctx.pair_prob(lower["rank"])
                v = g.card_value(lower)
                total += v + avg * (1.0 - p) - p * v
                continue
        for card in (upper, lower):
            if card is None:
                continue
            total += g.card_value(card) if card["face_up"] else avg
    return total


def best_slot(grid, incoming, ctx=None):
    """Returns (slot, gain): where `incoming` lowers the estimated score most."""
    now = estimate_grid(grid, ctx)
    best_index, best_gain = 0, None
    for slot in range(len(grid)):
        trial = list(grid)
        trial[slot] = incoming
        gain = now - estimate_grid(trial, ctx)
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
    # knock_at:  knock when the estimated grid score is this low (None = never)
    LEVELS = {"easy":   {"take_gain": 4.0, "keep_gain": 0.0, "mistakes": 0.3,
                         "knock_at": None},
              "normal": {"take_gain": 2.5, "keep_gain": 0.5, "mistakes": 0.0,
                         "knock_at": 4.0}}

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
        if not state.get("rules_on") or state.get("help_on"):
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
        elif phase == "flip":
            self._flip(state, sfx)

    def _reveal(self, state, sfx):
        """Prefer revealing from a column that has no face-up card yet.

        That leaves a face-down partner behind which can later be flipped for
        free after discarding from the deck, giving a real chance of pairing
        the column.
        """
        grid = state["players"][self.seat]["grid_occ"]
        candidates = []
        for top, bottom in g.GRID_COLUMNS:
            col_has_up = any(
                grid[i] is not None and grid[i]["face_up"] for i in (top, bottom)
            )
            if col_has_up:
                continue
            for i in (top, bottom):
                if grid[i] is not None and not grid[i]["face_up"]:
                    candidates.append(grid[i])
        if not candidates:
            candidates = [c for c in grid if c is not None and not c["face_up"]]
        if candidates:
            g.reveal_card(state, self.rng.choice(candidates), sfx)

    def _should_knock(self, state, ctx):
        if self.cfg["knock_at"] is None or state["ender"] is not None:
            return False
        my_est = estimate_grid(state["players"][self.seat]["grid_occ"], ctx)
        opp_est = estimate_grid(state["players"][1 - self.seat]["grid_occ"], ctx)
        # If the opponent is clearly ahead, don't knock — keep trying to improve.
        if opp_est + 2 < my_est:
            return False
        # Comfortably low score: take the risk-free win.
        if my_est <= self.cfg["knock_at"]:
            return True
        # Far enough ahead that the opponent's one final turn (~3 points of
        # expected improvement) shouldn't be able to overtake.
        return my_est + 4 <= opp_est

    def _draw(self, state, sfx):
        grid = state["players"][self.seat]["grid_occ"]
        ctx = BotContext(state, self.seat)
        if self._should_knock(state, ctx):
            g.knock(state, sfx)
            return
        take = False
        if state["discard"]:
            _, gain = best_slot(grid, state["discard"][-1], ctx)
            take = gain >= self.cfg["take_gain"]
            if self.rng.random() < self.cfg["mistakes"]:
                take = self.rng.random() < 0.5
        if take:
            g.draw_from_discard(state, sfx)
        elif g.draw_from_deck(state, sfx) is None and state["discard"]:
            g.draw_from_discard(state, sfx)

    def _flip(self, state, sfx):
        """Flip the face-down card that has the best chance of completing a pair.

        The expected benefit is pair_probability x (partner's value + average
        hidden value) — i.e. how much the estimate drops if the pair lands.
        Falls back to a random hidden card when no column is eligible.
        """
        grid = state["players"][self.seat]["grid_occ"]
        ctx = BotContext(state, self.seat)
        best_card, best_score = None, -1.0
        for top, bottom in g.GRID_COLUMNS:
            for i, j in ((top, bottom), (bottom, top)):
                card, partner = grid[i], grid[j]
                if card is None or card["face_up"]:
                    continue
                if partner is None or not partner["face_up"]:
                    continue
                p = ctx.pair_prob(partner["rank"])
                benefit = p * (g.card_value(partner) + ctx.avg)
                if benefit > best_score:
                    best_score, best_card = benefit, card
        if best_card is None:
            hidden = [c for c in grid if c is not None and not c["face_up"]]
            best_card = self.rng.choice(hidden) if hidden else None
        if best_card is not None:
            g.flip_after_discard(state, best_card, sfx)
        else:
            g.skip_flip(state)

    def _place(self, state):
        player = state["players"][self.seat]
        held = [c for c in player["hand_occ"] if c is not None]
        if not held:
            return
        held = held[0]
        grid = player["grid_occ"]
        ctx = BotContext(state, self.seat)
        slot, gain = best_slot(grid, held, ctx)
        from_deck = state["drawn_from"] == "deck"
        discard = from_deck and gain < self.cfg["keep_gain"]
        if self.rng.random() < self.cfg["mistakes"]:
            slot = self.rng.randrange(len(grid))
            discard = from_deck and self.rng.random() < 0.3
        target = (g.DISCARD_POS if discard
                  else g.PLAYER_GRID_SLOTS[self.seat][slot])
        held["press_pos"] = tuple(held["pos"])
        g.release_card(held, target, state)


def filter_events(events, state, bot_seats):
    """Ignore clicks, SPACE and K (knock) while it is a bot's turn."""
    if (not state.get("rules_on") or state["phase"] == "scored"
            or state["current"] not in bot_seats):
        return events
    kept = []
    for event in events:
        if event.type == pygame.MOUSEBUTTONDOWN:
            continue
        if (event.type == pygame.KEYDOWN
                and event.key in (pygame.K_SPACE, pygame.K_k)):
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
    state["help_on"] = not both      # how-to-play on launch (not bot vs bot)
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