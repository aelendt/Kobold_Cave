"""Kobold Cave: a small text-based RPG."""

import random
from dataclasses import dataclass, field, replace

DEBUG = False  # set to True to see every dice roll

BOSS_CS = 10  # creep score needed to reach the Kobold Leader
REST_HEAL = 0.15  # fraction of max HP recovered after each fight


def debug(message):
    if DEBUG:
        print(message)


def show(scene, **details):
    """Tell a graphical front end what is on screen. The terminal has none,
    so this does nothing and returns False; the browser version replaces it
    to draw the scene and returns True. Details must be plain data."""
    return False


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


# --- Items ----------------------------------------------------------------

@dataclass(frozen=True)
class Item:
    name: str
    kind: str  # which slot it fits: 'sword', 'shield' or 'staff'
    attack: int = 0
    max_health: int = 0
    spell_power: int = 0
    mana: int = 0

    def describe(self):
        bonuses = [(self.attack, 'attack'), (self.max_health, 'max HP'),
                   (self.spell_power, 'spell power'), (self.mana, 'mana')]
        return ', '.join(f'+{amount} {stat}' for amount, stat in bonuses if amount)


ITEMS = {
    'fine_sword': Item('Fine Sword', 'sword', attack=5),
    'firebrand': Item('Firebrand Sword', 'sword', attack=10),
    'mithril_blade': Item('Mithril Blade', 'sword', attack=15),
    'fine_shield': Item('Fine Shield', 'shield', max_health=25),
    'thick_shield': Item('Thick Kite Shield', 'shield', max_health=50),
    'mithril_buckler': Item('Mithril Buckler', 'shield', max_health=75),
    'apprentice_staff': Item('Apprentice Staff', 'staff', spell_power=10),
    'staff_of_insight': Item('Staff of Insight', 'staff', mana=1),
    'ember_staff': Item('Ember Staff', 'staff', spell_power=25),
    'crystal_staff': Item('Crystal Staff', 'staff', spell_power=10, mana=2),
}


# Loot tables per job. Common loot is rolled on a d10 (None means the camp
# is empty); rare loot is rolled on a d20 and tougher kobolds always carry
# something.
WARRIOR_LOOT = {
    'common': ((2, ITEMS['fine_sword']), (2, ITEMS['fine_shield']),
               (1, ITEMS['firebrand']), (1, ITEMS['thick_shield']), (4, None)),
    'rare': ((2, ITEMS['fine_sword']), (3, ITEMS['fine_shield']),
             (8, ITEMS['firebrand']), (5, ITEMS['thick_shield']),
             (1, ITEMS['mithril_blade']), (1, ITEMS['mithril_buckler'])),
}

ROGUE_LOOT = {
    'common': ((4, ITEMS['fine_sword']), (2, ITEMS['firebrand']), (4, None)),
    'rare': ((5, ITEMS['fine_sword']), (13, ITEMS['firebrand']),
             (2, ITEMS['mithril_blade'])),
}

WIZARD_LOOT = {
    'common': ((2, ITEMS['apprentice_staff']), (2, ITEMS['fine_shield']),
               (1, ITEMS['staff_of_insight']), (1, ITEMS['thick_shield']), (4, None)),
    'rare': ((2, ITEMS['apprentice_staff']), (3, ITEMS['fine_shield']),
             (4, ITEMS['ember_staff']), (4, ITEMS['staff_of_insight']),
             (5, ITEMS['thick_shield']), (1, ITEMS['crystal_staff']),
             (1, ITEMS['mithril_buckler'])),
}


# --- Jobs -----------------------------------------------------------------

@dataclass(frozen=True)
class Job:
    name: str
    health: int
    attack: int
    dodge: int
    slots: dict  # slot name -> kind of item it holds
    loot: dict  # 'common' / 'rare' -> loot table
    special: str | None = None  # extra action shown in the combat menu
    special_power: int = 0
    mana: int = 0


JOBS = {
    'warrior': Job('Warrior', health=150, attack=15, dodge=3,
                   slots={'Weapon': 'sword', 'Shield': 'shield'}, loot=WARRIOR_LOOT),
    'rogue': Job('Rogue', health=120, attack=12, dodge=4,
                 slots={'Main hand': 'sword', 'Off hand': 'sword'}, loot=ROGUE_LOOT,
                 special='Flee'),
    'wizard': Job('Wizard', health=110, attack=10, dodge=3,
                  slots={'Staff': 'staff', 'Shield': 'shield'}, loot=WIZARD_LOOT,
                  special='Cast: Fireball', special_power=50, mana=4),
}


