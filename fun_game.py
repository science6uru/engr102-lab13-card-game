import random

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
    """Return ONE card as a dict"""
    raise NotImplementedError("Stage 1: make_card")


def make_deck():
    """Return a list of 52 card dicts, one for every suit x rank."""
    raise NotImplementedError("Stage 1: make_deck")


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
