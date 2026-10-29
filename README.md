# Kobold Cave Text-Based RPG

This is my humble attempt at designing a simple game in order to teach myself Python.

Pick a warrior, rogue or wizard and fight your way through the Kobold Mines. The
more kobolds you slay, the nastier they get. Slay ten and you reach the Kobold
Leader's chamber, where you win by defeating it.

Each class carries different gear and finds loot to match:

| Class   | Gear            | Special                                         |
|---------|-----------------|-------------------------------------------------|
| Warrior | Sword & shield  | None, just a lot of health                      |
| Rogue   | Two swords      | Flee (not from the Leader)                      |
| Wizard  | Staff & shield  | Fireball, which costs mana; staves add spell power or mana |

Swords add attack and shields add max HP. When you find something for a full
slot, you choose whether to swap it in. After every fight you rest, recovering
some health and all of your mana.

## Playing

Requires Python 3.10 or newer, with no other dependencies.

```bash
python3 kobold_cave.py
```

To see every dice roll, set `DEBUG = True` at the top of `kobold_cave.py`.

## Tests

```bash
python3 -m unittest
```