@dataclass
class Character:
    name: str
    job: Job
    health: int
    mana: int
    cs: int = 0  # creep score: how many kobolds you have slain
    equipment: dict = field(default_factory=dict)  # slot name -> Item or None

    @classmethod
    def create(cls, name, job):
        return cls(name, job, job.health, job.mana,
                   equipment={slot: None for slot in job.slots})

    def _bonus(self, stat):
        return sum(getattr(item, stat) for item in self.equipment.values() if item)

    @property
    def attack(self):
        return self.job.attack + self._bonus('attack')

    @property
    def max_health(self):
        return self.job.health + self._bonus('max_health')

    @property
    def spell_power(self):
        return self.job.special_power + self._bonus('spell_power')

    @property
    def max_mana(self):
        return self.job.mana + self._bonus('mana')

    @property
    def dodge(self):
        return self.job.dodge

    @property
    def alive(self):
        return self.health > 0


def print_job_stats(job):
    print('------------------------')
    print(f'        Job: {job.name}')
    print(f'     Health: {job.health}')
    print(f'     Attack: {job.attack}')
    print(f'      Dodge: {job.dodge}')
    if job.mana:
        print(f'       Mana: {job.mana}')
    if job.special:
        print(f'Special ATK: {job.special}')
    print(f'       Gear: {" & ".join(job.slots)}')


def job_view(job):
    return {'name': job.name, 'health': job.health, 'attack': job.attack,
            'dodge': job.dodge, 'mana': job.mana, 'special': job.special,
            'gear': list(job.slots)}


def hero_view(character):
    return {'name': character.name, 'job': character.job.name,
            'health': character.health, 'max_health': character.max_health,
            'mana': character.mana, 'max_mana': character.max_mana}


def monster_view(monster):
    return {'name': monster.name, 'health': monster.health,
            'max_health': monster.max_health, 'boss': monster.boss}


def show_party(scene, character, monster=None):
    # A list, so companions can join the hero later.
    details = {'party': [hero_view(character)]}
    if monster:
        details['enemy'] = monster_view(monster)
    show(scene, **details)


def print_status(character, monster):
    print(f'Hero Current HP: {character.health}/{character.max_health}')
    if character.max_mana:
        print(f'           Mana: {character.mana}/{character.max_mana}')
    print(f'       Enemy HP: {monster.health}')


# --- Equipment ------------------------------------------------------------

def choose_slot(character, item, ask=input):
    """Return the slot to put the item in, or None to leave it behind."""
    slots = [slot for slot, kind in character.job.slots.items() if kind == item.kind]
    for slot in slots:
        if character.equipment[slot] is None:
            return slot
    if not slots:
        return None

    for slot in slots:
        current = character.equipment[slot]
        print(f'{slot:>11}: [{current.name}] ({current.describe()})')
    options = {slot.lower(): slot for slot in slots}
    menu = f'[{" / ".join(slots)} / Keep] '
    while True:
        answer = ask(f'Replace which? {menu}').strip().lower()
        if answer == 'keep':
            return None
        if answer in options:
            return options[answer]
        print('Please select a valid option.')


def equip(character, slot, item):
    """Put an item in a slot. Bigger max HP or mana also tops you up by
    the difference; smaller only trims you down to the new max."""
    old_max_health, old_max_mana = character.max_health, character.max_mana
    character.equipment[slot] = item
    character.health = min(character.health + max(0, character.max_health - old_max_health),
                           character.max_health)
    character.mana = min(character.mana + max(0, character.max_mana - old_max_mana),
                         character.max_mana)


def search_camp(character, monster, rng=random, ask=input):
    item = roll_on_table(character.job.loot[monster.loot_tier], rng)
    if item is None:
        print('You search the kobolds camp but find nothing of worth. '
              'You take your frustration out on the kobolds corpse.')
        return
    print(f'You search the kobolds camp and find a [{item.name}] ({item.describe()}).')
    slot = choose_slot(character, item, ask)
    if slot is None:
        print(f'You leave the [{item.name}] behind.')
        return
    equip(character, slot, item)
    print(f'You equip the [{item.name}].')


def rest(character):
    healed = min(round(character.max_health * REST_HEAL),
                 character.max_health - character.health)
    character.health += healed
    message = f'You catch your breath and recover {healed} HP.'
    if character.mana < character.max_mana:
        character.mana = character.max_mana
        message += ' Your magic returns to you.'
    print(message)


# --- Monsters -------------------------------------------------------------

@dataclass
class Monster:
    name: str
    health: int
    attack: int
    loot_tier: str = 'common'
    boss: bool = False
    max_health: int = 0  # filled in from health

    def __post_init__(self):
        self.max_health = self.max_health or self.health


BESTIARY = {
    'kobold_miner': Monster('Kobold Miner', health=35, attack=10),
    'kobold_guard': Monster('Kobold Guardsman', health=55, attack=18),
    'kobold_heavy': Monster('Kobold Heavy', health=90, attack=25, loot_tier='rare'),
    'kobold_leader': Monster('Kobold Leader', health=200, attack=30, boss=True),
}


