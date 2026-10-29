"""Kobold Cave: a small text-based RPG."""

import random
from dataclasses import dataclass, replace

DEBUG = False  # set to True to see every dice roll


def debug(message):
    if DEBUG:
        print(message)


def roll_on_table(table, rng=random):
    """Pick an entry from a weighted table of (weight, value) pairs.

    Rolls one die with as many sides as the weights add up to, so
    ((2, 'a'), (8, 'b')) gives 'a' on a 1-2 and 'b' on a 3-10.
    """
    roll = rng.randint(1, sum(weight for weight, _ in table))
    debug(f'Table Roll: {roll}')
    for weight, value in table:
        if roll <= weight:
            return value
        roll -= weight
    raise AssertionError('unreachable: roll exceeded table total')


# --- Jobs -----------------------------------------------------------------

@dataclass(frozen=True)
class Job:
    name: str
    health: int
    attack: int
    dodge: int
    special: str | None = None  # extra action shown in the combat menu
    special_power: int = 0


JOBS = {
    'warrior': Job('Warrior', health=150, attack=15, dodge=3),
    'rogue': Job('Rogue', health=120, attack=12, dodge=4, special='Flee'),
    'wizard': Job('Wizard', health=100, attack=10, dodge=2,
                  special='Cast: Fireball', special_power=50),
}


@dataclass
class Character:
    name: str
    job: Job
    health: int
    attack: int
    dodge: int
    cs: int = 0  # creep score: how many kobolds you have slain

    @classmethod
    def create(cls, name, job):
        return cls(name, job, job.health, job.attack, job.dodge)

    @property
    def alive(self):
        return self.health > 0


def print_job_stats(job):
    print('------------------------')
    print(f'        Job: {job.name}')
    print(f'     Health: {job.health}')
    print(f'     Attack: {job.attack}')
    print(f'      Dodge: {job.dodge}')
    if job.special:
        print(f'Special ATK: {job.special}')


# --- Items and loot -------------------------------------------------------

@dataclass(frozen=True)
class Item:
    name: str
    attack: int = 0
    health: int = 0


ITEMS = {
    'fine_sword': Item('Fine Sword', attack=5),
    'firebrand': Item('Firebrand Sword', attack=10),
    'mithril_blade': Item('Mithril Blade', attack=15),
    'fine_shield': Item('Fine Shield', health=25),
    'thick_shield': Item('Thick Kite Shield', health=50),
    'mithril_buckler': Item('Mithril Buckler', health=75),
}

# Rolled on a d10; None means the camp is empty.
COMMON_LOOT = (
    (2, ITEMS['fine_sword']),
    (2, ITEMS['fine_shield']),
    (1, ITEMS['firebrand']),
    (1, ITEMS['thick_shield']),
    (4, None),
)

# Rolled on a d20; tougher kobolds always carry something.
RARE_LOOT = (
    (2, ITEMS['fine_sword']),
    (3, ITEMS['fine_shield']),
    (8, ITEMS['firebrand']),
    (5, ITEMS['thick_shield']),
    (1, ITEMS['mithril_blade']),
    (1, ITEMS['mithril_buckler']),
)


def search_camp(character, monster, rng=random):
    item = roll_on_table(monster.loot, rng)
    if item is None:
        print('You search the kobolds camp but find nothing of worth. '
              'You take your frustration out on the kobolds corpse.')
        return
    character.attack += item.attack
    character.health += item.health
    print(f'You search the kobolds camp and find a [{item.name}].')


# --- Monsters -------------------------------------------------------------

@dataclass
class Monster:
    name: str
    health: int
    attack: int
    loot: tuple


BESTIARY = {
    'kobold_miner': Monster('Kobold Miner', health=35, attack=10, loot=COMMON_LOOT),
    'kobold_guard': Monster('Kobold Guardsman', health=50, attack=15, loot=COMMON_LOOT),
    'kobold_heavy': Monster('Kobold Heavy', health=75, attack=20, loot=RARE_LOOT),
    'kobold_leader': Monster('Kobold Leader', health=100, attack=25, loot=RARE_LOOT),
}


def spawn(monster_key):
    """Return a fresh copy so damage never leaks into the bestiary."""
    return replace(BESTIARY[monster_key])


# The deeper you go (higher creep score), the nastier the kobolds.
SHALLOW_ENCOUNTERS = ((2, 'kobold_guard'), (8, 'kobold_miner'))
MIDDLE_ENCOUNTERS = ((3, 'kobold_miner'), (5, 'kobold_guard'), (2, 'kobold_heavy'))
DEEP_ENCOUNTERS = ((5, 'kobold_miner'), (10, 'kobold_guard'),
                   (4, 'kobold_heavy'), (1, 'kobold_leader'))


