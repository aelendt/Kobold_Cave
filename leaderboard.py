"""The shared leaderboard: leaderboard.json, kept in the repository.

A finished run offers a link that opens a GitHub issue with the run's facts
in it (kobold_cave.submit_link). The Leaderboard workflow runs this script
on every new issue titled "Run: ...". It checks the facts are ones a real
run could have, grades the run again from them (so a grade typed into the
issue counts for nothing), and adds it to leaderboard.json under the GitHub
account that sent it. The reply to post on the issue is printed; the exit
status says whether the run was added.

    ISSUE_BODY=... ISSUE_AUTHOR=... ISSUE_NUMBER=... python3 leaderboard.py

Nothing stops someone writing in facts of their own making, as long as they
hang together. It's a leaderboard for friends, not a bank.
"""

import json
import os
import re
import sys
from datetime import date

import kobold_cave as game

LEADERBOARD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'leaderboard.json')
MAX_NAME = 24
FIGHTS = sum(stage.fights for stage in game.STAGES)
STAGE_NAMES = [stage.name for stage in game.STAGES]
JOB_NAMES = [job.name for job in game.JOBS.values()]
KILLERS = [monster.name for monster in game.BESTIARY.values()]
RECRUITS = [f'{name} the {game.JOBS[key].name}'
            for key, names in game.PRISONERS.items() for name in names]


def extract(body):
    """The run's facts from the ```json block in an issue."""
    found = re.search(r'```json\s*(\{.*?\})\s*```', body or '', re.DOTALL)
    if not found:
        raise ValueError('There is no ```json block with the run in this issue.')
    try:
        run = json.loads(found.group(1))
    except ValueError:
        raise ValueError("The run's ```json block isn't valid JSON.") from None
    if not isinstance(run, dict):
        raise ValueError("The run's ```json block should hold one run.")
    return run


def whole(run, key, low, high):
    value = run.get(key)
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'`{key}` should be a whole number from {low} to {high}.')
    return value


def check(run):
    """Return the run's facts, tidied, if a real run could have them;
    otherwise raise ValueError saying what's wrong."""
    missing = [key for key in game.FACTS if key not in run]
    if missing:
        raise ValueError(f'The run is missing {", ".join(missing)}.')
    name = run['name']
    if not isinstance(name, str):
        raise ValueError('`name` should be text.')
    name = ''.join(ch for ch in name if ch.isprintable()).strip()[:MAX_NAME]
    if not name:
        raise ValueError('`name` is empty.')
    if run['job'] not in JOB_NAMES:
        raise ValueError(f'`job` should be one of {", ".join(JOB_NAMES)}.')
    if type(run['won']) is not bool:
        raise ValueError('`won` should be true or false.')
    won = run['won']
    depth = whole(run, 'depth', 0, len(game.STAGES) - 1)
    if run['stage'] != STAGE_NAMES[depth]:
        raise ValueError('`stage` and `depth` disagree.')
    # A run that fell in a stage slew the bosses before it; a win slew them all.
    bosses = whole(run, 'bosses', 0, len(game.STAGES))
    if bosses != (len(game.STAGES) if won else depth):
        raise ValueError('`bosses` should be 3 for a win, or the number of stages cleared.')
    if won and run['killer']:
        raise ValueError('A won run has no `killer`.')
    if not won and run['killer'] not in KILLERS:
        raise ValueError('`killer` should be the name of a kobold or boss.')
    recruits = run['recruits']
    if not isinstance(recruits, list) or len(recruits) > min(bosses, game.MAX_PARTY - 1) \
            or any(recruit not in RECRUITS for recruit in recruits):
        raise ValueError('`recruits` should list the prisoners who joined, like "Vex the Rogue".')
    hoards = whole(run, 'hoards', 0, min(bosses, len(game.STAGES) - 1))
    if hoards + len(recruits) > min(bosses, len(game.STAGES) - 1):
        raise ValueError('Each boss offers a prisoner or the hoard, not both.')
    slain = whole(run, 'slain', 0, FIGHTS + 20)  # ambushes can add a few
    return {'name': name, 'job': run['job'], 'level': whole(run, 'level', 1, len(game.LEVEL_XP)),
            'recruits': recruits, 'won': won, 'stage': run['stage'], 'depth': depth,
            'killer': run['killer'], 'slain': slain, 'bosses': bosses,
            'ratings': whole(run, 'ratings', 0, 3 * (slain + bosses)),
            'relics': whole(run, 'relics', 0, len(game.TROPHIES)),
            'gold': whole(run, 'gold', 0, 5000), 'hoards': hoards,
            'fled': whole(run, 'fled', 0, 200)}


def load(path=LEADERBOARD_FILE):
    try:
        with open(path) as file:
            return json.load(file)
    except FileNotFoundError:
        return []


def add(run, player, issue, path=LEADERBOARD_FILE, today=None):
    """Grade the run, put it on the leaderboard (best first) and return
    its entry and place."""
    runs = [entry for entry in load(path) if entry.get('issue') != issue]
    grade = game.run_grade(run)
    entry = {**run, 'grade': grade, 'tier': game.tier_of(grade), 'parts': game.grade_parts(run),
             'player': player, 'issue': issue, 'date': (today or date.today()).isoformat()}
    runs.append(entry)
    runs.sort(key=lambda other: (-other['grade'], other['date'], other['issue']))
    with open(path, 'w') as file:
        json.dump(runs, file, indent=1)
        file.write('\n')
    return entry, runs.index(entry) + 1


def reply_for(entry, place):
    lines = [f"Added to the leaderboard: **{entry['grade']}, {entry['tier']}**, "
             f"#{place}.", '', f"{game.run_summary(entry)}.", '']
    lines += [f'- {label}: {points:+}' for label, points in entry['parts']]
    return '\n'.join(lines)


def main():
    try:
        run = check(extract(os.environ.get('ISSUE_BODY', '')))
    except ValueError as problem:
        print(f"This run couldn't be added to the leaderboard: {problem}\n\n"
              'Runs are sent from the game with the Submit button in the Hall of Legends '
              '(or the link printed at the end of a run in the terminal).')
        return 1
    entry, place = add(run, os.environ['ISSUE_AUTHOR'], int(os.environ['ISSUE_NUMBER']),
                       LEADERBOARD_FILE)
    print(reply_for(entry, place))
    return 0


if __name__ == '__main__':
    sys.exit(main())
