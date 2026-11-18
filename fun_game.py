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
CARD_SIZE   = (90, 126)        # smaller so two grids fit on one screen
NUM_PLAYERS = 2
HOLES = 9                      # a full game is nine hands (Stage 11)
SUITS = ["clubs", "diamonds", "hearts", "spades"]
RANKS = ["ace", "2", "3", "4", "5", "6", "7", "8", "9", "10",
         "jack", "queen", "king"]

# deck and discard are shared (not per-plauyer), in the middle of the table
DECK_POS    = (460, 330)
DISCARD_POS = (600, 330)

# anti-diagonal layout (issue #13): player 1 owns the top-left corner,
# player 0 the bottom-right; piles stay in the middle where they cross.
# slots 0,1 = top row of a grid, 2,3 = bottom row (Golf columns: (0,2), (1,3))
PLAYER_GRID_SLOTS = [
    [(700, 415), (810, 415), (700, 550), (810, 550)],   # player 0
    [(190, 110), (300, 110), (190, 245), (300, 245)]]   # player 1

# one list of hand slots PER PLAYER (Golf needs one "held card" spot each)
PLAYER_HAND_SLOTS = [[(500, 482)],    # player 0
                     [(500, 178)]]    # player 1


def make_card(suit, rank, zone="deck", pos=DECK_POS, face_up=False):
    """
    creates the card with its different properties
    """
    card = {"suit": suit, "rank": rank,
            "pos": list(pos),  # store as a list, not the original tuple
            "face_up": face_up, "zone": zone, "slot": None, "owner": None,
            "motion": None, "target": [0.0, 0.0],
            # Stage 6 (issue #8): dragging with the mouse
            "dragging": False,
            "drag_offset": (0.0, 0.0),   # where on the card the mouse grabbed it
            "press_pos": (0.0, 0.0),     # where the mouse was on click
            # Stage 7 (issue #14): click vs drag
            "pickup_flip": False,       # did begin_drag already flip it?
            # Stage 9 (issue #17): a dealt card's flight through the air
            "t": 0.0,                    # seconds into a "deal" flight
            "start": [0.0, 0.0],         # where the flight began
            "arc": 0.0}                  # how high the flight arcs
    return card


def make_deck():
    """
    creates 52 deck of cards
    returns a list of 52 card dicts, one for every suit and every rank.
    """
    deck = []
    for suit in SUITS:
        for rank in RANKS:
            card = make_card(suit, rank)
            deck.append(card)

    return deck


# ----------------------------------------------------------------------
# Stage 2 - PLAYERS, ZONES, SHUFFLING AND DEALING (issue #2)
# ----------------------------------------------------------------------
def reset_card_zone(card, zone, pos=None, slot=None, face_up=None,
                    owner=None):
    '''
    is the one way to put a card in a zone and slot. Game rules will call this.
    '''
    # card = 0suit, 1rank, 2pos, 3face_up, 4zone, 5slot, 6owner, 7motion, 8target

    card["zone"] = zone # sets the zone, slot, owner based on parameter
    card["slot"] = slot
    card["owner"] = owner

    if face_up is not None:
        card["face_up"] = face_up

    if pos is not None:
        card["pos"] = list(pos)  # store as a list, not the original tuple
        card["motion"] = None

    if card["zone"] == "deck" or card["zone"] == "discard": # ensuring no owner if in deck or discard pile
        card["owner"] = None


def shuffle_deck(deck):
    '''
    randomizes the deck
    '''
    random.shuffle(deck)


def deal_card(deck, hand):
    '''
    returns the card, or None
    Takes the top card of the deck (deck.pop(0)) and puts it in the first empty hand slot (the first None in the list).
    '''
    if not deck: # ensure deck isnt empty
        return None

    room_check = False
    for spot in hand:  # checking hand has slots
        if spot is None:
            room_check = True
            break

    if not room_check:
        return None

    top_card = deck.pop(0)
    slot = hand.index(None)   # WHERE we will put it (the index, not the value)
    hand[slot] = top_card     # write the card INTO the list
    reset_card_zone(top_card, "hand", slot=slot, face_up=True)
    return top_card


