import pygame

from resource_loader import (
    load_deck_faces,
    load_card_back,
    load_sfx,
    play
)

from fun_game import CARD_SIZE, SUITS, RANKS


def test_deck_faces():
    faces = load_deck_faces()

    assert len(faces) == 52

    for suit in SUITS:
        for rank in RANKS:
            assert (suit, rank) in faces


def test_card_sizes():
    faces = load_deck_faces()
    back = load_card_back()

    for face in faces.values():
        assert face.get_size() == CARD_SIZE

    assert back.get_size() == CARD_SIZE


def test_sfx_keys():
    sfx = load_sfx()

    expected = [
        "slide",
        "place",
        "shove",
        "fan",
        "shuffle",
        "pack_open",
        "pack_take_out"
    ]

    for kind in expected:
        assert kind in sfx
        assert isinstance(sfx[kind], list)


def test_no_repeated_sounds():
    class FakeSound:
        def __init__(self, name):
            self.name = name
            self.play_count = 0

        def play(self):
            self.play_count += 1

    sounds = {
        "slide": [
            FakeSound("sound1"),
            FakeSound("sound2")
        ]
    }

    # Reset previous-play tracking for this test.
    import resource_loader
    resource_loader._last_played.clear()

    previous = None

    for _ in range(100):
        play(sounds, "slide")

        # Determine the most recently played sound using
        # the stored index.
        played = sounds["slide"][
            resource_loader._last_played["slide"]
        ].name

        assert played != previous
        previous = played

    play({}, "slide")
    play({"slide": []}, "slide")
    play({"place": []}, "slide")


if __name__ == "__main__":
    pygame.init()
    pygame.display.set_mode((1, 1))

    test_deck_faces()
    test_card_sizes()
    test_sfx_keys()
    test_no_repeated_sounds()

    print("All Stage 3 tests passed!")

    pygame.quit()