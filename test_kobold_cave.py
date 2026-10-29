import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO

import kobold_cave as game


class FakeRng:
    """Stands in for the random module and hands out pre-chosen rolls."""

    def __init__(self, *rolls):
        self.rolls = list(rolls)

    def randint(self, low, high):
        roll = self.rolls.pop(0)
        assert low <= roll <= high, f'roll {roll} outside {low}-{high}'
        return roll


def answers(*replies):
    replies = list(replies)
    return lambda prompt: replies.pop(0)


def quietly(func, *args):
    with redirect_stdout(StringIO()):
        return func(*args)


def hero(job='warrior', **stat_changes):
    return game.Character.create('Test', replace(game.JOBS[job], **stat_changes))


class TableTests(unittest.TestCase):
    def test_roll_on_table_respects_weights(self):
        table = ((2, 'a'), (8, 'b'))
        self.assertEqual(game.roll_on_table(table, FakeRng(2)), 'a')
        self.assertEqual(game.roll_on_table(table, FakeRng(3)), 'b')
        self.assertEqual(game.roll_on_table(table, FakeRng(10)), 'b')

    def test_tables_use_the_expected_dice(self):
        tables = [(game.SHALLOW_ENCOUNTERS, 10), (game.MIDDLE_ENCOUNTERS, 10),
                  (game.DEEP_ENCOUNTERS, 20)]
        for job in game.JOBS.values():
            tables += [(job.loot['common'], 10), (job.loot['rare'], 20)]
        for table, sides in tables:
            self.assertEqual(sum(weight for weight, _ in table), sides)

    def test_every_job_only_finds_gear_it_can_use(self):
        for job in game.JOBS.values():
            usable = set(job.slots.values())
            for table in job.loot.values():
                for _, item in table:
                    if item:
                        self.assertIn(item.kind, usable, f'{job.name} found {item.name}')

    def test_leader_only_appears_as_the_boss(self):
        for table in (game.SHALLOW_ENCOUNTERS, game.MIDDLE_ENCOUNTERS, game.DEEP_ENCOUNTERS):
            self.assertNotIn('kobold_leader', [key for _, key in table])

    def test_encounters_get_harder_with_creep_score(self):
        self.assertIs(game.encounter_table(2), game.SHALLOW_ENCOUNTERS)
        self.assertIs(game.encounter_table(3), game.MIDDLE_ENCOUNTERS)
        self.assertIs(game.encounter_table(5), game.DEEP_ENCOUNTERS)

    def test_spawn_does_not_share_health_with_bestiary(self):
        monster = game.spawn('kobold_miner')
        monster.health -= 10
        self.assertEqual(game.BESTIARY['kobold_miner'].health, 35)


class EquipmentTests(unittest.TestCase):
    def test_first_sword_is_equipped_automatically(self):
        warrior = hero()
        quietly(game.search_camp, warrior, game.spawn('kobold_miner'), FakeRng(1))
        self.assertEqual(warrior.attack, 20)

    def test_shield_raises_max_and_current_health(self):
        warrior = hero()
        warrior.health = 100
        quietly(game.search_camp, warrior, game.spawn('kobold_heavy'), FakeRng(20))
        self.assertEqual((warrior.health, warrior.max_health), (175, 225))

    def test_swords_no_longer_stack_for_warriors(self):
        warrior = hero()
        quietly(game.equip, warrior, 'Weapon', game.ITEMS['fine_sword'])
        quietly(game.search_camp, warrior, game.spawn('kobold_miner'), FakeRng(5),
                answers('weapon'))
        self.assertEqual(warrior.attack, 15 + 10)

    def test_keeping_your_gear_leaves_the_new_item(self):
        warrior = hero()
        game.equip(warrior, 'Weapon', game.ITEMS['mithril_blade'])
        quietly(game.search_camp, warrior, game.spawn('kobold_miner'), FakeRng(1),
                answers('nonsense', 'keep'))
        self.assertEqual(warrior.equipment['Weapon'], game.ITEMS['mithril_blade'])

    def test_downgrading_a_shield_only_trims_health_to_the_new_max(self):
        warrior = hero()
        game.equip(warrior, 'Shield', game.ITEMS['mithril_buckler'])
        warrior.health = 200
        game.equip(warrior, 'Shield', game.ITEMS['fine_shield'])
        self.assertEqual((warrior.health, warrior.max_health), (175, 175))

    def test_rogue_dual_wields(self):
        rogue = hero('rogue')
        quietly(game.search_camp, rogue, game.spawn('kobold_miner'), FakeRng(1))
        quietly(game.search_camp, rogue, game.spawn('kobold_miner'), FakeRng(5))
        self.assertEqual(rogue.attack, 12 + 5 + 10)

    def test_rogue_picks_which_hand_to_replace(self):
        rogue = hero('rogue')
        game.equip(rogue, 'Main hand', game.ITEMS['fine_sword'])
        game.equip(rogue, 'Off hand', game.ITEMS['firebrand'])
        quietly(game.search_camp, rogue, game.spawn('kobold_heavy'), FakeRng(20),
                answers('main hand'))
        self.assertEqual(rogue.attack, 12 + 15 + 10)

    def test_staves_add_spell_power_or_mana(self):
        wizard = hero('wizard')
        game.equip(wizard, 'Staff', game.ITEMS['crystal_staff'])
        self.assertEqual((wizard.spell_power, wizard.max_mana, wizard.mana), (60, 6, 6))

    def test_empty_camp_changes_nothing(self):
        warrior = hero()
        quietly(game.search_camp, warrior, game.spawn('kobold_miner'), FakeRng(10))
        self.assertEqual((warrior.health, warrior.attack), (150, 15))

    def test_rest_heals_up_to_max_and_refills_mana(self):
        wizard = hero('wizard')
        wizard.health, wizard.mana = 50, 0
        quietly(game.rest, wizard)
        self.assertEqual((wizard.health, wizard.mana), (50 + round(110 * game.REST_HEAL), 4))
        wizard.health = 109
        quietly(game.rest, wizard)
        self.assertEqual(wizard.health, 110)