def encounter_table(cs):
    if cs < 3:
        return SHALLOW_ENCOUNTERS
    if cs < 5:
        return MIDDLE_ENCOUNTERS
    return DEEP_ENCOUNTERS


# --- Combat ---------------------------------------------------------------

def monster_hits(character, monster, rng):
    damage = monster.attack + rng.randint(-3, 3)
    character.health -= damage
    return damage


def attack(character, monster, rng):
    dodge_roll = character.dodge + rng.randint(-2, 3)
    damage = character.attack + rng.randint(-2, 2)
    debug(f'Dodge Roll: {dodge_roll}')
    monster.health -= damage
    print(f'You strike the kobold dealing {damage} damage.')
    if dodge_roll < 4:
        print(f'You are struck for {monster_hits(character, monster, rng)} damage.')


def defend(character, monster, rng):
    roll = rng.randint(1, 10)
    debug(f'Defend Roll: {roll}')
    if roll <= 5:
        print("You parry the enemy's blow.")
    elif roll <= 9:
        print('You parry the enemy attack and stagger the enemy. '
              'Taking advantage of the situation you manage a counterattack.')
        damage = round(character.attack / 2 + rng.randint(-3, 0))
        monster.health -= damage
        print(f'You strike the kobold dealing {damage} damage.')
    else:
        print('You fail to defend against the enemy attack')
        print(f'You are struck for {monster_hits(character, monster, rng)} damage.')


def flee(character, monster, rng):
    """Returns True if you got away."""
    if rng.randint(1, 5) >= 4:
        print('You get away from the kobold.')
        return True
    print('You fail to escape the kobold, and receive a blow to the head from his fist.')
    print(f'You are struck for {monster_hits(character, monster, rng)} damage.')
    return False


def cast_fireball(character, monster, rng):
    roll = rng.randint(1, 10)
    debug(f'Misfire Roll: {roll}')
    power = character.job.special_power
    if roll <= 3:
        character.health -= power // 2
        print('CRITICAL FAIL: Fireball Misfire')
    elif roll <= 5:
        print('Your fireball passes harmlessly over the kobolds head.')
        print(f'You are struck for {monster_hits(character, monster, rng)} damage.')
    else:
        print('Your fireball hits the kobold square in the chest. The enemy is staggered.')
        monster.health -= power


def fight(character, monster, rng=random, ask=input):
    options = ['Attack', 'Defend']
    if character.job.special:
        options.append(character.job.special)
    menu = f'[{" / ".join(options)}] '

    print('')
    print(f'You have encountered a {monster.name}. What will you do?')
    while character.alive and monster.health > 0:
        action = ask(menu).strip().lower()
        print('')
        if action == 'attack':
            attack(character, monster, rng)
        elif action == 'defend':
            defend(character, monster, rng)
        elif action == 'flee' and character.job.special == 'Flee':
            if flee(character, monster, rng):
                return
        elif action == 'cast: fireball' and character.job.special == 'Cast: Fireball':
            cast_fireball(character, monster, rng)
        else:
            print('Please select a valid action.')
            continue
        print(f'Hero Current HP: {character.health}')
        print(f'       Enemy HP: {monster.health}')

    if not character.alive:
        return
    character.cs += 1
    print('Your enemy has fallen. You may move on.')
    print(f'Creep Score: {character.cs}')
    search_camp(character, monster, rng)
    print('-----------------------------------------------------')


# --- Game flow ------------------------------------------------------------

def choose_job(ask=input):
    while True:
        choice = ask('Which would you prefer? [Warrior / Rogue / Wizard]: ').strip().lower()
        if choice in JOBS:
            print('Please do take care. You will find no friends in the mines.')
            return JOBS[choice]
        print('Please select a class exactly as it appears idiot.')


def explore(character, rng=random, ask=input):
    while character.alive:
        monster_key = roll_on_table(encounter_table(character.cs), rng)
        fight(character, spawn(monster_key), rng, ask)
    print('You have fallen during the encounter. GAME OVER')


def main():
    name = input('Hello traveller, you are about to enter the Kobold Mines. '
                 'Before you venture in and probably die would you share your name? ')
    print(f'Well {name}, I can clearly see that you are suicidal. '
          'So to give you a fighting chance of making it through the mines '
          'I will bestow you with your choice of a special talent. '
          'You can be a mighty warrior, a sneaky rogue, or an intelligent wizard.')
    for job in JOBS.values():
        print_job_stats(job)

    character = Character.create(name, choose_job())

    print('As you venture into the cavern the light from the entrance fades from view. '
          'In front of you is 3 branching paths.')
    input('[Left / Middle / Right] ')
    explore(character)


if __name__ == '__main__':
    main()
