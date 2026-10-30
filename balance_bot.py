"""A bot that plays whole runs of Kobold Cave, for checking the balance.

It answers the game's questions the way a sensible player would: it uses
its skills, guards against announced moves, heals when hurt, equips better
gear and spends its gold and scrap. It is not a perfect player, so its win
rates are best used to compare classes, or the same class before and after
a change, rather than as the odds a person will see.

    python3 balance_bot.py                 # 200 runs of each class
    python3 balance_bot.py --runs 400 --hoard
    python3 balance_bot.py --job wizard --fork trader

Runs are seeded 0, 1, 2 and so on, so the same command gives the same
numbers until the game changes.
"""

import argparse
import random
import re
from collections import Counter
from contextlib import contextmanager, redirect_stdout
from io import StringIO

import kobold_cave as game

MAX_ANSWERS = 5000  # more than any real run needs; stops a bot stuck re-answering

# Skills the bot learns first, best first.
SKILL_ORDER = {
    'Warrior': ('Cleave', 'Battle Cry', 'Shield Bash', 'Second Wind', 'Shield Wall'),
    'Rogue': ('Twin Strike', 'Stunning Strike', 'Poison Blade', 'Smoke Bomb', 'Pickpocket'),
    'Wizard': ('Fireball', 'Frost Bolt', 'Drain Life', 'Arcane Shield', 'Mend'),
}

# Rough worth of a trinket's effect, in the same units as one point of attack.
EFFECT_VALUE = {'lifesteal': 18, 'lucky': 22, 'thorns': 15, 'fireward': 12, 'satchel': 8,
                'bossbane': 15, 'vial': 30}


class Bot:
    """Stands in for input(): call it with a question, get back an answer."""

    def __init__(self, job_key, rng, hoard=False, fork=None):
        # The bot's own dice, so its choices don't shift the game's rolls.
        self.job_key, self.rng, self.hoard, self.fork = job_key, rng, hoard, fork
        self.party = None
        self.monster = None  # the enemy in the current fight, see watch_fights
        self.mend_target = None
        self.answers = 0

    def __call__(self, question):
        self.answers += 1
        if self.answers > MAX_ANSWERS:
            raise RuntimeError(f'The bot is stuck on: {question}')
        self.equip_upgrades()
        party = self.party
        if question.startswith('Which would you prefer?'):
            return self.job_key
        options = re.findall(r'\[([^\]]*)\]\s*$', question.strip())[0].split(' / ')
        if 'Attack' in options:
            return self.combat(self.member_asked(question), options)
        if 'Which skill?' in question:
            order = next(order for order in SKILL_ORDER.values() if options[0] in order)
            return min(options, key=order.index)
        if question.startswith('Free the prisoner'):
            return options[-1] if self.hoard else options[0]
        if question.startswith('Use a bandage?'):
            for option in options:
                member = party.living[0] if option == 'Yes' else \
                    next((m for m in party.living if m.name == option), None)
                if member and member.health < member.max_health * 0.6:
                    return option
            return 'No'
        if question.startswith('Mend whom?'):
            return (self.mend_target or party.living[0]).name
        if question.startswith('Who claims'):
            return options[0]
        if question.startswith('Which way?'):
            return self.fork or options[self.rng.randint(0, len(options) - 1)]
        if question.startswith('What will you do at the forge?'):
            if party.bag:
                return 'Salvage'
            return 'Reforge' if self.forgeable() else 'Leave'
        if question.startswith('Salvage what?'):
            return 'All'
        if question.startswith('Reforge what?'):
            return (self.forgeable() or ['Back'])[0]
        if question.startswith('What will you buy?'):
            return self.shop(options)
        if question.startswith('Equip something'):
            return 'Done'  # equip_upgrades has already done it
        if options == ['Press on']:
            return 'Press on'
        raise RuntimeError(f'The bot has no answer for: {question}')

    def member_asked(self, question):
        """Whose orders a combat menu wants: in a party it starts 'Name: '."""
        living = self.party.living
        if len(living) == 1:
            return living[0]
        return next(member for member in living if question.startswith(f'{member.name}: '))

    def ready(self, member, name):
        action = game.ACTIONS[name]
        return not member.cooldowns.get(name) and member.mana >= action.mana \
            and not (action.once and name in member.used)

    def combat(self, member, options):
        def ready(name):
            return name in options and self.ready(member, name)

        monster, party = self.monster, self.party
        health = member.health / member.max_health
        warned = monster.charging  # a big move was announced last turn
        if health < 0.35 and ready('Drink Vial'):
            return 'Drink Vial'
        job = member.job.name
        if job == 'Warrior':
            if health < 0.3 and ready('Last Stand'):
                return 'Last Stand'
            if health < 0.45 and ready('Second Wind'):
                return 'Second Wind'
            if warned and ready('Shield Bash'):
                return 'Shield Bash'
            if warned and len(party.living) > 1 and ready('Shield Wall'):
                return 'Shield Wall'
            moves = ('Execute', 'Battle Cry', 'Cleave', 'Shield Bash')
        elif job == 'Rogue':
            if warned and ready('Stunning Strike'):
                return 'Stunning Strike'
            if warned and ready('Smoke Bomb'):
                return 'Smoke Bomb'
            if (monster.stunned or monster.dazed) and ready('Backstab'):
                return 'Backstab'
            if monster.health <= monster.max_health * 0.3 and ready('Assassinate'):
                return 'Assassinate'
            moves = ('Backstab', 'Twin Strike', 'Poison Blade', 'Stunning Strike', 'Pickpocket')
        else:
            hurt = min(party.living, key=lambda m: m.health / m.max_health)
            if monster.boss and not monster.stunned and ready('Time Stop'):
                return 'Time Stop'
            if warned and ready('Arcane Shield'):
                return 'Arcane Shield'
            if hurt.health < hurt.max_health * 0.4 and ready('Mend'):
                self.mend_target = hurt
                return 'Mend'
            if ready('Meteor'):
                return 'Meteor'
            if health < 0.5 and ready('Drain Life'):
                return 'Drain Life'
            if member.mana <= 1 and monster.health > member.spell_power and ready('Mana Surge'):
                return 'Mana Surge'
            moves = ('Fireball', 'Arcane Shield', 'Frost Bolt', 'Drain Life', 'Mana Surge')
        return next((name for name in moves if ready(name)), 'Attack')

    def worth(self, member, item):
        """A rough score for an item in this member's hands."""
        if item is None:
            return -1
        wizard = member.job.name == 'Wizard'
        return (item.attack * (0.2 if wizard else 1) + item.max_health * 0.35
                + item.spell_power * (1.2 if wizard else 0) + item.mana * (25 if wizard else 0)
                + item.dodge * 10 + EFFECT_VALUE.get(item.effect, 0))

    def equip_upgrades(self):
        """Between fights, put on anything in the bag that beats what's worn,
        as a player would with the party panel's Equip buttons."""
        party = self.party
        if not party or party.in_fight:
            return
        swapped = True
        while swapped:
            swapped = False
            for item in party.bag:
                best = max(((self.worth(member, item) - self.worth(member, member.equipment[slot]),
                             member, slot)
                            for member in party.living for slot in game.slots_for(member, item)),
                           key=lambda choice: choice[0], default=None)
                if best and best[0] > 0:
                    with redirect_stdout(StringIO()):
                        game.equip_from_bag(party, best[1], best[2], item)
                    swapped = True
                    break

    def forgeable(self):
        """Labels the forge would accept that the party can afford: weapons
        and staves first, least reforged first."""
        party, choices = self.party, []
        for member in party.living:
            for item in member.equipment.values():
                if item and item.kind in game.REFORGE and item.forged < game.FORGE_LIMIT \
                        and item.forged + 2 <= party.scrap:
                    choices.append((item.kind not in ('sword', 'staff'), item.forged,
                                    f"{member.name}'s {item.name}"))
        return [label for *_, label in sorted(choices)]

    def shop(self, options):
        party = self.party
        tome = next((option for option in options if option.startswith('Tome')), None)
        if tome and party.gold >= 45:
            return tome
        if "Troll's Blood Vial" in options and party.gold >= 20 \
                and any(member.trinket is None for member in party.living):
            return "Troll's Blood Vial"
        if party.gold >= 8 and party.bandages < 4:
            return 'Bandage'
        return 'Leave'


