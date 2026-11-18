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
import io
import contextlib
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
        self.assertEqual(g.DECK_POS, (460, 330))

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


class Stage4Drawing(unittest.TestCase):
    """Issue #4 - drawing a still table."""

    def test_4_1_card_rect_size_and_center(self):
        card = g.make_card("hearts", "queen")
        card["pos"] = [123.4, 77.7]
        rect = g.card_rect(card)
        self.assertEqual(rect.size, g.CARD_SIZE)
        self.assertEqual(rect.center, (123, 78))

    def test_4_2_current_texture_face_or_back(self):
        face = pygame.Surface((7, 7))    # dummy "face" surface
        back = pygame.Surface((9, 9))    # dummy "back" surface
        faces = {("hearts", "queen"): face}
        card = g.make_card("hearts", "queen")

        card["face_up"] = True
        self.assertIs(g.current_texture(card, faces, back), face)
        card["face_up"] = False
        self.assertIs(g.current_texture(card, faces, back), back)


class Stage5LoopAndVsync(unittest.TestCase):
    """Issue #5 - the game loop, time and vsync."""

    def test_5_1_main_runs_120_frames_headless(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            g.main(frames=120)
        out = buf.getvalue()
        self.assertTrue(out.startswith("pacing:"), out)
        self.assertIn("120 frames", out)


def placed(suit, rank, zone="hand", slot=0, owner=0, pos=(100, 100),
           face_up=True):
    """A real make_card put on the table the official way."""
    c = g.make_card(suit, rank, face_up=face_up)
    g.reset_card_zone(c, zone, pos=pos, slot=slot, owner=owner)
    return c


class Stage6PickingUp(unittest.TestCase):
    """Issue #8 - blend, top_card_at, begin_drag, update_drag."""

    def test_6_0_make_card_has_the_announced_keys(self):
        """Contract: the new drag keys exist with their starting values."""
        c = g.make_card("hearts", "queen")
        self.assertFalse(c["dragging"])
        self.assertEqual(c["drag_offset"], (0.0, 0.0))
        self.assertEqual(c["press_pos"], (0.0, 0.0))

    def test_6_1_top_card_wins_empty_table_gives_none(self):
        """Two overlapping cards: the LATER one in the list is on top."""
        a = placed("hearts", "queen", slot=0, pos=(100, 100))
        b = placed("clubs", "2", slot=1, pos=(110, 100))
        point = (105, 100)                   # inside both rectangles
        self.assertIs(g.top_card_at([a, b], point), b)
        self.assertIs(g.top_card_at([b, a], point), a)
        self.assertIsNone(g.top_card_at([a, b], (900, 600)))
        self.assertIsNone(g.top_card_at([], point))

    def test_6_2_deck_cards_are_never_returned(self):
        """A card in zone "deck" cannot be grabbed, even under the point."""
        c = g.make_card("hearts", "queen")   # zone "deck" at DECK_POS
        self.assertIsNone(g.top_card_at([c], g.DECK_POS))

    def test_6_3_begin_drag_remembers_grab_offset(self):
        """Card at [100,100], mouse (110,90): offset is (-10, 10)."""
        c = placed("hearts", "queen", pos=(100, 100))
        g.begin_drag(c, (110, 90), {})
        self.assertTrue(c["dragging"])
        self.assertEqual(c["drag_offset"], (-10, 10))
        self.assertEqual(c["press_pos"], (110, 90))

    def test_6_4_update_drag_eases_toward_the_cursor(self):
        """One frame: strictly between start and target. Two seconds:
        within 1 pixel of the target."""
        c = placed("hearts", "queen", pos=(100, 100))
        g.begin_drag(c, (100, 100), {})      # offset (0, 0)
        g.update_drag(c, (200, 100), 1 / 120)
        self.assertGreater(c["pos"][0], 100)
        self.assertLess(c["pos"][0], 200)
        for _ in range(240):                 # 240 frames x 1/120 s = 2 s
            g.update_drag(c, (200, 100), 1 / 120)
        self.assertAlmostEqual(c["pos"][0], 200, delta=1)

    def test_6_5_blend_is_frame_rate_independent(self):
        """One second of frames leaves the same distance at 60 and 240 fps."""
        rate = 12
        left_60 = 1.0
        for _ in range(60):
            left_60 *= 1 - g.blend(rate, 1 / 60)
        left_240 = 1.0
        for _ in range(240):
            left_240 *= 1 - g.blend(rate, 1 / 240)
        self.assertAlmostEqual(left_60, left_240, delta=1e-9)

    def test_6_6_top_card_at_respects_the_owner_filter(self):
        """owner=1 ignores player 0's card under the point."""
        mine = placed("hearts", "queen", owner=0, slot=0, pos=(100, 100))
        theirs = placed("clubs", "2", owner=1, slot=0, pos=(100, 100))
        point = (100, 100)
        # player 0's card is LATER (on top), yet owner=1 must skip it
        self.assertIs(g.top_card_at([theirs, mine], point, owner=1), theirs)
        self.assertIsNone(g.top_card_at([mine], point, owner=1))
        self.assertIs(g.top_card_at([theirs, mine], point), mine)


class Stage7FlippingAndClicking(unittest.TestCase):
    """Issue #14 - flip_card, pickup_flip, release_card (click vs drag)."""

    def setUp(self):
        self.state = g.make_state(2)
        self.state["sfx"] = {}

    def test_7_0_pickup_flip_key_starts_false(self):
        """Contract: make_card gains pickup_flip, starting False."""
        self.assertFalse(g.make_card("hearts", "queen")["pickup_flip"])

    def test_7_1_flip_card_toggles_immediately(self):
        c = placed("hearts", "queen", face_up=True)
        g.flip_card(c, {})
        self.assertFalse(c["face_up"])
        g.update_card(c, g.FLIP_DURATION + 0.01, (0, 0), {})   # spin ends
        g.flip_card(c, {})
        self.assertTrue(c["face_up"])

    def test_7_2_click_on_a_face_up_card_flips_it_down(self):
        c = placed("hearts", "queen", face_up=True, pos=(100, 100))
        g.begin_drag(c, (100, 100), {})
        g.release_card(c, (100, 100), self.state)
        self.assertFalse(c["face_up"])
        self.assertFalse(c["dragging"])

    def test_7_3_click_on_a_face_down_card_reveals_it_once(self):
        c = placed("hearts", "queen", face_up=False, pos=(100, 100))
        g.begin_drag(c, (100, 100), {})
        self.assertTrue(c["face_up"])        # flipped as it was lifted
        self.assertTrue(c["pickup_flip"])
        g.release_card(c, (100, 100), self.state)
        self.assertTrue(c["face_up"])        # NOT flipped back down
        self.assertFalse(c["pickup_flip"])

    def test_7_4_a_real_drag_is_not_a_click(self):
        """Extra: moving 8 px or more before release never flips."""
        up = placed("hearts", "queen", face_up=True, pos=(100, 100))
        g.begin_drag(up, (100, 100), {})
        g.release_card(up, (100 + g.CLICK_DIST, 100), self.state)
        self.assertTrue(up["face_up"])       # a drag leaves it as it was
        down = placed("clubs", "2", face_up=False, pos=(100, 100))
        g.begin_drag(down, (100, 100), {})
        g.release_card(down, (300, 100), self.state)
        self.assertTrue(down["face_up"])     # revealed by lifting, once


class Stage8PlacingSwappingDiscarding(unittest.TestCase):
    """Issue #16 - send_card and the drop decision in release_card."""

    def setUp(self):
        self.state = g.make_state(2)
        self.state["sfx"] = {}

    def hand_card(self, player=0, suit="hearts", rank="queen"):
        """A face-up card sitting in that player's hand slot 0."""
        pos = g.PLAYER_HAND_SLOTS[player][0]
        c = placed(suit, rank, zone="hand", slot=0, owner=player, pos=pos)
        self.state["players"][player]["hand_occ"][0] = c
        return c

    def grid_card(self, player, slot, suit="clubs", rank="2"):
        """A face-up card sitting in that player's grid slot."""
        pos = g.PLAYER_GRID_SLOTS[player][slot]
        c = placed(suit, rank, zone="grid", slot=slot, owner=player, pos=pos)
        self.state["players"][player]["grid_occ"][slot] = c
        return c

    def drop(self, c, point):
        """Pick the card up where it sits, then let go at point."""
        g.begin_drag(c, tuple(c["pos"]), {})
        g.release_card(c, point, self.state)

    def test_8_0_send_card_sets_target_without_teleporting(self):
        """Contract: glide + target + zone/slot/owner, pos untouched."""
        c = self.hand_card()
        before = list(c["pos"])
        g.send_card(c, g.PLAYER_GRID_SLOTS[0][3], "grid", 3, owner=0)
        self.assertEqual(c["motion"], "glide")
        self.assertEqual(c["target"], list(g.PLAYER_GRID_SLOTS[0][3]))
        self.assertEqual(c["zone"], "grid")
        self.assertEqual(c["slot"], 3)
        self.assertEqual(c["owner"], 0)
        self.assertEqual(c["pos"], before)

    def test_8_1_nearest_slot_wins(self):
        """x = 770 is between slots 0 (700) and 1 (810): slot 1 is nearer."""
        c = self.hand_card()
        self.drop(c, (770, 415))
        self.assertEqual(c["zone"], "grid")
        self.assertEqual(c["slot"], 1)

    def test_8_2_place_into_an_empty_slot(self):
        c = self.hand_card()
        self.drop(c, g.PLAYER_GRID_SLOTS[0][2])
        p0 = self.state["players"][0]
        self.assertEqual(c["zone"], "grid")
        self.assertEqual(c["slot"], 2)
        self.assertEqual(c["owner"], 0)           # send_card kept the owner
        self.assertIs(p0["grid_occ"][2], c)
        self.assertIsNone(p0["hand_occ"][0])
        self.assertEqual(c["target"], list(g.PLAYER_GRID_SLOTS[0][2]))

    def test_8_3_swap_sends_the_old_card_to_the_discard_face_up(self):
        old = self.grid_card(0, 0)
        old["face_up"] = False
        c = self.hand_card()
        self.drop(c, g.PLAYER_GRID_SLOTS[0][0])
        p0 = self.state["players"][0]
        self.assertEqual(old["zone"], "discard")
        self.assertTrue(old["face_up"])
        self.assertIsNone(old["owner"])
        self.assertEqual(old["target"], list(g.DISCARD_POS))
        self.assertIs(p0["grid_occ"][0], c)
        self.assertEqual(c["zone"], "grid")
        self.assertIsNone(p0["hand_occ"][0])

    def test_8_4_discard(self):
        c = self.hand_card()
        self.drop(c, g.DISCARD_POS)
        self.assertEqual(c["zone"], "discard")
        self.assertIsNone(c["owner"])
        self.assertTrue(c["face_up"])
        self.assertIsNone(self.state["players"][0]["hand_occ"][0])
        self.assertEqual(c["target"], list(g.DISCARD_POS))

    def test_8_5_far_from_everything_goes_home(self):
        c = self.hand_card()
        self.drop(c, (100, 600))
        self.assertEqual(c["zone"], "hand")
        self.assertEqual(c["slot"], 0)
        self.assertEqual(c["owner"], 0)
        self.assertIs(self.state["players"][0]["hand_occ"][0], c)
        self.assertEqual(c["target"], list(g.PLAYER_HAND_SLOTS[0][0]))

    def test_8_6_cannot_drop_on_the_other_players_grid(self):
        c = self.hand_card(player=1)
        self.drop(c, g.PLAYER_GRID_SLOTS[0][0])   # player 0's grid
        self.assertEqual(c["zone"], "hand")
        self.assertEqual(c["owner"], 1)
        self.assertEqual(c["target"], list(g.PLAYER_HAND_SLOTS[1][0]))
        self.assertEqual(self.state["players"][0]["grid_occ"], [None] * 4)

    def test_8_7_player_1_places_into_player_1s_grid(self):
        c = self.hand_card(player=1)
        self.drop(c, g.PLAYER_GRID_SLOTS[1][0])
        self.assertIs(self.state["players"][1]["grid_occ"][0], c)
        self.assertEqual(c["owner"], 1)
        self.assertEqual(self.state["players"][0]["grid_occ"], [None] * 4)

    def test_8_8_dropping_on_its_own_slot_settles_back(self):
        c = self.grid_card(0, 1)
        x, y = g.PLAYER_GRID_SLOTS[0][1]
        self.drop(c, (x + 20, y))                 # moved, so not a click
        p0 = self.state["players"][0]
        self.assertEqual(c["zone"], "grid")
        self.assertEqual(c["slot"], 1)
        self.assertIs(p0["grid_occ"][1], c)
        self.assertEqual(c["target"], list(g.PLAYER_GRID_SLOTS[0][1]))
        self.assertEqual(sum(1 for s in p0["grid_occ"] if s), 1)

    def test_8_9_a_grid_card_dropped_on_the_discard_empties_its_slot(self):
        c = self.grid_card(0, 1)
        self.drop(c, g.DISCARD_POS)
        self.assertEqual(c["zone"], "discard")
        self.assertIsNone(self.state["players"][0]["grid_occ"][1])

    def test_8_10_a_click_never_triggers_a_drop(self):
        """The click check returns early: no glide, nothing moves slots."""
        c = self.grid_card(0, 1)
        g.begin_drag(c, tuple(c["pos"]), {})
        g.release_card(c, tuple(c["pos"]), self.state)
        self.assertIsNone(c["motion"])
        self.assertIs(self.state["players"][0]["grid_occ"][1], c)


class Stage9MovementOverTime(unittest.TestCase):
    """Issue #17 - gliding, dealing, the queue and update()."""

    def setUp(self):
        self.state = g.make_state(2)
        self.state["sfx"] = {}

    def full_deck(self):
        self.state["cards"] = g.make_deck()
        self.state["deck"] = list(self.state["cards"])

    def run_frames(self, seconds, fps=60, mouse=(0, 0)):
        for _ in range(round(seconds * fps)):
            g.update(self.state, 1 / fps, mouse, {})

    def test_9_0_make_card_has_the_announced_keys(self):
        c = g.make_card("hearts", "queen")
        self.assertEqual(c["t"], 0.0)
        self.assertEqual(c["start"], [0.0, 0.0])
        self.assertEqual(c["arc"], 0.0)

    def test_9_1_glide_lands_on_the_slot(self):
        c = placed("hearts", "queen", zone="hand", owner=0,
                   pos=g.PLAYER_HAND_SLOTS[0][0])
        self.state["cards"].append(c)
        g.send_card(c, g.PLAYER_GRID_SLOTS[0][3], "grid", 3, owner=0)
        self.run_frames(2)
        self.assertIsNone(c["motion"])
        self.assertEqual(c["pos"], list(g.PLAYER_GRID_SLOTS[0][3]))
        self.assertEqual(c["zone"], "grid")
        self.assertEqual(c["slot"], 3)

    def test_9_2_glide_lands_at_30_60_and_240_fps(self):
        for fps in (30, 60, 240):
            c = placed("hearts", "queen", zone="hand", owner=0,
                       pos=g.PLAYER_HAND_SLOTS[0][0])
            self.state["cards"] = [c]
            g.send_card(c, g.PLAYER_GRID_SLOTS[0][3], "grid", 3, owner=0)
            self.run_frames(2, fps=fps)
            self.assertIsNone(c["motion"], f"still gliding at {fps} fps")
            self.assertEqual(c["pos"], list(g.PLAYER_GRID_SLOTS[0][3]))

    def test_9_3_deal_to_hand_lands_in_the_hand(self):
        self.full_deck()
        card = g.deal_to_hand(self.state, 1, {})
        self.run_frames(0.6, fps=120)
        target = g.PLAYER_HAND_SLOTS[1][0]
        self.assertAlmostEqual(card["pos"][0], target[0], delta=1)
        self.assertAlmostEqual(card["pos"][1], target[1], delta=1)
        self.assertEqual(card["owner"], 1)
        self.assertIs(self.state["players"][1]["hand_occ"][0], card)
        self.assertEqual(self.state["players"][0]["hand_occ"], [None])
        self.assertTrue(card["face_up"])
        self.assertEqual(card["zone"], "hand")
        self.assertIsNone(card["motion"])

    def test_9_4_deal_from_an_empty_deck_sets_a_message(self):
        self.state["deck"] = []
        self.assertIsNone(g.deal_to_hand(self.state, 0, {}))
        self.assertEqual(self.state["message"], "deck is empty!")
        self.assertEqual(self.state["message_t"], 1.5)
        self.run_frames(1.6)                      # the message times out
        self.assertFalse(self.state["message"])

    def test_9_4b_deal_into_a_full_hand_says_hand_is_full(self):
        self.full_deck()
        g.deal_to_hand(self.state, 0, {})
        self.assertIsNone(g.deal_to_hand(self.state, 0, {}))
        self.assertEqual(self.state["message"], "hand is full!")
        self.assertEqual(len(self.state["deck"]), 51)

    def test_9_5_reset_table_deals_four_face_down_cards_each(self):
        g.reset_table(self.state, {})
        self.run_frames(3)
        for player in (0, 1):
            grid = self.state["players"][player]["grid_occ"]
            self.assertEqual(len(grid), 4)
            for slot, c in enumerate(grid):
                self.assertIsNotNone(c)
                self.assertFalse(c["face_up"])
                self.assertEqual(c["owner"], player)
                self.assertEqual(c["slot"], slot)
                self.assertIsNone(c["motion"])
                self.assertEqual(c["pos"],
                                 list(g.PLAYER_GRID_SLOTS[player][slot]))
        self.assertEqual(len(self.state["deck"]), 44)
        self.assertEqual(len(self.state["cards"]), 52)
        self.assertEqual(self.state["queue"], [])

    def test_9_5b_reset_table_queue_alternates_players(self):
        g.reset_table(self.state, {})
        queue = self.state["queue"]
        self.assertEqual(len(queue), 8)
        for i, (delay, player, slot) in enumerate(queue):
            self.assertAlmostEqual(delay, 0.2 + 0.18 * i)
            self.assertEqual(player, i % 2)
            self.assertEqual(slot, i // 2)

    def test_9_6_dragging_moves_only_once_per_frame(self):
        """update must not call update_drag in addition to update_motion."""
        c = placed("hearts", "queen", pos=(100, 100))
        self.state["cards"] = [c]
        g.begin_drag(c, (100, 100), {})
        g.update(self.state, 1 / 120, (200, 100), {})
        expected = 100 + 100 * g.blend(g.DRAG_FOLLOW, 1 / 120)
        self.assertAlmostEqual(c["pos"][0], expected)


def golf_card(rank, face_up=False, owner=0, zone="grid", slot=None):
    """A card of the given rank for the Golf rule tests."""
    c = g.make_card("hearts", rank)
    g.reset_card_zone(c, zone, slot=slot, face_up=face_up, owner=owner)
    return c


class Stage11GolfRules(unittest.TestCase):
    """Issue #20 - four-card Golf: scoring, legal moves, turns, winner."""

    def setUp(self):
        self.state = g.make_state(2)

    def test_11_0_card_values(self):
        values = {"ace": 1, "2": -2, "3": 3, "10": 10,
                  "jack": 10, "queen": 10, "king": 0}
        for rank, points in values.items():
            self.assertEqual(g.card_value(golf_card(rank)), points, rank)

    def test_11_1_score_grid_known_grid(self):
        """ace + 5 (column 0,2) and queen + 3 (column 1,3) = 1+5+10+3."""
        grid = [golf_card("ace"), golf_card("queen"),
                golf_card("5"), golf_card("3")]
        self.assertEqual(g.score_grid(grid), 19)

    def test_11_2_score_grid_empty_pair_and_king(self):
        self.assertEqual(g.score_grid([None] * 4), 0)
        # a pair of 7s in column (0,2) scores 0; the other column 2 + king
        grid = [golf_card("7"), golf_card("2"),
                golf_card("7"), golf_card("king")]
        self.assertEqual(g.score_grid(grid), -2)
        # equal ranks in a ROW (slots 0,1) are not a pair
        row = [golf_card("7"), golf_card("7"), golf_card("ace"),
               golf_card("king")]
        self.assertEqual(g.score_grid(row), 7 + 7 + 1)

    def test_11_3_legal_move_rules(self):
        s = self.state
        held = golf_card("9", face_up=True, zone="hand", slot=0)
        s["phase"] = "place"
        s["drawn_from"] = "deck"
        self.assertTrue(g.legal_move(s, held, ("grid", 2)))
        self.assertTrue(g.legal_move(s, held, ("discard", None)))
        self.assertTrue(g.legal_move(s, held, ("hand", None)))
        self.assertFalse(g.legal_move(s, held, ("grid", 4)))   # no slot 4
        # taken from the discard: it must be swapped in, never thrown back
        s["drawn_from"] = "discard"
        self.assertFalse(g.legal_move(s, held, ("discard", None)))
        self.assertTrue(g.legal_move(s, held, ("grid", 0)))
        # wrong phase: nothing may be dropped before drawing
        s["phase"] = "draw"
        self.assertFalse(g.legal_move(s, held, ("grid", 0)))
        # grid cards cannot be dragged around on their own
        s["phase"] = "place"
        in_grid = golf_card("9", zone="grid", slot=1)
        self.assertFalse(g.legal_move(s, in_grid, ("grid", 2)))

    def test_11_4_next_turn_wraps_to_first_player(self):
        s = self.state
        s["phase"] = "place"
        s["current"] = 1
        g.next_turn(s)
        self.assertEqual(s["current"], 0)
        self.assertEqual(s["phase"], "draw")
        self.assertIsNone(s["drawn_from"])

    def test_11_4b_ender_gives_everyone_else_one_final_turn(self):
        s = self.state
        s["players"][0]["grid_occ"] = [golf_card("3", face_up=True)
                                       for _ in range(4)]
        s["current"] = 0
        g.next_turn(s)                       # player 0 turned the last card
        self.assertEqual(s["ender"], 0)
        self.assertEqual(s["current"], 1)
        self.assertFalse(g.round_over(s))    # player 1 still has a turn
        g.next_turn(s)                       # the final turn is done
        self.assertTrue(g.round_over(s))

    def test_11_5_game_over_only_after_the_last_hole(self):
        s = self.state
        self.assertFalse(g.game_over(s))
        for _ in range(g.HOLES - 1):
            g.end_round(s)
        self.assertFalse(g.game_over(s))     # hole 9 is still being played
        g.end_round(s)
        self.assertTrue(g.game_over(s))

    def test_11_5b_end_round_adds_scores_to_totals(self):
        s = self.state
        s["players"][0]["grid_occ"] = [golf_card("5")] * 4   # two pairs = 0
        s["players"][1]["grid_occ"] = [golf_card("ace"), None,
                                       golf_card("4"), None]
        g.end_round(s)
        self.assertEqual([p["score"] for p in s["players"]], [0, 5])
        g.end_round(s)
        self.assertEqual([p["total"] for p in s["players"]], [0, 10])
        self.assertEqual(s["hole"], 3)

    def test_11_6_winner_is_lowest_total_and_ties_give_none(self):
        s = self.state
        s["players"][0]["total"] = 30
        s["players"][1]["total"] = 12
        self.assertIsNone(g.winner(s))       # game not over yet
        s["hole"] = g.HOLES + 1
        self.assertEqual(g.winner(s), 1)
        s["players"][0]["total"] = 12
        self.assertIsNone(g.winner(s))       # tie

    def test_11_7_cannot_move_the_other_players_cards(self):
        s = self.state
        s["phase"] = "place"
        s["drawn_from"] = "deck"
        theirs = golf_card("9", face_up=True, owner=1, zone="hand", slot=0)
        s["current"] = 0
        self.assertFalse(g.legal_move(s, theirs, ("grid", 0)))
        s["current"] = 1                     # same move, now their turn
        self.assertTrue(g.legal_move(s, theirs, ("grid", 0)))

    def test_11_8_make_state_has_separate_golf_fields(self):
        s = g.make_state(2)
        self.assertEqual(s["phase"], "reveal")
        self.assertEqual(s["hole"], 1)
        self.assertEqual([p["total"] for p in s["players"]], [0, 0])
        s["revealed"][0] = 2
        self.assertEqual(s["revealed"], [2, 0])


# ---- Stage 11 wiring: whole turns played through handle_input ----------
def golf_table(phase="draw", current=0):
    """A Golf table with the rules ON: 4 face-down cards per player.

    Cards are dealt from an UNSHUFFLED deck (so the numbers are known):
    player 0 gets clubs ace, 2, 3, 4; player 1 gets clubs 5, 6, 7, 8; the
    next cards off the deck are clubs 9, 10, ...
    """
    s = g.make_state(2)
    s["rules_on"] = True
    s["sfx"] = {}
    s["phase"] = phase
    s["current"] = current
    deck = g.make_deck()
    s["cards"] = list(deck)
    s["deck"] = list(deck)
    for p in (0, 1):
        for slot in range(4):
            c = s["deck"].pop(0)
            g.reset_card_zone(c, "grid", pos=g.PLAYER_GRID_SLOTS[p][slot],
                              slot=slot, face_up=False, owner=p)
            s["players"][p]["grid_occ"][slot] = c
    return s


def press(s, pos):
    """A left mouse press at pos, sent through handle_input."""
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)
    return g.handle_input([event], s, {}, pos)


def release(s, pos):
    """A left mouse release at pos, sent through handle_input."""
    event = pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos)
    return g.handle_input([event], s, {}, pos)


