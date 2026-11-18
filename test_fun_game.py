"""Headless tests for fun_game.py - Stage 1 harness (issue #1).

No window, no pygame, no sound card needed. Run from this folder:

    python -m unittest -v test_fun_game

Every test is one numbered case from game_plan.txt section 4. A stage is
finished when its tests pass.

Tests written with the help of GLM 5.3 (AI-assisted code, allowed by the
lab rules; the planning document and reflection stay team-written).
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Stage 3+ needs pygame headless.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import fun_game as g          # noqa: E402  (after sys.path setup)
import pygame                 # noqa: E402


class Stage1CardsAsData(unittest.TestCase):
    """Issue #1 - make_card and make_deck."""

    def test_1_1_deck_has_52_unique_cards(self):
        """make_deck(): 52 cards, every (suit, rank) pair exactly once."""
        deck = g.make_deck()
        self.assertEqual(len(deck), 52)
        pairs = {(c["suit"], c["rank"]) for c in deck}
        self.assertEqual(pairs, {(s, r) for s in g.SUITS for r in g.RANKS})

    def test_1_2_make_card_starting_values(self):
        """make_card("hearts", "queen") starts with the contract values."""
        card = g.make_card("hearts", "queen")
        self.assertEqual(card["suit"], "hearts")
        self.assertEqual(card["rank"], "queen")
        self.assertEqual(card["zone"], "deck")
        self.assertIsNone(card["slot"])
        self.assertIsNone(card["owner"])
        self.assertFalse(card["face_up"])
        self.assertIsNone(card["motion"])
        self.assertEqual(card["target"], [0.0, 0.0])
        # pos must EQUAL DECK_POS and be a LIST, not the tuple itself
        self.assertEqual(card["pos"], list(g.DECK_POS))
        self.assertIsInstance(card["pos"], list)

    def test_1_3_cards_do_not_share_a_position(self):
        """Moving card A in place must not move card B or the constant.

        The trap: pos=DECK_POS with list(pos) forgotten means every card
        edits the SAME position list.
        """
        a = g.make_card("hearts", "queen")
        b = g.make_card("clubs", "2")
        a["pos"][0] = 5                       # change A's pos IN PLACE
        self.assertEqual(b["pos"], list(g.DECK_POS))
        self.assertEqual(g.DECK_POS, (430, 330))

    def test_1_4_slot_layout_fits_and_does_not_overlap(self):
        """Every grid/hand slot, deck and discard: inside the window,
        card rectangles never overlapping."""
        self.assertEqual(len(g.PLAYER_GRID_SLOTS), g.NUM_PLAYERS)
        centers = []
        for slots in g.PLAYER_GRID_SLOTS:
            self.assertEqual(len(slots), 4)
            centers.extend(slots)
        for slots in g.PLAYER_HAND_SLOTS:
            centers.extend(slots)
        centers.extend([g.DECK_POS, g.DISCARD_POS])
        w, h = g.CARD_SIZE
        win_w, win_h = g.WINDOW_SIZE
        for x, y in centers:
            self.assertTrue(x - w / 2 >= 0 and x + w / 2 <= win_w,
                            f"slot {(x, y)} sticks out sideways")
            self.assertTrue(y - h / 2 >= 0 and y + h / 2 <= win_h,
                            f"slot {(x, y)} sticks out vertically")
        boxes = [(x - w / 2, y - h / 2, x + w / 2, y + h / 2)
                 for x, y in centers]
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                overlaps = (a[0] < b[2] and b[0] < a[2]
                            and a[1] < b[3] and b[1] < a[3])
                self.assertFalse(
                    overlaps,
                    f"card rectangles of {centers[i]} and {centers[j]} overlap")

    def test_1_5_make_card_owner_starts_none(self):
        """A fresh card belongs to no player yet."""
        self.assertIsNone(g.make_card("spades", "10")["owner"])


def card(suit="hearts", rank="queen"):
    """Stand-in for make_card() until Stage 1 merges - same contract.

    Lets the Stage 2 tests run while make_card is still a stub. Once
    Stage 1 lands, these tests could use g.make_card directly.
    """
    return {"suit": suit, "rank": rank, "pos": list(g.DECK_POS),
            "face_up": False, "zone": "deck", "slot": None,
            "owner": None, "motion": None, "target": [0.0, 0.0]}


def deck_of_52():
    """52 fresh cards via the stand-in (avoids the make_deck stub)."""
    return [card(s, r) for s in g.SUITS for r in g.RANKS]


