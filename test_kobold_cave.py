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


def give(member, item_key, slot=None):
    """Equip an item from the bag, as the party panel's Equip button does."""
    party = party_of(member)
    item = game.ITEMS[item_key]
    party.bag.append(item)
    quietly(game.equip_from_bag, party, member, slot or game.slots_for(member, item)[0], item)
    return party


def slog(monster, party):
    """A monster beaten the hard way, so the win earns no ratings."""
    monster.rounds = 5
    party.members[0].bloodied = True
    return monster


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
        tables += [table for stage in game.STAGES for table in stage.loot.values()]
        for table in tables:
            self.assertIn(sum(weight for weight, _ in table), (10, 20))

    def test_every_class_can_find_gear_in_every_tier_its_stage_offers(self):
        for stage in game.STAGES:
            for table in stage.loot.values():
                for _, outcome in table:
                    if isinstance(outcome, int):
                        for job in game.JOBS.values():
                            member = hero(job.name.lower())
                            self.assertTrue([item for item in game.GEAR if item.tier == outcome
                                             and game.fits(member, item)], (job.name, outcome))

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
    def test_a_find_fills_an_empty_slot_by_itself(self):
        warrior = hero()
        party = party_of(warrior)
        self.assertEqual(quietly(game.take, party, game.ITEMS['fine_sword']), 'to Test')
        self.assertEqual((warrior.attack, party.bag), (20, []))

    def test_a_find_for_full_slots_goes_in_the_bag(self):
        warrior = hero()
        game.equip(warrior, 'Weapon', game.ITEMS['mithril_blade'])
        party = party_of(warrior)
        self.assertEqual(quietly(game.take, party, game.ITEMS['fine_sword']), 'into the bag')
        self.assertEqual(party.bag, [game.ITEMS['fine_sword']])

    def test_shield_raises_max_and_current_health(self):
        warrior = hero()
        warrior.health = 100
        give(warrior, 'mithril_buckler')
        self.assertEqual((warrior.health, warrior.max_health), (175, 225))

    def test_swords_do_not_stack(self):
        warrior = hero()
        game.equip(warrior, 'Weapon', game.ITEMS['fine_sword'])
        party = give(warrior, 'firebrand')
        self.assertEqual(warrior.attack, 15 + 10)
        self.assertEqual(party.bag, [game.ITEMS['fine_sword']])  # the old sword is kept

    def test_rogues_choose_which_hand(self):
        rogue = hero('rogue')
        game.equip(rogue, 'Main hand', game.ITEMS['fine_sword'])
        game.equip(rogue, 'Off hand', game.ITEMS['firebrand'])
        party = give(rogue, 'mithril_blade', 'Main hand')
        self.assertEqual(rogue.equipment['Main hand'], game.ITEMS['mithril_blade'])
        self.assertEqual(party.bag, [game.ITEMS['fine_sword']])

    def test_downgrading_a_shield_only_trims_health_to_the_new_max(self):
        warrior = hero()
        game.equip(warrior, 'Shield', game.ITEMS['mithril_buckler'])
        warrior.health = 200
        game.equip(warrior, 'Shield', game.ITEMS['fine_shield'])
        self.assertEqual((warrior.health, warrior.max_health), (175, 175))

    def test_rogue_dual_wields(self):
        rogue = hero('rogue')
        party = party_of(rogue)
        quietly(game.take, party, game.ITEMS['fine_sword'])
        quietly(game.take, party, game.ITEMS['firebrand'])
        self.assertEqual(rogue.attack, 12 + 5 + 10)

    def test_rogue_off_hand_takes_a_parrying_dagger(self):
        rogue = hero('rogue')
        game.equip(rogue, 'Main hand', game.ITEMS['firebrand'])
        quietly(game.take, party_of(rogue), game.ITEMS['parrying_dagger'])
        self.assertEqual(rogue.equipment['Off hand'], game.ITEMS['parrying_dagger'])
        self.assertEqual((rogue.attack, rogue.max_health), (12 + 10 + 4, 120 + 35))

    def test_only_rogues_can_use_daggers_and_only_wizards_find_mana_crystals(self):
        dagger, crystal = game.ITEMS['parrying_dagger'], game.ITEMS['mana_crystal']
        self.assertTrue(game.fits(hero('rogue'), dagger))
        self.assertFalse(game.fits(hero(), dagger))
        self.assertTrue(game.fits(hero('wizard'), crystal))
        self.assertFalse(game.fits(hero('rogue'), crystal))

    def test_staves_add_spell_power_or_mana(self):
        wizard = hero('wizard')
        game.equip(wizard, 'Staff', game.ITEMS['crystal_staff'])
        self.assertEqual((wizard.spell_power, wizard.max_mana, wizard.mana), (70, 7, 7))

    def test_loot_rolls_give_nothing_a_trinket_or_gear_of_a_tier(self):
        rogue = [hero('rogue')]
        table = ((1, None), (1, 'trinket'), (1, 2))
        self.assertIsNone(game.roll_loot(rogue, table, FakeRng(1)))
        self.assertEqual(game.roll_loot(rogue, table, FakeRng(2, 0)).kind, 'trinket')
        tier_two = [game.roll_loot(rogue, table, FakeRng(3, i)) for i in (0, 1)]
        self.assertEqual({item.name for item in tier_two}, {'Firebrand Sword', 'Parrying Dagger'})

    def test_loot_is_rolled_for_the_whole_party(self):
        table = ((1, 1),)
        solo = {game.roll_loot([hero()], table, FakeRng(1, i)).name for i in (0, 1)}
        self.assertEqual(solo, {'Fine Sword', 'Fine Shield'})
        party = [hero(), companion('wizard', 'Ysolde')]
        found = {game.roll_loot(party, table, FakeRng(1, i)).name for i in (0, 1, 2)}
        self.assertEqual(found, {'Fine Sword', 'Fine Shield', 'Apprentice Staff'})

    def test_each_stage_finds_better_gear(self):
        best = [max(value for _, value in stage.loot['rare'] if isinstance(value, int))
                for stage in game.STAGES]
        self.assertEqual(best, sorted(best))
        self.assertEqual(best[-1], 4)

    def test_camp_finds_go_to_whoever_has_room_without_asking(self):
        warrior, wizard = hero(), companion('wizard', 'Ysolde')
        # tier 1 on the Upper Mines table; the third tier-1 item the party can use
        found = quietly(game.search_camp, party_of(warrior, wizard), kobold(), FakeRng(8, 2),
                        answers())
        self.assertEqual(found, 'Apprentice Staff: to Ysolde')
        self.assertEqual(wizard.equipment['Staff'], game.ITEMS['apprentice_staff'])

    def test_a_trinket_goes_to_the_first_hero_with_a_free_trinket_slot(self):
        warrior, rogue = hero(), companion()
        game.equip(warrior, 'Trinket', game.ITEMS['lucky_coin'])
        quietly(game.take, party_of(warrior, rogue), game.ITEMS['vampires_fang'])
        self.assertEqual(rogue.trinket, game.ITEMS['vampires_fang'])