def key(s, k):
    """A key press, sent through handle_input."""
    return g.handle_input([pygame.event.Event(pygame.KEYDOWN, key=k)],
                          s, {}, (0, 0))


def run(s, seconds):
    """Run update() at 120 fps for that many seconds."""
    for _ in range(int(seconds * 120)):
        g.update(s, 1 / 120, (0, 0), {})


def draw_and_land(s):
    """Player draws from the deck and the card finishes flying to the hand."""
    card = g.draw_from_deck(s, {})
    run(s, 1.0)
    return card


class Stage11Wiring(unittest.TestCase):
    """Issue #20 - the rules hooked up: reveal, draw, place, score."""

    def test_11_9_reveal_phase_two_cards_each_then_play_starts(self):
        s = golf_table("reveal")
        press(s, g.PLAYER_GRID_SLOTS[1][0])        # not your card
        self.assertFalse(s["players"][1]["grid_occ"][0]["face_up"])
        press(s, g.PLAYER_GRID_SLOTS[0][0])
        press(s, g.PLAYER_GRID_SLOTS[0][0])        # already up: ignored
        self.assertEqual(s["revealed"], [1, 0])
        press(s, g.PLAYER_GRID_SLOTS[0][1])
        self.assertEqual((s["current"], s["phase"]), (1, "reveal"))
        press(s, g.PLAYER_GRID_SLOTS[1][2])
        press(s, g.PLAYER_GRID_SLOTS[1][3])
        self.assertEqual((s["current"], s["phase"]), (0, "draw"))
        self.assertEqual(len(s["discard"]), 1)     # the discard pile started
        self.assertTrue(s["discard"][0]["face_up"])
        self.assertEqual(len(s["deck"]), 43)

    def test_11_10_drag_is_not_allowed_before_drawing(self):
        s = golf_table("draw")
        press(s, g.PLAYER_GRID_SLOTS[0][0])
        self.assertFalse(any(c["dragging"] for c in s["cards"]))
        s["phase"] = "place"                       # even holding a card
        press(s, g.PLAYER_GRID_SLOTS[0][0])        # a GRID card stays put
        self.assertFalse(any(c["dragging"] for c in s["cards"]))

    def test_11_11_click_the_deck_or_press_space_draws(self):
        s = golf_table("draw")
        press(s, g.DECK_POS)
        self.assertEqual((s["phase"], s["drawn_from"]), ("place", "deck"))
        self.assertIsNotNone(s["players"][0]["hand_occ"][0])
        self.assertEqual(len(s["deck"]), 43)
        s2 = golf_table("draw")
        self.assertTrue(key(s2, pygame.K_SPACE))
        self.assertEqual(s2["phase"], "place")
        # SPACE does nothing while you already hold a card
        key(s2, pygame.K_SPACE)
        self.assertEqual(len(s2["deck"]), 43)

    def test_11_12_take_the_top_of_the_discard_pile(self):
        s = golf_table("draw")
        top = g.start_discard(s, {})
        run(s, 1.0)
        press(s, g.DISCARD_POS)
        self.assertEqual((s["phase"], s["drawn_from"]), ("place", "discard"))
        self.assertIs(s["players"][0]["hand_occ"][0], top)
        self.assertEqual(s["discard"], [])
        self.assertEqual((top["zone"], top["owner"]), ("hand", 0))

    def test_11_13_swap_replaces_a_grid_card_and_passes_the_turn(self):
        s = golf_table("draw")
        held = draw_and_land(s)
        self.assertEqual(held["pos"], list(g.PLAYER_HAND_SLOTS[0][0]))
        old = s["players"][0]["grid_occ"][2]
        press(s, g.PLAYER_HAND_SLOTS[0][0])
        release(s, g.PLAYER_GRID_SLOTS[0][2])
        self.assertIs(s["players"][0]["grid_occ"][2], held)
        self.assertIsNone(s["players"][0]["hand_occ"][0])
        self.assertEqual(old["zone"], "discard")
        self.assertTrue(old["face_up"])
        self.assertIs(s["discard"][-1], old)       # the newest card is last
        self.assertEqual((s["current"], s["phase"]), (1, "draw"))
        self.assertEqual(s["message"], "PLAYER 2'S TURN")

    def test_11_14_a_drawn_deck_card_may_be_discarded(self):
        s = golf_table("draw")
        held = draw_and_land(s)
        press(s, g.PLAYER_HAND_SLOTS[0][0])
        release(s, g.DISCARD_POS)
        self.assertEqual(held["zone"], "discard")
        self.assertIs(s["discard"][-1], held)
        self.assertIsNone(s["players"][0]["hand_occ"][0])
        self.assertEqual((s["current"], s["phase"]), (0, "flip"))
        key(s, pygame.K_SPACE)
        self.assertEqual((s["current"], s["phase"]), (1, "draw"))

    def test_11_15_a_card_from_the_discard_must_be_swapped_in(self):
        s = golf_table("draw")
        g.start_discard(s, {})
        run(s, 1.0)
        press(s, g.DISCARD_POS)
        run(s, 1.0)
        held = s["players"][0]["hand_occ"][0]
        press(s, g.PLAYER_HAND_SLOTS[0][0])
        release(s, g.DISCARD_POS)                  # not allowed: goes home
        self.assertEqual(held["zone"], "hand")
        self.assertEqual(held["target"], list(g.PLAYER_HAND_SLOTS[0][0]))
        self.assertEqual((s["current"], s["phase"]), (0, "place"))

    def test_11_16_dropping_on_the_other_grid_goes_home(self):
        s = golf_table("draw")
        held = draw_and_land(s)
        press(s, g.PLAYER_HAND_SLOTS[0][0])
        release(s, g.PLAYER_GRID_SLOTS[1][0])
        self.assertEqual(held["zone"], "hand")
        self.assertEqual((s["current"], s["phase"]), (0, "place"))

    def test_11_17_clicking_the_held_card_does_not_flip_it(self):
        s = golf_table("draw")
        held = draw_and_land(s)
        press(s, g.PLAYER_HAND_SLOTS[0][0])
        release(s, g.PLAYER_HAND_SLOTS[0][0])      # a click, not a drag
        self.assertTrue(held["face_up"])
        self.assertEqual(held["target"], list(g.PLAYER_HAND_SLOTS[0][0]))
        self.assertEqual((s["current"], s["phase"]), (0, "place"))

    def test_11_18_a_whole_hole_is_played_and_scored(self):
        s = golf_table("draw")
        for slot in range(3):                      # player 0: 3 cards up
            g.flip_card(s["players"][0]["grid_occ"][slot], {})
        draw_and_land(s)                           # clubs 9
        press(s, g.PLAYER_HAND_SLOTS[0][0])
        release(s, g.PLAYER_GRID_SLOTS[0][3])      # swap the last face-down
        self.assertEqual(s["ender"], 0)            # player 0 is finished
        self.assertEqual((s["current"], s["phase"]), (1, "draw"))
        draw_and_land(s)                           # player 1: the final turn
        press(s, g.PLAYER_HAND_SLOTS[1][0])
        release(s, g.DISCARD_POS)                  # throws clubs 10 away
        self.assertEqual(s["phase"], "flip")        # optional flip offered
        key(s, pygame.K_SPACE)                     # player 1 skips the flip
        self.assertEqual(s["phase"], "round_over")
        g.update(s, 1 / 120, (0, 0), {})           # update scores the hole
        self.assertEqual(s["phase"], "scored")
        self.assertEqual(s["hole"], 2)
        for p in (0, 1):
            for c in s["players"][p]["grid_occ"]:
                self.assertTrue(c["face_up"])      # everything turned over
        # player 0: ace,2 / 3,9 -> (1+3) + (-2+9) = 11; player 1: 5,6 / 7,8 = 26
        self.assertEqual([p["score"] for p in s["players"]], [11, 26])
        self.assertEqual([p["total"] for p in s["players"]], [11, 26])

    def test_11_19_click_after_the_scores_starts_the_next_hole(self):
        s = golf_table("scored")
        s["hole"] = 2
        s["players"][0]["total"] = 11
        press(s, (5, 5))
        self.assertEqual(s["phase"], "reveal")
        self.assertEqual(len(s["queue"]), 8)       # a fresh deal
        self.assertEqual(s["discard"], [])
        self.assertEqual(s["current"], 1)          # the starter rotates
        self.assertEqual(s["players"][0]["total"], 11)   # totals are kept

    def test_11_20_after_the_last_hole_a_click_starts_a_new_game(self):
        s = golf_table("scored")
        s["hole"] = g.HOLES + 1
        s["players"][0]["total"] = 40
        s["players"][1]["total"] = 33
        lines = [text for text, _ in g.golf_hud_lines(s)]
        self.assertIn("PLAYER 2 WINS!", lines)
        key(s, pygame.K_SPACE)
        self.assertEqual(s["hole"], 1)
        self.assertEqual([p["total"] for p in s["players"]], [0, 0])
        self.assertEqual(s["phase"], "reveal")

    def test_11_21_the_deck_is_refilled_from_the_discard_pile(self):
        s = golf_table("draw")
        s["deck"] = []
        for _ in range(4):                         # four cards in the discard
            card = s["cards"][-1 - len(s["discard"])]
            g.send_card(card, g.DISCARD_POS, "discard", None, face_up=True)
            s["discard"].append(card)
        top = s["discard"][-1]
        self.assertTrue(g.refill_deck(s))
        self.assertEqual(len(s["deck"]), 3)
        self.assertEqual(s["discard"], [top])      # the top card stays
        for c in s["deck"]:
            self.assertEqual(c["zone"], "deck")
            self.assertFalse(c["face_up"])
        s["deck"] = []
        s["discard"] = [top]
        self.assertFalse(g.refill_deck(s))         # nothing left to reuse

    def test_11_22_tab_is_ignored_and_r_restarts(self):
        s = golf_table("draw")
        key(s, pygame.K_TAB)
        self.assertEqual(s["current"], 0)          # turns are automatic
        s["players"][1]["total"] = 9
        s["hole"] = 4
        key(s, pygame.K_r)
        self.assertEqual((s["hole"], s["phase"]), (1, "reveal"))
        self.assertEqual(s["players"][1]["total"], 0)

    def test_11_23_the_hud_tells_each_player_what_to_do(self):
        s = golf_table("reveal")
        lines = [text for text, _ in g.golf_hud_lines(s)]
        self.assertEqual(lines[0], "HOLE 1 OF 9")
        self.assertIn("PLAYER 1: FLIP 2 OF YOUR CARDS", lines)
        s["phase"] = "draw"
        s["ender"] = 1
        lines = [text for text, _ in g.golf_hud_lines(s)]
        self.assertIn("PLAYER 1: DRAW A CARD", lines)
        self.assertIn("PLAYER 2 IS DONE: LAST TURN", lines)