class Stage2ZonesShufflingDealing(unittest.TestCase):
    """Issue #2 - reset_card_zone, shuffle_deck, deal_card, make_state."""

    def test_2_1_reset_zone_without_pos(self):
        """zone/slot/face_up change; motion is left alone."""
        c = card()
        c["motion"] = "glide"                     # must NOT be touched
        g.reset_card_zone(c, "grid", slot=2, face_up=True)
        self.assertEqual(c["zone"], "grid")
        self.assertEqual(c["slot"], 2)
        self.assertTrue(c["face_up"])
        self.assertEqual(c["motion"], "glide")

    def test_2_2_reset_zone_with_pos_teleports_and_clears_motion(self):
        """Giving a pos moves the card there and clears motion."""
        c = card()
        c["motion"] = "glide"
        c["pos"] = [0.0, 0.0]
        g.reset_card_zone(c, "discard", pos=g.DISCARD_POS)
        self.assertEqual(c["pos"], list(g.DISCARD_POS))
        self.assertIsNone(c["motion"])
        self.assertEqual(c["zone"], "discard")

    def test_2_3_shuffle_keeps_same_cards_different_order(self):
        """Same 52 (suit, rank) pairs, different order. Needs the real
        make_deck, so this test stays RED until Stage 1 merges."""
        deck = g.make_deck()
        before = sorted((c["suit"], c["rank"]) for c in deck)
        g.shuffle_deck(deck)
        after = sorted((c["suit"], c["rank"]) for c in deck)
        self.assertEqual(before, after)
        self.assertNotEqual([c["suit"] for c in deck],
                            [c["suit"] for c in sorted(
                                deck, key=lambda c: (c["suit"], c["rank"]))])

    def test_2_4_deal_from_empty_deck_returns_none(self):
        """Empty deck: None, no crash, hand unchanged."""
        hand = [None] * 5
        self.assertIsNone(g.deal_card([], hand))
        self.assertEqual(hand, [None] * 5)

    def test_2_5_deal_moves_top_card_into_the_hand(self):
        """Fresh deck into an empty hand: hand[0] is the card, it is
        face up in zone "hand" slot 0, and the deck shrinks by 1."""
        deck = deck_of_52()
        top = deck[0]
        hand = [None] * 1
        dealt = g.deal_card(deck, hand)
        self.assertIs(dealt, top)
        self.assertIs(hand[0], top)
        self.assertEqual(top["zone"], "hand")
        self.assertEqual(top["slot"], 0)
        self.assertTrue(top["face_up"])
        self.assertEqual(len(deck), 51)

    def test_2_6_deal_into_full_hand_returns_none(self):
        """Full hand: None, nothing changes anywhere."""
        deck = deck_of_52()
        full = [card() for _ in range(2)]
        self.assertIsNone(g.deal_card(deck, full))
        self.assertEqual(len(deck), 52)

    def test_2_7_dealing_to_player_1_leaves_player_0_alone(self):
        """deal_card into player 1's hand: player 0's hand stays empty."""
        state = g.make_state(2)
        deck = deck_of_52()
        g.deal_card(deck, state["players"][1]["hand_occ"])
        self.assertIsNotNone(state["players"][1]["hand_occ"][0])
        self.assertEqual(state["players"][0]["hand_occ"], [None])

    def test_2_8_make_state_players_are_separate(self):
        """Two players, OWN lists each, current starts at 0."""
        state = g.make_state(2)
        self.assertEqual(len(state["players"]), 2)
        self.assertEqual(state["current"], 0)
        state["players"][0]["grid_occ"][0] = "x"
        self.assertIsNone(state["players"][1]["grid_occ"][0])

    def test_2_9_reset_zone_sets_and_clears_owner(self):
        """owner=1 sticks in "grid"; moving to "discard" clears it."""
        c = card()
        g.reset_card_zone(c, "grid", slot=1, owner=1)
        self.assertEqual(c["owner"], 1)
        g.reset_card_zone(c, "discard")
        self.assertIsNone(c["owner"])


class Stage3Loading(unittest.TestCase):
    """Issue #3 - loading pictures and sounds (ported from
    test_resource_loader.py, unittest + numbering per team harness)."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))   # convert_alpha needs a display

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_3_1_deck_faces_has_52_entries(self):
        faces = g.load_deck_faces()
        self.assertEqual(len(faces), 52)
        for suit in g.SUITS:
            for rank in g.RANKS:
                self.assertIn((suit, rank), faces)

    def test_3_2_every_picture_is_card_size(self):
        faces = g.load_deck_faces()
        back = g.load_card_back()
        for face in faces.values():
            self.assertEqual(face.get_size(), g.CARD_SIZE)
        self.assertEqual(back.get_size(), g.CARD_SIZE)

    def test_3_3_load_sfx_returns_every_kind(self):
        sfx = g.load_sfx()
        for kind in ["slide", "place", "shove", "fan", "shuffle",
                     "pack_open", "pack_take_out"]:
            self.assertIn(kind, sfx)
            self.assertIsInstance(sfx[kind], list)
            self.assertTrue(sfx[kind], f"no sounds loaded for {kind!r}")

    def test_3_4_play_never_repeats_a_variant(self):
        class FakeSound:
            def __init__(self, name):
                self.name = name
                self.play_count = 0

            def play(self):
                self.play_count += 1

        sounds = {"slide": [FakeSound("sound1"), FakeSound("sound2")]}
        g._last_played.clear()

        previous = None
        for _ in range(100):
            g.play(sounds, "slide")
            played = sounds["slide"][g._last_played["slide"]].name
            self.assertNotEqual(played, previous)
            previous = played

        # No sounds / unknown kind: play() does nothing, no crash.
        g.play({}, "slide")
        g.play({"slide": []}, "slide")
        g.play({"place": []}, "slide")


if __name__ == "__main__":
    unittest.main()