class BagTests(unittest.TestCase):
    def test_a_full_bag_drops_its_oldest_item(self):
        party = party_of(hero())
        for key in ('fine_sword', 'fine_shield', 'firebrand', 'thick_shield', 'mithril_blade',
                    'mithril_buckler', 'lucky_coin', 'apprentice_staff', 'ember_staff'):
            quietly(game.stow, party, game.ITEMS[key])
        self.assertEqual(len(party.bag), game.BAG_SIZE)
        self.assertNotIn(game.ITEMS['fine_sword'], party.bag)

    def test_the_terminal_equips_from_the_bag_between_fights(self):
        warrior, rogue = hero(), companion()
        party = party_of(warrior, rogue)
        party.bag = [game.ITEMS['trolls_blood'], game.ITEMS['fine_shield']]
        quietly(game.open_bag, party,
                answers("troll's blood vial", 'mira', 'done'))
        self.assertEqual(rogue.trinket, game.ITEMS['trolls_blood'])
        self.assertEqual(party.bag, [game.ITEMS['fine_shield']])

    def test_swapping_from_the_bag_puts_the_old_item_back(self):
        warrior = hero()
        game.equip(warrior, 'Trinket', game.ITEMS['lucky_coin'])
        party = party_of(warrior)
        party.bag = [game.ITEMS['trolls_blood']]
        quietly(game.open_bag, party, answers("troll's blood vial", 'done'))
        self.assertEqual(warrior.trinket, game.ITEMS['trolls_blood'])
        self.assertEqual(party.bag, [game.ITEMS['lucky_coin']])

    def test_the_equip_button_swaps_gear_from_the_bag(self):
        warrior = hero()
        game.equip(warrior, 'Weapon', game.ITEMS['fine_sword'])
        party = party_of(warrior)
        party.bag = [game.ITEMS['lucky_coin'], game.ITEMS['mithril_blade']]
        quietly(game.gear_command, party, 'equip\x1fTest\x1fWeapon\x1f1')
        self.assertEqual(warrior.equipment['Weapon'], game.ITEMS['mithril_blade'])
        self.assertEqual(party.bag, [game.ITEMS['lucky_coin'], game.ITEMS['fine_sword']])

    def test_no_changing_gear_mid_fight(self):
        warrior = hero()
        party = party_of(warrior)
        party.bag = [game.ITEMS['mithril_blade']]
        party.in_fight = True
        _, out = captured(game.gear_command, party, 'equip\x1fTest\x1fWeapon\x1f0')
        self.assertIn('no time to change gear', out)
        self.assertIsNone(warrior.equipment['Weapon'])

    def test_an_equip_that_does_not_fit_is_refused(self):
        warrior = hero()
        party = party_of(warrior)
        party.bag = [game.ITEMS['apprentice_staff']]
        _, out = captured(game.gear_command, party, 'equip\x1fTest\x1fWeapon\x1f0')
        self.assertIn('does not fit', out)
        self.assertEqual(party.bag, [game.ITEMS['apprentice_staff']])

    def test_fights_lock_gear_and_unlock_it_after(self):
        party = party_of(hero(attack=200))
        seen = []
        quietly(game.fight, party, kobold(), FakeRng(0),
                lambda prompt: seen.append(party.in_fight) or 'attack')
        self.assertEqual((seen, party.in_fight), ([True], False))

    def test_the_panel_knows_which_bag_items_fit_each_slot(self):
        warrior = hero()
        party = party_of(warrior)
        party.bag = [game.ITEMS['apprentice_staff'], game.ITEMS['firebrand'],
                     game.ITEMS['lucky_coin']]
        gear = {row['slot']: row for row in game.party_details(party)['party'][0]['gear']}
        self.assertEqual([c['name'] for c in gear['Weapon']['candidates']], ['Firebrand Sword'])
        self.assertEqual([c['index'] for c in gear['Trinket']['candidates']], [2])
        self.assertEqual(gear['Shield']['candidates'], [])