def make_state(num_players=NUM_PLAYERS):
    '''
    returns the state: one dictionary holding everything the game currently knows (who has which card, whose turn it is, what message is showing). It is plain data only, so it doesn't use pygame and can be tested without a window.
    '''
    state = {"cards": [], "deck": [],
             "players": [{"grid_occ": [None] * len(PLAYER_GRID_SLOTS[i]),
                          "hand_occ": [None] * len(PLAYER_HAND_SLOTS[i]),
                          "score": 0,      # this hole (Stage 11)
                          "total": 0}      # running total over all holes
                         for i in range(num_players)],
             "current": 0,
             "message": None, "message_t": 0.0,
             "sfx": None, "queue": [], "hud_lines": [],
             # Stage 11 (issue #20): the Golf rules
             "rules_on": False,   # True = Golf rules (main() turns them on)
             "discard": [],        # the discard pile, top (newest) card LAST
             "phase": "reveal",   # reveal, draw, place, round_over, scored
             "hole": 1,           # which hole is being played (1..HOLES)
             "ender": None,       # player who turned their last card up
             "drawn_from": None,  # "deck" or "discard" during a turn
             "revealed": [0] * num_players}   # flips done while revealing
    return state


# ----------------------------------------------------------------------
# Stage 3 - LOADING PICTURES AND SOUNDS (issue #3)
# ----------------------------------------------------------------------
# Remember the last sound variant played for each kind.
_last_played = {}

# Assets live next to this file, so the game runs from any directory.
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "assets")


def scale_card(surface):
    """Resize a card image to CARD_SIZE."""
    return pygame.transform.smoothscale(surface, CARD_SIZE)


def load_card_face(suit, rank):
    """Load one card face and scale it."""
    filename = f"{rank} of {suit}.png"
    path = os.path.join(ASSETS_DIR, "cards", "fronts", suit, filename)

    image = pygame.image.load(path).convert_alpha()
    return scale_card(image)


def load_deck_faces():
    """Load all 52 card faces into a dictionary."""
    return {
        (suit, rank): load_card_face(suit, rank)
        for suit in SUITS
        for rank in RANKS
    }


def load_card_back(color="blue"):
    """Load and scale a card back."""
    filename = f"card back {color}.png"
    path = os.path.join(ASSETS_DIR, "cards", "backs", filename)

    image = pygame.image.load(path).convert_alpha()
    return scale_card(image)


def load_sfx():
    """Load all sound effects, grouped by kind."""
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
    """Play a random sound without repeating the previous variant."""
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


# ----------------------------------------------------------------------
# Stage 4 - DRAWING A STILL TABLE (issue #4)
# ----------------------------------------------------------------------
TABLE_GREEN  = (28, 105, 60)
SLOT_GREEN   = (22, 88, 50)
ACTIVE_GREEN = (70, 170, 105)     # active player's slot outlines
TEXT_COLOR   = (235, 245, 235)


def create_display():
    """
    opens the window. Returns (screen, refresh_hz, vsynced).
    Safe even if vsync is not supported - the flag is just ignored.
    """
    screen = pygame.display.set_mode(WINDOW_SIZE, pygame.SCALED, vsync=1)
    vsynced = pygame.display.is_vsync()           # did it really happen?
    refresh_hz = pygame.display.get_current_refresh_rate()
    if refresh_hz == 0:                           # headless machines
        refresh_hz = 60
    return screen, refresh_hz, vsynced


def card_rect(card):
    """
    Used for drawing cards. Rectangle CARD_SIZE big, centered on pos.
    """
    rect = pygame.Rect((0, 0), CARD_SIZE)
    rect.center = (round(card["pos"][0]), round(card["pos"][1]))
    return rect


def current_texture(card, faces, back):
    """
    returns the Surface to show:
    faces[(card["suit"], card["rank"])] if the card is face up,
    otherwise back.
    """
    if card["face_up"]:
        return faces[(card["suit"], card["rank"])]
    else:
        return back