def spawn(monster_key):
    """Return a fresh copy so damage never leaks into the bestiary."""
    return replace(BESTIARY[monster_key])


# The deeper you go (higher creep score), the nastier the kobolds. The
# Kobold Leader waits at the bottom, see BOSS_CS.
SHALLOW_ENCOUNTERS = ((2, 'kobold_guard'), (8, 'kobold_miner'))
MIDDLE_ENCOUNTERS = ((3, 'kobold_miner'), (5, 'kobold_guard'), (2, 'kobold_heavy'))
DEEP_ENCOUNTERS = ((5, 'kobold_miner'), (10, 'kobold_guard'), (5, 'kobold_heavy'))


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
    character.mana -= 1
    roll = rng.randint(1, 10)
    debug(f'Misfire Roll: {roll}')
    power = character.spell_power
    if roll <= 2:
        character.health -= power // 2
        print('CRITICAL FAIL: Fireball Misfire')
    elif roll <= 4:
        print('Your fireball passes harmlessly over the kobolds head.')
        print(f'You are struck for {monster_hits(character, monster, rng)} damage.')
    else:
        print('Your fireball hits the kobold square in the chest. The enemy is staggered.')
        monster.health -= power


def fight(character, monster, rng=random, ask=input):
    """Returns True if the monster was slain, False if you fled or died."""
    options = ['Attack', 'Defend']
    if character.job.special:
        options.append(character.job.special)
    menu = f'[{" / ".join(options)}] '

    print('')
    print(f'You have encountered a {monster.name}. What will you do?')
    show_party('combat', character, monster)
    while character.alive and monster.health > 0:
        action = ask(menu).strip().lower()
        print('')
        if action == 'attack':
            attack(character, monster, rng)
        elif action == 'defend':
            defend(character, monster, rng)
        elif action == 'flee' and character.job.special == 'Flee':
            if monster.boss:
                print(f'There is no escaping the {monster.name}.')
                continue
            if flee(character, monster, rng):
                show_party('explore', character)
                return False
        elif action == 'cast: fireball' and character.job.special == 'Cast: Fireball':
            if character.mana < 1:
                print('You reach for your magic and find nothing left. You are out of mana.')
                continue
            cast_fireball(character, monster, rng)
        else:
            print('Please select a valid action.')
            continue
        print_status(character, monster)
        show_party('combat', character, monster)
    return character.alive


# --- Game flow ------------------------------------------------------------

def choose_job(ask=input):
    while True:
        choice = ask('Which would you prefer? [Warrior / Rogue / Wizard]: ').strip().lower()
        if choice in JOBS:
            print('Please do take care. You will find no friends in the mines.')
            return JOBS[choice]
        print('Please select a class exactly as it appears idiot.')


def game_over(character):
    show_party('defeat', character)
    print('You have fallen during the encounter. GAME OVER')
    print(f'Kobolds slain: {character.cs}')


def explore(character, rng=random, ask=input):
    """Play until you die or beat the Kobold Leader. Returns True on a win."""
    while character.alive and character.cs < BOSS_CS:
        monster = spawn(roll_on_table(encounter_table(character.cs), rng))
        if fight(character, monster, rng, ask):
            character.cs += 1
            print('Your enemy has fallen. You may move on.')
            print(f'Creep Score: {character.cs}')
            search_camp(character, monster, rng, ask)
            rest(character)
            show_party('explore', character)
            print('-----------------------------------------------------')
    if not character.alive:
        game_over(character)
        return False

    print('')
    print('The tunnel opens into a torch-lit chamber. Atop a throne of stolen junk '
          'sits the Kobold Leader, who does not look happy to see you.')
    if not fight(character, spawn('kobold_leader'), rng, ask):
        game_over(character)
        return False
    show_party('victory', character)
    print('')
    print('The Kobold Leader collapses onto his pile of junk. The mines fall silent.')
    print(f'Well I never. {character.name} the {character.job.name} actually made it out. '
          'I had money on you not making it past the first miner.')
    return True


def main():
    name = input('Hello traveller, you are about to enter the Kobold Mines. '
                 'Before you venture in and probably die would you share your name? ')
    print(f'Well {name}, I can clearly see that you are suicidal. '
          'So to give you a fighting chance of making it through the mines '
          'I will bestow you with your choice of a special talent. '
          'You can be a mighty warrior, a sneaky rogue, or an intelligent wizard.')
    if not show('jobs', jobs=[job_view(job) for job in JOBS.values()]):
        for job in JOBS.values():
            print_job_stats(job)

    character = Character.create(name, choose_job())
    show_party('explore', character)

    print('As you venture into the cavern the light from the entrance fades from view. '
          'In front of you is 3 branching paths.')
    input('[Left / Middle / Right] ')
    explore(character)


if __name__ == '__main__':
    main()
