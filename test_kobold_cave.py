import json
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


def captured(func, *args):
    out = StringIO()
    with redirect_stdout(out):
        result = func(*args)
    return result, out.getvalue()


def hero(job='warrior', name='Test', **stat_changes):
    return game.Character.create(name, replace(game.JOBS[job], **stat_changes), hero=True)


def party_of(*members):
    return game.Party(list(members))


def companion(job='rogue', name='Mira', **stat_changes):
    return game.Character.create(name, replace(game.JOBS[job], **stat_changes))


class TableTests(unittest.TestCase):
    def test_roll_on_table_respects_weights(self):
        table = ((2, 'a'), (8, 'b'))
        self.assertEqual(game.roll_on_table(table, FakeRng(2)), 'a')
        self.assertEqual(game.roll_on_table(table, FakeRng(3)), 'b')
        self.assertEqual(game.roll_on_table(table, FakeRng(10)), 'b')

    def test_tables_use_d10s_and_d20s(self):
        tables = [table for stage in game.STAGES for _, table in stage.encounters]
        for job in game.JOBS.values():
            tables += [job.loot['common'], job.loot['rare']]
        for table in tables:
            self.assertIn(sum(weight for weight, _ in table), (10, 20))

    def test_every_job_only_finds_gear_it_can_use(self):
        for job in game.JOBS.values():
            usable = set(job.slots.values())
            for table in job.loot.values():
                for _, item in table:
                    if item:
                        self.assertIn(item.kind, usable, f'{job.name} found {item.name}')

    def test_bosses_only_appear_at_the_end_of_their_stage(self):
        for stage in game.STAGES:
            self.assertTrue(game.BESTIARY[stage.boss].boss)
            for _, table in stage.encounters:
                for _, key in table:
                    self.assertFalse(game.BESTIARY[key].boss, key)

    def test_upper_mines_get_harder_as_you_go(self):
        mines = game.STAGES[0]
        self.assertIs(game.encounter_table(mines, 2), game.SHALLOW_ENCOUNTERS)
        self.assertIs(game.encounter_table(mines, 3), game.MIDDLE_ENCOUNTERS)
        self.assertIs(game.encounter_table(mines, 7), game.DEEP_ENCOUNTERS)

    def test_spawn_does_not_share_health_with_bestiary(self):
        monster = game.spawn('kobold_miner')
        monster.health -= 10
        self.assertEqual(game.BESTIARY['kobold_miner'].health, 35)
        self.assertEqual(monster.max_health, 35)


