import math
import random
import os
import sys
import glob
import time
import statistics
import pygame

os.environ.setdefault("SDL_MOUSE_FOCUS_CLICKTHROUGH", "1")

WINDOW_SIZE = (1000, 660)
CARD_SIZE   = (90, 126)
NUM_PLAYERS = 2
HOLES = 9
SUITS = ["clubs", "diamonds", "hearts", "spades"]
RANKS = ["ace", "2", "3", "4", "5", "6", "7", "8", "9", "10",
         "jack", "queen", "king"]

DECK_POS    = (460, 330)
DISCARD_POS = (600, 330)

# player 1 owns the top-left corner, player 0 the bottom-right
# slots 0,1 = top row of a grid, 2,3 = bottom row (Golf columns: (0,2), (1,3))
PLAYER_GRID_SLOTS = [
    [(700, 415), (810, 415), (700, 550), (810, 550)],   # player 0
    [(190, 110), (300, 110), (190, 245), (300, 245)]]   # player 1

PLAYER_HAND_SLOTS = [[(500, 482)],
                     [(500, 178)]]


def make_card(suit, rank, zone="deck", pos=DECK_POS, face_up=False):
    card = {"suit": suit, "rank": rank,
            "pos": list(pos),  # store as a list, not the original tuple
            "face_up": face_up, "zone": zone, "slot": None, "owner": None,
            "motion": None, "target": [0.0, 0.0],
            "dragging": False,
            "drag_offset": (0.0, 0.0),   # where on the card the mouse grabbed it
            "press_pos": (0.0, 0.0),     # where the mouse was on click
            "pickup_flip": False,       # did begin_drag already flip it?
            "t": 0.0,                    # seconds into a "deal" flight
            "start": [0.0, 0.0],         # where the flight began
            "arc": 0.0,                  # how high the flight arcs
            # polish fields: only update_polish and the flip timer write these
            "vel": [0.0, 0.0],           # px/s, feeds bend and tilt
            "bend": 0.0,                 # strip shear while dragging
            "tilt": 0.0,                 # lean in degrees
            "lift": 0.0,                 # smoothed height above the table
            "wobble_t": 0.0,             # seconds left in the landing wobble
            "flipping": False,           # is the flip spin playing?
            "flip_t": 0.0}               # seconds into the flip spin
    return card


def make_deck():
    deck = []
    for suit in SUITS:
        for rank in RANKS:
            card = make_card(suit, rank)
            deck.append(card)

    return deck


# Stage 2 - PLAYERS, ZONES, SHUFFLING AND DEALING
def reset_card_zone(card, zone, pos=None, slot=None, face_up=None,
                    owner=None):
    """The one way to put a card in a zone and slot (rules call this)."""

    card["zone"] = zone
    card["slot"] = slot
    card["owner"] = owner

    if face_up is not None:
        card["face_up"] = face_up

    if pos is not None:
        card["pos"] = list(pos)  # store as a list, not the original tuple
        card["motion"] = None

    if card["zone"] == "deck" or card["zone"] == "discard":
        card["owner"] = None


def shuffle_deck(deck):
    random.shuffle(deck)


def deal_card(deck, hand):
    """Move the top deck card into the first empty hand slot. Returns the card or None."""
    if not deck:
        return None

    room_check = False
    for spot in hand:
        if spot is None:
            room_check = True
            break

    if not room_check:
        return None

    top_card = deck.pop(0)
    slot = hand.index(None)
    hand[slot] = top_card
    reset_card_zone(top_card, "hand", slot=slot, face_up=True)
    return top_card


def make_state(num_players=NUM_PLAYERS):
    """One dict holding everything the game knows. Plain data, no pygame."""
    state = {"cards": [], "deck": [],
             "players": [{"grid_occ": [None] * len(PLAYER_GRID_SLOTS[i]),
                          "hand_occ": [None] * len(PLAYER_HAND_SLOTS[i]),
                          "score": 0,      # this hole
                          "total": 0}      # running total over all holes
                         for i in range(num_players)],
             "current": 0,
             "message": None, "message_t": 0.0,
             "sfx": None, "queue": [],
             "rules_on": False,   # True = Golf rules (main() turns them on)
             "discard": [],        # the discard pile, top (newest) card LAST
             "phase": "reveal",   # reveal, draw, place, round_over, scored
             "hole": 1,           # which hole is being played (1..HOLES)
             "ender": None,       # player who turned their last card up
             "drawn_from": None,  # "deck" or "discard" during a turn
             "revealed": [0] * num_players}   # flips done while revealing
    return state


# Stage 3 - LOADING PICTURES AND SOUNDS
_last_played = {}

# Assets live next to this file, so the game runs from any directory.
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "assets")


def scale_card(surface):
    return pygame.transform.smoothscale(surface, CARD_SIZE)


def load_card_face(suit, rank):
    filename = f"{rank} of {suit}.png"
    path = os.path.join(ASSETS_DIR, "cards", "fronts", suit, filename)

    image = pygame.image.load(path).convert_alpha()
    return scale_card(image)


def load_deck_faces():
    return {
        (suit, rank): load_card_face(suit, rank)
        for suit in SUITS
        for rank in RANKS
    }


def load_card_back(color="blue"):
    filename = f"card back {color}.png"
    path = os.path.join(ASSETS_DIR, "cards", "backs", filename)

    image = pygame.image.load(path).convert_alpha()
    return scale_card(image)