class Stage11OptionalFlipAndKnock(unittest.TestCase):
    """After discarding a deck card the flip is OPTIONAL (flip or skip).
    Knocking and the help panel are wired in too."""

    def discard_a_deck_card(self):
        s = golf_table("draw")
        draw_and_land(s)
        press(s, g.PLAYER_HAND_SLOTS[0][0])
        release(s, g.DISCARD_POS)
        return s

    def test_11_24_discarding_offers_an_optional_flip(self):
        s = self.discard_a_deck_card()
        self.assertEqual((s["current"], s["phase"]), (0, "flip"))
        self.assertFalse(any(c["face_up"]
                             for c in s["players"][0]["grid_occ"]))
        self.assertIsNotNone(g.action_button(s))
        self.assertEqual(g.action_button(s)[1], "SKIP")

    def test_11_25_flipping_a_face_down_card_ends_the_turn(self):
        s = self.discard_a_deck_card()
        target = s["players"][0]["grid_occ"][1]
        press(s, g.PLAYER_GRID_SLOTS[0][1])
        self.assertTrue(target["face_up"])
        self.assertEqual((s["current"], s["phase"]), (1, "draw"))

    def test_11_26_only_your_own_face_down_cards_can_be_flipped(self):
        s = self.discard_a_deck_card()
        press(s, g.PLAYER_GRID_SLOTS[1][0])        # the other player's card
        self.assertFalse(s["players"][1]["grid_occ"][0]["face_up"])
        self.assertEqual((s["current"], s["phase"]), (0, "flip"))
        g.flip_card(s["players"][0]["grid_occ"][0], {})   # already face up
        run(s, 1.0)
        press(s, g.PLAYER_GRID_SLOTS[0][0])
        self.assertEqual((s["current"], s["phase"]), (0, "flip"))

    def test_11_27_space_skips_the_flip(self):
        s = self.discard_a_deck_card()
        key(s, pygame.K_SPACE)
        self.assertEqual((s["current"], s["phase"]), (1, "draw"))
        self.assertFalse(any(c["face_up"]
                             for c in s["players"][0]["grid_occ"]))

    def test_11_28_the_skip_button_skips_the_flip(self):
        s = self.discard_a_deck_card()
        rect, label = g.action_button(s)
        self.assertEqual(label, "SKIP")
        press(s, rect.center)
        self.assertEqual((s["current"], s["phase"]), (1, "draw"))
        self.assertFalse(any(c["face_up"]
                             for c in s["players"][0]["grid_occ"]))

    def test_11_29_no_face_down_card_left_ends_the_turn_by_itself(self):
        s = golf_table("draw")
        for c in s["players"][0]["grid_occ"]:
            g.flip_card(c, {})
        run(s, 1.0)
        draw_and_land(s)
        press(s, g.PLAYER_HAND_SLOTS[0][0])
        release(s, g.DISCARD_POS)
        self.assertEqual((s["current"], s["phase"]), (1, "draw"))
        self.assertEqual(s["ender"], 0)

    def test_11_30_skip_does_nothing_outside_the_flip_phase(self):
        s = golf_table("draw")
        self.assertFalse(g.skip_flip(s))
        key(s, pygame.K_SPACE)                     # in draw phase: draws
        self.assertEqual(s["phase"], "place")
        self.assertIsNone(g.action_button(s))

    def test_11_31_a_card_from_the_discard_still_has_no_flip(self):
        s = golf_table("draw")
        g.start_discard(s, {})
        run(s, 1.0)
        press(s, g.DISCARD_POS)
        run(s, 1.0)
        press(s, g.PLAYER_HAND_SLOTS[0][0])
        release(s, g.PLAYER_GRID_SLOTS[0][0])
        self.assertEqual((s["current"], s["phase"]), (1, "draw"))

    def test_11_32_knock_ends_the_hole_after_one_last_turn(self):
        s = golf_table("draw")
        key(s, pygame.K_k)
        self.assertEqual(s["ender"], 0)
        self.assertEqual((s["current"], s["phase"]), (1, "draw"))
        self.assertFalse(g.knock(s, {}))           # already knocked
        draw_and_land(s)
        press(s, g.PLAYER_HAND_SLOTS[1][0])
        release(s, g.PLAYER_GRID_SLOTS[1][0])      # swap: the last turn ends
        self.assertEqual(s["phase"], "round_over")

    def test_11_33_knock_button_and_knock_only_at_the_start_of_a_turn(self):
        s = golf_table("draw")
        rect, label = g.action_button(s)
        self.assertEqual(label, "KNOCK")
        press(s, rect.center)
        self.assertEqual(s["ender"], 0)
        s2 = golf_table("draw")
        draw_and_land(s2)                          # now holding a card
        self.assertFalse(g.knock(s2, {}))
        self.assertIsNone(s2["ender"])

    def test_11_34_the_help_panel_opens_and_closes(self):
        s = golf_table("draw")
        key(s, pygame.K_h)
        self.assertTrue(s["help_on"])
        key(s, pygame.K_SPACE)                     # closes it, draws nothing
        self.assertFalse(s["help_on"])
        self.assertEqual(s["phase"], "draw")

    def test_11_35_the_hud_explains_the_optional_flip(self):
        s = golf_table("flip")
        lines = [text for text, _ in g.golf_hud_lines(s)]
        self.assertIn("PLAYER 1: FLIP A CARD (OPTIONAL)", lines)


