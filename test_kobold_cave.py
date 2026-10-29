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


def hero(job='warrior', name='Test', skills=(), **stat_changes):
    member = game.Character.create(name, replace(game.JOBS[job], **stat_changes), hero=True)
    member.actions += list(skills)
    return member


def companion(job='rogue', name='Mira', skills=(), **stat_changes):
    member = game.Character.create(name, replace(game.JOBS[job], **stat_changes))
    member.actions += list(skills)
    return member


def party_of(*members):
    return game.Party(list(members))


# Monsters with fixed stats, so tests check the rules rather than the balance.
def kobold(health=35, attack=10, **details):
    return game.Monster('Test Kobold', health=health, attack=attack, **details)


def boss(health=200, attack=30, **details):
    return game.Monster('Test Boss', health=health, attack=attack, boss=True,
                        called='the Boss', **details)


def turn(member, party, monster, rolls, *replies):
    return quietly(game.take_turn, member, party, monster, FakeRng(*rolls), answers(*replies))


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
        full = game.BESTIARY['kobold_miner'].health
        monster = game.spawn('kobold_miner')
        monster.health -= 10
        self.assertEqual(game.BESTIARY['kobold_miner'].health, full)
        self.assertEqual(monster.max_health, full)

    def test_every_skill_exists_and_each_class_has_five_plus_two(self):
        for job in game.JOBS.values():
            self.assertEqual(len(job.skills), 5, job.name)
            self.assertEqual(len(job.boon_abilities), 2, job.name)
            for name in job.actions + job.skills + job.boon_abilities:
                self.assertIn(name, game.ACTIONS)


