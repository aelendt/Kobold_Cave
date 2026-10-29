"""Kobold Cave: a small text-based RPG."""

import random
from dataclasses import dataclass, field, replace

DEBUG = False  # set to True to see every dice roll

REST_HEAL = 0.15  # fraction of max HP recovered after each fight
BANDAGE_HEAL = 0.4  # fraction of max HP a bandage restores
MEND_POWER = 0.6  # Mend heals this fraction of the caster's spell power
START_BANDAGES = 2
MAX_PARTY = 3


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
    dodge: int = 0

    def describe(self):
        bonuses = [(self.attack, 'attack'), (self.max_health, 'max HP'),
                   (self.spell_power, 'spell power'), (self.mana, 'mana'),
                   (self.dodge, 'dodge')]
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

# Power-ups offered after a boss, instead of freeing a prisoner. Keeping the
# hoard also teaches the hero's next skill (Job.lessons).
BOONS = {
    'Warrior': Item("Warlord's Vigour", 'boon', attack=9, max_health=75),
    'Rogue': Item('Shadow Training', 'boon', attack=10, max_health=45),
    'Wizard': Item('Arcane Mastery', 'boon', spell_power=20, mana=1, max_health=45),
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
    spell_power: int = 0
    mana: int = 0
    actions: tuple = ()  # specials known from the start, see ACTIONS
    lessons: tuple = ()  # skills learned, in order, by keeping a boss's hoard


JOBS = {
    'warrior': Job('Warrior', health=150, attack=15, dodge=3,
                   slots={'Weapon': 'sword', 'Shield': 'shield'}, loot=WARRIOR_LOOT,
                   lessons=('Cleave', 'Shield Wall')),
    'rogue': Job('Rogue', health=120, attack=12, dodge=4,
                 slots={'Main hand': 'sword', 'Off hand': 'sword'}, loot=ROGUE_LOOT,
                 actions=('Flee',), lessons=('Stunning Strike', 'Backstab')),
    'wizard': Job('Wizard', health=130, attack=10, dodge=3,
                  slots={'Staff': 'staff', 'Shield': 'shield'}, loot=WIZARD_LOOT,
                  spell_power=60, mana=5, actions=('Fireball', 'Mend'),
                  lessons=('Frost Bolt', 'Meteor')),
}


@dataclass
class Character:
    name: str
    job: Job
    health: int
    mana: int
    hero: bool = False  # the player's own character, narrated as "you"
    equipment: dict = field(default_factory=dict)  # slot name -> Item or None
    boons: list = field(default_factory=list)  # power-ups taken after bosses
    actions: list = field(default_factory=list)  # specials this hero knows
    cooldowns: dict = field(default_factory=dict)  # action name -> rounds left
    defending: bool = False  # chose Defend this round
    shield_wall: bool = False  # drawing every strike this round

    @classmethod
    def create(cls, name, job, hero=False):
        return cls(name, job, job.health, job.mana, hero,
                   equipment={slot: None for slot in job.slots},
                   actions=list(job.actions))

    def _bonus(self, stat):
        gear = [item for item in self.equipment.values() if item] + self.boons
        return sum(getattr(item, stat) for item in gear)

    @property
    def attack(self):
        return self.job.attack + self._bonus('attack')

    @property
    def max_health(self):
        return self.job.health + self._bonus('max_health')

    @property
    def spell_power(self):
        return self.job.spell_power + self._bonus('spell_power')

    @property
    def max_mana(self):
        return self.job.mana + self._bonus('mana')

    @property
    def dodge(self):
        return self.job.dodge + self._bonus('dodge')

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
    if job.actions:
        print(f'Special ATK: {", ".join(job.actions)}')
    print(f'  Can learn: {", ".join(job.lessons)}')
    print(f'       Gear: {" & ".join(job.slots)}')


def job_view(job):
    return {'name': job.name, 'health': job.health, 'attack': job.attack,
            'dodge': job.dodge, 'mana': job.mana,
            'special': ', '.join(job.actions) or None,
            'lessons': list(job.lessons), 'gear': list(job.slots)}


def hero_view(character):
    return {'name': character.name, 'job': character.job.name,
            'health': character.health, 'max_health': character.max_health,
            'mana': character.mana, 'max_mana': character.max_mana,
            'hero': character.hero}


def monster_view(monster):
    return {'name': monster.name, 'health': monster.health,
            'max_health': monster.max_health, 'boss': monster.boss}


def narrate(member, you, them):
    """Print `you` for the player's hero ("You strike...") and `them` for a
    companion ("{name} strikes..."). Both may use {name}."""
    print((you if member.hero else them).format(name=member.name))


@dataclass
class Party:
    members: list
    bandages: int = START_BANDAGES
    cs: int = 0  # creep score: how many kobolds you have slain
    stage: str = ''

    @property
    def living(self):
        return [member for member in self.members if member.alive]

    @property
    def alive(self):
        return bool(self.living)


def show_party(scene, party, monster=None, active=None):
    details = {'party': [hero_view(member) for member in party.members],
               'bandages': party.bandages, 'cs': party.cs, 'stage': party.stage,
               'active': party.members.index(active) if active else None}
    if monster:
        details['enemy'] = monster_view(monster)
    show(scene, **details)


def print_status(party, monster):
    for member in party.living:
        label = 'Hero Current HP' if member.hero else f'{member.name} HP'
        print(f'{label:>15}: {member.health}/{member.max_health}')
        if member.max_mana:
            print(f'{"Mana":>15}: {member.mana}/{member.max_mana}')
    print(f'{"Enemy HP":>15}: {monster.health}')


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


def pick(options, rng):
    """A random choice that doesn't spend a dice roll when there is only one."""
    return options[0] if len(options) == 1 else options[rng.randint(0, len(options) - 1)]


def search_camp(party, monster, rng=random, ask=input):
    # Whoever searches finds gear for their own class.
    finder = pick(party.living, rng)
    item = roll_on_table(finder.job.loot[monster.loot_tier], rng)
    if item is None:
        narrate(finder, 'You search the kobolds camp but find nothing of worth. '
                        'You take your frustration out on the kobolds corpse.',
                '{name} searches the kobolds camp but finds nothing of worth.')
        return
    narrate(finder, f'You search the kobolds camp and find a [{item.name}] ({item.describe()}).',
            f'{{name}} searches the kobolds camp and finds a [{item.name}] ({item.describe()}).')
    slot = choose_slot(finder, item, ask)
    if slot is None:
        print(f'You leave the [{item.name}] behind.')
        return
    equip(finder, slot, item)
    narrate(finder, f'You equip the [{item.name}].', f'{{name}} equips the [{item.name}].')


def find_bandages(party, monster, rng=random):
    found = 2 if monster.boss else int(rng.randint(1, 4) == 1)
    if found:
        party.bandages += found
        print(f'You find {"a roll" if found == 1 else f"{found} rolls"} of bandages. '
              f'Bandages: {party.bandages}')


def heal(member, amount):
    healed = min(amount, member.max_health - member.health)
    member.health += healed
    return healed


def rest(party):
    for member in party.living:
        healed = heal(member, round(member.max_health * REST_HEAL))
        recharged = member.mana < member.max_mana
        member.mana = member.max_mana
        narrate(member, f'You catch your breath and recover {healed} HP.'
                        + (' Your magic returns to you.' if recharged else ''),
                f'{{name}} catches their breath and recovers {healed} HP.'
                + (' Their magic returns.' if recharged else ''))


def offer_bandages(party, ask=input):
    """Between fights, let the player patch up whoever is hurt."""
    while party.bandages:
        hurt = [member for member in party.living if member.health < member.max_health]
        if not hurt:
            return
        # On your own it's a yes/no question; in a party you pick who.
        if len(party.members) == 1:
            options = {'Yes': hurt[0]}
        else:
            options = {member.name: member for member in hurt}
        menu = ' / '.join(list(options) + ['No'])
        answer = ask(f'Use a bandage? ({party.bandages} left) [{menu}] ').strip().lower()
        options = {label.lower(): member for label, member in options.items()}
        if answer == 'no':
            return
        if answer not in options:
            print('Please select a valid option.')
            continue
        member = options[answer]
        party.bandages -= 1
        healed = heal(member, round(member.max_health * BANDAGE_HEAL))
        narrate(member, f'You bind your wounds and recover {healed} HP.',
                f'You bind {{name}}\'s wounds. They recover {healed} HP.')
        show_party('explore', party)


# --- Monsters -------------------------------------------------------------

@dataclass
class Monster:
    name: str
    health: int
    attack: int
    loot_tier: str = 'common'
    boss: bool = False
    attacks: int = 1  # strikes per round
    breath: int = 0  # if set, every third round hits the whole party this hard
    called: str = 'the kobold'  # how the narration refers to it mid-fight
    stunned: bool = False  # loses its next turn
    dazed: bool = False  # lost its last turn to a stun
    max_health: int = 0  # filled in from health

    def __post_init__(self):
        self.max_health = self.max_health or self.health


BESTIARY = {
    'kobold_miner': Monster('Kobold Miner', health=35, attack=10),
    'kobold_guard': Monster('Kobold Guardsman', health=55, attack=18),
    'kobold_heavy': Monster('Kobold Heavy', health=90, attack=25, loot_tier='rare'),
    'kobold_shaman': Monster('Kobold Shaman', health=70, attack=24),
    'kobold_dragonguard': Monster('Kobold Dragonguard', health=120, attack=30, loot_tier='rare'),
    'kobold_leader': Monster('Kobold Leader', health=160, attack=28, boss=True,
                             called='the Leader'),
    'kobold_warchief': Monster('Kobold Warchief', health=360, attack=30, boss=True, attacks=2,
                               called='the Warchief'),
    'red_dragon': Monster('Cinderjaw the Red', health=680, attack=34, boss=True, attacks=2,
                          breath=30, called='Cinderjaw'),
}


def spawn(monster_key):
    """Return a fresh copy so damage never leaks into the bestiary."""
    return replace(BESTIARY[monster_key])


# --- Stages ---------------------------------------------------------------

@dataclass(frozen=True)
class Stage:
    name: str
    fights: int  # kobolds to slay before the boss
    encounters: tuple  # (kills so far below this, table) pairs, checked in order
    boss: str
    arrival: str
    boss_intro: str
    boss_outro: str


SHALLOW_ENCOUNTERS = ((2, 'kobold_guard'), (8, 'kobold_miner'))
MIDDLE_ENCOUNTERS = ((3, 'kobold_miner'), (5, 'kobold_guard'), (2, 'kobold_heavy'))
DEEP_ENCOUNTERS = ((5, 'kobold_miner'), (10, 'kobold_guard'), (5, 'kobold_heavy'))
WARREN_ENCOUNTERS = ((4, 'kobold_guard'), (4, 'kobold_heavy'), (2, 'kobold_shaman'))
LOWER_WARREN_ENCOUNTERS = ((2, 'kobold_guard'), (5, 'kobold_heavy'), (3, 'kobold_shaman'))
HOARD_ENCOUNTERS = ((3, 'kobold_heavy'), (3, 'kobold_shaman'), (4, 'kobold_dragonguard'))

STAGES = (
    Stage('Upper Mines', fights=8,
          encounters=((3, SHALLOW_ENCOUNTERS), (5, MIDDLE_ENCOUNTERS), (99, DEEP_ENCOUNTERS)),
          boss='kobold_leader',
          arrival='',
          boss_intro='The tunnel opens into a torch-lit chamber. Atop a throne of stolen junk '
                     'sits the Kobold Leader, who does not look happy to see you.',
          boss_outro='The Kobold Leader collapses onto his pile of junk.'),
    Stage('Deep Warrens', fights=8,
          encounters=((4, WARREN_ENCOUNTERS), (99, LOWER_WARREN_ENCOUNTERS)),
          boss='kobold_warchief',
          arrival="Behind the Leader's throne a crude ladder drops into the Deep Warrens. "
                  "The air gets warmer. That's never a good sign.",
          boss_intro='War drums. A Kobold Warchief in a horned helm stomps out of the dark, '
                     'dragging an axe bigger than he is.',
          boss_outro='The Warchief topples. Somewhere far below, something enormous rolls '
                     'over in its sleep.'),
    Stage('The Hoard', fights=6,
          encounters=((99, HOARD_ENCOUNTERS),),
          boss='red_dragon',
          arrival='The tunnels open onto a cavern glittering with gold. Kobolds in '
                  "red-lacquered armour guard it like it's their mother. To be fair, it might be.",
          boss_intro='The gold shifts. Then it stands up. Cinderjaw the Red opens one eye, '
                     'then the other, then its mouth.',
          boss_outro='Cinderjaw crashes onto the hoard with a sound like a thousand dropped '
                     'coins. It does not get up.'),
)

# Prisoners found in each boss's lair, offered as recruits.
PRISONERS = {
    'warrior': ('Brann', 'Hilda'),
    'rogue': ('Mira', 'Vex'),
    'wizard': ('Ysolde', 'Old Tobin'),
}
PRISONER_GEAR = {
    'warrior': ('fine_sword', 'thick_shield'),
    'rogue': ('fine_sword', 'firebrand'),
    'wizard': ('apprentice_staff', 'fine_shield'),
}


def encounter_table(stage, kills):
    for below, table in stage.encounters:
        if kills < below:
            return table
    return stage.encounters[-1][1]


# --- Combat ---------------------------------------------------------------
# Each round every living party member acts, then the monster strikes back.
# Every choice in the combat menu is an Action in ACTIONS below.

RETRY = 'retry'  # the action couldn't happen; ask again without using the turn
FLED = 'fled'


def capitalised(text):
    return text[0].upper() + text[1:]


def wound(member, damage, you, them):
    """Take damage, narrate it, and announce it if this blow drops them."""
    was_standing = member.alive
    member.health -= damage
    narrate(member, you, them)
    if was_standing and not member.alive:
        narrate(member, 'You collapse.', '{name} has fallen.')


def hit(member, damage):
    wound(member, damage, f'You are struck for {damage} damage.',
          f'{{name}} is struck for {damage} damage.')


def stun(monster, rng):
    """Ordinary kobolds always lose their next turn; bosses shake off half."""
    if monster.boss and rng.randint(1, 2) == 1:
        print(f'{capitalised(monster.called)} shakes it off.')
        return
    monster.stunned = True
    print(f'{capitalised(monster.called)} is stunned and will lose its next turn.')


def choose_ally(party, ask, question):
    if len(party.living) == 1:
        return party.living[0]
    options = {member.name.lower(): member for member in party.living}
    while True:
        names = ' / '.join(member.name for member in party.living)
        answer = ask(f'{question} [{names}] ').strip().lower()
        if answer in options:
            return options[answer]
        print('Please select a valid option.')


def strike(member, monster, damage, you, them):
    monster.health -= damage
    narrate(member, you.format(target=monster.called, damage=damage),
            them.format(name='{name}', target=monster.called, damage=damage))


def attack(member, party, monster, rng, ask):
    strike(member, monster, member.attack + rng.randint(-2, 2),
           'You strike {target} dealing {damage} damage.',
           '{name} strikes {target} dealing {damage} damage.')


def defend(member, party, monster, rng, ask):
    member.defending = True
    narrate(member, 'You raise your guard.', '{name} raises their guard.')


def flee(member, party, monster, rng, ask):
    """The whole party runs for it."""
    if monster.boss:
        print(f'There is no escaping {monster.called}.')
        return RETRY
    if rng.randint(1, 5) >= 4:
        print(f'You get away from {monster.called}.')
        return FLED
    narrate(member, f'You fail to escape {monster.called}.',
            f'{{name}} looks for a way out, but {monster.called} blocks it.')


def cast_fireball(member, party, monster, rng, ask):
    roll = rng.randint(1, 10)
    debug(f'Misfire Roll: {roll}')
    power = member.spell_power
    if roll <= 2:
        wound(member, power // 2, 'CRITICAL FAIL: Fireball Misfire',
              "CRITICAL FAIL: {name}'s fireball misfires")
    elif roll <= 4:
        print(f"The fireball passes harmlessly over {monster.called}'s head.")
    else:
        print(f'The fireball hits {monster.called} square in the chest. The enemy is staggered.')
        monster.health -= power


def mend(member, party, monster, rng, ask):
    target = choose_ally(party, ask, 'Mend whom?')
    healed = heal(target, round(member.spell_power * MEND_POWER))
    caster = 'You' if member.hero else member.name
    whom = ('yourself' if member.hero else 'themselves') if target is member else \
        ('you' if target.hero else target.name)
    print(f'{caster} {"cast" if member.hero else "casts"} Mend on {whom}, '
          f'restoring {healed} HP.')


def frost_bolt(member, party, monster, rng, ask):
    damage = round(member.spell_power * 0.6)
    monster.health -= damage
    print(f'A shard of ice slams into {monster.called} for {damage} damage.')
    if monster.health > 0 and rng.randint(1, 2) == 1:
        stun(monster, rng)


def meteor(member, party, monster, rng, ask):
    damage = member.spell_power * 2
    monster.health -= damage
    print(f'A meteor tears through the ceiling and lands on {monster.called} '
          f'for {damage} damage.')


def cleave(member, party, monster, rng, ask):
    strike(member, monster, member.attack * 2 + rng.randint(-2, 2),
           'You put your whole weight into it and cleave {target} for {damage} damage.',
           '{name} cleaves {target} for {damage} damage.')


def shield_wall(member, party, monster, rng, ask):
    member.defending = member.shield_wall = True
    narrate(member, 'You plant your shield. Everything comes at you this round.',
            "{name} plants their shield and draws the enemy's attention.")


def stunning_strike(member, party, monster, rng, ask):
    strike(member, monster, member.attack + rng.randint(-2, 2),
           'You crack {target} across the skull for {damage} damage.',
           '{name} cracks {target} across the skull for {damage} damage.')
    if monster.health > 0:
        stun(monster, rng)


def backstab(member, party, monster, rng, ask):
    helpless = monster.stunned or monster.dazed
    damage = member.attack * (4 if helpless else 2) + rng.randint(-2, 2)
    strike(member, monster, damage,
           'You slip behind {target} and stab for {damage} damage.',
           '{name} slips behind {target} and stabs for {damage} damage.')
    if helpless:
        print('It never saw it coming.')


@dataclass(frozen=True)
class Action:
    name: str
    perform: object  # function(member, party, monster, rng, ask)
    description: str
    mana: int = 0
    cooldown: int = 0  # rounds to wait before using it again


ACTIONS = {action.name: action for action in (
    Action('Attack', attack, 'Hit with your weapons.'),
    Action('Defend', defend, 'Parry, and maybe counter, if the enemy comes for you.'),
    Action('Flee', flee, 'Get the whole party away. Not from bosses.'),
    Action('Fireball', cast_fireball, 'Heavy fire damage, but it can misfire.', mana=1),
    Action('Mend', mend, 'Heal yourself or an ally.', mana=1),
    Action('Frost Bolt', frost_bolt, 'Never misses, and may freeze the enemy in place.', mana=1),
    Action('Meteor', meteor, 'Double spell power, guaranteed. Costs 2 mana.', mana=2),
    Action('Cleave', cleave, 'A double-damage swing. Every 3 rounds.', cooldown=3),
    Action('Shield Wall', shield_wall, 'Guard, and draw every strike to you this round. '
                                       'Every 3 rounds.', cooldown=3),
    Action('Stunning Strike', stunning_strike, 'A hit that makes the enemy lose its next turn. '
                                               'Every 3 rounds.', cooldown=3),
    Action('Backstab', backstab, 'Double damage, quadruple against a stunned enemy. '
                                 'Every 3 rounds.', cooldown=3),
)}


def monster_strikes(target, monster, rng):
    damage = monster.attack + rng.randint(-3, 3)
    if target.defending:
        roll = rng.randint(1, 10)
        debug(f'Defend Roll: {roll}')
        if roll <= 5:
            narrate(target, "You parry the enemy's blow.", "{name} parries the enemy's blow.")
        elif roll <= 9:
            counter = round(target.attack / 2 + rng.randint(-3, 0))
            monster.health -= counter
            narrate(target, 'You parry the enemy attack and stagger the enemy. Taking advantage '
                            f'of the situation you manage a counterattack for {counter} damage.',
                    '{name} parries and staggers the enemy, then counterattacks '
                    f'for {counter} damage.')
        else:
            narrate(target, 'You fail to defend against the enemy attack',
                    '{name} fails to defend against the enemy attack')
            hit(target, damage)
        return
    dodge_roll = target.dodge + rng.randint(-2, 3)
    debug(f'Dodge Roll: {dodge_roll}')
    if dodge_roll >= 4:
        attacker = capitalised(monster.called)
        narrate(target, f'{attacker} swings at you and misses.',
                f'{attacker} swings at {{name}} and misses.')
    else:
        hit(target, damage)


def monster_turn(party, monster, round_number, rng):
    monster.dazed = False
    if monster.stunned:
        monster.stunned, monster.dazed = False, True
        print(f'{capitalised(monster.called)} is still reeling and loses its turn.')
    elif monster.breath and round_number % 3 == 0:
        print(f'{monster.name} breathes a roaring torrent of fire!')
        for member in party.living:
            damage = monster.breath + rng.randint(-3, 3)
            wound(member, damage, f'You are scorched for {damage} damage.',
                  f'{{name}} is scorched for {damage} damage.')
    else:
        for _ in range(monster.attacks):
            if party.alive and monster.health > 0:
                walls = [member for member in party.living if member.shield_wall]
                target = walls[0] if walls else pick(party.living, rng)
                monster_strikes(target, monster, rng)
    for member in party.members:
        member.defending = member.shield_wall = False
        member.cooldowns = {name: rounds - 1 for name, rounds in member.cooldowns.items()
                            if rounds > 1}


def take_turn(member, party, monster, rng, ask):
    """Ask one party member for orders. Returns True if the party fled."""
    options = ['Attack', 'Defend'] + member.actions
    by_name = {option.lower(): option for option in options}
    who = f'{member.name}: ' if len(party.living) > 1 else ''
    menu = f'{who}[{" / ".join(options)}] '
    while True:
        answer = ask(menu).strip().lower()
        print('')
        if answer not in by_name:
            print('Please select a valid action.')
            continue
        action = ACTIONS[by_name[answer]]
        waiting = member.cooldowns.get(action.name)
        if waiting:
            rounds = f'{waiting} more round{"s" if waiting > 1 else ""}'
            narrate(member, f'You are not ready to use {action.name} again ({rounds}).',
                    f'{{name}} is not ready to use {action.name} again ({rounds}).')
            continue
        if member.mana < action.mana:
            narrate(member, 'You reach for your magic and find nothing left. You are out of mana.',
                    '{name} is out of mana.')
            continue
        result = action.perform(member, party, monster, rng, ask)
        if result == RETRY:
            continue
        member.mana -= action.mana
        if action.cooldown:
            member.cooldowns[action.name] = action.cooldown
        return result == FLED


def fight(party, monster, rng=random, ask=input):
    """Returns True if the monster was slain, False if the party fled or fell."""
    print('')
    if monster.called.startswith('the '):
        print(f'You have encountered a {monster.name}. What will you do?')
    else:
        print(f'{monster.name} blocks your path. What will you do?')
    for member in party.members:
        member.cooldowns = {}
    round_number = 0
    while party.alive and monster.health > 0:
        round_number += 1
        for member in party.living:
            if monster.health <= 0:
                break
            if not member.alive:  # a misfire can drop someone mid-round
                continue
            show_party('combat', party, monster, active=member)
            if take_turn(member, party, monster, rng, ask):
                show_party('explore', party)
                return False
        if monster.health > 0:
            monster_turn(party, monster, round_number, rng)
        print_status(party, monster)
    show_party('combat', party, monster)
    return party.alive


# --- Game flow ------------------------------------------------------------

def choose_job(ask=input):
    while True:
        choice = ask('Which would you prefer? [Warrior / Rogue / Wizard]: ').strip().lower()
        if choice in JOBS:
            print('Please do take care. You will find no friends in the mines.')
            return JOBS[choice]
        print('Please select a class exactly as it appears idiot.')


def game_over(party):
    show_party('defeat', party)
    print('You have fallen during the encounter. GAME OVER')
    print(f'Kobolds slain: {party.cs}')


def prisoner(job_key, stage_index):
    member = Character.create(PRISONERS[job_key][stage_index], JOBS[job_key])
    for item_key in PRISONER_GEAR[job_key]:
        slot = choose_slot(member, ITEMS[item_key])
        equip(member, slot, ITEMS[item_key])
    return member


def next_lesson(member):
    return next((name for name in member.job.lessons if name not in member.actions), None)


def power_up(member):
    """Keep the hoard: a stat boon, plus the next skill for the hero's class."""
    boon, lesson = BOONS[member.job.name], next_lesson(member)
    old_max_health, old_max_mana = member.max_health, member.max_mana
    member.boons.append(boon)
    member.health += member.max_health - old_max_health
    member.mana += member.max_mana - old_max_mana
    narrate(member, f'You claim the hoard and gain [{boon.name}] ({boon.describe()}).',
            f'{{name}} claims the hoard and gains [{boon.name}] ({boon.describe()}).')
    if lesson:
        member.actions.append(lesson)
        narrate(member, f'You also learn {lesson}: {ACTIONS[lesson].description}',
                f'{{name}} also learns {lesson}: {ACTIONS[lesson].description}')


def boss_reward(party, stage_index, ask=input):
    """After a boss: free a prisoner to join the party, or keep the hoard to
    power up and learn a skill. Recruiting never powers you up as well."""
    leader = party.living[0]
    if len(party.living) >= MAX_PARTY:
        print('Your party is full, so you let the prisoners go. '
              'The hoard is far too heavy to carry with all of you.')
        return
    prisoners = [prisoner(job_key, stage_index) for job_key in JOBS]
    boon, lesson = BOONS[leader.job.name], next_lesson(leader)
    print('In the corner of the lair is a cage of prisoners, all very keen to leave.')
    for member in prisoners:
        print(f'  {member.name} the {member.job.name}')
    learning = f' and learn {lesson}' if lesson else ''
    narrate(leader, f'Or you could leave them and keep the hoard: [{boon.name}] '
                    f'({boon.describe()}){learning}.',
            f'Or {{name}} could keep the hoard: [{boon.name}] ({boon.describe()}){learning}.')
    show('recruit', prisoners=[{**hero_view(member), **job_view(member.job),
                                'name': member.name, 'job': member.job.name}
                               for member in prisoners],
         boon={'name': boon.name, 'describe': boon.describe(), 'for': leader.name,
               'job': leader.job.name, 'lesson': lesson,
               'lesson_describe': ACTIONS[lesson].description if lesson else None})
    options = {member.name.lower(): member for member in prisoners}
    labels = [member.name for member in prisoners] + ['Power up']
    while True:
        answer = ask(f'Free a prisoner or power up? [{" / ".join(labels)}] ').strip().lower()
        if answer == 'power up':
            power_up(leader)
            return
        if answer in options:
            recruit = options[answer]
            party.members = party.living + [recruit]
            print(f'{recruit.name} the {recruit.job.name} joins your party. '
                  'They seem almost grateful. Almost.')
            return
        print('Please select a valid option.')


def clear_stage(party, stage, rng=random, ask=input):
    """Fight through one stage and its boss. Returns True if the party survives."""
    party.stage = stage.name
    if stage.arrival:
        print('')
        print(stage.arrival)
    show_party('explore', party)
    kills = 0
    while party.alive and kills < stage.fights:
        monster = spawn(roll_on_table(encounter_table(stage, kills), rng))
        if fight(party, monster, rng, ask):
            kills += 1
            party.cs += 1
            print('Your enemy has fallen. You may move on.')
            print(f'Creep Score: {party.cs}')
            search_camp(party, monster, rng, ask)
            find_bandages(party, monster, rng)
            rest(party)
            show_party('explore', party)
            offer_bandages(party, ask)
            print('-----------------------------------------------------')
    if not party.alive:
        return False

    print('')
    print(stage.boss_intro)
    boss = spawn(stage.boss)
    if not fight(party, boss, rng, ask):
        return False
    party.cs += 1
    print('')
    print(stage.boss_outro)
    find_bandages(party, boss, rng)
    return True


def play(party, rng=random, ask=input):
    """Play every stage. Returns True if the party slays the dragon."""
    for stage_index, stage in enumerate(STAGES):
        if not clear_stage(party, stage, rng, ask):
            game_over(party)
            return False
        if stage_index < len(STAGES) - 1:
            boss_reward(party, stage_index, ask)
            rest(party)
            show_party('explore', party)
            offer_bandages(party, ask)
            print('-----------------------------------------------------')

    show_party('victory', party)
    names = [member.name for member in party.living]
    survivors = names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]
    print('')
    print(f'Well I never. {survivors} actually made it out, with a dragon\'s hoard no less. '
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

    party = Party([Character.create(name, choose_job(), hero=True)])
    show_party('explore', party)

    print('As you venture into the cavern the light from the entrance fades from view. '
          'In front of you is 3 branching paths.')
    input('[Left / Middle / Right] ')
    play(party)


if __name__ == '__main__':
    main()
