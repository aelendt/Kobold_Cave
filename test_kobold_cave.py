import unittest
from contextlib import redirect_stdout
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


def warrior():
    return game.Character.create('Test', game.JOBS['warrior'])


class TableTests(unittest.TestCase):
    def test_roll_on_table_respects_weights(self):
        table = ((2, 'a'), (8, 'b'))
        self.assertEqual(game.roll_on_table(table, FakeRng(2)), 'a')
        self.assertEqual(game.roll_on_table(table, FakeRng(3)), 'b')
        self.assertEqual(game.roll_on_table(table, FakeRng(10)), 'b')

    def test_tables_use_the_original_dice(self):
        for table, sides in [(game.SHALLOW_ENCOUNTERS, 10), (game.MIDDLE_ENCOUNTERS, 10),
                             (game.DEEP_ENCOUNTERS, 20), (game.COMMON_LOOT, 10),
                             (game.RARE_LOOT, 20)]:
            self.assertEqual(sum(weight for weight, _ in table), sides)

    def test_encounters_get_harder_with_creep_score(self):
        self.assertIs(game.encounter_table(2), game.SHALLOW_ENCOUNTERS)
        self.assertIs(game.encounter_table(3), game.MIDDLE_ENCOUNTERS)
        self.assertIs(game.encounter_table(5), game.DEEP_ENCOUNTERS)

    def test_spawn_does_not_share_health_with_bestiary(self):
        monster = game.spawn('kobold_miner')
        monster.health -= 10
        self.assertEqual(game.BESTIARY['kobold_miner'].health, 35)


class LootTests(unittest.TestCase):
    def test_finding_a_sword_raises_attack(self):
        hero = warrior()
        quietly(game.search_camp, hero, game.spawn('kobold_miner'), FakeRng(1))
        self.assertEqual(hero.attack, 20)

    def test_finding_a_shield_raises_health(self):
        hero = warrior()
        quietly(game.search_camp, hero, game.spawn('kobold_heavy'), FakeRng(20))
        self.assertEqual(hero.health, 225)

    def test_empty_camp_changes_nothing(self):
        hero = warrior()
        quietly(game.search_camp, hero, game.spawn('kobold_miner'), FakeRng(10))
        self.assertEqual((hero.health, hero.attack), (150, 15))


class CombatTests(unittest.TestCase):
    def test_attack_trades_blows_when_dodge_fails(self):
        hero, miner = warrior(), game.spawn('kobold_miner')
        # dodge 3 + 0 = 3 (fails), hit for 15 + 1, miner hits for 10 + 2
        quietly(game.attack, hero, miner, FakeRng(0, 1, 2))
        self.assertEqual((hero.health, miner.health), (138, 19))

    def test_attack_avoids_damage_when_dodge_succeeds(self):
        hero, miner = warrior(), game.spawn('kobold_miner')
        quietly(game.attack, hero, miner, FakeRng(3, 0))
        self.assertEqual((hero.health, miner.health), (150, 20))

    def test_defend_counterattacks_for_half_attack(self):
        hero, miner = warrior(), game.spawn('kobold_miner')
        quietly(game.defend, hero, miner, FakeRng(7, 0))
        self.assertEqual(miner.health, 35 - round(15 / 2))

    def test_fireball_misfire_burns_the_wizard(self):
        wizard = game.Character.create('Test', game.JOBS['wizard'])
        quietly(game.cast_fireball, wizard, game.spawn('kobold_miner'), FakeRng(1))
        self.assertEqual(wizard.health, 75)

    def test_only_rogues_can_flee(self):
        hero, miner = warrior(), game.spawn('kobold_miner')
        out = StringIO()
        with redirect_stdout(out):
            # 'flee' is rejected, then three clean hits of 17 (dodge succeeds) and an empty camp
            game.fight(hero, miner, FakeRng(3, 2, 3, 2, 3, 2, 10),
                       answers('flee', 'attack', 'attack', 'attack'))
        self.assertIn('Please select a valid action.', out.getvalue())
        self.assertEqual(hero.cs, 1)

    def test_rogue_escape_gives_no_creep_score(self):
        rogue = game.Character.create('Test', game.JOBS['rogue'])
        quietly(game.fight, rogue, game.spawn('kobold_miner'), FakeRng(5), answers('flee'))
        self.assertEqual(rogue.cs, 0)

    def test_dying_ends_the_fight_without_loot(self):
        hero, leader = warrior(), game.spawn('kobold_leader')
        hero.health = 5
        quietly(game.fight, hero, leader, FakeRng(10, 0), answers('defend'))
        self.assertFalse(hero.alive)
        self.assertEqual(hero.cs, 0)


class FlowTests(unittest.TestCase):
    def test_choose_job_insists_on_a_real_class(self):
        out = StringIO()
        with redirect_stdout(out):
            job = game.choose_job(answers('bard', ' Wizard '))
        self.assertEqual(job.name, 'Wizard')
        self.assertIn('idiot', out.getvalue())


if __name__ == '__main__':
    unittest.main()