@contextmanager
def watch_fights(bot, deaths):
    """Let the bot see each fight's enemy, and note who ended the run."""
    fight_rounds = game.fight_rounds

    def watched(party, monster, rng, ask):
        bot.monster = monster
        alive = fight_rounds(party, monster, rng, ask)
        if not party.alive:
            deaths.append((party.stage, monster.name))
        return alive

    game.fight_rounds = watched
    try:
        yield
    finally:
        game.fight_rounds = fight_rounds


def play_run(job_key, seed, hoard=False, fork=None):
    """Play one run quietly. Returns (won, (stage, enemy) that ended it or None)."""
    rng = random.Random(seed)
    bot = Bot(job_key, random.Random(-1 - seed), hoard, fork)
    hero = game.Character.create('Bot', game.JOBS[job_key], hero=True)
    bot.party = game.Party([hero])
    deaths = []
    with watch_fights(bot, deaths), redirect_stdout(StringIO()):
        game.choose_skill(hero, rng, bot, count=3)
        won = game.play(bot.party, rng, bot)
    return won, (deaths[0] if deaths else None)


def main():
    parser = argparse.ArgumentParser(description='Play bot runs of Kobold Cave and report '
                                                 'win rates by class.')
    parser.add_argument('--runs', type=int, default=200, help='runs per class (default 200)')
    parser.add_argument('--job', choices=list(game.JOBS), help='only this class')
    parser.add_argument('--hoard', action='store_true',
                        help='keep the hoard after each boss instead of freeing the prisoner')
    parser.add_argument('--fork', choices=['Forge', 'Trader', 'Tunnel'],
                        help='always take this way at forks (default: at random)')
    args = parser.parse_args()
    for job_key in [args.job] if args.job else list(game.JOBS):
        wins, killers = 0, Counter()
        for seed in range(args.runs):
            won, death = play_run(job_key, seed, args.hoard, args.fork)
            wins += won
            if death:
                killers[death[1]] += 1
        top = ', '.join(f'{name} {count}' for name, count in killers.most_common(4))
        print(f'{job_key:8} {wins / args.runs:5.0%}  lost to: {top or "nothing"}')


if __name__ == '__main__':
    main()