class TrinketTests(unittest.TestCase):
    def test_every_class_has_a_trinket_slot(self):
        for job in game.JOBS.values():
            self.assertIn('Trinket', job.slots)

    def test_vial_is_drunk_mid_fight_and_used_up(self):
        warrior = hero()
        game.equip(warrior, 'Trinket', game.ITEMS['trolls_blood'])
        warrior.health = 50
        turn(warrior, party_of(warrior), kobold(), [], 'drink vial')
        self.assertEqual(warrior.health, 50 + 60)
        self.assertIsNone(warrior.trinket)

    def test_no_vial_no_drink(self):
        warrior = hero()
        _, out = captured(game.take_turn, warrior, party_of(warrior), kobold(), FakeRng(0),
                          answers('drink vial', 'attack'))
        self.assertIn('Please select a valid action.', out)

    def test_vampires_fang_heals_from_damage_dealt(self):
        warrior = hero()
        game.equip(warrior, 'Trinket', game.ITEMS['vampires_fang'])
        warrior.health = 100
        turn(warrior, party_of(warrior), kobold(health=100), [0], 'attack')
        self.assertEqual(warrior.health, 100 + round(15 * 0.15))

    def test_emberward_halves_fire_breath(self):
        warrior, rogue = hero(), companion()
        game.equip(warrior, 'Trinket', game.ITEMS['emberward_charm'])
        dragon = boss(breath=30, signature='Fire Breath', charging='Fire Breath')
        quietly(game.monster_turn, party_of(warrior, rogue), dragon, 4, FakeRng(0, 0))
        self.assertEqual((warrior.health, rogue.health), (150 - 15, 120 - 30))

    def test_lucky_coin_can_turn_a_blow_aside(self):
        warrior = hero()
        game.equip(warrior, 'Trinket', game.ITEMS['lucky_coin'])
        quietly(game.monster_strikes, warrior, kobold(), FakeRng(0, -2, 1))  # the coin rolls 1
        self.assertEqual(warrior.health, 150)
        quietly(game.monster_strikes, warrior, kobold(), FakeRng(0, -2, 2))
        self.assertEqual(warrior.health, 140)

    def test_medics_satchel_boosts_bandages(self):
        warrior = hero()
        game.equip(warrior, 'Trinket', game.ITEMS['medics_satchel'])
        warrior.health = 20
        quietly(game.offer_bandages, party_of(warrior), answers('yes', 'no'))
        self.assertEqual(warrior.health, 20 + round(150 * game.BANDAGE_HEAL * 1.5))

    def test_thorned_bracer_bites_back(self):
        warrior, monster = hero(), kobold(attack=20)
        game.equip(warrior, 'Trinket', game.ITEMS['thorned_bracer'])
        quietly(game.monster_strikes, warrior, monster, FakeRng(0, -2))
        self.assertEqual(monster.health, 35 - 5)

    def test_bosses_drop_a_unique_for_the_hero_who_claims_it(self):
        rogue = hero('rogue')
        quietly(game.claim_boss_drop, party_of(rogue), game.spawn('kobold_warchief'),
                answers())
        self.assertIn(game.ITEMS['hand_axe'], rogue.equipment.values())
        found = quietly(game.claim_boss_drop, party_of(rogue), game.spawn('kobold_leader'))
        self.assertEqual(rogue.trinket, game.ITEMS['junk_crown'])
        self.assertEqual(found, ('Junk Crown: to Test', 'Fills an empty slot'))

    def test_a_boss_drop_for_a_full_slot_is_compared_with_what_is_worn(self):
        warrior = hero()
        game.equip(warrior, 'Weapon', game.ITEMS['firebrand'])
        party = party_of(warrior)
        found, against = quietly(game.claim_boss_drop, party, game.spawn('kobold_warchief'))
        self.assertEqual(found, "Warchief's War Axe: into the bag")
        self.assertEqual(against, '+10 attack vs your Firebrand Sword')

    def test_in_a_party_you_choose_who_claims_the_prize(self):
        warrior, wizard = hero(), companion('wizard', 'Ysolde')
        quietly(game.claim_boss_drop, party_of(warrior, wizard), game.spawn('kobold_warchief'),
                answers('ysolde'))  # who claims it; it fills Ysolde's empty shield slot
        self.assertEqual(wizard.equipment['Shield'], game.ITEMS['drum_shield'])

    def test_junk_crown_hits_bosses_harder(self):
        warrior = hero()
        game.equip(warrior, 'Trinket', game.ITEMS['junk_crown'])
        monster = boss(health=300)
        turn(warrior, party_of(warrior), monster, [0], 'attack')
        self.assertEqual(monster.health, 300 - round(15 * 1.15))


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

    def test_dragon_breath_hits_everyone(self):
        warrior, rogue = hero(), companion()
        dragon = boss(breath=30, signature='Fire Breath', charging='Fire Breath')
        quietly(game.monster_turn, party_of(warrior, rogue), dragon, 4, FakeRng(0, 0))
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
        recruit = game.prisoner('warrior', 0, 1, FakeRng(4))
        self.assertEqual(recruit.actions, ['Battle Cry'])

    def test_higher_level_prisoners_know_more_skills(self):
        recruit = game.prisoner('rogue', 0, 4, FakeRng(0, 0, 0))
        self.assertEqual(recruit.level, 4)
        self.assertEqual(recruit.actions, ['Flee', 'Stunning Strike', 'Poison Blade', 'Smoke Bomb'])
        self.assertEqual(recruit.health, recruit.max_health)


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