class CombatTests(unittest.TestCase):
    def test_attack_trades_blows_when_dodge_fails(self):
        warrior, miner = hero(), game.spawn('kobold_miner')
        # dodge 3 + 0 = 3 (fails), hit for 15 + 1, miner hits for 10 + 2
        quietly(game.attack, warrior, miner, FakeRng(0, 1, 2))
        self.assertEqual((warrior.health, miner.health), (138, 19))

    def test_attack_avoids_damage_when_dodge_succeeds(self):
        warrior, miner = hero(), game.spawn('kobold_miner')
        quietly(game.attack, warrior, miner, FakeRng(3, 0))
        self.assertEqual((warrior.health, miner.health), (150, 20))

    def test_defend_counterattacks_for_half_attack(self):
        warrior, miner = hero(), game.spawn('kobold_miner')
        quietly(game.defend, warrior, miner, FakeRng(7, 0))
        self.assertEqual(miner.health, 35 - round(15 / 2))

    def test_fireball_uses_spell_power_and_mana(self):
        wizard, heavy = hero('wizard'), game.spawn('kobold_heavy')
        game.equip(wizard, 'Staff', game.ITEMS['ember_staff'])
        quietly(game.cast_fireball, wizard, heavy, FakeRng(10))
        self.assertEqual((heavy.health, wizard.mana), (90 - 75, 3))

    def test_fireball_misfire_burns_the_wizard(self):
        wizard = hero('wizard')
        quietly(game.cast_fireball, wizard, game.spawn('kobold_miner'), FakeRng(1))
        self.assertEqual(wizard.health, 110 - 25)

    def test_no_fireball_without_mana(self):
        wizard, miner = hero('wizard', attack=200), game.spawn('kobold_miner')
        wizard.mana = 0
        out = StringIO()
        with redirect_stdout(out):
            # the cast is refused without using a turn or any dice, then one swing ends it
            won = game.fight(wizard, miner, FakeRng(3, 0),
                             answers('cast: fireball', 'attack'))
        self.assertIn('out of mana', out.getvalue())
        self.assertTrue(won)
        self.assertEqual(wizard.health, 110)

    def test_only_rogues_can_flee(self):
        warrior, miner = hero(), game.spawn('kobold_miner')
        out = StringIO()
        with redirect_stdout(out):
            # 'flee' is rejected, then three clean hits of 17 (dodge succeeds)
            won = game.fight(warrior, miner, FakeRng(3, 2, 3, 2, 3, 2),
                             answers('flee', 'attack', 'attack', 'attack'))
        self.assertIn('Please select a valid action.', out.getvalue())
        self.assertTrue(won)

    def test_rogue_can_escape_a_normal_fight(self):
        rogue = hero('rogue')
        won = quietly(game.fight, rogue, game.spawn('kobold_miner'), FakeRng(5), answers('flee'))
        self.assertFalse(won)
        self.assertTrue(rogue.alive)

    def test_no_escaping_the_boss(self):
        rogue = hero('rogue', attack=200)
        out = StringIO()
        with redirect_stdout(out):
            won = game.fight(rogue, game.spawn('kobold_leader'), FakeRng(3, 0),
                             answers('flee', 'attack'))
        self.assertIn('There is no escaping', out.getvalue())
        self.assertTrue(won)

    def test_dying_loses_the_fight(self):
        warrior, guard = hero(), game.spawn('kobold_guard')
        warrior.health = 5
        won = quietly(game.fight, warrior, guard, FakeRng(10, 0), answers('defend'))
        self.assertFalse(won)
        self.assertFalse(warrior.alive)


class FlowTests(unittest.TestCase):
    def test_choose_job_insists_on_a_real_class(self):
        out = StringIO()
        with redirect_stdout(out):
            job = game.choose_job(answers('bard', ' Wizard '))
        self.assertEqual(job.name, 'Wizard')
        self.assertIn('idiot', out.getvalue())

    def test_beating_the_leader_wins_the_game(self):
        champion = hero(attack=200)
        champion.cs = game.BOSS_CS
        out = StringIO()
        with redirect_stdout(out):
            won = game.explore(champion, FakeRng(3, 0), answers('attack'))
        self.assertTrue(won)
        self.assertIn('actually made it out', out.getvalue())

    def test_a_win_earns_creep_score_loot_and_rest(self):
        warrior = hero(attack=200)
        warrior.health = 100
        game.BOSS_CS, saved = 1, game.BOSS_CS
        try:
            # miner encounter, one clean hit, find a Fine Shield, then a one-hit boss
            won = quietly(game.explore, warrior, FakeRng(5, 3, 0, 3, 3, 0),
                          answers('attack', 'attack'))
        finally:
            game.BOSS_CS = saved
        self.assertTrue(won)
        self.assertEqual(warrior.cs, 1)
        self.assertEqual(warrior.max_health, 175)
        self.assertEqual(warrior.health, 100 + 25 + round(175 * game.REST_HEAL))


if __name__ == '__main__':
    unittest.main()
