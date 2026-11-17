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
    raise NotImplementedError("Stage 2: reset_card_zone")


def shuffle_deck(deck):
    raise NotImplementedError("Stage 2: shuffle_deck")


def deal_card(deck, hand):
    raise NotImplementedError("Stage 2: deal_card")


def make_state(num_players=NUM_PLAYERS):
    raise NotImplementedError("Stage 2: make_state")
