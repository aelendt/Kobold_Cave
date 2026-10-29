"""Kobold Cave: a small text-based RPG."""

import random
from dataclasses import dataclass, field, replace

DEBUG = False  # set to True to see every dice roll

REST_HEAL = 0.15  # fraction of max HP recovered after each fight
BANDAGE_HEAL = 0.4  # fraction of max HP a bandage restores
MEND_POWER = 0.5  # Mend heals this fraction of the caster's spell power
START_BANDAGES = 2
MAX_PARTY = 3
LEVEL_XP = (0, 50, 120, 220, 350, 520, 720, 950)  # total XP needed to reach each level
SKILL_LEVELS = (2, 4)  # level-ups that also teach a basic skill (1 of 2 offered)


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

# Stat power-ups for keeping a boss's hoard instead of freeing a prisoner.
# Keeping the hoard also teaches one of the hero's Boon Abilities.
BOONS = {
    'Warrior': Item("Warlord's Vigour", 'boon', attack=16, max_health=130),
    'Rogue': Item('Shadow Training', 'boon', attack=16, max_health=90),
    'Wizard': Item('Arcane Mastery', 'boon', spell_power=30, mana=1, max_health=80),
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
    actions: tuple = ()  # signature moves every hero of this class knows
    skills: tuple = ()  # basic skills; each run starts with 1 of 3 random picks
    boon_abilities: tuple = ()  # powerful skills learned by keeping a boss's hoard
    growth: object = None  # Item of stats gained per level (mana per two levels)


JOBS = {
    'warrior': Job('Warrior', health=150, attack=15, dodge=3,
                   slots={'Weapon': 'sword', 'Shield': 'shield'}, loot=WARRIOR_LOOT,
                   skills=('Cleave', 'Shield Bash', 'Shield Wall', 'Second Wind', 'Battle Cry'),
                   boon_abilities=('Execute', 'Last Stand'),
                   growth=Item('Level', 'growth', attack=3, max_health=25)),
    'rogue': Job('Rogue', health=120, attack=12, dodge=4,
                 slots={'Main hand': 'sword', 'Off hand': 'sword'}, loot=ROGUE_LOOT,
                 actions=('Flee',),
                 skills=('Stunning Strike', 'Poison Blade', 'Smoke Bomb', 'Twin Strike',
                         'Pickpocket'),
                 boon_abilities=('Backstab', 'Assassinate'),
                 growth=Item('Level', 'growth', attack=2, max_health=10)),
    'wizard': Job('Wizard', health=130, attack=10, dodge=3,
                  slots={'Staff': 'staff', 'Shield': 'shield'}, loot=WIZARD_LOOT,
                  spell_power=60, mana=5, actions=('Mana Surge',),
                  skills=('Fireball', 'Mend', 'Frost Bolt', 'Arcane Shield', 'Drain Life'),
                  boon_abilities=('Meteor', 'Time Stop'),
                  growth=Item('Level', 'growth', spell_power=5, max_health=10, mana=1)),
}


@dataclass
class Character:
    name: str
    job: Job
    health: int
    mana: int
    hero: bool = False  # the player's own character, narrated as "you"
    level: int = 1
    xp: int = 0
    equipment: dict = field(default_factory=dict)  # slot name -> Item or None
    boons: list = field(default_factory=list)  # power-ups taken after bosses
    actions: list = field(default_factory=list)  # specials this hero knows
    cooldowns: dict = field(default_factory=dict)  # action name -> rounds left
    used: set = field(default_factory=set)  # once-per-fight actions already used
    defending: bool = False  # chose Defend this round
    shield_wall: bool = False  # drawing every strike this round
    rallied: int = 0  # rounds of Battle Cry left
    last_stand: int = 0  # rounds of Last Stand left
    hexed: int = 0  # rounds of dealing 25% less damage (Shaman's Hex)
    burning: int = 0  # rounds of fire damage left (Fire Spear)
    burn: int = 0  # damage per round while burning
    reeling: int = 0  # turns to lose (Dirty Trick, Wing Buffet)

    @classmethod
    def create(cls, name, job, hero=False):
        return cls(name, job, job.health, job.mana, hero,
                   equipment={slot: None for slot in job.slots},
                   actions=list(job.actions))

    def _bonus(self, stat):
        gear = [item for item in self.equipment.values() if item] + self.boons
        levels = (self.level - 1) // 2 if stat == 'mana' else self.level - 1
        growth = getattr(self.job.growth, stat) * levels if self.job.growth else 0
        return sum(getattr(item, stat) for item in gear) + growth

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
    print(f'     Skills: {", ".join(job.skills)}')
    print(f'      Boons: {", ".join(job.boon_abilities)}')
    print(f'       Gear: {" & ".join(job.slots)}')


def job_view(job):
    return {'name': job.name, 'health': job.health, 'attack': job.attack,
            'dodge': job.dodge, 'mana': job.mana,
            'special': ', '.join(job.actions) or None, 'skills': list(job.skills),
            'boon_abilities': list(job.boon_abilities), 'gear': list(job.slots)}


def hero_view(character):
    return {'name': character.name, 'job': character.job.name,
            'health': character.health, 'max_health': character.max_health,
            'mana': character.mana, 'max_mana': character.max_mana,
            'hero': character.hero, 'level': character.level, 'xp': character.xp,
            'xp_from': LEVEL_XP[character.level - 1],
            'xp_to': LEVEL_XP[character.level] if character.level < len(LEVEL_XP) else None,
            'effects': hero_effects(character)}


def hero_effects(member):
    return [label for label, on in (('Hexed', member.hexed), ('Burning', member.burning),
                                    ('Reeling', member.reeling),
                                    ('Battle Cry', member.rallied),
                                    ('Last Stand', member.last_stand)) if on]


def monster_effects(monster):
    effects = [label for label, on in (('Stunned', monster.stunned),
                                       ('Poisoned', monster.poison_rounds),
                                       ('Shield Up', monster.guarding), ('Rallied', monster.fury),
                                       ('War Drums', monster.enraged),
                                       ('Berserk', monster.berserk)) if on]
    if monster.charging:
        effects.append(f'Winding up: {monster.charging}')
    return effects


def monster_view(monster):
    return {'name': monster.name, 'health': monster.health,
            'max_health': monster.max_health, 'boss': monster.boss,
            'effects': monster_effects(monster)}


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
    smoke: bool = False  # Smoke Bomb: every strike misses this round
    shielded: bool = False  # Arcane Shield: damage is halved this round

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
    breath: int = 0  # Fire Breath damage
    called: str = 'the kobold'  # how the narration refers to it mid-fight
    xp: int = 0  # experience for the party when slain
    abilities: tuple = ()  # basic abilities, see MONSTER_ABILITIES
    signature: str = ''  # a boss's signature ability
    stunned: int = 0  # turns it will lose
    dazed: bool = False  # lost its last turn to a stun
    poison: int = 0  # damage per round from Poison Blade
    poison_rounds: int = 0
    guarding: bool = False  # Shield Up: takes half damage until its next turn
    fury: int = 0  # Rally: strikes left at +50%
    enraged: int = 0  # War Drums: turns left at +30% attack
    berserk: bool = False
    charging: str = ''  # an announced ability it will use on its next turn
    signature_used: bool = False
    breath_timer: int = 0  # turns since Fire Breath
    cooldowns: dict = field(default_factory=dict)  # ability name -> turns left
    max_health: int = 0  # filled in from health

    def __post_init__(self):
        self.max_health = self.max_health or self.health


BESTIARY = {
    'kobold_miner': Monster('Kobold Miner', health=40, attack=13, xp=10,
                            abilities=('Rock Toss',)),
    'kobold_guard': Monster('Kobold Guardsman', health=64, attack=22, xp=15,
                            abilities=('Shield Up',)),
    'kobold_heavy': Monster('Kobold Heavy', health=135, attack=38, xp=25, loot_tier='rare',
                            abilities=('Crushing Blow',)),
    'kobold_shaman': Monster('Kobold Shaman', health=105, attack=37, xp=25,
                             abilities=('Hex',)),
    'kobold_dragonguard': Monster('Kobold Dragonguard', health=181, attack=44, xp=35,
                                  loot_tier='rare', abilities=('Fire Spear',)),
    'kobold_leader': Monster('Kobold Leader', health=284, attack=42, xp=60, boss=True,
                             called='the Leader', abilities=('Dirty Trick', 'Rally'),
                             signature='Junk Avalanche'),
    'kobold_warchief': Monster('Kobold Warchief', health=638, attack=44, xp=100, boss=True,
                               attacks=2, called='the Warchief',
                               abilities=('War Drums', 'Sweeping Axe'), signature='Berserk'),
    'red_dragon': Monster('Cinderjaw the Red', health=1204, attack=51, boss=True, attacks=2,
                          breath=40, called='Cinderjaw',
                          abilities=('Tail Sweep', 'Wing Buffet'), signature='Fire Breath'),
}


def spawn(monster_key):
    """Return a fresh copy so damage never leaks into the bestiary."""
    return replace(BESTIARY[monster_key], cooldowns={})


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
    if member.last_stand and member.health < 1:
        member.health = 1
        narrate(member, 'You refuse to fall.', '{name} refuses to fall.')
    if was_standing and not member.alive:
        narrate(member, 'You collapse.', '{name} has fallen.')


def hit(member, damage):
    wound(member, damage, f'You are struck for {damage} damage.',
          f'{{name}} is struck for {damage} damage.')


def stun(monster, rng, turns=1, resistible=True):
    """Ordinary kobolds always lose their next turn; bosses shake off half."""
    if resistible and monster.boss and rng.randint(1, 2) == 1:
        print(f'{capitalised(monster.called)} shakes it off.')
        return
    monster.stunned = max(monster.stunned, turns)
    lost = 'its next turn' if turns == 1 else f'its next {turns} turns'
    print(f'{capitalised(monster.called)} is stunned and will lose {lost}.')


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


def dealt(member, monster, damage):
    """Damage a hero's blow or spell actually does: 25% less while hexed,
    and half against an enemy behind Shield Up."""
    if member.hexed:
        damage *= 0.75
    if monster.guarding:
        damage *= 0.5
    return round(damage)


def strike(member, monster, damage, you, them):
    """A weapon blow. Battle Cry makes these 50% stronger."""
    if member.rallied:
        damage = round(damage * 1.5)
    damage = dealt(member, monster, damage)
    monster.health -= damage
    narrate(member, you.format(target=monster.called, damage=damage),
            them.format(name='{name}', target=monster.called, damage=damage))


def weapon_roll(member, multiplier, rng):
    return round(member.attack * multiplier) + rng.randint(-2, 2)


# Everyone

def attack(member, party, monster, rng, ask):
    strike(member, monster, weapon_roll(member, 1, rng),
           'You strike {target} dealing {damage} damage.',
           '{name} strikes {target} dealing {damage} damage.')


def defend(member, party, monster, rng, ask):
    member.defending = True
    narrate(member, 'You raise your guard.', '{name} raises their guard.')


# Warrior

def cleave(member, party, monster, rng, ask):
    strike(member, monster, weapon_roll(member, 1.5, rng),
           'You put your whole weight into it and cleave {target} for {damage} damage.',
           '{name} cleaves {target} for {damage} damage.')


def shield_bash(member, party, monster, rng, ask):
    strike(member, monster, weapon_roll(member, 0.5, rng),
           'You slam your shield into {target} for {damage} damage.',
           '{name} slams their shield into {target} for {damage} damage.')
    if monster.health > 0:
        stun(monster, rng)


def shield_wall(member, party, monster, rng, ask):
    member.defending = member.shield_wall = True
    narrate(member, 'You plant your shield. Everything comes at you this round.',
            "{name} plants their shield and draws the enemy's attention.")


def second_wind(member, party, monster, rng, ask):
    healed = heal(member, round(member.max_health * 0.25))
    narrate(member, f'You catch a second wind and recover {healed} HP.',
            f'{{name}} catches a second wind and recovers {healed} HP.')


def battle_cry(member, party, monster, rng, ask):
    for ally in party.living:
        ally.rallied = 2
    narrate(member, 'You let out a battle cry. Your party hits 50% harder this round and next.',
            '{name} lets out a battle cry. The party hits 50% harder this round and next.')


def execute(member, party, monster, rng, ask):
    missing = monster.max_health - monster.health
    strike(member, monster, weapon_roll(member, 1, rng) + missing // 3,
           'You find the weak spot in {target} and execute a brutal blow for {damage} damage.',
           '{name} finds the weak spot in {target} and hits for {damage} damage.')


def last_stand(member, party, monster, rng, ask):
    member.last_stand = 2
    narrate(member, 'You plant your feet. Nothing will drop you for two rounds.',
            '{name} plants their feet. Nothing will drop them for two rounds.')


# Rogue

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


def stunning_strike(member, party, monster, rng, ask):
    strike(member, monster, weapon_roll(member, 1, rng),
           'You crack {target} across the skull for {damage} damage.',
           '{name} cracks {target} across the skull for {damage} damage.')
    if monster.health > 0:
        stun(monster, rng)


def poison_blade(member, party, monster, rng, ask):
    strike(member, monster, weapon_roll(member, 1, rng),
           'You cut {target} with a poisoned blade for {damage} damage.',
           '{name} cuts {target} with a poisoned blade for {damage} damage.')
    monster.poison, monster.poison_rounds = round(member.attack * 0.4), 3


def smoke_bomb(member, party, monster, rng, ask):
    party.smoke = True
    narrate(member, "You hurl a smoke bomb. The enemy can't see a thing this round.",
            "{name} hurls a smoke bomb. The enemy can't see a thing this round.")


def twin_strike(member, party, monster, rng, ask):
    for _ in range(2):
        strike(member, monster, weapon_roll(member, 0.75, rng),
               'You slash {target} for {damage} damage.',
               '{name} slashes {target} for {damage} damage.')


def pickpocket(member, party, monster, rng, ask):
    attack(member, party, monster, rng, ask)
    party.bandages += 1
    narrate(member, f'You lift a roll of bandages off {monster.called}. Bandages: {party.bandages}',
            f'{{name}} lifts a roll of bandages off {monster.called}. Bandages: {party.bandages}')


def backstab(member, party, monster, rng, ask):
    helpless = monster.stunned or monster.dazed
    strike(member, monster, weapon_roll(member, 4 if helpless else 2, rng),
           'You slip behind {target} and stab for {damage} damage.',
           '{name} slips behind {target} and stabs for {damage} damage.')
    if helpless:
        print('It never saw it coming.')


def assassinate(member, party, monster, rng, ask):
    finishing = monster.health <= monster.max_health * 0.3
    strike(member, monster, weapon_roll(member, 3 if finishing else 1, rng),
           'You go for the throat of {target} for {damage} damage.',
           '{name} goes for the throat of {target} for {damage} damage.')
    if finishing:
        print('A killing blow, or near enough.')


# Wizard

def mana_surge(member, party, monster, rng, ask):
    gained = min(2, member.max_mana - member.mana)
    if not gained:
        narrate(member, 'Your mana is already full.', "{name}'s mana is already full.")
        return RETRY
    member.mana += gained
    narrate(member, f'You draw in the magic around you and regain {gained} mana.',
            f'{{name}} draws in the magic around them and regains {gained} mana.')


def cast_fireball(member, party, monster, rng, ask):
    roll = rng.randint(1, 10)
    debug(f'Misfire Roll: {roll}')
    power = member.spell_power
    if roll <= 1:
        wound(member, power // 2, 'CRITICAL FAIL: Fireball Misfire',
              "CRITICAL FAIL: {name}'s fireball misfires")
    elif roll <= 3:
        print(f"The fireball passes harmlessly over {monster.called}'s head.")
    else:
        damage = dealt(member, monster, power)
        print(f'The fireball hits {monster.called} square in the chest for {damage} damage. '
              'The enemy is staggered.')
        monster.health -= damage


def mend(member, party, monster, rng, ask):
    target = choose_ally(party, ask, 'Mend whom?')
    healed = heal(target, round(member.spell_power * MEND_POWER))
    caster = 'You' if member.hero else member.name
    whom = ('yourself' if member.hero else 'themselves') if target is member else \
        ('you' if target.hero else target.name)
    print(f'{caster} {"cast" if member.hero else "casts"} Mend on {whom}, '
          f'restoring {healed} HP.')


def frost_bolt(member, party, monster, rng, ask):
    damage = dealt(member, monster, member.spell_power * 0.45)
    monster.health -= damage
    print(f'A shard of ice slams into {monster.called} for {damage} damage.')
    if monster.health > 0 and rng.randint(1, 3) == 1:
        stun(monster, rng)


def arcane_shield(member, party, monster, rng, ask):
    party.shielded = True
    damage = dealt(member, monster, member.spell_power * 0.6)
    monster.health -= damage
    print('A shimmering shield wraps the party. Damage is halved this round. '
          f'It flares outward and burns {monster.called} for {damage} damage.')


def drain_life(member, party, monster, rng, ask):
    damage = dealt(member, monster, member.spell_power * 0.4)
    monster.health -= damage
    healed = heal(member, damage // 2)
    narrate(member, f'You drain {damage} life from {monster.called} and recover {healed} HP.',
            f'{{name}} drains {damage} life from {monster.called} and recovers {healed} HP.')


def meteor(member, party, monster, rng, ask):
    damage = dealt(member, monster, member.spell_power * 2)
    monster.health -= damage
    print(f'A meteor tears through the ceiling and lands on {monster.called} '
          f'for {damage} damage.')


def time_stop(member, party, monster, rng, ask):
    print(f'Time grinds to a halt around {monster.called}.')
    stun(monster, rng, turns=2, resistible=False)


@dataclass(frozen=True)
class Action:
    name: str
    perform: object  # function(member, party, monster, rng, ask)
    description: str
    mana: int = 0
    cooldown: int = 0  # rounds to wait before using it again
    once: bool = False  # once per fight


ACTIONS = {action.name: action for action in (
    Action('Attack', attack, 'Hit with your weapons.'),
    Action('Defend', defend, 'Parry, and maybe counter, if the enemy comes for you.'),
    # Warrior skills
    Action('Cleave', cleave, 'A swing for 1.5x damage. Every 3 rounds.', cooldown=3),
    Action('Shield Bash', shield_bash, 'Half damage, but stuns the enemy. Every 3 rounds.',
           cooldown=3),
    Action('Shield Wall', shield_wall, 'Guard, and draw every strike to you this round. '
                                       'Every 2 rounds.', cooldown=2),
    Action('Second Wind', second_wind, 'Recover 25% of your max HP. Once per fight.', once=True),
    Action('Battle Cry', battle_cry, 'The whole party hits 50% harder this round and next. '
                                     'Every 3 rounds.', cooldown=3),
    # Warrior Boon Abilities
    Action('Execute', execute, 'A blow that adds a third of the damage the enemy has already '
                               'taken. Every 4 rounds.', cooldown=4),
    Action('Last Stand', last_stand, 'Nothing can drop you below 1 HP for two rounds. '
                                     'Once per fight.', once=True),
    # Rogue
    Action('Flee', flee, 'Get the whole party away. Not from bosses.'),
    Action('Stunning Strike', stunning_strike, 'A hit that makes the enemy lose its next turn. '
                                               'Every 3 rounds.', cooldown=3),
    Action('Poison Blade', poison_blade, 'A hit that poisons the enemy for 3 rounds. '
                                         'Every 4 rounds.', cooldown=4),
    Action('Smoke Bomb', smoke_bomb, 'Every enemy strike misses this round. Every 3 rounds.',
           cooldown=3),
    Action('Twin Strike', twin_strike, 'Two quick hits at 0.75x damage. Every 2 rounds.',
           cooldown=2),
    Action('Pickpocket', pickpocket, 'A normal hit that also steals a roll of bandages. '
                                     'Once per fight.', once=True),
    # Rogue Boon Abilities
    Action('Backstab', backstab, 'Double damage, quadruple against a stunned enemy. '
                                 'Every 4 rounds.', cooldown=4),
    Action('Assassinate', assassinate, 'Triple damage against an enemy below 30% health. '
                                       'Every 4 rounds.', cooldown=4),
    # Wizard
    Action('Mana Surge', mana_surge, 'Spend your turn regaining 2 mana. Every 3 rounds.',
           cooldown=3),
    Action('Fireball', cast_fireball, 'Heavy fire damage, but it sometimes misses or '
                                      'misfires.', mana=1),
    Action('Mend', mend, 'Heal yourself or an ally.', mana=1),
    Action('Frost Bolt', frost_bolt, 'Never misses, and may freeze the enemy in place.', mana=1),
    Action('Arcane Shield', arcane_shield, 'The party takes half damage this round, and the '
                                           'shield burns the enemy. Every 2 rounds.',
           mana=1, cooldown=2),
    Action('Drain Life', drain_life, 'Damage the enemy and heal yourself for half of it.',
           mana=1),
    # Wizard Boon Abilities
    Action('Meteor', meteor, 'Double spell power, guaranteed. Costs 2 mana. Every 3 rounds.',
           mana=2, cooldown=3),
    Action('Time Stop', time_stop, 'The enemy loses its next 2 turns, bosses included. '
                                   'Costs 3 mana. Once per fight.', mana=3, once=True),
)}


def monster_damage(monster, rng, scale=1.0):
    damage = monster.attack * scale
    if monster.enraged:
        damage *= 1.3
    if monster.fury:
        damage *= 1.5
        monster.fury -= 1
    return round(damage) + rng.randint(-3, 3)


def monster_strikes(target, monster, rng, halved=False, scale=1.0, parry=True, dodge=True):
    """One blow at one hero. Returns True if it landed."""
    damage = monster_damage(monster, rng, scale)
    if halved:
        damage //= 2
    if target.defending and parry:
        roll = rng.randint(1, 10)
        debug(f'Defend Roll: {roll}')
        if roll <= 5:
            narrate(target, "You parry the enemy's blow.", "{name} parries the enemy's blow.")
            return False
        if roll <= 9:
            counter = dealt(target, monster, target.attack / 2 + rng.randint(-3, 0))
            monster.health -= counter
            narrate(target, 'You parry the enemy attack and stagger the enemy. Taking advantage '
                            f'of the situation you manage a counterattack for {counter} damage.',
                    '{name} parries and staggers the enemy, then counterattacks '
                    f'for {counter} damage.')
            return False
        narrate(target, 'You fail to defend against the enemy attack',
                '{name} fails to defend against the enemy attack')
        hit(target, damage)
        return True
    if dodge:
        dodge_roll = target.dodge + rng.randint(-2, 3)
        debug(f'Dodge Roll: {dodge_roll}')
        if dodge_roll >= 4:
            attacker = capitalised(monster.called)
            narrate(target, f'{attacker} swings at you and misses.',
                    f'{attacker} swings at {{name}} and misses.')
            return False
    hit(target, damage)
    return True


def target_of(party, rng):
    """Shield Wall draws every blow; otherwise the monster picks at random."""
    walls = [member for member in party.living if member.shield_wall]
    return walls[0] if walls else pick(party.living, rng)


def area_attack(party, monster, base, rng, you, them, dodgeable=False):
    """Hits every hero. Defending or Arcane Shield halves it."""
    for member in party.living:
        if dodgeable and member.dodge + rng.randint(-2, 3) >= 4:
            narrate(member, 'You leap clear.', '{name} leaps clear.')
            continue
        damage = round(base) + rng.randint(-3, 3)
        if party.shielded:
            damage //= 2
        if member.defending:
            damage //= 2
        wound(member, damage, you.format(damage=damage), them.format(name='{name}', damage=damage))


# Kobold abilities

def rock_toss(party, monster, rng):
    target = target_of(party, rng)
    print(f'{capitalised(monster.called)} hurls a rock. It can\'t be parried.')
    monster_strikes(target, monster, rng, party.shielded, scale=0.7, parry=False)


def shield_up(party, monster, rng):
    monster.guarding = True
    print(f'{capitalised(monster.called)} raises its shield. '
          'Your blows will do half damage until its next turn.')


def crushing_blow(party, monster, rng):
    target = target_of(party, rng)
    print(f'{capitalised(monster.called)} brings its maul crashing down. It can\'t be dodged!')
    monster_strikes(target, monster, rng, party.shielded, scale=1.5, dodge=False)


def hex_curse(party, monster, rng):
    target = pick(party.living, rng)
    target.hexed = 3  # counts down at the end of this round, so it covers two of your rounds
    narrate(target, f'{capitalised(monster.called)} hexes you. You deal 25% less damage '
                    'for 2 rounds.',
            f'{capitalised(monster.called)} hexes {{name}}. They deal 25% less damage '
            'for 2 rounds.')


def fire_spear(party, monster, rng):
    target = target_of(party, rng)
    if monster_strikes(target, monster, rng, party.shielded) and target.alive:
        target.burning, target.burn = 2, round(monster.attack * 0.3)
        narrate(target, 'The spear sets you alight.', 'The spear sets {name} alight.')


# Boss abilities

def dirty_trick(party, monster, rng):
    target = pick(party.living, rng)
    if target.dodge + rng.randint(-2, 3) >= 4:
        narrate(target, 'The Leader throws a fistful of sand. You turn away just in time.',
                'The Leader throws a fistful of sand. {name} turns away just in time.')
        return
    target.reeling = 1
    narrate(target, 'The Leader throws sand in your eyes. You will lose your next turn.',
            "The Leader throws sand in {name}'s eyes. They will lose their next turn.")


def rally(party, monster, rng):
    monster.fury = 2
    print(f'{capitalised(monster.called)} bellows for his kin. His next two blows will '
          'hit 50% harder.')


def junk_avalanche(party, monster, rng):
    print('The throne of junk comes crashing down on the party!')
    area_attack(party, monster, monster.attack * 1.2, rng,
                'You are buried under junk for {damage} damage.',
                '{name} is buried under junk for {damage} damage.')


def war_drums(party, monster, rng):
    monster.enraged = 4  # counts down at the end of this turn: three more turns of fury
    print(f'War drums pound. {capitalised(monster.called)} hits 30% harder for 3 rounds.')


def sweeping_axe(party, monster, rng):
    print(f'{capitalised(monster.called)} swings his axe in a wide arc.')
    targets = [target_of(party, rng)]
    others = [member for member in party.living if member is not targets[0]]
    if targets[0].shield_wall:
        targets.append(targets[0])  # the shield wall takes both blows
    elif others:
        targets.append(pick(others, rng))
    for target in targets:
        if target.alive:
            monster_strikes(target, monster, rng, party.shielded)


def tail_sweep(party, monster, rng):
    print('Cinderjaw sweeps its tail across the cavern.')
    area_attack(party, monster, monster.attack * 0.6, rng,
                'The tail catches you for {damage} damage.',
                'The tail catches {name} for {damage} damage.', dodgeable=True)


def wing_buffet(party, monster, rng):
    target = target_of(party, rng)
    print('Cinderjaw beats its wings.')
    if monster_strikes(target, monster, rng, party.shielded, scale=0.5) and target.alive:
        target.reeling = 1
        narrate(target, 'You are knocked flat and will lose your next turn.',
                '{name} is knocked flat and will lose their next turn.')


def fire_breath(party, monster, rng):
    print(f'{monster.name} breathes a roaring torrent of fire!')
    area_attack(party, monster, monster.breath, rng,
                'You are scorched for {damage} damage.',
                '{name} is scorched for {damage} damage.')


@dataclass(frozen=True)
class MonsterAbility:
    name: str
    perform: object  # function(party, monster, rng)
    description: str
    cooldown: int = 3
    warning: str = ''  # if set, announced a turn ahead with this line


MONSTER_ABILITIES = {ability.name: ability for ability in (
    MonsterAbility('Rock Toss', rock_toss, 'A weaker hit that cannot be parried.'),
    MonsterAbility('Shield Up', shield_up, 'Takes half damage until its next turn.'),
    MonsterAbility('Crushing Blow', crushing_blow, 'A heavy hit that cannot be dodged.',
                   warning='{monster} raises its maul high overhead.'),
    MonsterAbility('Hex', hex_curse, 'One hero deals 25% less damage for 2 rounds.'),
    MonsterAbility('Fire Spear', fire_spear, 'A hit that sets a hero burning for 2 rounds.'),
    MonsterAbility('Dirty Trick', dirty_trick, 'Sand in the eyes: a hero loses their next turn.'),
    MonsterAbility('Rally', rally, 'His next two blows hit 50% harder.'),
    MonsterAbility('Junk Avalanche', junk_avalanche, 'Signature: brings his throne down on the '
                                                     'whole party, once, below half health.',
                   warning='The Leader grabs a leg of his throne of junk and starts to heave.'),
    MonsterAbility('War Drums', war_drums, 'Hits 30% harder for 3 rounds.', cooldown=5),
    MonsterAbility('Sweeping Axe', sweeping_axe, 'Strikes two heroes at once.'),
    MonsterAbility('Berserk', None, 'Signature: below 30% health he attacks three times a round.'),
    MonsterAbility('Tail Sweep', tail_sweep, 'A lighter hit on the whole party.'),
    MonsterAbility('Wing Buffet', wing_buffet, 'Knocks a hero flat: they lose their next turn.'),
    MonsterAbility('Fire Breath', fire_breath, 'Signature: fire over the whole party every third '
                                               'turn, every other turn below half health.',
                   warning='Cinderjaw draws in a long, rumbling breath.'),
)}


def wind_up(monster, name):
    """Announce a big move; the monster uses it on its next turn."""
    monster.charging = name
    warning = MONSTER_ABILITIES[name].warning.format(monster=capitalised(monster.called))
    print(f'{warning} Brace yourselves!')


def monster_act(party, monster, rng):
    """Pick and perform the monster's move for this turn."""
    half = monster.health <= monster.max_health * 0.5
    if monster.signature == 'Berserk' and not monster.berserk \
            and monster.health <= monster.max_health * 0.3:
        monster.berserk, monster.attacks = True, 3
        print(f'{capitalised(monster.called)} flies into a berserk rage! '
              'He will attack three times a round.')
    if monster.signature == 'Junk Avalanche' and half and not monster.signature_used:
        monster.signature_used = True
        wind_up(monster, 'Junk Avalanche')
        return
    if monster.signature == 'Fire Breath':
        monster.breath_timer += 1
        if monster.breath_timer >= (2 if half else 3):
            monster.breath_timer = 0
            wind_up(monster, 'Fire Breath')
            return

    monster.cooldowns = {name: turns - 1 for name, turns in monster.cooldowns.items() if turns > 1}
    ready = [name for name in monster.abilities if name not in monster.cooldowns]
    if ready and rng.randint(1, 2 if monster.boss else 3) == 1:
        ability = MONSTER_ABILITIES[pick(ready, rng)]
        monster.cooldowns[ability.name] = ability.cooldown
        if ability.warning:
            wind_up(monster, ability.name)
        else:
            ability.perform(party, monster, rng)
        return

    for _ in range(monster.attacks):
        if party.alive and monster.health > 0:
            monster_strikes(target_of(party, rng), monster, rng, halved=party.shielded)


def end_round(party):
    """Clear this round's effects and count down cooldowns."""
    party.smoke = party.shielded = False
    for member in party.members:
        member.defending = member.shield_wall = False
        member.rallied = max(0, member.rallied - 1)
        member.last_stand = max(0, member.last_stand - 1)
        member.hexed = max(0, member.hexed - 1)
        member.cooldowns = {name: rounds - 1 for name, rounds in member.cooldowns.items()
                            if rounds > 1}


def monster_turn(party, monster, round_number, rng):
    monster.dazed = monster.guarding = False
    if monster.poison_rounds:
        monster.poison_rounds -= 1
        monster.health -= monster.poison
        print(f'Poison burns through {monster.called} for {monster.poison} damage.')
    for member in party.living:
        if member.burning:
            member.burning -= 1
            wound(member, member.burn, f'You burn for {member.burn} damage.',
                  f'{{name}} burns for {member.burn} damage.')
    called = capitalised(monster.called)
    if monster.health <= 0 or not party.alive:
        pass
    elif monster.stunned:
        monster.stunned -= 1
        monster.dazed = True
        if monster.charging:
            print(f'The stun breaks its concentration: no {monster.charging} this time.')
            monster.charging = ''
        print(f'{called} is still reeling and loses its turn.')
    elif party.smoke:
        print(f'{called} lashes out blindly into the smoke and hits nothing.')
        monster.charging = ''
    elif monster.charging:
        name, monster.charging = monster.charging, ''
        MONSTER_ABILITIES[name].perform(party, monster, rng)
    else:
        monster_act(party, monster, rng)
    monster.enraged = max(0, monster.enraged - 1)
    end_round(party)


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
        if action.once and action.name in member.used:
            narrate(member, f'You have already used {action.name} this fight.',
                    f'{{name}} has already used {action.name} this fight.')
            continue
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
        if action.once:
            member.used.add(action.name)
        return result == FLED


def fight(party, monster, rng=random, ask=input):
    """Returns True if the monster was slain, False if the party fled or fell."""
    print('')
    if monster.called.startswith('the '):
        print(f'You have encountered a {monster.name}. What will you do?')
    else:
        print(f'{monster.name} blocks your path. What will you do?')
    for member in party.members:
        member.cooldowns, member.used = {}, set()
        member.rallied = member.last_stand = member.hexed = member.burning = member.reeling = 0
    round_number = 0
    while party.alive and monster.health > 0:
        round_number += 1
        for member in party.living:
            if monster.health <= 0:
                break
            if not member.alive:  # a misfire can drop someone mid-round
                continue
            show_party('combat', party, monster, active=member)
            if member.reeling:
                member.reeling -= 1
                narrate(member, 'You are still reeling and lose your turn.',
                        '{name} is still reeling and loses their turn.')
                continue
            if take_turn(member, party, monster, rng, ask):
                end_round(party)
                show_party('explore', party)
                return False
        if monster.health > 0:
            monster_turn(party, monster, round_number, rng)
        else:
            end_round(party)
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


def offer_skills(member, count, rng):
    """`count` different basic skills this hero doesn't know yet, at random."""
    pool = [name for name in member.job.skills if name not in member.actions]
    return [pool.pop(rng.randint(0, len(pool) - 1)) for _ in range(min(count, len(pool)))]


def choose_skill(member, rng=random, ask=input, count=3):
    options = offer_skills(member, count, rng)
    if not options:
        return
    if member.hero and member.level == 1:
        print('Every adventurer needs a trick or two. Pick one to take into the mines:')
    else:
        narrate(member, 'You can learn a new skill:', '{name} can learn a new skill:')
    for name in options:
        print(f'  {name}: {ACTIONS[name].description}')
    show('skills', job=member.job.name, who=member.name,
         skills=[{'name': name, 'description': ACTIONS[name].description} for name in options])
    by_name = {name.lower(): name for name in options}
    who = '' if member.hero else f'{member.name}: '
    while True:
        answer = ask(f'{who}Which skill? [{" / ".join(options)}] ').strip().lower()
        if answer in by_name:
            member.actions.append(by_name[answer])
            if member.hero and member.level == 1:
                print(f'You will go in knowing {by_name[answer]}. It might even help.')
            else:
                narrate(member, f'You learn {by_name[answer]}.',
                        f'{{name}} learns {by_name[answer]}.')
            return
        print('Please select a valid option.')


def level_up(member, rng=random, ask=input):
    """Stats only: max HP and mana rise, and current HP and mana rise by the
    same amount, but nothing is healed."""
    old_max_health, old_max_mana = member.max_health, member.max_mana
    member.level += 1
    member.health += member.max_health - old_max_health
    member.mana += member.max_mana - old_max_mana
    gains = replace(member.job.growth, mana=member.max_mana - old_max_mana).describe()
    narrate(member, f'You reach level {member.level}! ({gains})',
            f'{{name}} reaches level {member.level}! ({gains})')
    if member.level in SKILL_LEVELS:
        choose_skill(member, rng, ask, count=2)


def award_xp(party, monster, rng=random, ask=input):
    if not monster.xp:
        return
    print(f'The party earns {monster.xp} XP.')
    for member in party.living:
        member.xp += monster.xp
        while member.level < len(LEVEL_XP) and member.xp >= LEVEL_XP[member.level]:
            level_up(member, rng, ask)


def prisoner(job_key, stage_index, level=1, rng=random):
    """A prisoner comes with basic gear, and the skills their level would have
    taught: one to start, plus one for each skill level they've passed."""
    job = JOBS[job_key]
    member = Character.create(PRISONERS[job_key][stage_index], job)
    for item_key in PRISONER_GEAR[job_key]:
        slot = choose_slot(member, ITEMS[item_key])
        equip(member, slot, ITEMS[item_key])
    member.level, member.xp = level, LEVEL_XP[level - 1]
    member.health, member.mana = member.max_health, member.max_mana
    for _ in range(1 + sum(1 for skill_level in SKILL_LEVELS if level >= skill_level)):
        member.actions += offer_skills(member, 1, rng)
    return member


def unlearned_boon_abilities(member):
    return [name for name in member.job.boon_abilities if name not in member.actions]


def power_up(member, ability=None):
    """Keep the hoard: a stat boon, plus a Boon Ability if one is left to learn."""
    boon = BOONS[member.job.name]
    old_max_health, old_max_mana = member.max_health, member.max_mana
    member.boons.append(boon)
    member.health += member.max_health - old_max_health
    member.mana += member.max_mana - old_max_mana
    narrate(member, f'You claim the hoard and gain [{boon.name}] ({boon.describe()}).',
            f'{{name}} claims the hoard and gains [{boon.name}] ({boon.describe()}).')
    if ability:
        member.actions.append(ability)
        narrate(member, f'You learn the Boon Ability {ability}: {ACTIONS[ability].description}',
                f'{{name}} learns the Boon Ability {ability}: {ACTIONS[ability].description}')


def boss_reward(party, stage_index, rng=random, ask=input):
    """After a boss: free a prisoner to join the party, or keep the hoard to
    power up and learn a Boon Ability. Recruiting never powers you up as well."""
    leader = party.living[0]
    if len(party.living) >= MAX_PARTY:
        print('Your party is full, so you let the prisoners go. '
              'The hoard is far too heavy to carry with all of you.')
        return
    # One prisoner, of a random class, within a level of your hero.
    job_key = list(JOBS)[rng.randint(0, len(JOBS) - 1)]
    level = min(max(1, leader.level + rng.randint(-1, 1)), len(LEVEL_XP))
    prisoners = [prisoner(job_key, stage_index, level, rng)]
    boon, abilities = BOONS[leader.job.name], unlearned_boon_abilities(leader)
    caged = prisoners[0]
    known = [name for name in caged.actions if name in caged.job.skills]
    print(f'In the corner of the lair sits a cage. Inside is {caged.name} the {caged.job.name} '
          f'(level {caged.level}), who knows {" and ".join(known)} and is very keen to leave.')
    narrate(leader, f'Or you could leave them and keep the hoard: [{boon.name}] ({boon.describe()})',
            f'Or {{name}} could keep the hoard: [{boon.name}] ({boon.describe()})')
    for ability in abilities:
        print(f'  plus the Boon Ability {ability}: {ACTIONS[ability].description}')
    show('recruit', prisoners=[{**hero_view(member), **job_view(member.job),
                                'name': member.name, 'job': member.job.name,
                                'skills': [name for name in member.actions
                                           if name in member.job.skills]}
                               for member in prisoners],
         boon={'name': boon.name, 'describe': boon.describe(), 'for': leader.name,
               'job': leader.job.name},
         abilities=[{'name': name, 'description': ACTIONS[name].description}
                    for name in abilities])

    recruits = {member.name.lower(): member for member in prisoners}
    hoard = {name.lower(): name for name in abilities} or {'power up': None}
    labels = [member.name for member in prisoners] + (abilities or ['Power up'])
    while True:
        answer = ask(f'Free the prisoner, or keep the hoard? [{" / ".join(labels)}] ')
        answer = answer.strip().lower()
        if answer in hoard:
            power_up(leader, hoard[answer])
            return
        if answer in recruits:
            recruit = recruits[answer]
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
            award_xp(party, monster, rng, ask)
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
    award_xp(party, boss, rng, ask)
    find_bandages(party, boss, rng)
    return True


def play(party, rng=random, ask=input):
    """Play every stage. Returns True if the party slays the dragon."""
    for stage_index, stage in enumerate(STAGES):
        if not clear_stage(party, stage, rng, ask):
            game_over(party)
            return False
        if stage_index < len(STAGES) - 1:
            boss_reward(party, stage_index, rng, ask)
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

    hero = Character.create(name, choose_job(), hero=True)
    choose_skill(hero, count=3)
    party = Party([hero])
    show_party('explore', party)

    print('As you venture into the cavern the light from the entrance fades from view. '
          'In front of you is 3 branching paths.')
    input('[Left / Middle / Right] ')
    play(party)


if __name__ == '__main__':
    main()