class MonsterAbilityTests(unittest.TestCase):
    def test_every_monster_ability_exists(self):
        for monster in game.BESTIARY.values():
            for name in monster.abilities + ((monster.signature,) if monster.signature else ()):
                self.assertIn(name, game.MONSTER_ABILITIES, monster.name)
            self.assertEqual(len(monster.abilities), 2 if monster.boss else 1, monster.name)

    def test_rock_toss_cannot_be_parried(self):
        warrior = hero()
        warrior.defending = True
        # ability roll 1 (of 3), damage roll 0, dodge roll -2 (fails)
        quietly(game.monster_turn, party_of(warrior), kobold(abilities=('Rock Toss',)), 1,
                FakeRng(1, 0, -2))
        self.assertEqual(warrior.health, 150 - 7)

    def test_abilities_wait_out_their_cooldown(self):
        warrior, monster = hero(), kobold(abilities=('Rock Toss',))
        party = party_of(warrior)
        quietly(game.monster_turn, party, monster, 1, FakeRng(1, 0, -2))
        # on cooldown: no ability roll, just a normal blow
        quietly(game.monster_turn, party, monster, 2, FakeRng(0, -2))
        self.assertEqual(warrior.health, 150 - 7 - 10)

    def test_shield_up_halves_your_damage_until_its_next_turn(self):
        warrior, monster = hero(), kobold(abilities=('Shield Up',))
        party = party_of(warrior)
        quietly(game.monster_turn, party, monster, 1, FakeRng(1))
        turn(warrior, party, monster, [0], 'attack')
        self.assertEqual(monster.health, 35 - 8)

    def test_crushing_blow_is_announced_then_cannot_be_dodged(self):
        warrior, monster = hero(), kobold(abilities=('Crushing Blow',))
        party = party_of(warrior)
        _, out = captured(game.monster_turn, party, monster, 1, FakeRng(1))
        self.assertIn('Brace yourselves!', out)
        self.assertEqual((warrior.health, monster.charging), (150, 'Crushing Blow'))
        quietly(game.monster_turn, party, monster, 2, FakeRng(0))  # damage roll only
        self.assertEqual(warrior.health, 150 - 15)

    def test_a_stun_interrupts_a_wind_up(self):
        warrior, monster = hero(), kobold(charging='Crushing Blow', stunned=1)
        _, out = captured(game.monster_turn, party_of(warrior), monster, 1, FakeRng())
        self.assertIn('no Crushing Blow this time', out)
        self.assertEqual((warrior.health, monster.charging), (150, ''))

    def test_smoke_wastes_a_wind_up(self):
        warrior, monster = hero(), kobold(charging='Crushing Blow')
        party = party_of(warrior)
        party.smoke = True
        quietly(game.monster_turn, party, monster, 1, FakeRng())
        self.assertEqual((warrior.health, monster.charging), (150, ''))

    def test_defending_halves_an_area_attack(self):
        warrior, rogue = hero(), companion()
        warrior.defending = True
        leader = boss(attack=30, signature='Junk Avalanche', charging='Junk Avalanche')
        quietly(game.monster_turn, party_of(warrior, rogue), leader, 1, FakeRng(0, 0))
        self.assertEqual((warrior.health, rogue.health), (150 - 18, 120 - 36))

    def test_junk_avalanche_comes_once_below_half_health(self):
        leader = boss(health=200, signature='Junk Avalanche')
        leader.health = 99
        party = party_of(hero())
        quietly(game.monster_turn, party, leader, 1, FakeRng())
        self.assertEqual(leader.charging, 'Junk Avalanche')
        quietly(game.monster_turn, party, leader, 2, FakeRng(0))
        quietly(game.monster_turn, party, leader, 3, FakeRng(0, -2))  # a normal blow after
        self.assertEqual(leader.charging, '')

    def test_hex_weakens_a_hero(self):
        warrior, monster = hero(), kobold(health=100, abilities=('Hex',))
        party = party_of(warrior)
        quietly(game.monster_turn, party, monster, 1, FakeRng(1))
        self.assertTrue(warrior.hexed)
        turn(warrior, party, monster, [0], 'attack')
        self.assertEqual(monster.health, 100 - 11)

    def test_fire_spear_sets_you_burning(self):
        warrior, monster = hero(), kobold(attack=20, abilities=('Fire Spear',))
        party = party_of(warrior)
        quietly(game.monster_turn, party, monster, 1, FakeRng(1, 0, -2))
        self.assertEqual((warrior.health, warrior.burning), (130, 2))
        quietly(game.monster_turn, party, monster, 2, FakeRng(0, 1))  # burns, then a miss
        self.assertEqual(warrior.health, 130 - 6)

    def test_dirty_trick_costs_you_a_turn(self):
        warrior = hero(attack=200)
        warrior.reeling = 1
        prompts = []
        def ask(prompt):
            prompts.append(prompt)
            return 'attack'
        won = quietly(game.fight, party_of(warrior), kobold(), FakeRng(0, 1, 0), ask)
        self.assertTrue(won)
        self.assertEqual(len(prompts), 1)  # the first round was lost

    def test_sweeping_axe_hits_two_heroes(self):
        warrior, rogue = hero(), companion()
        quietly(game.sweeping_axe, party_of(warrior, rogue), boss(), FakeRng(0, 0, -2, 0, -2))
        self.assertEqual((warrior.health, rogue.health), (120, 90))

    def test_the_warchief_goes_berserk_below_30_percent(self):
        warrior, warchief = hero(), boss(health=100, signature='Berserk')
        warchief.health = 25
        quietly(game.monster_turn, party_of(warrior), warchief, 1,
                FakeRng(0, -2, 0, -2, 0, -2))
        self.assertEqual(warrior.health, 150 - 90)
        self.assertIn('Berserk', game.monster_view(warchief)['effects'])

    def test_fire_breath_is_announced_every_third_turn(self):
        dragon = boss(signature='Fire Breath', breath=30, breath_timer=2)
        quietly(game.monster_turn, party_of(hero()), dragon, 3, FakeRng())
        self.assertEqual(dragon.charging, 'Fire Breath')
        self.assertIn('Winding up: Fire Breath', game.monster_view(dragon)['effects'])