class EquipmentTests(unittest.TestCase):
    def test_first_sword_is_equipped_automatically(self):
        warrior = hero()
        quietly(game.search_camp, party_of(warrior), game.spawn('kobold_miner'), FakeRng(1))
        self.assertEqual(warrior.attack, 20)

    def test_shield_raises_max_and_current_health(self):
        warrior = hero()
        warrior.health = 100
        quietly(game.search_camp, party_of(warrior), game.spawn('kobold_heavy'), FakeRng(20))
        self.assertEqual((warrior.health, warrior.max_health), (175, 225))

    def test_swords_do_not_stack(self):
        warrior = hero()
        game.equip(warrior, 'Weapon', game.ITEMS['fine_sword'])
        quietly(game.search_camp, party_of(warrior), game.spawn('kobold_miner'), FakeRng(5),
                answers('weapon'))
        self.assertEqual(warrior.attack, 15 + 10)

    def test_keeping_your_gear_leaves_the_new_item(self):
        warrior = hero()
        game.equip(warrior, 'Weapon', game.ITEMS['mithril_blade'])
        quietly(game.search_camp, party_of(warrior), game.spawn('kobold_miner'), FakeRng(1),
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
        quietly(game.search_camp, party_of(rogue), game.spawn('kobold_miner'), FakeRng(1))
        quietly(game.search_camp, party_of(rogue), game.spawn('kobold_miner'), FakeRng(5))
        self.assertEqual(rogue.attack, 12 + 5 + 10)

    def test_staves_add_spell_power_or_mana(self):
        wizard = hero('wizard')
        game.equip(wizard, 'Staff', game.ITEMS['crystal_staff'])
        self.assertEqual((wizard.spell_power, wizard.max_mana, wizard.mana), (70, 7, 7))

    def test_in_a_party_whoever_searches_gets_gear_for_their_class(self):
        warrior, wizard = hero(), companion('wizard', 'Ysolde')
        # the second member searches, then rolls a 1 on the wizard's table
        quietly(game.search_camp, party_of(warrior, wizard), game.spawn('kobold_miner'),
                FakeRng(1, 1))
        self.assertEqual(wizard.equipment['Staff'], game.ITEMS['apprentice_staff'])
        self.assertIsNone(warrior.equipment['Weapon'])


class HealingTests(unittest.TestCase):
    def test_you_start_with_bandages(self):
        self.assertEqual(party_of(hero()).bandages, game.START_BANDAGES)

    def test_kobolds_sometimes_drop_bandages_and_bosses_always_do(self):
        party = party_of(hero())
        quietly(game.find_bandages, party, game.spawn('kobold_miner'), FakeRng(2))
        self.assertEqual(party.bandages, 2)
        quietly(game.find_bandages, party, game.spawn('kobold_miner'), FakeRng(1))
        self.assertEqual(party.bandages, 3)
        quietly(game.find_bandages, party, game.spawn('kobold_leader'), FakeRng())
        self.assertEqual(party.bandages, 5)

    def test_bandage_heals_on_your_own(self):
        warrior = hero()
        warrior.health = 20
        party = party_of(warrior)
        quietly(game.offer_bandages, party, answers('yes', 'no'))
        self.assertEqual(warrior.health, 20 + round(150 * game.BANDAGE_HEAL))
        self.assertEqual(party.bandages, 1)

    def test_bandages_stop_when_everyone_is_healthy(self):
        warrior = hero()
        warrior.health = 140
        party = party_of(warrior)
        quietly(game.offer_bandages, party, answers('yes'))  # no second question
        self.assertEqual((warrior.health, party.bandages), (150, 1))

    def test_in_a_party_you_pick_who_to_bandage(self):
        warrior, rogue = hero(), companion()
        warrior.health, rogue.health = 100, 30
        party = party_of(warrior, rogue)
        quietly(game.offer_bandages, party, answers('nobody', 'mira', 'no'))
        self.assertEqual((warrior.health, rogue.health), (100, 30 + 48))

    def test_rest_heals_everyone_standing_and_refills_mana(self):
        wizard, rogue = hero('wizard'), companion()
        wizard.health, wizard.mana, rogue.health = 50, 0, 0
        quietly(game.rest, party_of(wizard, rogue))
        self.assertEqual((wizard.health, wizard.mana), (50 + round(130 * game.REST_HEAL), 5))
        self.assertEqual(rogue.health, 0)  # the fallen stay down


class CombatTests(unittest.TestCase):
    def test_attack_deals_your_attack_plus_a_roll(self):
        warrior, miner = hero(), game.spawn('kobold_miner')
        quietly(game.attack, warrior, party_of(warrior), miner, FakeRng(1), None)
        self.assertEqual(miner.health, 35 - 16)

    def test_kobold_hits_when_dodge_fails(self):
        warrior, miner = hero(), game.spawn('kobold_miner')
        quietly(game.monster_strikes, warrior, miner, FakeRng(2, 0))  # dodge 3 + 0 fails
        self.assertEqual(warrior.health, 150 - 12)

    def test_kobold_misses_when_dodge_succeeds(self):
        warrior, miner = hero(), game.spawn('kobold_miner')
        quietly(game.monster_strikes, warrior, miner, FakeRng(2, 1))  # dodge 3 + 1 holds
        self.assertEqual(warrior.health, 150)

    def test_defending_parries_or_counterattacks(self):
        warrior, miner = hero(), game.spawn('kobold_miner')
        warrior.defending = True
        quietly(game.monster_strikes, warrior, miner, FakeRng(0, 3))
        self.assertEqual((warrior.health, miner.health), (150, 35))
        quietly(game.monster_strikes, warrior, miner, FakeRng(0, 7, 0))
        self.assertEqual((warrior.health, miner.health), (150, 35 - round(15 / 2)))

    def test_fireball_uses_spell_power_and_mana(self):
        wizard, heavy = hero('wizard'), game.spawn('kobold_heavy')
        game.equip(wizard, 'Staff', game.ITEMS['apprentice_staff'])
        quietly(game.take_turn, wizard, party_of(wizard), heavy, FakeRng(10), answers('fireball'))
        self.assertEqual((heavy.health, wizard.mana), (90 - 70, 4))

    def test_fireball_misfire_burns_the_wizard(self):
        wizard = hero('wizard')
        quietly(game.cast_fireball, wizard, party_of(wizard), game.spawn('kobold_miner'),
                FakeRng(1), None)
        self.assertEqual(wizard.health, 130 - 30)

    def test_no_fireball_without_mana(self):
        wizard = hero('wizard', attack=200)
        wizard.mana = 0
        won, out = captured(game.fight, party_of(wizard), game.spawn('kobold_miner'),
                            FakeRng(0), answers('fireball', 'attack'))
        self.assertIn('out of mana', out)
        self.assertTrue(won)

    def test_only_rogues_can_flee(self):
        warrior = hero(attack=200)
        won, out = captured(game.fight, party_of(warrior), game.spawn('kobold_miner'),
                            FakeRng(0), answers('flee', 'attack'))
        self.assertIn('Please select a valid action.', out)
        self.assertTrue(won)

    def test_rogue_can_get_the_party_away(self):
        party = party_of(hero('rogue'), companion('warrior', 'Brann'))
        won = quietly(game.fight, party, game.spawn('kobold_miner'), FakeRng(5), answers('flee'))
        self.assertFalse(won)
        self.assertTrue(party.alive)

    def test_no_escaping_a_boss(self):
        rogue = hero('rogue', attack=200)
        won, out = captured(game.fight, party_of(rogue), game.spawn('kobold_leader'),
                            FakeRng(0), answers('flee', 'attack'))
        self.assertIn('There is no escaping', out)
        self.assertTrue(won)

    def test_every_party_member_gets_orders(self):
        warrior, rogue = hero(attack=20), companion(attack=20)
        prompts = []
        def ask(prompt):
            prompts.append(prompt)
            return 'attack'
        # 22 + 22 kills the miner before it can strike back
        quietly(game.fight, party_of(warrior, rogue), game.spawn('kobold_miner'),
                FakeRng(2, 2), ask)
        self.assertEqual(prompts, ['Test: [Attack / Defend] ', 'Mira: [Attack / Defend / Flee] '])

    def test_kobold_strikes_a_random_party_member(self):
        warrior, rogue = hero(), companion()
        party = party_of(warrior, rogue)
        # picks the second member, then rolls 0 damage and a dodge of 4 - 2 (fails)
        quietly(game.monster_turn, party, game.spawn('kobold_miner'), 1, FakeRng(1, 0, -2))
        self.assertEqual((warrior.health, rogue.health), (150, 110))

    def test_warchief_strikes_twice(self):
        warrior = hero()
        quietly(game.monster_turn, party_of(warrior), game.spawn('kobold_warchief'), 1,
                FakeRng(0, 0, 0, 0))
        self.assertEqual(warrior.health, 150 - 60)

    def test_dragon_breath_hits_everyone_every_third_round(self):
        warrior, rogue = hero(), companion()
        quietly(game.monster_turn, party_of(warrior, rogue), game.spawn('red_dragon'), 3,
                FakeRng(0, 0))
        self.assertEqual((warrior.health, rogue.health), (120, 90))

    def test_the_fight_goes_on_when_a_companion_falls(self):
        warrior, rogue = hero(), companion()
        rogue.health = 5
        party = party_of(warrior, rogue)
        _, out = captured(game.monster_turn, party, game.spawn('kobold_miner'), 1,
                          FakeRng(1, 0, -2))
        self.assertIn('Mira has fallen.', out)
        self.assertEqual(party.living, [warrior])

    def test_losing_everyone_loses_the_fight(self):
        warrior = hero()
        warrior.health = 5
        won = quietly(game.fight, party_of(warrior), game.spawn('kobold_guard'),
                      FakeRng(0, 0, 0), answers('attack'))
        self.assertFalse(won)


class SkillTests(unittest.TestCase):
    def test_classes_start_with_their_specials(self):
        self.assertEqual(hero('wizard').actions, ['Fireball', 'Mend'])
        self.assertEqual(hero('rogue').actions, ['Flee'])
        self.assertEqual(hero().actions, [])

    def test_mend_heals_the_chosen_ally_and_costs_mana(self):
        wizard, rogue = hero('wizard'), companion()
        rogue.health = 50
        party = party_of(wizard, rogue)
        quietly(game.take_turn, wizard, party, game.spawn('kobold_miner'), FakeRng(),
                answers('mend', 'mira'))
        self.assertEqual((rogue.health, wizard.mana), (50 + round(60 * game.MEND_POWER), 4))

    def test_mend_on_your_own_heals_yourself(self):
        wizard = hero('wizard')
        wizard.health = 40
        quietly(game.take_turn, wizard, party_of(wizard), game.spawn('kobold_miner'), FakeRng(),
                answers('mend'))
        self.assertEqual(wizard.health, 40 + round(60 * game.MEND_POWER))

    def test_frost_bolt_can_freeze_a_kobold_out_of_its_turn(self):
        wizard, heavy = hero('wizard'), game.spawn('kobold_heavy')
        party = party_of(wizard)
        quietly(game.frost_bolt, wizard, party, heavy, FakeRng(1), None)
        self.assertEqual(heavy.health, 90 - 36)
        _, out = captured(game.monster_turn, party, heavy, 1, FakeRng())
        self.assertIn('loses its turn', out)
        self.assertEqual(wizard.health, 130)

    def test_meteor_costs_two_mana(self):
        wizard, heavy = hero('wizard'), game.spawn('kobold_heavy')
        wizard.actions.append('Meteor')
        wizard.mana = 1
        _, out = captured(game.take_turn, wizard, party_of(wizard), heavy, FakeRng(0),
                          answers('meteor', 'attack'))  # refused, then a normal attack
        self.assertIn('out of mana', out)

    def test_bosses_shake_off_half_of_all_stuns(self):
        leader = game.spawn('kobold_leader')
        quietly(game.stun, leader, FakeRng(1))
        self.assertFalse(leader.stunned)
        quietly(game.stun, leader, FakeRng(2))
        self.assertTrue(leader.stunned)

    def test_cleave_doubles_damage_then_needs_three_rounds(self):
        warrior, guard = hero(), game.spawn('kobold_guard')
        warrior.actions.append('Cleave')
        party = party_of(warrior)
        quietly(game.take_turn, warrior, party, guard, FakeRng(0), answers('cleave'))
        self.assertEqual(guard.health, 55 - 30)
        _, out = captured(game.take_turn, warrior, party, guard, FakeRng(0),
                          answers('cleave', 'attack'))
        self.assertIn('not ready to use Cleave again (3 more rounds)', out)
        for _ in range(3):
            quietly(game.monster_turn, party, guard, 1, FakeRng(0, 3))
        self.assertEqual(warrior.cooldowns, {})

    def test_shield_wall_draws_every_strike(self):
        warrior, rogue = hero(), companion()
        warrior.actions.append('Shield Wall')
        party = party_of(warrior, rogue)
        warchief = game.spawn('kobold_warchief')
        quietly(game.take_turn, warrior, party, warchief, FakeRng(), answers('shield wall'))
        # two strikes, no target rolls: both parried by the warrior
        quietly(game.monster_turn, party, warchief, 1, FakeRng(0, 3, 0, 3))
        self.assertEqual((warrior.health, rogue.health), (150, 120))

    def test_stunned_enemies_take_a_brutal_backstab(self):
        rogue, heavy = hero('rogue'), game.spawn('kobold_heavy')
        party = party_of(rogue)
        rogue.actions += ['Stunning Strike', 'Backstab']
        quietly(game.take_turn, rogue, party, heavy, FakeRng(0), answers('stunning strike'))
        self.assertTrue(heavy.stunned)
        quietly(game.monster_turn, party, heavy, 1, FakeRng())  # loses its turn
        quietly(game.take_turn, rogue, party, heavy, FakeRng(0), answers('backstab'))
        self.assertEqual(heavy.health, 90 - 12 - 48)


class RewardTests(unittest.TestCase):
    def test_freeing_a_prisoner_adds_them_with_gear(self):
        party = party_of(hero())
        quietly(game.boss_reward, party, 0, answers('ysolde'))
        recruit = party.members[1]
        self.assertEqual((recruit.name, recruit.job.name), ('Ysolde', 'Wizard'))
        self.assertEqual(recruit.equipment['Staff'], game.ITEMS['apprentice_staff'])
        self.assertEqual(recruit.health, recruit.max_health)
        self.assertFalse(recruit.hero)

    def test_fallen_companions_make_room_for_new_ones(self):
        rogue = companion()
        rogue.health = 0
        party = party_of(hero(), rogue)
        quietly(game.boss_reward, party, 1, answers('hilda'))
        self.assertEqual([member.name for member in party.members], ['Test', 'Hilda'])

    def test_keeping_the_hoard_powers_up_and_teaches_a_skill(self):
        warrior = hero()
        warrior.health = 100
        quietly(game.boss_reward, party_of(warrior), 0, answers('power up'))
        self.assertEqual((warrior.attack, warrior.max_health, warrior.health), (24, 225, 175))
        self.assertEqual(warrior.actions, ['Cleave'])

    def test_each_hoard_teaches_the_next_skill(self):
        rogue = hero('rogue')
        quietly(game.boss_reward, party_of(rogue), 0, answers('power up'))
        quietly(game.boss_reward, party_of(rogue), 1, answers('power up'))
        self.assertEqual(rogue.actions, ['Flee', 'Stunning Strike', 'Backstab'])
        quietly(game.power_up, rogue)  # nothing left to learn, but the boon still stacks
        self.assertEqual(len(rogue.actions), 3)
        self.assertEqual(len(rogue.boons), 3)

    def test_recruiting_gives_no_power_up(self):
        warrior = hero()
        quietly(game.boss_reward, party_of(warrior), 0, answers('mira'))
        self.assertEqual((warrior.boons, warrior.actions), ([], []))

    def test_a_full_party_gets_nothing_extra(self):
        party = party_of(hero(), companion(), companion('wizard', 'Ysolde'))
        quietly(game.boss_reward, party, 1, answers())
        self.assertEqual(party.members[0].boons, [])
        self.assertEqual(len(party.members), 3)


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.stages = game.STAGES

    def tearDown(self):
        game.STAGES = self.stages

    def test_choose_job_insists_on_a_real_class(self):
        job, out = captured(game.choose_job, answers('bard', ' Wizard '))
        self.assertEqual(job.name, 'Wizard')
        self.assertIn('idiot', out)

    def test_slaying_all_three_bosses_wins(self):
        game.STAGES = tuple(replace(stage, fights=0) for stage in self.stages)
        party = party_of(hero(attack=1000))
        won, out = captured(game.play, party, FakeRng(0, 0, 0),
                            answers('attack', 'power up', 'attack', 'vex', 'attack'))
        self.assertTrue(won)
        self.assertIn('actually made it out', out)
        self.assertEqual(party.cs, 3)
        self.assertEqual([member.name for member in party.members], ['Test', 'Vex'])

    def test_a_win_earns_creep_score_loot_bandages_and_rest(self):
        game.STAGES = (replace(self.stages[0], fights=1),)
        warrior = hero(attack=1000)
        warrior.health = 100
        party = party_of(warrior)
        # encounter: miner; one hit; Fine Shield; a bandage drop; then the boss
        won = quietly(game.play, party, FakeRng(5, 0, 3, 1, 0), answers('attack', 'no', 'attack'))
        self.assertTrue(won)
        self.assertEqual(party.cs, 2)
        self.assertEqual(warrior.max_health, 175)
        self.assertEqual(party.bandages, game.START_BANDAGES + 1 + 2)
        self.assertEqual(warrior.health, 100 + 25 + round(175 * game.REST_HEAL))


class ShowHookTests(unittest.TestCase):
    """The browser draws from show(); its details must survive json.dumps."""

    def setUp(self):
        self.scenes = []
        self.original = game.show
        game.show = lambda scene, **details: self.scenes.append((scene, json.dumps(details))) or True

    def tearDown(self):
        game.show = self.original

    def test_combat_scenes_carry_the_party_and_enemy(self):
        party = party_of(hero('wizard', attack=200), companion())
        quietly(game.fight, party, game.spawn('kobold_miner'), FakeRng(0), answers('attack'))
        scene, details = self.scenes[0]
        self.assertEqual(scene, 'combat')
        details = json.loads(details)
        self.assertEqual([member['name'] for member in details['party']], ['Test', 'Mira'])
        self.assertEqual(details['active'], 0)
        self.assertEqual(details['enemy']['name'], 'Kobold Miner')

    def test_recruit_scene_lists_the_prisoners(self):
        quietly(game.boss_reward, party_of(hero()), 0, answers('brann'))
        scene, details = next(item for item in self.scenes if item[0] == 'recruit')
        names = [prisoner['name'] for prisoner in json.loads(details)['prisoners']]
        self.assertEqual(names, ['Brann', 'Mira', 'Ysolde'])

    def test_class_cards_are_plain_data(self):
        game.show('jobs', jobs=[game.job_view(job) for job in game.JOBS.values()])
        self.assertEqual(self.scenes[0][0], 'jobs')


if __name__ == '__main__':
    unittest.main()
