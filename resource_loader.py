import os
import glob
import random
import pygame

# Assumes CARD_SIZE, SUITS, and RANKS are defined in your project.
from fun_game import CARD_SIZE, SUITS, RANKS


# Remember the last sound variant played for each kind.
_last_played = {}


def scale_card(surface):
    """Resize a card image to CARD_SIZE."""
    return pygame.transform.smoothscale(surface, CARD_SIZE)


def load_card_face(suit, rank):
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

    try:
        for kind in kinds:
            # Convert underscores to hyphens for filenames.
            filename_kind = kind.replace("_", "-")

            pattern = os.path.join(
                sfx_dir,
                f"{filename_kind}-*.ogg"
            )

            files = glob.glob(pattern)

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