class ExperienceTests(unittest.TestCase):
    def test_kills_give_xp_to_everyone_standing(self):
        warrior, rogue = hero(), companion()
        rogue.health = 0
        quietly(game.award_xp, party_of(warrior, rogue), kobold(xp=30))
        self.assertEqual((warrior.xp, rogue.xp), (30, 0))

    def test_level_up_raises_stats_without_healing(self):
        warrior = hero(skills=['Cleave'])
        warrior.health = 100
        quietly(game.award_xp, party_of(warrior), kobold(xp=50), FakeRng(0, 0),
                answers('shield bash'))
        growth = game.JOBS['warrior'].growth
        self.assertEqual(warrior.level, 2)
        self.assertEqual(warrior.attack, 15 + growth.attack)
        self.assertEqual(warrior.max_health, 150 + growth.max_health)
        self.assertEqual(warrior.health, 100 + growth.max_health)  # still just as wounded

    def test_levels_two_and_four_offer_two_new_skills(self):
        warrior = hero(skills=['Cleave'])
        prompts = []
        def ask(prompt):
            prompts.append(prompt)
            return prompt[prompt.index('[') + 1:].split(' / ')[0]
        quietly(game.award_xp, party_of(warrior), kobold(xp=game.LEVEL_XP[-1]),
                FakeRng(*[0] * 10), ask)
        self.assertEqual(warrior.level, len(game.LEVEL_XP))
        self.assertEqual(len(prompts), 2)
        self.assertTrue(all(prompt.count(' / ') == 1 for prompt in prompts))  # 2 options each
        basics = [name for name in warrior.actions if name in warrior.job.skills]
        self.assertEqual(len(basics), 3)  # every hero ends with three basic skills

    def test_wizards_gain_mana_every_other_level(self):
        wizard = hero('wizard')
        wizard.level = 3
        self.assertEqual(wizard.max_mana, 5 + 1)
        self.assertEqual(wizard.spell_power, 60 + 2 * 5)

    def test_companions_choose_their_own_skills(self):
        warrior, rogue = hero(), companion(skills=['Twin Strike'])
        rogue.xp = 40
        prompts = []
        def ask(prompt):
            prompts.append(prompt)
            return 'smoke bomb'
        quietly(game.award_xp, party_of(warrior, rogue), kobold(xp=10), FakeRng(1, 1), ask)
        self.assertTrue(prompts[0].startswith('Mira: Which skill?'))
        self.assertIn('Smoke Bomb', rogue.actions)


class RewardTests(unittest.TestCase):
    def test_freeing_a_prisoner_adds_them_with_gear_and_a_skill(self):
        party = party_of(hero())
        # class roll: wizard; level roll: -1 (but never below 1); skill roll
        quietly(game.boss_reward, party, 0, FakeRng(2, -1, 0), answers('ysolde'))
        recruit = party.members[1]
        self.assertEqual((recruit.name, recruit.job.name), ('Ysolde', 'Wizard'))
        self.assertEqual(recruit.equipment['Staff'], game.ITEMS['ember_staff'])
        self.assertEqual(recruit.actions, ['Mana Surge', 'Fireball'])
        self.assertEqual(recruit.health, recruit.max_health)
        self.assertFalse(recruit.hero)

    def test_fallen_companions_make_room_for_new_ones(self):
        rogue = companion()
        rogue.health = 0
        party = party_of(hero(), rogue)
        quietly(game.boss_reward, party, 1, FakeRng(0, 0, 0), answers('hilda'))
        self.assertEqual(len(party.members), 2)
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
        quietly(game.boss_reward, party_of(warrior), 0, FakeRng(1, 0, 0), answers('mira'))
        self.assertEqual((warrior.boons, warrior.actions), ([], []))

    def test_only_one_prisoner_is_offered_within_a_level_of_you(self):
        warrior = hero()
        warrior.level = 3
        prompts = []
        def ask(prompt):
            prompts.append(prompt)
            return 'vex'
        party = party_of(warrior)
        quietly(game.boss_reward, party, 1, FakeRng(1, 1, 0, 0, 0), ask)
        self.assertEqual(prompts, ['Free the prisoner, or keep the hoard? '
                                   '[Vex / Execute / Last Stand] '])
        self.assertEqual(party.members[1].level, 4)

    def test_a_full_party_gets_nothing_extra(self):
        party = party_of(hero(), companion(), companion('wizard', 'Ysolde'))
        quietly(game.boss_reward, party, 1, FakeRng(), answers())
        self.assertEqual(party.members[0].boons, [])
        self.assertEqual(len(party.members), 3)


