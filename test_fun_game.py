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

import fun_game as g          # noqa: E402  (after sys.path setup)


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


if __name__ == "__main__":
    unittest.main()