def draw_card(screen, card, faces, back):
    """blits that picture centered
    on the card's position. dependent on face up or face down"""
    screen.blit(current_texture(card, faces, back), card_rect(card))


def draw_piles(screen, cards, faces, back, discard=None):
    """
    Deck: draw the top 3 cards still in zone "deck" face-down, each
        2 pixels higher than the last, so the pile looks thick.
    Discard: draw the 3 NEWEST cards in zone "discard" face-up with a
        tiny offset each, so the pile looks fanned. `discard` is the
        state's discard list (oldest first, newest last); without it the
        cards are taken in list order.
    """
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
    # draw only as many layers as the pile actually has.
    for i in range(min(3, deck_parse_count) - 1, -1, -1):
        rect = pygame.Rect((0, 0), CARD_SIZE)
        rect.center = (DECK_POS[0], DECK_POS[1] - 2 * i)
        screen.blit(back, rect)

    # cards in discard: centered on the card's own pos, offset per layer
    move_over = 0
    for card in top_3_in_discard:           # oldest first, newest on top
        rect = card_rect(card)
        rect.move_ip(move_over, move_over)
        screen.blit(current_texture(card, faces, back), rect)
        move_over += 2


def draw_table(screen, font, current=None):
    """
    Felt + slot outlines (active player lighter) + DECK/DISCARD outlines
    + labels. Drawing only READS: no state is modified here.
    """
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
    """
    Draw everything in order: table, piles, then every card that is in
    a hand or grid of ANY player (cards drawn LAST appear ON TOP).
    """
    draw_table(screen, font, state["current"])
    draw_piles(screen, state["cards"], faces, back, state.get("discard"))
    # resting cards first; dragged and gliding cards LAST so they are
    # never hidden under a card that is standing still
    moving = []
    for card in state["cards"]:
        if card["zone"] in ("hand", "grid"):
            if card["dragging"] or card["motion"] is not None:
                moving.append(card)
            else:
                draw_card(screen, card, faces, back)
    for card in moving:
        draw_card(screen, card, faces, back)


# ----------------------------------------------------------------------
# Stage 5 - THE GAME LOOP, TIME AND VSYNC (issue #5)
# ----------------------------------------------------------------------
MAX_DT = 0.05    # clamp: a stalled frame must not teleport things


