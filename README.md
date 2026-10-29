# Kobold Cave Text-Based RPG

This is my humble attempt at designing a simple game in order to teach myself Python.

Pick a warrior, rogue or wizard and fight down through three stages of the
Kobold Mines: the Upper Mines, the Deep Warrens and the Hoard. Each ends with a
boss: the Kobold Leader, the Kobold Warchief, and finally Cinderjaw the Red,
the dragon the kobolds serve.

Each class carries different gear, finds loot to match, and has its own
moves. Every run you're offered 3 of your class's 5 skills and pick 1, so no
two runs play quite the same. Keeping a boss's hoard teaches a Boon Ability:
a powerful move with a longer cooldown.

Slain kobolds give the party experience. Each level raises your stats (but
heals nothing; that's what bandages are for), and levels 2 and 4 each offer a
choice of 2 new basic skills, so every hero ends a run knowing 3 of their 5.
A full run reaches about level 6.

| Class   | Gear           | Signature  | Skills (start with 1 of 3)                                         | Boon Abilities          |
|---------|----------------|------------|--------------------------------------------------------------------|-------------------------|
| Warrior | Sword & shield | (none)     | Cleave, Shield Bash, Shield Wall, Second Wind, Battle Cry          | Execute, Last Stand     |
| Rogue   | Two swords     | Flee       | Stunning Strike, Poison Blade, Smoke Bomb, Twin Strike, Pickpocket | Backstab, Assassinate   |
| Wizard  | Staff & shield | Mana Surge | Fireball, Mend, Frost Bolt, Arcane Shield, Drain Life              | Meteor, Time Stop       |

**Warrior**
- **Cleave**: 1.5x damage. Every 3 rounds.
- **Shield Bash**: half damage, and stuns. Every 3 rounds.
- **Shield Wall**: guard, and draw every strike to you this round. Every 2 rounds.
- **Second Wind**: recover 25% of your max HP. Once per fight.
- **Battle Cry**: the whole party hits 50% harder this round and next. Every 3 rounds.
- **Execute** (Boon): a blow that adds a third of the damage the enemy has already taken. Every 4 rounds.
- **Last Stand** (Boon): nothing can drop you below 1 HP for two rounds. Once per fight.

**Rogue**
- **Flee** (signature): get the whole party away. Not from bosses.
- **Stunning Strike**: a hit that makes the enemy lose its next turn. Every 3 rounds.
- **Poison Blade**: a hit that poisons the enemy for 3 rounds. Every 4 rounds.
- **Smoke Bomb**: every enemy strike misses this round. Every 3 rounds.
- **Twin Strike**: two quick hits at 0.75x. Every 2 rounds.
- **Pickpocket**: a normal hit that also steals a roll of bandages. Once per fight.
- **Backstab** (Boon): double damage, quadruple against a stunned enemy. Every 4 rounds.
- **Assassinate** (Boon): triple damage against an enemy below 30% health. Every 4 rounds.

**Wizard**
- **Mana Surge** (signature): spend your turn regaining 2 mana. Every 3 rounds.
- **Fireball** (1 mana): heavy damage, but it sometimes misses or misfires.
- **Mend** (1 mana): heal yourself or an ally.
- **Frost Bolt** (1 mana): never misses, and may freeze the enemy in place.
- **Arcane Shield** (1 mana): the party takes half damage this round, and the shield burns the enemy. Every 2 rounds.
- **Drain Life** (1 mana): damage the enemy and heal yourself for half of it.
- **Meteor** (Boon, 2 mana): double spell power, guaranteed. Every 3 rounds.
- **Time Stop** (Boon, 3 mana): the enemy loses its next 2 turns, bosses included. Once per fight.

Stuns make the enemy lose a turn; bosses shake off half of them. Staves add
spell power or mana.

Fights go in rounds: every hero in your party gets orders, then the enemy
strikes back at one of you. Defending sets up a parry or counterattack if
you're the one it targets, and halves attacks that hit the whole party.

The kobolds fight back with abilities of their own, and bosses have two plus a
signature move. Big moves are announced a turn ahead ("Brace yourselves!"):
stun the enemy to interrupt it, throw a Smoke Bomb to waste it, or Defend,
Shield Wall or Arcane Shield to soften it.

| Enemy | Abilities | Signature |
|---|---|---|
| Kobold Miner | Rock Toss (can't be parried) | |
| Kobold Guardsman | Shield Up (takes half damage until its next turn) | |
| Kobold Heavy | Crushing Blow (announced; can't be dodged) | |
| Kobold Shaman | Hex (a hero deals 25% less for 2 rounds) | |
| Kobold Dragonguard | Fire Spear (sets a hero burning) | |
| Kobold Leader | Dirty Trick (a hero loses a turn), Rally (+50% on his next two blows) | Junk Avalanche: below half health, announced, hits everyone |
| Kobold Warchief | War Drums (+30% for 3 rounds), Sweeping Axe (hits two heroes) | Berserk: three attacks a round below 30% health |
| Cinderjaw the Red | Tail Sweep (hits everyone, dodgeable), Wing Buffet (a hero loses a turn) | Fire Breath: announced, every third turn, every other below half health |

After the first two bosses you choose: free the prisoner in the boss's cage
to join your party (one prisoner of a random class, within a level of your
hero, with the skills that level would have taught; up to three heroes), or
leave them and keep the hoard, which powers up your hero and teaches the Boon
Ability you pick. Recruiting never powers you up as well. A fallen companion
stays down; the run ends when the whole party falls.

Swords add attack and shields add max HP. Loot is rolled for the whole party:
a camp only turns up things someone standing can use, and you choose who takes
each find (the list shows what it would replace), or put it in the party bag.
Anything a hero swaps out goes in the bag too, and you can hand bag items out
between fights. The bag holds 6 items; when it overflows, the oldest is left
behind. Loot gets better the deeper you go:
the Upper Mines turn up Fine and Firebrand gear, the Deep Warrens Firebrand and
Mithril, and the Hoard Mithril and Dragonbone. Rogues can carry a parrying
dagger in their off hand instead of a second sword: less attack, more health.

Every hero also has a trinket slot:

| Trinket | Effect |
|---|---|
| Vampire's Fang | Heals you for 15% of the damage you deal |
| Emberward Charm | Halves fire damage (Fire Breath, Fire Spear, burning) |
| Lucky Coin | A 1 in 5 chance any blow against you misses |
| Medic's Satchel | Bandages heal you 50% more |
| Thorned Bracer | Reflects 25% of the damage from blows that hit you |
| Mana Crystal | +2 mana (wizards only) |
| Troll's Blood Vial | Drink it mid-fight to heal 40% of your max HP; then it's gone |

The first two bosses always drop something special, and you choose which hero
claims it: the Leader's Junk Crown (+15% damage to bosses), and from the
Warchief a War Axe, Hand-Axe or Bone-Drum Shield to suit the claimant's class. After every fight you rest, recovering
some health and all of your mana. You start with two bandages for bigger
wounds; kobolds drop more now and then, and bosses always do.

## Playing

Requires Python 3.10 or newer, with no other dependencies.

```bash
python3 kobold_cave.py
```

To see every dice roll, set `DEBUG = True` at the top of `kobold_cave.py`.

### In the browser

`index.html` runs the same `kobold_cave.py` in Chrome using
[Pyodide](https://pyodide.org) (Python compiled to WebAssembly). Menus become
buttons, number keys pick options, and a picture panel shows pixel-art
portraits, health bars and mana for each fight. The sprites live in
`sprites.js` as 16x16 grids of letters, one per pixel, so you can edit them in
any text editor. Serve the folder, then open
http://localhost:8000 in Chrome 137 or newer:

```bash
python3 -m http.server 8000
```

Opening `index.html` straight from disk won't work, because the browser blocks
it from reading `kobold_cave.py`. The page loads Pyodide from the jsDelivr CDN;
to play offline, put a copy of Pyodide (from `npm install pyodide@314.0.7`) in
a `pyodide/` folder next to `index.html`.

## Tests

```bash
python3 -m unittest
```