class ForgeTests(unittest.TestCase):
    def test_reforging_adds_stats_and_a_plus(self):
        blade = game.reforged(game.ITEMS['mithril_blade'])
        self.assertEqual((blade.name, blade.attack, blade.forged), ('Mithril Blade +1', 19, 1))
        blade = game.reforged(blade)
        self.assertEqual((blade.name, blade.attack), ('Mithril Blade +2', 23))

    def test_salvage_turns_bag_items_into_scrap(self):
        party = party_of(hero())
        party.bag = [game.ITEMS['fine_sword'], game.ITEMS['mithril_buckler'],
                     game.ITEMS['lucky_coin']]
        quietly(game.visit_forge, party, answers('salvage', 'fine sword', 'salvage', 'all',
                                                 'leave'))
        self.assertEqual((party.bag, party.scrap), ([], 1 + 3 + 2))

    def test_reforge_spends_scrap_on_equipped_gear(self):
        warrior = hero()
        game.equip(warrior, 'Weapon', game.ITEMS['firebrand'])
        party = party_of(warrior)
        party.scrap = 5  # the first reforge costs 2 scrap, the second 3
        quietly(game.visit_forge, party, answers('reforge', "test's firebrand sword",
                                                 'reforge', "test's firebrand sword +1", 'leave'))
        self.assertEqual(warrior.equipment['Weapon'].name, 'Firebrand Sword +2')
        self.assertEqual((warrior.attack, party.scrap), (15 + 10 + 8, 0))

    def test_reforging_needs_enough_scrap_and_stops_at_plus_three(self):
        warrior = hero()
        maxed = game.ITEMS['fine_shield']
        for _ in range(game.FORGE_LIMIT):
            maxed = game.reforged(maxed)
        game.equip(warrior, 'Shield', maxed)
        game.equip(warrior, 'Weapon', game.ITEMS['fine_sword'])
        party = party_of(warrior)
        party.scrap = 1
        prompts = []
        def ask(prompt):
            prompts.append(prompt)
            return ['reforge', "test's fine sword", 'leave'][len(prompts) - 1]
        _, out = captured(game.visit_forge, party, ask)
        self.assertIn('That needs 2 scrap', out)
        self.assertNotIn('Fine Shield', prompts[1])  # already +3


class TraderTests(unittest.TestCase):
    def test_trader_sells_bandages_vials_a_trinket_and_a_tome(self):
        rogue = hero('rogue', skills=['Twin Strike'])
        labels = [label for label, _, _ in game.trader_stock(party_of(rogue), FakeRng(0, 0))]
        self.assertEqual(labels[:2], ['Bandage', "Troll's Blood Vial"])
        self.assertEqual(len(labels), 4)
        self.assertTrue(labels[3].startswith('Tome of '))

    def test_buying_spends_gold(self):
        warrior = hero()
        party = party_of(warrior)
        party.gold = 36
        quietly(game.visit_trader, party, FakeRng(0, 0),
                answers('bandage', "troll's blood vial", 'bandage', 'leave'))
        self.assertEqual(party.bandages, game.START_BANDAGES + 2)
        self.assertEqual(warrior.trinket, game.ITEMS['trolls_blood'])
        self.assertEqual(party.gold, 36 - 8 - 20 - 8)

    def test_you_cannot_buy_what_you_cannot_afford(self):
        party = party_of(hero())
        party.gold = 5
        _, out = captured(game.visit_trader, party, FakeRng(0, 0), answers('bandage', 'leave'))
        self.assertIn('That costs 8 gold', out)
        self.assertEqual(party.bandages, game.START_BANDAGES)

    def test_a_tome_teaches_a_skill(self):
        warrior = hero(skills=['Cleave'])
        party = party_of(warrior)
        party.gold = 45
        stock = game.trader_stock(party, FakeRng(0, 0))
        tome = stock[-1][0]
        quietly(game.visit_trader, party, FakeRng(0, 0), answers(tome.lower(), 'leave'))
        self.assertEqual(len(warrior.actions), 2)
        self.assertEqual(party.gold, 0)

    def test_selling_bag_items(self):
        party = party_of(hero())
        party.bag = [game.ITEMS['mithril_blade']]
        quietly(game.visit_trader, party, FakeRng(0, 0), answers('sell', 'mithril blade', 'leave'))
        self.assertEqual((party.bag, party.gold), ([], 3 * 6))