def draw_hud(screen, font, message, lines):
    """Controls hint, stats block, and state["message"] if not empty."""
    hint = font.render("Click deck/discard or SPACE to draw | Drag to place"
                       " | R: new game | Esc quit", True, TEXT_COLOR)
    screen.blit(hint, (12, 10))
    y = 34
    for text, color in lines:
        surf = font.render(text, True, color)
        screen.blit(surf, (12, y))
        y += surf.get_height() + 2
    if message:
        surf = font.render(message, True, (255, 230, 120))
        screen.blit(surf, surf.get_rect(center=(WINDOW_SIZE[0] // 2, 60)))


DEAL_PICK_DIST = 90   # px around DECK_POS that counts as clicking the deck


def next_player(state):
    """Switch whose turn it is. (Stage 11's next_turn builds on this.)"""
    state["current"] = (state["current"] + 1) % len(state["players"])


def handle_input(events, state, sfx, mouse_pos):
    """
    Switchboard: send each event to the right function. False = quit.
      ESC / window close -> quit        SPACE / click the deck -> draw
      R -> new game                     TAB -> next player (free play only)
      left mouse down -> grab a card    left mouse up -> release it
    With state["rules_on"] the Golf rules decide what a click or SPACE
    means (golf_press, golf_space); this function still only dispatches.
    Mouse events use their OWN position (event.pos), because mouse_pos
    was read before the events and can be a frame behind the click.
    """
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
                # only the current player can grab (owner filter)
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
    """
    One step of the world (Stage 9):
    1. count the deal queue down and deal what is due,
    2. move every card (update_card handles dragging, gliding, dealing),
    3. count the on-screen message down.
    update does NOT call update_drag itself any more: update_motion does,
    otherwise a dragged card would move twice per frame.
    """
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

    # Stage 11: the last turn of a hole is done, so score it
    if state.get("rules_on") and state["phase"] == "round_over":
        finish_hole(state, sfx)


def _pacing_lines(frame_times, vsynced, refresh_hz, using_timer):
    """HUD stats like fps, pacing mode, frame-time spread (ms)."""
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
    """
    macOS only. A window opened from a terminal or VS Code often starts
    behind the app that launched it and ignores the mouse until you click
    off and back on. This makes the game the active app right away.
    Needs pyobjc (already in the .venv); does nothing if it is missing, on
    other systems, or in headless tests.
    """
    if sys.platform != "darwin" or pygame.display.get_driver() != "cocoa":
        return
    try:
        from AppKit import NSApplication
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    except Exception:
        pass


def main(frames=None):
    """The game window, assets, state, nd the loop."""
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
    state["rules_on"] = True         # play real Golf (Stage 11)
    reset_table(state, sfx)          # starts the opening deal (Stage 9)

    clock = pygame.time.Clock()
    using_timer = not vsynced
    target_fps = refresh_hz or 60
    last = time.perf_counter()
    window_times, all_times = [], []
    stat_clock = 0.0
    frame_count = 0
    running = True

    while running:
        # 1. dt
        now = time.perf_counter()
        raw_dt = now - last
        last = now
        dt = min(raw_dt, MAX_DT)
        if frame_count > 0:
            window_times.append(raw_dt)
            all_times.append(raw_dt)

        # 2. input
        mouse_pos = pygame.mouse.get_pos()
        running = handle_input(pygame.event.get(), state, sfx, mouse_pos)

        # 3. update
        update(state, dt, mouse_pos, sfx)

        # 4. render
        render(screen, state, font, faces, back)
        draw_hud(screen, font, state["message"], state["hud_lines"])
        draw_golf_hud(screen, font, golf_hud_lines(state))

        # 5. show
        pygame.display.flip()
        if using_timer:
            clock.tick(target_fps)

        # If "vsync" did not actually wait, fall back to a timer.
        if (vsynced and not using_timer and refresh_hz
                and len(all_times) == 60
                and statistics.mean(all_times) < 0.5 / refresh_hz):
            using_timer = True

        # HUD stats every 0.5 s
        stat_clock += raw_dt
        if stat_clock >= 0.5:
            state["hud_lines"] = _pacing_lines(window_times, vsynced,
                                               refresh_hz, using_timer)[0]
            window_times = []
            stat_clock = 0.0

        frame_count += 1
        if frames is not None and frame_count >= frames:
            running = False

    _, fps, mean_ms, sd_ms = _pacing_lines(all_times, vsynced,
                                           refresh_hz, using_timer)
    mode = "vsync" if vsynced and not using_timer else "timer"
    print(f"pacing: {frame_count} frames, {fps:.1f} fps, "
          f"{mean_ms:.2f} ms mean, {sd_ms:.2f} ms sd, {mode}")
    pygame.quit()


# ----------------------------------------------------------------------
# Stage 6 - PICKING CARDS UP WITH THE MOUSE (issue #8)
# ----------------------------------------------------------------------
DRAG_FOLLOW = 26     # how fast a dragged card catches up with the mouse


def blend(rate, dt):
    """
    How much of the remaining distance to cover this frame (0 to 1).
    1 - e^(-rate * dt) takes the same REAL time at 30, 60 or 240 fps.
    """
    return 1 - math.exp(-rate * dt)


def top_card_at(cards, point, owner=None):
    """
    Returns the card the player clicked, or None.
    Looks from the LAST card to the first (the last is drawn on top).
    Only cards in zone "hand" or "grid" that are not moving count.
    If owner is 0 or 1, only that player's cards count.
    """
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
    """
    Pick a card up: remember where on the card it was grabbed (so it does
    not jump to the mouse), where the mouse was, and play "slide".
    Stage 7: a face-down card is flipped as it is lifted (revealed).
    """
    card["dragging"] = True
    card["drag_offset"] = (card["pos"][0] - mouse_pos[0],
                           card["pos"][1] - mouse_pos[1])
    card["press_pos"] = tuple(mouse_pos)
    card["pickup_flip"] = not card["face_up"]
    if card["pickup_flip"]:
        flip_card(card, sfx)
    play(sfx, "slide")


def update_drag(card, mouse_pos, dt):
    """
    Each frame, move the card a FRACTION of the way to where it should
    be (mouse + grab offset). It eases toward the cursor, never snaps.
    """
    target_x = mouse_pos[0] + card["drag_offset"][0]
    target_y = mouse_pos[1] + card["drag_offset"][1]
    k = blend(DRAG_FOLLOW, dt)
    card["pos"][0] += (target_x - card["pos"][0]) * k
    card["pos"][1] += (target_y - card["pos"][1]) * k


# ----------------------------------------------------------------------
# Stage 7 - FLIPPING AND CLICKING (issue #14)
# ----------------------------------------------------------------------
CLICK_DIST = 8   # px: moved less than this since the press = a click


def flip_card(card, sfx):
    """
    Turns the card over IMMEDIATELY (rules can read face_up in the same
    step) and plays the "shove" sound.
    """
    card["face_up"] = not card["face_up"]
    play(sfx, "shove")


def release_card(card, mouse_pos, state):
    """
    Let go of a dragged card. A DECISION function: it decides and calls
    send_card, it never moves pixels (Stage 9 does that).

    Click check (Stage 7): moved less than CLICK_DIST since the press = a
    CLICK, so flip the card, unless begin_drag already flipped it
    (pickup_flip), then do NOT flip it back. Then stop.

    Otherwise (Stage 8), in this order:
      a) mouse within SNAP_DIST of DISCARD_POS    -> discard it
      b) nearest slot of the card's OWN grid within SNAP_DIST:
           its own slot -> settle back, empty -> place,
           another card there -> swap (old card to the discard, face up)
      c) else -> go home (back to its hand slot or grid slot)
    """
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
        return                      # a click is not a drop

    owner = card["owner"]
    player = state["players"][owner]
    old_zone, old_slot = card["zone"], card["slot"]   # where it came from
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
        old_occ[old_slot] = None                  # the card left its spot
        if occupant is not None:                  # swap: old card out
            send_card(occupant, DISCARD_POS, "discard", None, face_up=True)
            _push_discard(state, occupant)
        player["grid_occ"][nearest] = card        # the card takes the slot
        send_card(card, slots[nearest], "grid", nearest, owner=owner)
        if rules:
            next_turn(state)
        return

    # c) nowhere useful: go home (the occupancy lists stay as they were)
    send_card(card, home, old_zone, old_slot, owner=owner)


# ----------------------------------------------------------------------
# Stage 8 - PLACING, SWAPPING, DISCARDING (issue #16)
# ----------------------------------------------------------------------
SNAP_DIST = 80   # px: how close the mouse must be to a slot or the discard


def _distance(a, b):
    """Straight-line distance between two (x, y) points."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _push_discard(state, card):
    """Put a card on top of the discard pile (the newest card is LAST)."""
    state.setdefault("discard", []).append(card)


def _home_pos(card):
    """Screen position of the hand or grid slot the card belongs in."""
    table = PLAYER_HAND_SLOTS if card["zone"] == "hand" else PLAYER_GRID_SLOTS
    return table[card["owner"]][card["slot"]]


def send_card(card, target, zone, slot, face_up=None, owner=None):
    """
    Perform a decision: the card will GLIDE to target (Stage 9 moves it).
    zone, slot, face_up and owner are updated with reset_card_zone and NO
    pos, so the card is not teleported.
    TRAP: reset_card_zone sets owner to whatever it is given (None by
    default), so for "hand" and "grid" destinations the caller must pass
    owner=, or the card loses its owner.
    """
    reset_card_zone(card, zone, slot=slot, face_up=face_up, owner=owner)
    card["motion"] = "glide"
    card["target"] = list(target)


# ----------------------------------------------------------------------
# Stage 9 - MOVEMENT OVER TIME: GLIDING AND DEALING (issue #17)
# ----------------------------------------------------------------------
GLIDE = 12           # how fast a gliding card closes the distance
DEAL_TIME = 0.55     # seconds a dealt card takes to fly
DEAL_ARC = 130       # px: how high the flight arcs above the straight line
ARRIVE_DIST = 2      # px: this close to the target = arrived


def update_motion(card, dt, mouse_pos, sfx):
    """
    Advance ONE card by dt seconds:
      dragging       -> update_drag (Stage 6)
      "glide"        -> ease toward target; within ARRIVE_DIST it snaps
                        there, motion = None, and "place" plays
      "deal"         -> a DEAL_TIME flight with smoothstep easing and an arc
    """
    if card["dragging"]:
        update_drag(card, mouse_pos, dt)
    elif card["motion"] == "glide":
        k = blend(GLIDE, dt)
        card["pos"][0] += (card["target"][0] - card["pos"][0]) * k
        card["pos"][1] += (card["target"][1] - card["pos"][1]) * k
        if _distance(card["pos"], card["target"]) < ARRIVE_DIST:
            card["pos"] = list(card["target"])
            card["motion"] = None
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


def update_card(card, dt, mouse_pos, sfx):
    """The per-card step. For now it just calls update_motion."""
    update_motion(card, dt, mouse_pos, sfx)


def _start_deal_flight(card, target):
    """Start a "deal" flight from wherever the card is now to target."""
    card["motion"] = "deal"
    card["t"] = 0.0
    card["start"] = list(card["pos"])
    card["target"] = list(target)
    card["arc"] = DEAL_ARC


def deal_to_hand(state, player, sfx):
    """
    Golf wrapper: deal the top card into the player's hand and fly it
    there. Sets state["message"] if the deck is empty or the hand is full.
    Returns the card, or None.
    """
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
    """
    Opening deal: the top card goes FACE DOWN into that player's grid slot
    and flies there. Returns the card, or None if the deck is empty.
    """
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
    """
    Redeal: new shuffled deck, both players' hands and grids emptied, and
    one queue job (delay, player, slot) per grid slot, alternating players
    like a real deal: delay = 0.2 + 0.18 * i.
    """
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


# ----------------------------------------------------------------------
# Stage 11 - THE REAL GAME RULES: FOUR-CARD GOLF (issue #20)
# ----------------------------------------------------------------------
# Rules only CALL the earlier stages and read/write the state. They never
# draw and never move pixels.
CARD_VALUES = {"ace": 1, "2": -2, "jack": 10, "queen": 10, "king": 0}
GRID_COLUMNS = ((0, 2), (1, 3))    # slots 0,1 = top row; 2,3 = bottom row


def card_value(card):
    """
    Golf points of one card: Ace 1, Two -2, 3-10 face value,
    Jack and Queen 10, King 0.
    """
    rank = card["rank"]
    if rank in CARD_VALUES:
        return CARD_VALUES[rank]
    return int(rank)                 # "3" ... "10"


def score_grid(cards):
    """
    Add up one player's grid (their grid_occ list; None = empty slot, 0
    points). A pair of equal ranks in the same column scores 0 for that
    column. Counts every card, face up or down: at the end of a hole all
    cards are turned over before scoring.
    """
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
    """
    May this card be dropped on target = (zone, slot)?
    Only the current player's held card, and only in the "place" phase.
      ("grid", slot)    any slot of the player's own grid (a swap)
      ("discard", None) only if the card came from the DECK; a card taken
                        from the discard pile must be swapped in
      ("hand", None)    going home is always fine
    Release_card sends the card home when this says False.
    """
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
    """True if every slot holds a face-up card."""
    return all(c is not None and c["face_up"] for c in cards)


def next_turn(state):
    """
    End the current player's turn. If they now have all cards face up, they
    END the hole and everyone else gets one final turn; when the turn
    comes back round to the ender the phase becomes "round_over".
    """
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
    """True when the final turns of this hole are finished."""
    return state["phase"] == "round_over"


def end_round(state):
    """
    Score the hole: each player's score is score_grid of their grid, added
    to their running total, then the hole counter goes up. (Turning every
    card face up is the wiring's job, so it can be seen on screen.)
    """
    for player in state["players"]:
        player["score"] = score_grid(player["grid_occ"])
        player["total"] += player["score"]
    state["hole"] += 1
    state["ender"] = None
    state["drawn_from"] = None


def game_over(state):
    """True once all HOLES holes have been scored."""
    return state["hole"] > HOLES


def winner(state):
    """
    Index of the player with the LOWEST total once the game is over, or
    None if it is not over yet or the best total is tied.
    """
    if not game_over(state):
        return None
    totals = [player["total"] for player in state["players"]]
    best = min(totals)
    if totals.count(best) > 1:
        return None
    return totals.index(best)


# --- Stage 11 wiring: how a click or key plays a turn -------------------
# handle_input only dispatches; these functions hold the Golf flow. They
# call the Stage 2 and 6-9 functions and the rule functions above.
REVEAL_COUNT = 2                   # cards each player turns up to start
YELLOW = (255, 230, 120)


def _announce_turn(state):
    """Show the "hand over the mouse" banner for the current player."""
    state["message"] = f"PLAYER {state['current'] + 1}'S TURN"
    state["message_t"] = 1.5


def _over_pile(pos, center):
    """True if the point is on the card-sized area around a pile."""
    return (abs(pos[0] - center[0]) <= CARD_SIZE[0] / 2
            and abs(pos[1] - center[1]) <= CARD_SIZE[1] / 2)


def new_game(state, sfx):
    """Start over: totals and the hole counter back to 0, then a fresh deal."""
    for player in state["players"]:
        player["score"] = 0
        player["total"] = 0
    state["hole"] = 1
    reset_table(state, sfx)


def start_discard(state, sfx):
    """Turn the top card of the deck face up to start the discard pile."""
    if not state["deck"]:
        return None
    card = state["deck"].pop(0)
    send_card(card, DISCARD_POS, "discard", None, face_up=True)
    _push_discard(state, card)
    return card


def refill_deck(state):
    """
    If the deck has run out, shuffle the discard pile (except its top card)
    back in as a new face-down deck. Returns True if the deck has cards.
    """
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
    """
    Reveal phase: the current player turns one of their own face-down grid
    cards up. After REVEAL_COUNT cards the turn passes; once every player
    has revealed, the discard pile is started and play begins.
    Returns True if the card was turned.
    """
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
    """Draw phase: take the top of the deck into the player's hand."""
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
    """Draw phase: take the top of the discard pile into the hand."""
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
    """What a left click at pos means, depending on the phase."""
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
    """SPACE: draw from the deck, or go on to the next hole."""
    if state["phase"] == "draw":
        draw_from_deck(state, sfx)
    elif state["phase"] == "scored":
        continue_after_hole(state, sfx)


def finish_hole(state, sfx):
    """
    The last turn is done: turn every face-down card up, score the hole
    (end_round) and wait for a click or SPACE (phase "scored").
    """
    for player in state["players"]:
        for card in player["grid_occ"]:
            if card is not None and not card["face_up"]:
                flip_card(card, sfx)
    end_round(state)
    state["phase"] = "scored"


def continue_after_hole(state, sfx):
    """After the scores: the next hole, or a whole new game if it is over."""
    state["queue"] = []
    if game_over(state):
        new_game(state, sfx)
    else:
        reset_table(state, sfx)


def golf_hud_lines(state):
    """The (text, color) lines for the Golf panel at the top right."""
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
    """Draw the Golf panel, right-aligned in the free top-right corner."""
    y = 10
    for text, color in lines:
        surf = font.render(text, True, color)
        screen.blit(surf, surf.get_rect(topright=(WINDOW_SIZE[0] - 12, y)))
        y += surf.get_height() + 2


if __name__ == "__main__":
    main()
