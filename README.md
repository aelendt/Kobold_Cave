# Kobold Cave Text-Based RPG

This is my humble attempt at designing a simple game in order to teach myself Python.

Pick a warrior, rogue or wizard and fight down through three stages of the
Kobold Mines: the Upper Mines, the Deep Warrens and the Hoard. Each ends with a
boss: the Kobold Leader, the Kobold Warchief, and finally Cinderjaw the Red,
the dragon the kobolds serve.

Each class carries different gear, finds loot to match, and has its own
specials. Two more skills per class are learned by keeping a boss's hoard:

| Class   | Gear           | Starts with                  | Can learn                        |
|---------|----------------|------------------------------|----------------------------------|
| Warrior | Sword & shield | (a lot of health)            | Cleave, then Shield Wall         |
| Rogue   | Two swords     | Flee                         | Stunning Strike, then Backstab   |
| Wizard  | Staff & shield | Fireball, Mend               | Frost Bolt, then Meteor          |

- **Fireball** (1 mana): heavy damage, but can misfire and burn you.
- **Mend** (1 mana): heal yourself or an ally.
- **Frost Bolt** (1 mana): never misses, and may freeze the enemy out of its next turn.
- **Meteor** (2 mana): double spell power, guaranteed.
- **Cleave**: a swing for 1.5x damage. Every 3 rounds.
- **Shield Wall**: guard, and draw every strike to you this round. Every 3 rounds.
- **Stunning Strike**: a hit that makes the enemy lose its next turn. Every 3 rounds.
- **Backstab**: double damage, quadruple against a stunned enemy. Every 3 rounds.

Bosses shake off half of all stuns. Staves add spell power or mana.

Fights go in rounds: every hero in your party gets orders, then the enemy
strikes back at one of you. Defending sets up a parry or counterattack if
you're the one it targets.

After the first two bosses you choose: free a prisoner from the boss's cage
to join your party (up to three heroes), or leave them and keep the hoard,
which powers up your hero and teaches them their next skill. Recruiting never
powers you up as well. A fallen companion stays down; the run ends when the
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
