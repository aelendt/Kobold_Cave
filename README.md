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
you're the one it targets.

After the first two bosses you choose: free a prisoner from the boss's cage
to join your party (up to three heroes, each knowing one random skill), or
leave them and keep the hoard, which powers up your hero and teaches the Boon
Ability you pick. Recruiting never powers you up as well. A fallen companion stays down; the run ends when the
whole party falls.

Swords add attack and shields add max HP. When you find something for a full
slot, you choose whether to swap it in. After every fight you rest, recovering
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