class Stage12Polish(unittest.TestCase):
    """Issue #21 - game juice: update_polish, the flip spin, shadows."""

    def spin_done(self, c):
        """Advance one card until its flip spin has finished."""
        g.update_card(c, g.FLIP_DURATION + 0.01, (0, 0), {})

    def test_12_0_make_card_has_the_announced_keys(self):
        c = g.make_card("hearts", "queen")
        for key_name in ("bend", "tilt", "lift", "wobble_t", "flip_t"):
            self.assertEqual(c[key_name], 0.0)
        self.assertEqual(c["vel"], [0.0, 0.0])
        self.assertFalse(c["flipping"])

    def test_12_1_polish_never_changes_rules_state(self):
        """pos, zone, slot and face_up stay put; only tilt moves."""
        c = placed("hearts", "queen", zone="grid", slot=2, owner=1,
                   pos=(300, 200), face_up=True)
        before = (list(c["pos"]), c["zone"], c["slot"], c["face_up"],
                  c["owner"])
        prev = [c["pos"][0] - 12, c["pos"][1]]     # it "moved" 12 px
        for _ in range(60):
            g.update_polish(c, 1 / 60, prev)
        self.assertEqual((list(c["pos"]), c["zone"], c["slot"],
                          c["face_up"], c["owner"]), before)
        self.assertNotEqual(c["tilt"], 0.0)

    def test_12_2_flip_while_spinning_does_nothing(self):
        c = placed("hearts", "queen", face_up=False)
        g.flip_card(c, {})
        self.assertTrue(c["face_up"])
        self.assertTrue(c["flipping"])
        g.flip_card(c, {})                          # mid-spin: ignored
        self.assertTrue(c["face_up"])
        self.spin_done(c)
        self.assertFalse(c["flipping"])
        g.flip_card(c, {})                          # spin over: works
        self.assertFalse(c["face_up"])

    def test_12_3_the_picture_swaps_at_the_halfway_point(self):
        face = pygame.Surface((7, 7))
        back = pygame.Surface((9, 9))
        faces = {("hearts", "queen"): face}
        c = placed("hearts", "queen", face_up=False)
        g.flip_card(c, {})                          # now face up
        self.assertIs(g.current_texture(c, faces, back), back)   # old side
        c["flip_t"] = g.FLIP_DURATION * 0.75
        self.assertIs(g.current_texture(c, faces, back), face)   # new side
        self.spin_done(c)
        self.assertIs(g.current_texture(c, faces, back), face)

    def test_12_4_the_rules_do_not_wait_for_the_spin(self):
        """Scoring reads face_up the instant the card is flipped."""
        c = placed("hearts", "king", zone="grid", slot=0, face_up=False)
        g.flip_card(c, {})
        self.assertTrue(c["face_up"])
        self.assertTrue(c["flipping"])

    def test_12_5_lift_target_is_higher_when_held_or_flipping(self):
        rest = placed("hearts", "queen")
        held = placed("hearts", "queen")
        held["dragging"] = True
        flip = placed("hearts", "queen")
        g.flip_card(flip, {})
        flip["flip_t"] = g.FLIP_DURATION / 2        # the pop is at its peak
        self.assertEqual(g.lift_target(rest), 0.0)
        self.assertGreater(g.lift_target(held), 0.0)
        self.assertGreater(g.lift_target(flip), 0.0)

    def test_12_6_dragging_sideways_leans_the_way_it_moves(self):
        for direction in (1, -1):
            c = placed("hearts", "queen", pos=(500, 300))
            g.begin_drag(c, (500, 300), {})
            for i in range(30):                      # mouse sweeps sideways
                g.update_card(c, 1 / 60, (500 + direction * 12 * i, 300), {})
            self.assertGreater(c["tilt"] * direction, 0.5)
            self.assertGreater(c["bend"] * direction, 0.0)
            self.assertGreater(c["lift"], 10.0)

    def test_12_7_a_landing_card_wobbles_then_settles(self):
        c = placed("hearts", "queen", zone="grid", slot=0, owner=0,
                   pos=(400, 300))
        g.send_card(c, (430, 300), "grid", 0, owner=0)
        for _ in range(240):
            g.update_card(c, 1 / 120, (0, 0), {})
            if c["motion"] is None:
                break
        self.assertGreater(c["wobble_t"], 0.0)       # it just landed
        for _ in range(120 * 2):                     # two quiet seconds
            g.update_card(c, 1 / 120, (0, 0), {})
        self.assertEqual(c["wobble_t"], 0.0)
        self.assertAlmostEqual(c["tilt"], 0.0, places=1)
        self.assertAlmostEqual(c["lift"], 0.0, places=1)
        self.assertEqual(list(c["pos"]), [430.0, 300.0])

    def test_12_8_polish_is_frame_rate_independent(self):
        results = []
        for fps in (30, 60, 240):
            c = placed("hearts", "queen")
            c["dragging"] = True                     # lift target = 34
            for _ in range(fps // 2):                # half a second
                g.update_polish(c, 1 / fps, list(c["pos"]))
            results.append(c["lift"])
        self.assertAlmostEqual(results[0], results[1], delta=0.5)
        self.assertAlmostEqual(results[1], results[2], delta=0.5)

    def test_12_9_the_resting_shadow_is_built_once(self):
        self.assertIs(g.get_resting_shadow(), g.get_resting_shadow())

    def test_12_10_every_card_state_can_be_drawn(self):
        """draw_card must not crash resting, flipping, dragged or tilted."""
        screen = pygame.Surface(g.WINDOW_SIZE)
        face = pygame.Surface(g.CARD_SIZE, pygame.SRCALPHA)
        back = pygame.Surface(g.CARD_SIZE, pygame.SRCALPHA)
        faces = {("hearts", "queen"): face}
        for setup in ("rest", "flip", "drag", "wobble", "deal"):
            c = placed("hearts", "queen", pos=(300, 300), face_up=False)
            if setup == "flip":
                g.flip_card(c, {})
                c["flip_t"] = g.FLIP_DURATION * 0.5   # exactly edge-on
            elif setup == "drag":
                c["dragging"] = True
                c["bend"], c["tilt"], c["lift"] = 14.0, -9.0, 34.0
            elif setup == "wobble":
                c["wobble_t"], c["tilt"] = g.WOBBLE_TIME, 5.0
            elif setup == "deal":
                c["motion"], c["lift"] = "deal", 80.0
            g.draw_card(screen, c, faces, back)

    def test_12_11_render_draws_flipping_cards_last(self):
        """A spinning card is never hidden under a resting neighbour."""
        pygame.font.init()
        s = g.make_state(2)
        s["sfx"] = {}
        a = placed("clubs", "2", zone="grid", slot=0, owner=0, pos=(300, 300))
        b = placed("hearts", "queen", zone="grid", slot=1, owner=0,
                   pos=(310, 300))
        s["cards"] = [b, a]                 # a is later, so normally on top
        b["flipping"] = True                # ...but b is spinning
        order = []
        original = g.draw_card
        g.draw_card = lambda screen, card, faces, back: order.append(card)
        try:
            g.render(pygame.Surface(g.WINDOW_SIZE), s,
                     pygame.font.Font(None, 20), {}, None)
        finally:
            g.draw_card = original
        self.assertEqual(order, [a, b])

    def test_12_12_no_debug_stats_on_screen(self):
        """The fps / frame-time block is gone from the state and the HUD."""
        self.assertNotIn("hud_lines", g.make_state(2))
        pygame.font.init()
        screen = pygame.Surface(g.WINDOW_SIZE)
        g.draw_hud(screen, pygame.font.Font(None, 20), None)   # no 'lines'


if __name__ == "__main__":
    unittest.main()
