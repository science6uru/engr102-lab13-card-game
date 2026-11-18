import random
import os
import glob
import pygame

WINDOW_SIZE = (1000, 660)
CARD_SIZE   = (90, 126)        # smaller so two grids fit on one screen
NUM_PLAYERS = 2
SUITS = ["clubs", "diamonds", "hearts", "spades"]
RANKS = ["ace", "2", "3", "4", "5", "6", "7", "8", "9", "10",
         "jack", "queen", "king"]

# deck and discard are shared (not per-plauyer), in the middle of the table
DECK_POS    = (430, 330)
DISCARD_POS = (570, 330)

# one list of 4 grid slots PER PLAYER (player 0 = bottom, player 1 = top)
# slots 0,1 = top row of a grid, 2,3 = bottom row (Golf columns: (0,2), (1,3))
PLAYER_GRID_SLOTS = [
    [(440, 460), (560, 460), (440, 590), (560, 590)],   # player 0
    [(440, 70),  (560, 70),  (440, 200), (560, 200)]]   # player 1

# one list of hand slots PER PLAYER (Golf needs one "held card" spot each)
PLAYER_HAND_SLOTS = [[(760, 525)],    # player 0
                     [(760, 135)]]    # player 1


def make_card(suit, rank, zone="deck", pos=DECK_POS, face_up=False):
    """
    creates the card with its different properties
    """
    card = {"suit": suit, "rank": rank,
            "pos": list(pos),  # store as a list, not the original tuple
            "face_up": face_up, "zone": zone, "slot": None, "owner": None,
            "motion": None, "target": [0.0, 0.0]}
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
                          "score": 0} for i in range(num_players)],
             "current": 0,
             "message": None, "message_t": 0.0,
             "sfx": None, "queue": [], "hud_lines": []}
    return state


# ----------------------------------------------------------------------
# Stage 3 - LOADING PICTURES AND SOUNDS (issue #3)
# ----------------------------------------------------------------------
# Remember the last sound variant played for each kind.
_last_played = {}


def scale_card(surface):
    """Resize a card image to CARD_SIZE."""
    return pygame.transform.smoothscale(surface, CARD_SIZE)


def load_card_face(suit, rank):
    """Load one card face and scale it."""
    filename = f"{rank} of {suit}.png"
    path = os.path.join("assets", "cards", "fronts", suit, filename)

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
    path = os.path.join("assets", "cards", "backs", filename)

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

    sfx_dir = os.path.join("assets", "sfx", "cards")

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
    opens the window.
    """
    screen = pygame.display.set_mode(WINDOW_SIZE)
    return screen


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


def draw_piles(screen, cards, faces, back):
    """
    Deck: draw the top 3 cards still in zone "deck" face-down, each
        2 pixels higher than the last, so the pile looks thick.
    Discard: draw the cards in zone "discard" face-up with a tiny
        offset each, so the pile looks fanned.
    """
    top_3_in_discard = []
    discard_parse_count = 0
    deck_parse_count = 0

    for card in cards:
        if card["zone"] == "deck":
            deck_parse_count += 1
        if card["zone"] == "discard":
            discard_parse_count += 1
            top_3_in_discard.append(card)
        if discard_parse_count == 3:
            break

    # cards in deck: bottom layer first, top card drawn LAST (on top).
    # draw only as many layers as the pile actually has.
    for i in range(min(3, deck_parse_count) - 1, -1, -1):
        rect = pygame.Rect((0, 0), CARD_SIZE)
        rect.center = (DECK_POS[0], DECK_POS[1] - 2 * i)
        screen.blit(back, rect)

    # cards in discard: centered on the card's own pos, offset per layer
    move_over = 0
    for card in top_3_in_discard[::-1]:
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
        screen.blit(label, label.get_rect(midright=(410, grid_mid_y)))

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
    draw_piles(screen, state["cards"], faces, back)
    for card in state["cards"]:
        if card["zone"] in ("hand", "grid"):
            draw_card(screen, card, faces, back)