class ForkTests(unittest.TestCase):
    def test_the_fork_leads_where_you_choose(self):
        party = party_of(hero())
        stage = game.STAGES[0]
        _, out = captured(game.fork, party, stage, 3, FakeRng(), answers('forge', 'leave'))
        self.assertIn('Someone left this forge burning', out)
        _, out = captured(game.fork, party, stage, 3, FakeRng(0, 0), answers('trader', 'leave'))
        self.assertIn('Friends! Customers!', out)

    def test_the_dark_tunnel_can_hide_a_cache(self):
        party = party_of(hero())
        # cache roll, then common loot: a trinket (rolls 6-7), the first one
        quietly(game.dark_tunnel, party, game.STAGES[0], 3, FakeRng(1, 6, 0), answers())
        self.assertEqual(party.gold, 20)
        self.assertIsNotNone(party.members[0].trinket)

    def test_the_dark_tunnel_can_be_an_ambush(self):
        party = party_of(hero(attack=1000))
        # ambush roll, encounter roll on the stage's deepest table (a miner), its free
        # strike (no ability; damage, dodge), one blow; then XP, gold and the bandage
        # roll, but no camp to search; and no bandage used on the wound
        won_out = captured(game.dark_tunnel, party, game.STAGES[0], 3,
                           FakeRng(2, 5, 2, 0, -2, 0, 2), answers('attack', 'no'))[1]
        self.assertIn('they strike first', won_out)
        self.assertIn('You are struck', won_out)
        self.assertNotIn('search the kobolds camp', won_out)
        self.assertEqual(party.cs, 1)