def load_sfx():
    kinds = [
        "slide",
        "place",
        "shove",
        "fan",
        "shuffle",
        "pack_open",
        "pack_take_out"
    ]

    sfx = {kind: [] for kind in kinds}

    sfx_dir = os.path.join(ASSETS_DIR, "sfx", "cards")

    for kind in kinds:
        # Convert underscores to hyphens for filenames.
        filename_kind = kind.replace("_", "-")

        # Real files are card-slide-*.ogg etc (but card-shuffle.ogg has
        # no number), and the two pack kinds start with "cards-".
        prefix = "cards" if kind.startswith("pack") else "card"
        pattern = os.path.join(sfx_dir, f"{prefix}-{filename_kind}*.ogg")

        files = glob.glob(pattern)

        try:
            sfx[kind] = [
                pygame.mixer.Sound(file)
                for file in files
            ]
        except pygame.error as error:
            print(f"Could not load sound effects: {error}")

    return sfx


def play(sfx, kind):
    """Play a random sound of this kind, never the same variant twice in a row."""
    sounds = sfx.get(kind, [])

    if not sounds:
        return

    if len(sounds) == 1:
        sounds[0].play()
        return

    last = _last_played.get(kind)

    choices = [
        i for i in range(len(sounds))
        if i != last
    ]

    index = random.choice(choices)

    sounds[index].play()

    _last_played[kind] = index


# Stage 4 - DRAWING A STILL TABLE
TABLE_GREEN  = (28, 105, 60)
SLOT_GREEN   = (22, 88, 50)
ACTIVE_GREEN = (70, 170, 105)     # active player's slot outlines
TEXT_COLOR   = (235, 245, 235)


def create_display():
    """Open the window. Returns (screen, refresh_hz, vsynced)."""
    screen = pygame.display.set_mode(WINDOW_SIZE, pygame.SCALED, vsync=1)
    vsynced = pygame.display.is_vsync()
    refresh_hz = pygame.display.get_current_refresh_rate()
    if refresh_hz == 0:                           # headless machines
        refresh_hz = 60
    return screen, refresh_hz, vsynced


def card_rect(card):
    rect = pygame.Rect((0, 0), CARD_SIZE)
    rect.center = (round(card["pos"][0]), round(card["pos"][1]))
    return rect


def current_texture(card, faces, back):
    """Surface to show for the card. The first half of a flip still shows the old side."""
    shown_up = card["face_up"]
    if card["flipping"] and card["flip_t"] / FLIP_DURATION < 0.5:
        shown_up = not shown_up
    if shown_up:
        return faces[(card["suit"], card["rank"])]
    else:
        return back