class EquipmentTests(unittest.TestCase):
    def test_first_sword_is_equipped_automatically(self):
        warrior = hero()
        quietly(game.search_camp, party_of(warrior), kobold(), FakeRng(1))
        self.assertEqual(warrior.attack, 20)

    def test_shield_raises_max_and_current_health(self):
        warrior = hero()
        warrior.health = 100
        quietly(game.search_camp, party_of(warrior), kobold(loot_tier='rare'), FakeRng(20))
        self.assertEqual((warrior.health, warrior.max_health), (175, 225))

    def test_swords_do_not_stack(self):
        warrior = hero()
        game.equip(warrior, 'Weapon', game.ITEMS['fine_sword'])
        quietly(game.search_camp, party_of(warrior), kobold(), FakeRng(5), answers('weapon'))
        self.assertEqual(warrior.attack, 15 + 10)

    def test_keeping_your_gear_leaves_the_new_item(self):
        warrior = hero()
        game.equip(warrior, 'Weapon', game.ITEMS['mithril_blade'])
        quietly(game.search_camp, party_of(warrior), kobold(), FakeRng(1),
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
        quietly(game.search_camp, party_of(rogue), kobold(), FakeRng(1))
        quietly(game.search_camp, party_of(rogue), kobold(), FakeRng(5))
        self.assertEqual(rogue.attack, 12 + 5 + 10)

    def test_staves_add_spell_power_or_mana(self):
        wizard = hero('wizard')
        game.equip(wizard, 'Staff', game.ITEMS['crystal_staff'])
        self.assertEqual((wizard.spell_power, wizard.max_mana, wizard.mana), (70, 7, 7))

    def test_in_a_party_whoever_searches_gets_gear_for_their_class(self):
        warrior, wizard = hero(), companion('wizard', 'Ysolde')
        # the second member searches, then rolls a 1 on the wizard's table
        quietly(game.search_camp, party_of(warrior, wizard), kobold(), FakeRng(1, 1))
        self.assertEqual(wizard.equipment['Staff'], game.ITEMS['apprentice_staff'])
        self.assertIsNone(warrior.equipment['Weapon'])


class HealingTests(unittest.TestCase):
    def test_you_start_with_bandages(self):
        self.assertEqual(party_of(hero()).bandages, game.START_BANDAGES)

    def test_kobolds_sometimes_drop_bandages_and_bosses_always_do(self):
        party = party_of(hero())
        quietly(game.find_bandages, party, kobold(), FakeRng(2))
        self.assertEqual(party.bandages, 2)
        quietly(game.find_bandages, party, kobold(), FakeRng(1))
        self.assertEqual(party.bandages, 3)
        quietly(game.find_bandages, party, boss(), FakeRng())
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
        warrior, monster = hero(), kobold()
        turn(warrior, party_of(warrior), monster, [1], 'attack')
        self.assertEqual(monster.health, 35 - 16)

    def test_kobold_hits_when_dodge_fails(self):
        warrior = hero()
        quietly(game.monster_strikes, warrior, kobold(), FakeRng(2, 0))  # dodge 3 + 0 fails
        self.assertEqual(warrior.health, 150 - 12)

    def test_kobold_misses_when_dodge_succeeds(self):
        warrior = hero()
        quietly(game.monster_strikes, warrior, kobold(), FakeRng(2, 1))  # dodge 3 + 1 holds
        self.assertEqual(warrior.health, 150)

    def test_defending_parries_or_counterattacks(self):
        warrior, monster = hero(), kobold()
        warrior.defending = True
        quietly(game.monster_strikes, warrior, monster, FakeRng(0, 3))
        self.assertEqual((warrior.health, monster.health), (150, 35))
        quietly(game.monster_strikes, warrior, monster, FakeRng(0, 7, 0))
        self.assertEqual((warrior.health, monster.health), (150, 35 - round(15 / 2)))

    def test_only_rogues_can_flee(self):
        warrior = hero(attack=200)
        won, out = captured(game.fight, party_of(warrior), kobold(), FakeRng(0),
                            answers('flee', 'attack'))
        self.assertIn('Please select a valid action.', out)
        self.assertTrue(won)

    def test_rogue_can_get_the_party_away(self):
        party = party_of(hero('rogue'), companion('warrior', 'Brann'))
        won = quietly(game.fight, party, kobold(), FakeRng(5), answers('flee'))
        self.assertFalse(won)
        self.assertTrue(party.alive)

    def test_no_escaping_a_boss(self):
        rogue = hero('rogue', attack=300)
        won, out = captured(game.fight, party_of(rogue), boss(), FakeRng(0),
                            answers('flee', 'attack'))
        self.assertIn('There is no escaping', out)
        self.assertTrue(won)

    def test_every_party_member_gets_orders(self):
        warrior, rogue = hero(attack=20), companion(attack=20)
        prompts = []
        def ask(prompt):
            prompts.append(prompt)
            return 'attack'
        # 22 + 22 kills the kobold before it can strike back
        quietly(game.fight, party_of(warrior, rogue), kobold(), FakeRng(2, 2), ask)
        self.assertEqual(prompts, ['Test: [Attack / Defend] ', 'Mira: [Attack / Defend / Flee] '])

    def test_kobold_strikes_a_random_party_member(self):
        warrior, rogue = hero(), companion()
        party = party_of(warrior, rogue)
        # picks the second member, then rolls 0 damage and a dodge of 4 - 2 (fails)
        quietly(game.monster_turn, party, kobold(), 1, FakeRng(1, 0, -2))
        self.assertEqual((warrior.health, rogue.health), (150, 110))

    def test_bosses_can_strike_twice(self):
        warrior = hero()
        quietly(game.monster_turn, party_of(warrior), boss(attacks=2), 1, FakeRng(0, 0, 0, 0))
        self.assertEqual(warrior.health, 150 - 60)

    def test_dragon_breath_hits_everyone_every_third_round(self):
        warrior, rogue = hero(), companion()
        quietly(game.monster_turn, party_of(warrior, rogue), boss(breath=30), 3, FakeRng(0, 0))
        self.assertEqual((warrior.health, rogue.health), (120, 90))

    def test_the_fight_goes_on_when_a_companion_falls(self):
        warrior, rogue = hero(), companion()
        rogue.health = 5
        party = party_of(warrior, rogue)
        _, out = captured(game.monster_turn, party, kobold(), 1, FakeRng(1, 0, -2))
        self.assertIn('Mira has fallen.', out)
        self.assertEqual(party.living, [warrior])

    def test_losing_everyone_loses_the_fight(self):
        warrior = hero()
        warrior.health = 5
        won = quietly(game.fight, party_of(warrior), kobold(health=60), FakeRng(0, 0, 0),
                      answers('attack'))
        self.assertFalse(won)


class StartingSkillTests(unittest.TestCase):
    def test_signature_moves(self):
        self.assertEqual(hero().actions, [])
        self.assertEqual(hero('rogue').actions, ['Flee'])
        self.assertEqual(hero('wizard').actions, ['Mana Surge'])

    def test_you_pick_one_of_three_different_skills(self):
        wizard = hero('wizard')
        # pops from the pool of five: index 0, then 3 of the four left, then 1 of three
        _, out = captured(game.choose_skill, wizard, FakeRng(0, 3, 1), answers('mend', 'drain life'))
        self.assertIn('Fireball', out)
        self.assertIn('Drain Life', out)
        self.assertIn('Frost Bolt', out)
        self.assertNotIn('Mend:', out)
        self.assertEqual(wizard.actions, ['Mana Surge', 'Drain Life'])

    def test_prisoners_come_with_a_random_skill(self):
        recruit = game.prisoner('warrior', 0, FakeRng(4))
        self.assertEqual(recruit.actions, ['Battle Cry'])


class WarriorSkillTests(unittest.TestCase):
    def test_cleave_hits_for_one_and_a_half_then_needs_three_rounds(self):
        warrior, monster = hero(skills=['Cleave']), kobold(health=60)
        party = party_of(warrior)
        turn(warrior, party, monster, [0], 'cleave')
        self.assertEqual(monster.health, 60 - round(15 * 1.5))
        _, out = captured(game.take_turn, warrior, party, monster, FakeRng(0),
                          answers('cleave', 'attack'))
        self.assertIn('not ready to use Cleave again (3 more rounds)', out)
        for _ in range(3):
            game.end_round(party)
        self.assertEqual(warrior.cooldowns, {})

    def test_shield_bash_stuns(self):
        warrior, monster = hero(skills=['Shield Bash']), kobold(health=60)
        turn(warrior, party_of(warrior), monster, [0], 'shield bash')
        self.assertEqual((monster.health, monster.stunned), (60 - 8, 1))

    def test_shield_wall_draws_every_strike(self):
        warrior, rogue = hero(skills=['Shield Wall']), companion()
        party = party_of(warrior, rogue)
        turn(warrior, party, boss(attacks=2), [], 'shield wall')
        # two strikes, no target rolls: both parried by the warrior
        quietly(game.monster_turn, party, boss(attacks=2), 1, FakeRng(0, 3, 0, 3))
        self.assertEqual((warrior.health, rogue.health), (150, 120))

    def test_second_wind_heals_once_per_fight(self):
        warrior = hero(skills=['Second Wind'])
        warrior.health = 50
        party, monster = party_of(warrior), kobold()
        turn(warrior, party, monster, [], 'second wind')
        self.assertEqual(warrior.health, 50 + round(150 * 0.25))
        _, out = captured(game.take_turn, warrior, party, monster, FakeRng(0),
                          answers('second wind', 'attack'))
        self.assertIn('already used Second Wind this fight', out)

    def test_battle_cry_lifts_the_whole_party(self):
        warrior, rogue = hero(skills=['Battle Cry']), companion()
        party, monster = party_of(warrior, rogue), kobold(health=100)
        turn(warrior, party, monster, [], 'battle cry')
        turn(rogue, party, monster, [0], 'attack')
        self.assertEqual(monster.health, 100 - 18)  # 12 x 1.5

    def test_execute_grows_with_damage_already_dealt(self):
        warrior, monster = hero(skills=['Execute']), boss(health=300)
        monster.health = 150
        turn(warrior, party_of(warrior), monster, [0], 'execute')
        self.assertEqual(monster.health, 150 - (15 + 50))

    def test_last_stand_keeps_you_up_for_two_rounds(self):
        warrior = hero(skills=['Last Stand'])
        warrior.health = 5
        party = party_of(warrior)
        turn(warrior, party, kobold(), [], 'last stand')
        quietly(game.monster_turn, party, kobold(attack=50), 1, FakeRng(0, 0))
        self.assertEqual(warrior.health, 1)
        quietly(game.monster_turn, party, kobold(attack=50), 2, FakeRng(0, 0))
        self.assertEqual(warrior.health, 1)
        quietly(game.monster_turn, party, kobold(attack=50), 3, FakeRng(0, 0))
        self.assertFalse(warrior.alive)


class RogueSkillTests(unittest.TestCase):
    def test_bosses_shake_off_half_of_all_stuns(self):
        leader = boss()
        quietly(game.stun, leader, FakeRng(1))
        self.assertFalse(leader.stunned)
        quietly(game.stun, leader, FakeRng(2))
        self.assertTrue(leader.stunned)

    def test_poison_burns_for_three_rounds(self):
        rogue, monster = hero('rogue', skills=['Poison Blade']), kobold(health=100)
        party = party_of(rogue)
        turn(rogue, party, monster, [0], 'poison blade')
        for round_number in (1, 2, 3, 4):
            quietly(game.monster_turn, party, monster, round_number, FakeRng(0, 3))
        self.assertEqual(monster.health, 100 - 12 - 3 * 5)

    def test_smoke_bomb_makes_every_strike_miss(self):
        rogue = hero('rogue', skills=['Smoke Bomb'])
        party = party_of(rogue)
        turn(rogue, party, kobold(), [], 'smoke bomb')
        quietly(game.monster_turn, party, boss(attacks=2), 1, FakeRng())
        self.assertEqual(rogue.health, 120)

    def test_twin_strike_hits_twice(self):
        rogue, monster = hero('rogue', skills=['Twin Strike']), kobold(health=60)
        turn(rogue, party_of(rogue), monster, [0, 0], 'twin strike')
        self.assertEqual(monster.health, 60 - 2 * 9)

    def test_pickpocket_hits_and_steals_a_bandage(self):
        rogue, monster = hero('rogue', skills=['Pickpocket']), kobold()
        party = party_of(rogue)
        turn(rogue, party, monster, [0], 'pickpocket')
        self.assertEqual((monster.health, party.bandages), (35 - 12, game.START_BANDAGES + 1))

    def test_stunned_enemies_take_a_brutal_backstab(self):
        rogue = hero('rogue', skills=['Stunning Strike', 'Backstab'])
        monster, party = kobold(health=100), party_of(rogue)
        turn(rogue, party, monster, [0], 'stunning strike')
        quietly(game.monster_turn, party, monster, 1, FakeRng())  # loses its turn
        turn(rogue, party, monster, [0], 'backstab')
        self.assertEqual(monster.health, 100 - 12 - 48)

    def test_assassinate_finishes_a_wounded_enemy(self):
        rogue, monster = hero('rogue', skills=['Assassinate']), boss(health=200)
        monster.health = 50
        turn(rogue, party_of(rogue), monster, [0], 'assassinate')
        self.assertEqual(monster.health, 50 - 36)


class WizardSkillTests(unittest.TestCase):
    def test_mana_surge_restores_mana_but_not_past_full(self):
        wizard = hero('wizard')
        wizard.mana = 1
        party = party_of(wizard)
        turn(wizard, party, kobold(), [], 'mana surge')
        self.assertEqual(wizard.mana, 3)
        wizard.mana = 5
        game.end_round(party), game.end_round(party), game.end_round(party)
        _, out = captured(game.take_turn, wizard, party, kobold(), FakeRng(0),
                          answers('mana surge', 'attack'))
        self.assertIn('already full', out)

    def test_fireball_uses_spell_power_and_mana(self):
        wizard, monster = hero('wizard', skills=['Fireball']), kobold(health=100)
        game.equip(wizard, 'Staff', game.ITEMS['apprentice_staff'])
        turn(wizard, party_of(wizard), monster, [10], 'fireball')
        self.assertEqual((monster.health, wizard.mana), (100 - 70, 4))

    def test_fireball_misfire_burns_the_wizard(self):
        wizard = hero('wizard', skills=['Fireball'])
        turn(wizard, party_of(wizard), kobold(), [1], 'fireball')
        self.assertEqual(wizard.health, 130 - 30)

    def test_no_spells_without_mana(self):
        wizard = hero('wizard', skills=['Fireball'], attack=200)
        wizard.mana = 0
        won, out = captured(game.fight, party_of(wizard), kobold(), FakeRng(0),
                            answers('fireball', 'attack'))
        self.assertIn('out of mana', out)
        self.assertTrue(won)

    def test_mend_heals_the_chosen_ally(self):
        wizard, rogue = hero('wizard', skills=['Mend']), companion()
        rogue.health = 50
        turn(wizard, party_of(wizard, rogue), kobold(), [], 'mend', 'mira')
        self.assertEqual((rogue.health, wizard.mana), (50 + round(60 * game.MEND_POWER), 4))

    def test_mend_on_your_own_heals_yourself(self):
        wizard = hero('wizard', skills=['Mend'])
        wizard.health = 40
        turn(wizard, party_of(wizard), kobold(), [], 'mend')
        self.assertEqual(wizard.health, 40 + round(60 * game.MEND_POWER))

    def test_frost_bolt_can_freeze_a_kobold_out_of_its_turn(self):
        wizard, monster = hero('wizard', skills=['Frost Bolt']), kobold(health=100)
        party = party_of(wizard)
        turn(wizard, party, monster, [1], 'frost bolt')
        self.assertEqual(monster.health, 100 - 27)
        _, out = captured(game.monster_turn, party, monster, 1, FakeRng())
        self.assertIn('loses its turn', out)
        self.assertEqual(wizard.health, 130)

    def test_arcane_shield_halves_damage_and_burns(self):
        wizard, monster = hero('wizard', skills=['Arcane Shield']), kobold(health=100, attack=20)
        party = party_of(wizard)
        turn(wizard, party, monster, [], 'arcane shield')
        self.assertEqual(monster.health, 100 - 36)
        quietly(game.monster_turn, party, monster, 1, FakeRng(0, 0))
        self.assertEqual(wizard.health, 130 - 10)

    def test_drain_life_heals_for_half(self):
        wizard, monster = hero('wizard', skills=['Drain Life']), kobold(health=100)
        wizard.health = 100
        turn(wizard, party_of(wizard), monster, [], 'drain life')
        self.assertEqual((monster.health, wizard.health), (100 - 24, 100 + 12))

    def test_meteor_costs_two_mana(self):
        wizard = hero('wizard', skills=['Meteor'])
        wizard.mana = 1
        _, out = captured(game.take_turn, wizard, party_of(wizard), kobold(), FakeRng(0),
                          answers('meteor', 'attack'))  # refused, then a normal attack
        self.assertIn('out of mana', out)

    def test_time_stop_freezes_even_a_boss_for_two_turns(self):
        wizard, monster = hero('wizard', skills=['Time Stop']), boss()
        party = party_of(wizard)
        turn(wizard, party, monster, [], 'time stop')
        self.assertEqual((monster.stunned, wizard.mana), (2, 2))
        for round_number in (1, 2):
            quietly(game.monster_turn, party, monster, round_number, FakeRng())
        self.assertEqual(wizard.health, 130)


class RewardTests(unittest.TestCase):
    def test_freeing_a_prisoner_adds_them_with_gear_and_a_skill(self):
        party = party_of(hero())
        quietly(game.boss_reward, party, 0, FakeRng(0, 0, 0), answers('ysolde'))
        recruit = party.members[1]
        self.assertEqual((recruit.name, recruit.job.name), ('Ysolde', 'Wizard'))
        self.assertEqual(recruit.equipment['Staff'], game.ITEMS['apprentice_staff'])
        self.assertEqual(recruit.actions, ['Mana Surge', 'Fireball'])
        self.assertEqual(recruit.health, recruit.max_health)
        self.assertFalse(recruit.hero)

    def test_fallen_companions_make_room_for_new_ones(self):
        rogue = companion()
        rogue.health = 0
        party = party_of(hero(), rogue)
        quietly(game.boss_reward, party, 1, FakeRng(0, 0, 0), answers('hilda'))
        self.assertEqual([member.name for member in party.members], ['Test', 'Hilda'])

    def test_keeping_the_hoard_powers_up_and_teaches_your_pick(self):
        warrior = hero()
        warrior.health = 100
        quietly(game.boss_reward, party_of(warrior), 0, FakeRng(0, 0, 0), answers('last stand'))
        boon = game.BOONS['Warrior']
        self.assertEqual(warrior.attack, 15 + boon.attack)
        self.assertEqual(warrior.health, 100 + boon.max_health)
        self.assertEqual(warrior.actions, ['Last Stand'])

    def test_the_second_hoard_offers_the_other_boon_ability(self):
        rogue = hero('rogue')
        quietly(game.boss_reward, party_of(rogue), 0, FakeRng(0, 0, 0), answers('assassinate'))
        prompts = []
        def ask(prompt):
            prompts.append(prompt)
            return 'backstab'
        quietly(game.boss_reward, party_of(rogue), 1, FakeRng(0, 0, 0), ask)
        self.assertTrue(prompts[0].endswith('/ Backstab] '))
        self.assertEqual(rogue.actions, ['Flee', 'Assassinate', 'Backstab'])

    def test_recruiting_gives_no_power_up(self):
        warrior = hero()
        quietly(game.boss_reward, party_of(warrior), 0, FakeRng(0, 0, 0), answers('mira'))
        self.assertEqual((warrior.boons, warrior.actions), ([], []))

    def test_a_full_party_gets_nothing_extra(self):
        party = party_of(hero(), companion(), companion('wizard', 'Ysolde'))
        quietly(game.boss_reward, party, 1, FakeRng(), answers())
        self.assertEqual(party.members[0].boons, [])
        self.assertEqual(len(party.members), 3)


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.stages, self.bestiary = game.STAGES, game.BESTIARY

    def tearDown(self):
        game.STAGES, game.BESTIARY = self.stages, self.bestiary

    def test_choose_job_insists_on_a_real_class(self):
        job, out = captured(game.choose_job, answers('bard', ' Wizard '))
        self.assertEqual(job.name, 'Wizard')
        self.assertIn('idiot', out)

    def test_slaying_all_three_bosses_wins(self):
        game.STAGES = tuple(replace(stage, fights=0) for stage in self.stages)
        party = party_of(hero(attack=2000))
        won, out = captured(game.play, party, FakeRng(0, 0, 0, 0, 0, 0, 0, 0, 0),
                            answers('attack', 'execute', 'attack', 'vex', 'attack'))
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
        quietly(game.fight, party, kobold(), FakeRng(0), answers('attack'))
        scene, details = self.scenes[0]
        self.assertEqual(scene, 'combat')
        details = json.loads(details)
        self.assertEqual([member['name'] for member in details['party']], ['Test', 'Mira'])
        self.assertEqual(details['active'], 0)
        self.assertEqual(details['enemy']['name'], 'Test Kobold')

    def test_skill_and_recruit_scenes_are_plain_data(self):
        quietly(game.choose_skill, hero(), FakeRng(0, 0, 0), answers('cleave'))
        quietly(game.boss_reward, party_of(hero()), 0, FakeRng(0, 0, 0), answers('brann'))
        scenes = dict(self.scenes)
        self.assertIn('skills', scenes)
        recruit = json.loads(scenes['recruit'])
        self.assertEqual([p['name'] for p in recruit['prisoners']], ['Brann', 'Mira', 'Ysolde'])
        self.assertEqual([a['name'] for a in recruit['abilities']], ['Execute', 'Last Stand'])

    def test_class_cards_are_plain_data(self):
        game.show('jobs', jobs=[game.job_view(job) for job in game.JOBS.values()])
        self.assertEqual(self.scenes[0][0], 'jobs')


if __name__ == '__main__':
    unittest.main()