class VictoryTests(unittest.TestCase):
    def test_one_huge_blow_earns_every_rating(self):
        party, monster = party_of(hero(attack=1000)), kobold()
        quietly(game.fight, party, monster, FakeRng(0), answers('attack'))
        self.assertEqual(game.rate_victory(party, monster), ['Flawless', 'Swift', 'Overkill'])

    def test_a_long_bloody_fight_earns_none(self):
        party = party_of(hero())
        self.assertEqual(game.rate_victory(party, slog(kobold(), party)), [])

    def test_ratings_pay_gold_xp_and_scrap(self):
        party, guard = party_of(hero()), game.spawn('kobold_guard')
        guard.rounds, guard.overkill = 1, True
        ratings, bonus_xp, _ = quietly(game.judge_victory, party, guard)
        self.assertEqual([rating['name'] for rating in ratings], ['Flawless', 'Swift', 'Overkill'])
        self.assertEqual((party.gold, bonus_xp, party.scrap), (3, 4, 1))
        self.assertEqual(party.rating_counts, {'Flawless': 1, 'Swift': 1, 'Overkill': 1})

    def test_the_narrator_picks_a_verdict_without_rolling_dice(self):
        warrior = hero()
        party = party_of(warrior)
        self.assertIn(game.verdict(party, kobold(rounds=1), ['Flawless']),
                      game.VERDICTS['flawless'])
        warrior.health = 10
        self.assertIn(game.verdict(party, kobold(rounds=1), ['Flawless']),
                      [line.format(name='Test') for line in game.VERDICTS['close']])

    def test_rated_wins_build_a_trophy_set_for_the_whole_party(self):
        warrior, rogue = hero(), companion()
        party = party_of(warrior, rogue)
        attack = warrior.attack
        for _ in range(3):
            trophy = quietly(game.claim_trophy, party, game.spawn('kobold_miner'),
                             ['Flawless', 'Swift'])
        self.assertTrue(trophy['complete'])
        self.assertEqual((warrior.attack, rogue.attack - companion().attack), (attack + 3, 3))
        # The set is full, so no more picks; and one rating isn't enough for a trophy.
        self.assertIsNone(quietly(game.claim_trophy, party, game.spawn('kobold_miner'),
                                  ['Flawless', 'Swift']))
        self.assertIsNone(quietly(game.claim_trophy, party, game.spawn('kobold_guard'),
                                  ['Flawless']))

    def test_recruits_get_the_full_sets_too(self):
        party = party_of(hero())
        party.relics.append(game.TROPHIES['Kobold Guardsman'].relic)
        quietly(game.boss_reward, party, 0, FakeRng(0, 0, 0), answers('brann'))
        recruit = party.members[1]
        self.assertIn(game.TROPHIES['Kobold Guardsman'].relic, recruit.boons)
        self.assertEqual(recruit.health, recruit.max_health)


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.stages, self.bestiary = game.STAGES, game.BESTIARY

    def tearDown(self):
        game.STAGES, game.BESTIARY = self.stages, self.bestiary

    def test_choose_job_insists_on_a_real_class(self):
        job, out = captured(game.choose_job, answers('bard', ' Wizard '))
        self.assertEqual(job.name, 'Wizard')
        self.assertIn('idiot', out)

    def no_xp(self):
        game.BESTIARY = {key: replace(monster, xp=0) for key, monster in self.bestiary.items()}

    def test_slaying_all_three_bosses_wins(self):
        self.no_xp()
        game.STAGES = tuple(replace(stage, fights=0) for stage in self.stages)
        party = party_of(hero(attack=2000))
        # boss 1; a prisoner (class, level, skill); boss 2; Vex the rogue; boss 3
        won, out = captured(game.play, party, FakeRng(0, 0, 0, 0, 0, 1, 0, 0, 0),
                            answers('attack', 'execute', 'attack', 'vex', 'attack'))
        self.assertTrue(won)
        self.assertIn('actually made it out', out)
        self.assertEqual(party.cs, 3)
        self.assertEqual([member.name for member in party.members], ['Test', 'Vex'])

    def test_a_win_earns_creep_score_loot_bandages_and_rest(self):
        self.no_xp()
        game.STAGES = (replace(self.stages[0], fights=1),)
        warrior = hero(attack=1000)
        warrior.health = 100
        party = party_of(warrior)
        # encounter: miner; one hit; tier 1 gear, the Fine Shield, which the hero takes;
        # a bandage drop; then the boss, who drops the Junk Crown
        won = quietly(game.play, party, FakeRng(5, 0, 8, 1, 1, 0),
                      answers('attack', 'no', 'attack'))
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
        scene, details = self.scenes[1]  # after the 'encounter' that opens every fight
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
        self.assertEqual([p['name'] for p in recruit['prisoners']], ['Brann'])
        self.assertEqual([a['name'] for a in recruit['abilities']], ['Execute', 'Last Stand'])

    def test_panel_data_covers_stats_gear_skills_and_the_journey(self):
        wizard = hero('wizard', skills=['Fireball', 'Meteor'])
        game.equip(wizard, 'Trinket', game.ITEMS['lucky_coin'])
        wizard.cooldowns['Meteor'] = 2
        party = party_of(wizard)
        party.bag = [game.ITEMS['fine_sword']]
        game.show_party('combat', party, game.spawn('kobold_shaman'), active=wizard)
        details = json.loads(self.scenes[-1][1])
        member = details['party'][0]
        self.assertEqual(member['spell_power'], 60)
        self.assertIn({'slot': 'Trinket', 'name': 'Lucky Coin',
                       'describe': game.ITEMS['lucky_coin'].describe(), 'forged': 0,
                       'candidates': []},
                      member['gear'])
        skills = {skill['name']: skill for skill in member['skills']}
        self.assertEqual(skills['Mana Surge']['kind'], 'signature')
        self.assertEqual(skills['Meteor']['kind'], 'boon')
        self.assertEqual(skills['Meteor']['waiting'], 2)
        self.assertEqual(details['enemy']['abilities'][0]['name'], 'Hex')
        self.assertEqual([stage['boss'] for stage in details['stages']],
                         ['Kobold Leader', 'Kobold Warchief', 'Cinderjaw the Red'])
        self.assertEqual(details['bag'][0]['name'], 'Fine Sword')

    def test_a_win_ends_with_a_spoils_card(self):
        party = party_of(hero())
        guard = slog(game.spawn('kobold_guard'), party)
        quietly(game.after_victory, party, guard, FakeRng(5, 2), answers())
        scene, details = self.scenes[-1]
        self.assertEqual(scene, 'spoils')
        spoils = json.loads(details)['spoils']
        self.assertEqual((spoils['xp'], spoils['gold'], spoils['found']), (15, 6, 'Nothing of worth'))
        self.assertEqual(party.gold, 6)
        # The fight's end is marked first, so the log can start a fresh block.
        self.assertEqual(self.scenes[0][0], 'aftermath')

    def test_fights_start_with_an_encounter_scene(self):
        quietly(game.fight, party_of(hero(attack=1000)), kobold(), FakeRng(0), answers('attack'))
        self.assertEqual(self.scenes[0][0], 'encounter')

    def test_new_gear_in_the_bag_pauses_before_the_next_fight(self):
        party = party_of(hero())
        game.equip(party.members[0], 'Shield', game.ITEMS['fine_shield'])
        quietly(game.stow, party, game.ITEMS['thick_shield'])
        # No loot and no bandages, and nobody hurt: only the pause asks anything.
        quietly(game.after_victory, party, game.spawn('kobold_guard'), FakeRng(5, 2),
                answers('press on'))
        self.assertFalse(party.bag_changed)
        # Nothing new since: the next win doesn't stop (answers() would run dry).
        quietly(game.after_victory, party, game.spawn('kobold_guard'), FakeRng(5, 2), answers())

    def test_the_panel_shows_how_often_gear_was_reforged(self):
        warrior = hero()
        blade = game.reforged(game.reforged(game.ITEMS['mithril_blade']))
        game.equip(warrior, 'Weapon', blade)
        game.show_party('explore', party_of(warrior))
        gear = json.loads(self.scenes[-1][1])['party'][0]['gear']
        sword = next(slot for slot in gear if slot['slot'] == 'Weapon')
        self.assertEqual((sword['name'], sword['describe']), ('Mithril Blade +2', '+23 attack'))
        self.assertEqual((sword['forged'], sword['forge_limit'], sword['forge_gains']),
                         (2, game.FORGE_LIMIT, '+8 attack'))

    def test_class_cards_are_plain_data(self):
        game.show('jobs', jobs=[game.job_view(job) for job in game.JOBS.values()])
        self.assertEqual(self.scenes[0][0], 'jobs')


if __name__ == '__main__':
    unittest.main()