def draw_card(screen, card, faces, back):
    """Draw one card with its shadow. Resting cards take a fast path."""
    tex = current_texture(card, faces, back)

    if (card["motion"] is None and not card["dragging"]
            and not card["flipping"] and card["wobble_t"] <= 0.0
            and abs(card["bend"]) < 0.5 and abs(card["tilt"]) < 0.5
            and card["lift"] < 0.5):
        rect = card_rect(card)
        shadow = get_resting_shadow()
        screen.blit(shadow, shadow.get_rect(
            center=(rect.centerx + 3, rect.centery + 6)))
        screen.blit(tex, rect)
        return

    progress = (min(card["flip_t"] / FLIP_DURATION, 1.0)
                if card["flipping"] else 0.0)
    squash = abs(math.cos(math.pi * progress))      # width: 1 -> 0 -> 1
    pop = 1.0 + 0.12 * math.sin(math.pi * progress)  # height pops up
    w = max(int(CARD_SIZE[0] * squash), 2)
    h = int(CARD_SIZE[1] * pop)
    scaled = pygame.transform.smoothscale(tex, (w, h))

    # bend: shift 12 vertical strips by a sine curve
    bend = card["bend"]
    pad = int(abs(bend)) + 2
    temp = pygame.Surface((w, h + 2 * pad), pygame.SRCALPHA)
    strips = 12
    strip_w = w / strips
    for i in range(strips):
        t = (i + 0.5) / strips - 0.5
        dy = pad + math.sin(t * math.pi) * bend
        temp.blit(scaled, (i * strip_w, dy),
                  area=(int(i * strip_w), 0, int(math.ceil(strip_w)), h))
    if abs(card["tilt"]) > 0.5:
        temp = pygame.transform.rotozoom(temp, card["tilt"], 1.0)

    # shadow: the higher the card, the bigger, softer, fainter and
    # farther away it is (cheap blur = render small, scale up)
    lift = card["lift"]
    blur_k = 1.6 + lift / 25.0
    spread = 0.92 + lift / 160.0
    alpha = int(90 * max(0.3, 1.0 - lift / 130.0))
    small = pygame.Surface((max(int(w / blur_k), 6),
                            max(int(h / blur_k), 6)), pygame.SRCALPHA)
    pygame.draw.rect(small, (0, 0, 0, alpha), small.get_rect(),
                     border_radius=max(small.get_width() // 10, 2))
    shadow = pygame.transform.smoothscale(
        small, (max(int(w * spread), 6), max(int(h * spread), 6)))
    if abs(card["tilt"]) > 0.5:
        shadow = pygame.transform.rotozoom(shadow, card["tilt"], 1.0)
    cx, cy = card["pos"]
    screen.blit(shadow, shadow.get_rect(
        center=(cx + 3 + lift * 0.35, cy + 6 + lift * 0.6)))
    screen.blit(temp, temp.get_rect(center=(round(cx), round(cy))))


def draw_piles(screen, cards, faces, back, discard=None):
    """Deck: top 3 cards face down. Discard: 3 newest face up, slightly offset."""
    deck_parse_count = 0
    in_discard = []

    for card in cards:
        if card["zone"] == "deck":
            deck_parse_count += 1
        elif card["zone"] == "discard":
            in_discard.append(card)
    if discard:
        in_discard = list(discard)
    top_3_in_discard = in_discard[-3:]

    # cards in deck: bottom layer first, top card drawn LAST (on top).
    for i in range(min(3, deck_parse_count) - 1, -1, -1):
        rect = pygame.Rect((0, 0), CARD_SIZE)
        rect.center = (DECK_POS[0], DECK_POS[1] - 2 * i)
        screen.blit(back, rect)

    move_over = 0
    for card in top_3_in_discard:           # oldest first, newest on top
        rect = card_rect(card)
        rect.move_ip(move_over, move_over)
        screen.blit(current_texture(card, faces, back), rect)
        move_over += 2


def draw_table(screen, font, current=None):
    """Felt, slot outlines, pile outlines and labels."""
    screen.fill(TABLE_GREEN)

    for p in range(NUM_PLAYERS):
        color = ACTIVE_GREEN if p == current else SLOT_GREEN
        for slot in PLAYER_GRID_SLOTS[p] + PLAYER_HAND_SLOTS[p]:
            slot_rect = pygame.Rect((0, 0), CARD_SIZE)
            slot_rect.center = slot
            pygame.draw.rect(screen, color, slot_rect, 3, border_radius=8)
        grid_mid_y = (PLAYER_GRID_SLOTS[p][0][1]
                      + PLAYER_GRID_SLOTS[p][2][1]) // 2
        label = font.render(f"PLAYER {p + 1}", True,
                            ACTIVE_GREEN if p == current else TEXT_COLOR)
        if p == 0:    # bottom-right grid: label sits on its left
            screen.blit(label, label.get_rect(midright=(635, grid_mid_y)))
        else:         # top-left grid: label sits on its right
            screen.blit(label, label.get_rect(midleft=(365, grid_mid_y)))

    for center in (DECK_POS, DISCARD_POS):
        pile_rect = pygame.Rect((0, 0), CARD_SIZE)
        pile_rect.center = center
        pygame.draw.rect(screen, SLOT_GREEN, pile_rect, 3, border_radius=8)

    deck_label = font.render("DECK", True, TEXT_COLOR)
    discard_label = font.render("DISCARD", True, TEXT_COLOR)
    screen.blit(deck_label,
                deck_label.get_rect(midright=(DECK_POS[0] - CARD_SIZE[0]
                                              // 2 - 10, DECK_POS[1])))
    screen.blit(discard_label,
                discard_label.get_rect(midleft=(DISCARD_POS[0] + CARD_SIZE[0]
                                                // 2 + 10, DISCARD_POS[1])))


def render(screen, state, font, faces, back):
    """Table, piles, resting cards, then moving cards on top."""
    draw_table(screen, font, state["current"])
    draw_piles(screen, state["cards"], faces, back, state.get("discard"))
    # resting cards first; dragged and gliding cards LAST so they are
    # never hidden under a card that is standing still
    moving = []
    for card in state["cards"]:
        if card["zone"] in ("hand", "grid"):
            if (card["dragging"] or card["motion"] is not None
                    or card["flipping"]):
                moving.append(card)
            else:
                draw_card(screen, card, faces, back)
    for card in moving:
        draw_card(screen, card, faces, back)


# Stage 5 - THE GAME LOOP, TIME AND VSYNC
MAX_DT = 0.05    # clamp: a stalled frame must not teleport things


def draw_hud(screen, font, message):
    """Controls hint and the current message."""
    hint = font.render("Click deck/discard or SPACE to draw | Drag to place"
                       " | R: new game | Esc quit", True, TEXT_COLOR)
    screen.blit(hint, (12, 10))
    if message:
        surf = font.render(message, True, (255, 230, 120))
        screen.blit(surf, surf.get_rect(center=(WINDOW_SIZE[0] // 2, 60)))


DEAL_PICK_DIST = 90   # px around DECK_POS that counts as clicking the deck


def next_player(state):
    state["current"] = (state["current"] + 1) % len(state["players"])


def handle_input(events, state, sfx, mouse_pos):
    """Send each event to the right function. False = quit.
    With rules_on the Golf functions decide what a click or SPACE means."""
    rules = state.get("rules_on", False)
    for event in events:
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            if event.key == pygame.K_SPACE:
                if rules:
                    golf_space(state, sfx)
                else:
                    deal_to_hand(state, state["current"], sfx)
            elif event.key == pygame.K_TAB:
                if not rules:             # Golf passes the turn by itself
                    next_player(state)
            elif event.key == pygame.K_r:
                state["queue"] = []
                if rules:
                    new_game(state, sfx)
                else:
                    reset_table(state, sfx)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = getattr(event, "pos", mouse_pos)
            if rules:
                golf_press(state, pos, sfx)
            elif _distance(pos, DECK_POS) <= DEAL_PICK_DIST:
                deal_to_hand(state, state["current"], sfx)
            else:
                picked = top_card_at(state["cards"], pos,
                                     owner=state["current"])
                if picked is not None:
                    begin_drag(picked, pos, sfx)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            pos = getattr(event, "pos", mouse_pos)
            for held in state["cards"]:
                if held["dragging"]:
                    release_card(held, pos, state)
    return True


def update(state, dt, mouse_pos, sfx):
    """One step of the world: deal from the queue, move every card, count the message down, score a finished hole."""
    # queue entries are tuples (they cannot be edited), so build a NEW list
    waiting = []
    for delay, player, slot in state["queue"]:
        delay -= dt
        if delay <= 0:
            deal_to_grid(state, player, slot, sfx)
        else:
            waiting.append((delay, player, slot))
    state["queue"] = waiting

    for card in state["cards"]:
        update_card(card, dt, mouse_pos, sfx)

    if state["message_t"] > 0:
        state["message_t"] -= dt
        if state["message_t"] <= 0:
            state["message"] = None
            state["message_t"] = 0.0

    # last turn of the hole is done: score it
    if state.get("rules_on") and state["phase"] == "round_over":
        finish_hole(state, sfx)


def _pacing_lines(frame_times, vsynced, refresh_hz, using_timer):
    """fps, pacing mode and frame-time spread; printed on quit."""
    if len(frame_times) < 2:
        return [], 0.0, 0.0, 0.0
    mean = statistics.mean(frame_times)
    fps = 1.0 / mean if mean > 0 else 0.0
    spread = statistics.pstdev(frame_times) * 1000
    if vsynced and not using_timer:
        mode = f"vsync, target {refresh_hz} Hz"
    else:
        mode = f"cap {refresh_hz or 60} fps"
    lines = [(f"{fps:5.1f} fps", TEXT_COLOR),
             (mode, TEXT_COLOR),
             (f"frame time {mean * 1000:.2f} ms, sd {spread:.2f} ms",
              TEXT_COLOR)]
    return lines, fps, mean * 1000, spread


def _bring_window_to_front():
    """macOS only: make the window active so it takes mouse clicks right away."""
    if sys.platform != "darwin" or pygame.display.get_driver() != "cocoa":
        return
    try:
        from AppKit import NSApplication
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    except Exception:
        pass


def main(frames=None):
    pygame.init()
    screen, refresh_hz, vsynced = create_display()
    pygame.display.set_caption("Golf - 2 players")
    _bring_window_to_front()
    font = pygame.font.Font(None, 26)
    faces = load_deck_faces()
    back = load_card_back()
    sfx = load_sfx()

    state = make_state(NUM_PLAYERS)
    state["sfx"] = sfx
    state["rules_on"] = True
    reset_table(state, sfx)

    clock = pygame.time.Clock()
    using_timer = not vsynced
    target_fps = refresh_hz or 60
    last = time.perf_counter()
    all_times = []
    frame_count = 0
    running = True

    while running:
        now = time.perf_counter()
        raw_dt = now - last
        last = now
        dt = min(raw_dt, MAX_DT)
        if frame_count > 0:
            all_times.append(raw_dt)

        mouse_pos = pygame.mouse.get_pos()
        running = handle_input(pygame.event.get(), state, sfx, mouse_pos)

        update(state, dt, mouse_pos, sfx)

        render(screen, state, font, faces, back)
        draw_hud(screen, font, state["message"])
        draw_golf_hud(screen, font, golf_hud_lines(state))

        pygame.display.flip()
        if using_timer:
            clock.tick(target_fps)

        # If "vsync" did not actually wait, fall back to a timer.
        if (vsynced and not using_timer and refresh_hz
                and len(all_times) == 60
                and statistics.mean(all_times) < 0.5 / refresh_hz):
            using_timer = True

        frame_count += 1
        if frames is not None and frame_count >= frames:
            running = False

    _, fps, mean_ms, sd_ms = _pacing_lines(all_times, vsynced,
                                           refresh_hz, using_timer)
    mode = "vsync" if vsynced and not using_timer else "timer"
    print(f"pacing: {frame_count} frames, {fps:.1f} fps, "
          f"{mean_ms:.2f} ms mean, {sd_ms:.2f} ms sd, {mode}")
    pygame.quit()


# Stage 6 - PICKING CARDS UP WITH THE MOUSE
DRAG_FOLLOW = 26     # how fast a dragged card catches up with the mouse


def blend(rate, dt):
    """Fraction of the remaining distance to cover this frame; same real time at any fps."""
    return 1 - math.exp(-rate * dt)


def top_card_at(cards, point, owner=None):
    """Topmost clickable card at point (hand or grid, not moving), optionally one owner's only."""
    for card in reversed(cards):
        if card["zone"] not in ("hand", "grid"):
            continue
        if card["motion"] is not None:
            continue
        if owner is not None and card["owner"] != owner:
            continue
        if card_rect(card).collidepoint(point):
            return card
    return None


def begin_drag(card, mouse_pos, sfx):
    """Pick a card up. A face-down card is flipped as it is lifted."""
    card["dragging"] = True
    card["drag_offset"] = (card["pos"][0] - mouse_pos[0],
                           card["pos"][1] - mouse_pos[1])
    card["press_pos"] = tuple(mouse_pos)
    card["pickup_flip"] = not card["face_up"]
    if card["pickup_flip"]:
        flip_card(card, sfx)
    play(sfx, "slide")


def update_drag(card, mouse_pos, dt):
    """Ease the card toward the mouse (plus the grab offset)."""
    target_x = mouse_pos[0] + card["drag_offset"][0]
    target_y = mouse_pos[1] + card["drag_offset"][1]
    k = blend(DRAG_FOLLOW, dt)
    card["pos"][0] += (target_x - card["pos"][0]) * k
    card["pos"][1] += (target_y - card["pos"][1]) * k


# Stage 7 - FLIPPING AND CLICKING
CLICK_DIST = 8   # px: moved less than this since the press = a click


def flip_card(card, sfx):
    """Turn the card over now (face_up changes immediately); the spin is only visual. Ignored while spinning."""
    if card["flipping"]:
        return
    card["face_up"] = not card["face_up"]
    card["flipping"] = True
    card["flip_t"] = 0.0
    play(sfx, "shove")


def release_card(card, mouse_pos, state):
    """Let go of a dragged card: a click puts it back, otherwise discard, place/swap or go home.
    Only decides; send_card moves the card."""
    card["dragging"] = False
    revealed_on_pickup = card["pickup_flip"]
    card["pickup_flip"] = False

    moved = math.hypot(mouse_pos[0] - card["press_pos"][0],
                       mouse_pos[1] - card["press_pos"][1])
    rules = state.get("rules_on", False)
    if moved < CLICK_DIST:
        if rules:
            # Golf: clicking a held card never flips it. Put it back
            # exactly in its slot so it is not left a few pixels off.
            send_card(card, _home_pos(card), card["zone"], card["slot"],
                      owner=card["owner"])
        elif not revealed_on_pickup:
            flip_card(card, state["sfx"])
        return

    owner = card["owner"]
    player = state["players"][owner]
    old_zone, old_slot = card["zone"], card["slot"]
    if old_zone == "hand":
        old_occ = player["hand_occ"]
        home = PLAYER_HAND_SLOTS[owner][old_slot]
    else:
        old_occ = player["grid_occ"]
        home = PLAYER_GRID_SLOTS[owner][old_slot]

    # a) discard
    if _distance(mouse_pos, DISCARD_POS) <= SNAP_DIST:
        if rules and not legal_move(state, card, ("discard", None)):
            send_card(card, home, old_zone, old_slot, owner=owner)
            return                  # the rules forbid it: go home
        old_occ[old_slot] = None
        send_card(card, DISCARD_POS, "discard", None, face_up=True)
        _push_discard(state, card)
        if rules:
            next_turn(state)
        return

    # b) nearest slot of the card's OWN player's grid
    slots = PLAYER_GRID_SLOTS[owner]
    distances = [_distance(mouse_pos, slot_pos) for slot_pos in slots]
    nearest = distances.index(min(distances))
    if distances[nearest] <= SNAP_DIST:
        if old_zone == "grid" and nearest == old_slot:
            # dropped on its own slot: settle back in it
            send_card(card, slots[nearest], "grid", nearest, owner=owner)
            return
        if rules and not legal_move(state, card, ("grid", nearest)):
            send_card(card, home, old_zone, old_slot, owner=owner)
            return                  # the rules forbid it: go home
        occupant = player["grid_occ"][nearest]
        old_occ[old_slot] = None
        if occupant is not None:
            send_card(occupant, DISCARD_POS, "discard", None, face_up=True)
            _push_discard(state, occupant)
        player["grid_occ"][nearest] = card
        send_card(card, slots[nearest], "grid", nearest, owner=owner)
        if rules:
            next_turn(state)
        return

    # c) nowhere useful: go home (the occupancy lists stay as they were)
    send_card(card, home, old_zone, old_slot, owner=owner)


# Stage 8 - PLACING, SWAPPING, DISCARDING
SNAP_DIST = 80   # px: how close the mouse must be to a slot or the discard


def _distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _push_discard(state, card):
    state.setdefault("discard", []).append(card)


def _home_pos(card):
    table = PLAYER_HAND_SLOTS if card["zone"] == "hand" else PLAYER_GRID_SLOTS
    return table[card["owner"]][card["slot"]]


def send_card(card, target, zone, slot, face_up=None, owner=None):
    """Make the card glide to target and update its zone, slot and face_up.
    Pass owner= for hand and grid, or the card loses its owner."""
    reset_card_zone(card, zone, slot=slot, face_up=face_up, owner=owner)
    card["motion"] = "glide"
    card["target"] = list(target)


# Stage 9 - MOVEMENT OVER TIME: GLIDING AND DEALING
GLIDE = 12           # how fast a gliding card closes the distance
DEAL_TIME = 0.55     # seconds a dealt card takes to fly
DEAL_ARC = 130       # px: how high the flight arcs above the straight line
ARRIVE_DIST = 2      # px: this close to the target = arrived


def update_motion(card, dt, mouse_pos, sfx):
    """Advance one card by dt: dragging, gliding or dealing."""
    if card["dragging"]:
        update_drag(card, mouse_pos, dt)
    elif card["motion"] == "glide":
        k = blend(GLIDE, dt)
        card["pos"][0] += (card["target"][0] - card["pos"][0]) * k
        card["pos"][1] += (card["target"][1] - card["pos"][1]) * k
        if _distance(card["pos"], card["target"]) < ARRIVE_DIST:
            card["pos"] = list(card["target"])
            card["motion"] = None
            card["wobble_t"] = WOBBLE_TIME
            play(sfx, "place")
    elif card["motion"] == "deal":
        card["t"] += dt
        p = min(card["t"] / DEAL_TIME, 1)     # clamp: never overshoot
        ease = p * p * (3 - 2 * p)
        start, target = card["start"], card["target"]
        card["pos"][0] = start[0] + (target[0] - start[0]) * ease
        card["pos"][1] = (start[1] + (target[1] - start[1]) * ease
                          - card["arc"] * math.sin(math.pi * p))
        if p >= 1:
            card["pos"] = list(target)
            card["motion"] = None
            play(sfx, "place")

    # the flip spin runs on its own timer, whatever else the card is doing
    if card["flipping"]:
        card["flip_t"] += dt
        if card["flip_t"] >= FLIP_DURATION:
            card["flipping"] = False
            card["flip_t"] = 0.0


def update_card(card, dt, mouse_pos, sfx):
    """Motion first (may change state), then polish (writes only its own fields)."""
    prev = list(card["pos"])
    update_motion(card, dt, mouse_pos, sfx)
    update_polish(card, dt, prev)


def _start_deal_flight(card, target):
    card["motion"] = "deal"
    card["t"] = 0.0
    card["start"] = list(card["pos"])
    card["target"] = list(target)
    card["arc"] = DEAL_ARC


def deal_to_hand(state, player, sfx):
    """Deal the top card into the player's hand. Returns the card or None."""
    if not state["deck"]:
        state["message"] = "deck is empty!"
        state["message_t"] = 1.5
        return None
    card = deal_card(state["deck"], state["players"][player]["hand_occ"])
    if card is None:
        state["message"] = "hand is full!"
        state["message_t"] = 1.5
        return None
    # deal_card leaves owner = None, so set it now (keep face_up as is)
    reset_card_zone(card, "hand", slot=card["slot"], owner=player)
    _start_deal_flight(card, PLAYER_HAND_SLOTS[player][card["slot"]])
    play(sfx, "fan")
    return card


def deal_to_grid(state, player, slot, sfx):
    """Opening deal: top card face down into a grid slot. Returns the card or None."""
    if not state["deck"]:
        state["message"] = "deck is empty!"
        state["message_t"] = 1.5
        return None
    card = state["deck"].pop(0)
    reset_card_zone(card, "grid", slot=slot, face_up=False, owner=player)
    state["players"][player]["grid_occ"][slot] = card
    _start_deal_flight(card, PLAYER_GRID_SLOTS[player][slot])
    play(sfx, "fan")
    return card


def reset_table(state, sfx):
    """Redeal: new shuffled deck, empty hands and grids, one queued deal per grid slot."""
    deck = make_deck()
    shuffle_deck(deck)
    state["cards"] = deck               # every card (drawing order)
    state["deck"] = list(deck)          # same cards, only the undealt ones
    for player in state["players"]:
        player["grid_occ"] = [None] * len(player["grid_occ"])
        player["hand_occ"] = [None] * len(player["hand_occ"])
    n = len(state["players"])
    state["queue"] = [(0.2 + 0.18 * i, i % n, i // n)
                      for i in range(n * len(PLAYER_GRID_SLOTS[0]))]
    state["message"] = None
    state["message_t"] = 0.0
    # Stage 11: every hole starts in the reveal phase, with an empty discard
    # pile (start_discard turns the first card up once the reveal is done).
    # The player whose turn is first rotates: hole 1 player 0, hole 2 player 1...
    state["discard"] = []
    state["phase"] = "reveal"
    state["revealed"] = [0] * n
    state["ender"] = None
    state["drawn_from"] = None
    state["current"] = (state["hole"] - 1) % n
    play(sfx, "shuffle")


# Stage 11 - THE REAL GAME RULES: FOUR-CARD GOLF
CARD_VALUES = {"ace": 1, "2": -2, "jack": 10, "queen": 10, "king": 0}
GRID_COLUMNS = ((0, 2), (1, 3))    # slots 0,1 = top row; 2,3 = bottom row


def card_value(card):
    """Golf points: Ace 1, Two -2, 3-10 face value, Jack and Queen 10, King 0."""
    rank = card["rank"]
    if rank in CARD_VALUES:
        return CARD_VALUES[rank]
    return int(rank)


def score_grid(cards):
    """Score one grid (grid_occ list). A same-rank pair in a column scores 0 for it."""
    total = 0
    for top, bottom in GRID_COLUMNS:
        upper, lower = cards[top], cards[bottom]
        if (upper is not None and lower is not None
                and upper["rank"] == lower["rank"]):
            continue                 # a pair cancels the whole column
        for c in (upper, lower):
            if c is not None:
                total += card_value(c)
    return total


def legal_move(state, card, target):
    """May this card go to target = (zone, slot)? Only the current player's held card,
    in the place phase. A card taken from the discard pile cannot be discarded."""
    if state["phase"] != "place":
        return False
    if card["owner"] != state["current"] or card["zone"] != "hand":
        return False
    zone, slot = target
    if zone == "grid":
        return slot in range(len(PLAYER_GRID_SLOTS[card["owner"]]))
    if zone == "discard":
        return state["drawn_from"] == "deck"
    return zone == "hand"


def _all_face_up(cards):
    return all(c is not None and c["face_up"] for c in cards)


def next_turn(state):
    """End the turn. Whoever turns their last card up ends the hole; the others get one more turn."""
    me = state["current"]
    if state["ender"] is None and _all_face_up(state["players"][me]["grid_occ"]):
        state["ender"] = me
    next_player(state)
    state["drawn_from"] = None
    if state["ender"] is not None and state["current"] == state["ender"]:
        state["phase"] = "round_over"
    else:
        state["phase"] = "draw"
        _announce_turn(state)


def round_over(state):
    return state["phase"] == "round_over"


def end_round(state):
    """Score the hole into each player's total and advance the hole counter."""
    for player in state["players"]:
        player["score"] = score_grid(player["grid_occ"])
        player["total"] += player["score"]
    state["hole"] += 1
    state["ender"] = None
    state["drawn_from"] = None


def game_over(state):
    return state["hole"] > HOLES


def winner(state):
    """Index of the lowest total after the last hole, or None (not over or tied)."""
    if not game_over(state):
        return None
    totals = [player["total"] for player in state["players"]]
    best = min(totals)
    if totals.count(best) > 1:
        return None
    return totals.index(best)


# Stage 11 wiring: how a click or key plays a turn
REVEAL_COUNT = 2                   # cards each player turns up to start
YELLOW = (255, 230, 120)


def _announce_turn(state):
    state["message"] = f"PLAYER {state['current'] + 1}'S TURN"
    state["message_t"] = 1.5


def _over_pile(pos, center):
    return (abs(pos[0] - center[0]) <= CARD_SIZE[0] / 2
            and abs(pos[1] - center[1]) <= CARD_SIZE[1] / 2)


def new_game(state, sfx):
    for player in state["players"]:
        player["score"] = 0
        player["total"] = 0
    state["hole"] = 1
    reset_table(state, sfx)


def start_discard(state, sfx):
    """Turn the top deck card face up to start the discard pile."""
    if not state["deck"]:
        return None
    card = state["deck"].pop(0)
    send_card(card, DISCARD_POS, "discard", None, face_up=True)
    _push_discard(state, card)
    return card


def refill_deck(state):
    """If the deck is empty, shuffle the discard pile (except its top) back in. Returns True if the deck has cards."""
    if state["deck"]:
        return True
    if len(state["discard"]) <= 1:
        return False
    top = state["discard"][-1]
    old = state["discard"][:-1]
    random.shuffle(old)
    for card in old:
        reset_card_zone(card, "deck", pos=DECK_POS, face_up=False)
    state["deck"] = old
    state["discard"] = [top]
    return True


def reveal_card(state, card, sfx):
    """Reveal phase: turn one of the current player's face-down cards. Returns True if turned."""
    me = state["current"]
    if (state["phase"] != "reveal" or card["owner"] != me
            or card["zone"] != "grid" or card["face_up"]
            or state["revealed"][me] >= REVEAL_COUNT):
        return False
    flip_card(card, sfx)
    state["revealed"][me] += 1
    if state["revealed"][me] == REVEAL_COUNT:
        next_player(state)
        if all(r >= REVEAL_COUNT for r in state["revealed"]):
            start_discard(state, sfx)
            state["phase"] = "draw"
        _announce_turn(state)
    return True


def draw_from_deck(state, sfx):
    if state["phase"] != "draw":
        return None
    refill_deck(state)
    card = deal_to_hand(state, state["current"], sfx)
    if card is None:
        return None
    state["phase"] = "place"
    state["drawn_from"] = "deck"
    return card


def draw_from_discard(state, sfx):
    if state["phase"] != "draw" or not state["discard"]:
        return None
    me = state["current"]
    hand = state["players"][me]["hand_occ"]
    slot = hand.index(None)
    card = state["discard"].pop()
    hand[slot] = card
    send_card(card, PLAYER_HAND_SLOTS[me][slot], "hand", slot,
              face_up=True, owner=me)
    play(sfx, "slide")
    state["phase"] = "place"
    state["drawn_from"] = "discard"
    return card


def golf_press(state, pos, sfx):
    """What a left click means in the current phase."""
    phase = state["phase"]
    me = state["current"]
    if phase == "scored":
        continue_after_hole(state, sfx)
    elif phase == "reveal":
        picked = top_card_at(state["cards"], pos, owner=me)
        if picked is not None:
            reveal_card(state, picked, sfx)
    elif phase == "draw":
        if _over_pile(pos, DECK_POS):
            draw_from_deck(state, sfx)
        elif _over_pile(pos, DISCARD_POS):
            draw_from_discard(state, sfx)
    elif phase == "place":
        picked = top_card_at(state["cards"], pos, owner=me)
        if picked is not None and picked["zone"] == "hand":
            begin_drag(picked, pos, sfx)   # only the held card can be dragged


def golf_space(state, sfx):
    if state["phase"] == "draw":
        draw_from_deck(state, sfx)
    elif state["phase"] == "scored":
        continue_after_hole(state, sfx)


def finish_hole(state, sfx):
    """Turn every card face up and score the hole."""
    for player in state["players"]:
        for card in player["grid_occ"]:
            if card is not None and not card["face_up"]:
                flip_card(card, sfx)
    end_round(state)
    state["phase"] = "scored"


def continue_after_hole(state, sfx):
    state["queue"] = []
    if game_over(state):
        new_game(state, sfx)
    else:
        reset_table(state, sfx)


def golf_hud_lines(state):
    """(text, color) lines for the Golf panel."""
    phase = state["phase"]
    me = state["current"]
    hole = state["hole"] - 1 if phase == "scored" else state["hole"]
    hole = max(1, min(hole, HOLES))
    totals = "  ".join(f"P{i + 1}: {p['total']}"
                       for i, p in enumerate(state["players"]))
    lines = [(f"HOLE {hole} OF {HOLES}", TEXT_COLOR),
             (f"TOTALS  {totals}", TEXT_COLOR)]
    if phase == "reveal":
        left = REVEAL_COUNT - state["revealed"][me]
        lines.append((f"PLAYER {me + 1}: FLIP {left} OF YOUR CARDS", YELLOW))
    elif phase == "draw":
        lines.append((f"PLAYER {me + 1}: DRAW A CARD", YELLOW))
        lines.append(("click the deck or the discard", TEXT_COLOR))
    elif phase == "place":
        lines.append((f"PLAYER {me + 1}: PLACE YOUR CARD", YELLOW))
        if state["drawn_from"] == "deck":
            lines.append(("drop it on a grid card to swap,", TEXT_COLOR))
            lines.append(("or on the discard to throw it away", TEXT_COLOR))
        else:
            lines.append(("drop it on a grid card (must swap)", TEXT_COLOR))
    elif phase == "scored":
        scores = "  ".join(f"P{i + 1}: {p['score']}"
                           for i, p in enumerate(state["players"]))
        lines.append((f"HOLE SCORES  {scores}", YELLOW))
        if game_over(state):
            win = winner(state)
            lines.append(("TIE GAME!" if win is None
                          else f"PLAYER {win + 1} WINS!", YELLOW))
            lines.append(("click or SPACE: play again", TEXT_COLOR))
        else:
            lines.append(("click or SPACE: next hole", TEXT_COLOR))
    if state["ender"] is not None and phase in ("draw", "place"):
        lines.append((f"PLAYER {state['ender'] + 1} IS DONE: LAST TURN",
                      (255, 170, 130)))
    return lines


def draw_golf_hud(screen, font, lines):
    y = 10
    for text, color in lines:
        surf = font.render(text, True, color)
        screen.blit(surf, surf.get_rect(topright=(WINDOW_SIZE[0] - 12, y)))
        y += surf.get_height() + 2


# Stage 12 - POLISH, "GAME JUICE"
# RULE: polish may READ the game state but never changes pos, zone, slot
# or face_up. update_polish only writes vel, bend, tilt, lift and wobble_t.
FLIP_DURATION = 0.35     # seconds a full flip spin takes
WOBBLE_TIME = 0.45       # seconds a landed card wobbles
BEND_SCALE_DIV = 2500.0  # sideways speed (px/s) that gives the full bend
MAX_BEND = 18.0          # px of strip shear at full speed
TILT_SCALE = 0.045       # degrees of lean per px/s of sideways speed
MAX_TILT = 18.0          # degrees


def lift_target(card):
    """How high the card should be above the table right now, from its motion."""
    if card["motion"] == "deal":
        p = min(card["t"] / DEAL_TIME, 1.0)
        return card["arc"] * math.sin(math.pi * p) + 20.0
    if card["motion"] == "glide":
        return min(40.0, _distance(card["pos"], card["target"]) * 0.12)
    lift = 34.0 if card["dragging"] else 0.0
    if card["flipping"]:
        p = min(card["flip_t"] / FLIP_DURATION, 1.0)
        lift += 44.0 * math.sin(math.pi * p)
    return lift


_resting_shadow = None     # built once, shared by every resting card


def get_resting_shadow():
    global _resting_shadow
    if _resting_shadow is None:
        w, h = CARD_SIZE
        small = pygame.Surface((max(int(w / 1.6), 6), max(int(h / 1.6), 6)),
                               pygame.SRCALPHA)
        pygame.draw.rect(small, (0, 0, 0, 90), small.get_rect(),
                         border_radius=max(small.get_width() // 10, 2))
        _resting_shadow = pygame.transform.smoothscale(
            small, (max(int(w * 0.92), 6), max(int(h * 0.92), 6)))
    return _resting_shadow


def update_polish(card, dt, prev):
    """Ease vel, bend, tilt, lift and wobble toward their targets.
    Writes only those fields, never pos, zone, slot or face_up."""
    card["vel"] = [(card["pos"][i] - prev[i]) / max(dt, 1e-6)
                   for i in (0, 1)]
    bend_target = max(-1.0, min(1.0, card["vel"][0] / BEND_SCALE_DIV)) \
        * MAX_BEND
    card["bend"] += (bend_target - card["bend"]) * blend(10.0, dt)

    tilt_target = max(-MAX_TILT, min(MAX_TILT, card["vel"][0] * TILT_SCALE))
    if card["wobble_t"] > 0.0:
        card["wobble_t"] = max(card["wobble_t"] - dt, 0.0)
        q = 1.0 - card["wobble_t"] / WOBBLE_TIME
        tilt_target += (math.sin(q * math.pi * 2.5) * 7.0
                        * math.sin(q * math.pi))
    card["tilt"] += (tilt_target - card["tilt"]) * blend(12.0, dt)

    card["lift"] += (lift_target(card) - card["lift"]) * blend(14.0, dt)


if __name__ == "__main__":
    main()
