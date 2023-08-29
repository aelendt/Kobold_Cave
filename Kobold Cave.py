import random

global current_encounter, action

# tuple stat order Health, Attack, Dodge, Special Atk, CS tracker
jobs = ['warrior', 'rogue', 'wizard']
warrior_stats = (150, 15, 3, None, 0)
rogue_stats = (120, 12, 4, 'Flee', 0)
wizard_stats = (100, 10, 2, ('Cast: Fireball', 50), 0)


def print_char_stats(char_type: str):
    char_tuple = None
    health = ''
    attack = ''
    dodge = ''
    special_atk = ''

    if char_type.lower() == 'warrior':
        char_tuple = warrior_stats
    elif char_type.lower() == 'rogue':
        char_tuple = rogue_stats
    elif char_type.lower() == 'wizard':
        char_tuple = wizard_stats
    else:
        print('Incorrect Job Type!')

    health = str(char_tuple[0])
    attack = str(char_tuple[1])
    dodge = str(char_tuple[2])
    special_atk = str(char_tuple[3])

    print('------------------------')
    print('        Job: ' + char_type.capitalize())
    print('     Health: ' + health)
    print('     Attack: ' + attack)
    print('      Dodge: ' + dodge)
    if special_atk is not None:
        print('Special ATK: ' + special_atk)
    elif special_atk is None:
        print('')


# enemy stats
beastiary = {
    'kobold_miner': {
        'pretty_name': 'Kobold Miner',
        'health': 35,
        'attack ': 10},
    'kobold_guard': {
        'pretty_name': 'Kobold Guardsman',
        'health': 50,
        'attack': 15},
    'kobold_heavy': {
        'pretty_name': 'Kobold Heavy',
        'health': 75,
        'attack': 20},
    'kobold_leader': {
        'pretty_name': 'Kobold Leader',
        'health': 100,
        'attack': 25}}

def path_selector():
    print('As you venture into the cavern the light from the entrance fades from view. In front of you is 3 branching paths.')
    input('[Left / Middle / Right] ').lower()
    input('[]')


def encounter_roller(character: dict):
    global current_encounter
    while character['cs'] < 3:
        encounter_roll = random.randint(1, 10)
        print('Encounter Roll: ' + str(encounter_roll))  # encounter checker
        if encounter_roll < 3:
            current_encounter = 'kobold_guard'
            encounter(current_encounter, character)
        elif encounter_roll in range(3, 11):
            current_encounter = 'kobold_miner'
            encounter(current_encounter, character)
    while character['cs'] in range(3, 5):
        encounter_roll = random.randint(1, 10)
        print('Encounter Roll: ' + str(encounter_roll))  # encounter checker
        if encounter_roll < 4:
            current_encounter = 'kobold_miner'
            encounter(current_encounter, character)
        elif encounter_roll in range(4, 9):
            current_encounter = 'kobold_guard'
            encounter(current_encounter, character)
        elif encounter_roll in range(9, 11):
            current_encounter = 'kobold_heavy'
            encounter(current_encounter, character)
    while character['cs'] >= 5:
        encounter_roll = random.randint(1, 20)
        print('Encounter Roll: ' + str(encounter_roll))  # encounter checker
        if encounter_roll < 6:
            current_encounter = 'kobold_miner'
            encounter(current_encounter, character)
        elif encounter_roll in range(6, 16):
            current_encounter = 'kobold_guard'
            encounter(current_encounter, character)
        elif encounter_roll in range(16, 20):
            current_encounter = 'kobold_heavy'
            encounter(current_encounter, character)
        elif encounter_roll == 20:
            current_encounter = 'kobold_leader'
            encounter(current_encounter, character)


def loot_table(character: dict):
    global current_encounter
    while current_encounter == 'kobold_miner':
        item_roll = random.randint(1, 10)
        print('Item Roll: ' + str(item_roll))  # item checker
        if item_roll < 3:
            item('fine_sword', character)
            break
        elif item_roll in range(3, 5):
            item('fine_shield', character)
            break
        elif item_roll == 5:
            item('firebrand', character)
            break
        elif item_roll == 6:
            item('thick_shield', character)
            break
        else:
            print('')
    while current_encounter == 'kobold_guard':
        item_roll = random.randint(1, 10)
        print('Item Roll: ' + str(item_roll))  # item checker
        if item_roll < 3:
            item('fine_sword', character)
            break
        elif item_roll in range(3, 5):
            item('fine_shield', character)
            break
        elif item_roll == 5:
            item('firebrand', character)
            break
        elif item_roll == 6:
            item('thick_shield', character)
            break
        else:
            print('')
    while current_encounter == 'kobold_heavy':
        item_roll = random.randint(1, 20)
        print('Item Roll: ' + str(item_roll))  # item checker
        if item_roll < 3:
            item('fine_sword', character)
            break
        elif item_roll in range(3, 6):
            item('fine_shield', character)
            break
        elif item_roll in range(6, 14):
            item('firebrand', character)
            break
        elif item_roll in range(14, 19):
            item('thick_shield', character)
            break
        elif item_roll == 19:
            item('mithril_blade', character)
            break
        elif item_roll == 20:
            item('mithril_buckler', character)
            break
        else:
            print('')
    while current_encounter == 'kobold_leader':
        item_roll = random.randint(1, 20)
        print('Item Roll: ' + str(item_roll))  # item checker
        if item_roll < 3:
            item('fine_sword', character)
            break
        elif item_roll in range(3, 6):
            item('fine_shield', character)
            break
        elif item_roll in range(6, 14):
            item('firebrand', character)
            break
        elif item_roll in range(14, 19):
            item('thick_shield', character)
            break
        elif item_roll == 19:
            item('mithril_blade', character)
            break
        elif item_roll == 20:
            item('mithril_buckler', character)
            break
        else:
            print('')


def item(item_name, character: dict):
    current_item = item_name
    items = dict(fine_sword={'pretty_name': 'Fine Sword', 'attack': 5},
                 firebrand={'pretty_name': 'Firebrand Sword', 'attack': 10},
                 mithril_blade={'pretty_name': 'Mithril Blade', 'attack': 15},
                 fine_shield={'pretty_name': 'Fine Shield', 'health': 25},
                 thick_shield={'pretty_name': 'Thick Shield', 'health': 50},
                 mithril_buckler={'pretty_name': 'Mithril Buckler', 'health': 75})

    while True:
        if item_name == 'fine_sword':
            character['attack'] = character['attack'] + items[current_item]['attack']
            print('You search the kobolds camp and find a [Fine Sword].')
            break
        elif item_name == 'fine_shield':
            character['health'] = character['health'] + items[current_item]['health']
            print('You search the kobolds camp and find a [Fine Shield].')
            break
        elif item_name == 'firebrand':
            character['attack'] = character['attack'] + items[current_item]['attack']
            print('You search the kobolds camp and find a [Firebrand Sword].')
            break
        elif item_name == 'thick_shield':
            character['health'] = character['health'] + items[current_item]['health']
            print('You search the kobolds camp and find a [Thick Kite Shield].')
            break
        elif item_name == 'mithril_blade':
            character['attack'] = character['attack'] + items[current_item]['attack']
            print('You search the kobolds camp and find a [Mithril Blade].')
            break
        elif item_name == 'mithril_buckler':
            character['health'] = character['health'] + items[current_item]['health']
            print('You search the kobolds camp and find a [Mithril Buckler].')
            break
        else:
            print(
                'You search the kobolds camp but find nothing of worth. You take your frustration out on the kobolds corpse.')
            break
    print('Item Module has Resolved.')


def encounter(monster_name, character: dict):
    global action
    current_encounter = monster_name
    beastiary = dict(kobold_miner={'pretty_name': 'Kobold Miner', 'health': 35, 'attack': 10},
                     kobold_guard={'pretty_name': 'Kobold Guardsman', 'health': 50, 'attack': 15},
                     kobold_heavy={'pretty_name': 'Kobold Heavy', 'health': 75, 'attack': 20},
                     kobold_leader={'pretty_name': 'Kobold Leader', 'health': 100, 'attack': 25})

    # combat module
    while character['health'] > 0:
        if (beastiary['kobold_miner']) == True:
            if beastiary['kobold_miner']['Health'] > 0:
                player_dodge_chance = character['dodge'] + random.randint(-2, 3)
                monster_damage_roll = random.randint(-3, 3)
                print('')
                print('You have encountered a ' + str(beastiary[current_encounter]['pretty_name']) + '. What will you do?')
                if character['job'] == 'warrior':
                    action = input('[Attack / Defend] ').lower()
                elif character['job'] == 'rogue':
                    action = input('[Attack / Defend / Flee] ').lower()
                elif character['job'] == 'wizard':
                    action = input('[Attack / Defend / Cast: Fireball] ').lower()
                print('')
                if action == 'attack':
                    player_damage_roll = random.randint(-2, 2)
                    print('Damage Roll: ' + str(player_damage_roll))
                    if player_dodge_chance < 4:
                        character['health'] = character['health'] - (
                                beastiary[current_encounter]['attack'] + monster_damage_roll)
                        (beastiary[current_encounter]['health']) = (beastiary[current_encounter]['health']) - (int(character['attack']) + player_damage_roll)
                        print('You strike the kobold dealing ' + str(character['attack'] + player_damage_roll) + ' damage.')
                        print('You are struck for ' + str(beastiary[current_encounter]['attack'] + monster_damage_roll) + ' damage.')
                        print('Hero Current HP: ' + str(character['health']))
                        print('       Enemy HP: ' + str(beastiary[current_encounter]['health']))
                        continue
                    elif player_dodge_chance >= 4:
                        (beastiary[current_encounter]['health']) = (beastiary[current_encounter]['health']) - (character['attack'] + player_damage_roll)
                        print('You strike the kobold dealing ' + str(character['attack'] + player_damage_roll) + ' damage.')
                        print('Hero Current HP: ' + str(character['health']))
                        print('       Enemy HP: ' + str(beastiary[current_encounter]['health']))
                        continue
                elif action == 'defend':
                    defend_roll = random.randint(1, 10)
                    counter_atk_roll = random.randint(-3, 0)
                    print('Defend Roll: ' + str(defend_roll))
                    if defend_roll in range(1, 6):
                        print("You parry the enemy's blow.")
                        print('Hero Current HP: ' + str(character['health']))
                        print('       Enemy HP: ' + str(beastiary[current_encounter]['health']))
                        continue
                    elif defend_roll in range(6, 10):
                        print('You parry the enemy attack and stagger the enemy. Taking advantage of the situation you manage a counterattack.')
                        final_dmg_roll = round(((int(character['attack'])/2) + counter_atk_roll))
                        print('Final DMG Roll: ' + str(final_dmg_roll))
                        (beastiary[current_encounter]['health']) = (beastiary[current_encounter]['health']) - final_dmg_roll
                        print('You strike the kobold dealing ' + str(final_dmg_roll) + ' damage.')
                        print('Hero Current HP: ' + str(character['health']))
                        print('       Enemy HP: ' + str(beastiary[current_encounter]['health']))
                        continue
                    elif defend_roll == 10:
                        print('You fail to defend against the enemy attack')
                        character['health'] = character['health'] - (beastiary[current_encounter]['attack'] + monster_damage_roll)
                        print('Hero Current HP: ' + str(character['health']))
                        print('       Enemy HP: ' + str(beastiary[current_encounter]['health']))
                        continue
                elif action == 'flee':
                    flee_chance = random.randint(1, 5)
                    if flee_chance >= 4:
                        print('You get away from the kobold.')
                        break
                    elif flee_chance < 4:
                        print('You fail to escape the kobold, and receive a blow to the head from his fist.')
                        character['health'] = character['health'] - (
                                beastiary[current_encounter]['attack'] + monster_damage_roll)
                        print('Hero Current HP: ' + str(character['health']))
                        print('       Enemy HP: ' + str(beastiary[current_encounter]['health']))
                        continue
                elif action == 'cast: fireball':
                    misfire_chance = random.randint(1, 10)
                    print('misfire_chance:' + str(misfire_chance))
                    if misfire_chance <= 3:
                        character['health'] = character['health'] - (character['special_atk'][1] / 2)
                        print('CRITICAL FAIL: Fireball Misfire')
                        print('Hero Current HP: ' + str(character['health']))
                        print('       Enemy HP: ' + str(beastiary[current_encounter]['health']))
                    elif misfire_chance in range(4, 6):
                        print('Your fireball passes harmlessly over the kobolds head.')
                        character['health'] = character['health'] - (
                                beastiary[current_encounter]['attack'] + monster_damage_roll)
                        print('You are struck dealing ' + str(
                            beastiary[current_encounter]['attack'] + monster_damage_roll) + ' damage.')
                        print('Hero Current HP: ' + str(character['health']))
                        print('       Enemy HP: ' + str(beastiary[current_encounter]['health']))
                    elif misfire_chance > 5:
                        print('Your fireball hits the kobold square in the chest. The enemy is staggered.')
                        (beastiary[current_encounter]['health']) = (beastiary[current_encounter]['health']) - \
                                                                character['special_atk'][1]
                        print('Hero Current HP: ' + str(character['health']))
                        print('       Enemy HP: ' + str(beastiary[current_encounter]['health']))
                    continue
                else:
                    print('Please select a valid action.')
                    continue
            elif int(beastiary['kobold_miner']['health']) <= 0:
                character['cs'] = character['cs'] + 1
                print('Your enemy has fallen. You may move on.')
                print('Creep Score: ' + str(character['cs']))
                loot_table(character)
                print('-----------------------------------------------------')
                break
        elif (beastiary['kobold_guard']) == True:
        elif (beastiary['kobold_heavy']) == True:
        elif (beastiary['kobold_leader']) == True:
    while character['health'] <= 0:
        print('You have fallen during the encounter. GAME OVER')

    print('Combat Module Resolved')  # module checker


def start():
    character = {'name': input(
        'Hello traveller, you are about to enter the Kobold Mines. Before you venture in and probably die would you share your name? ')}
    print('Well ' + character['name']
          + ', I can clearly see that you are suicidal. '
            'So to give you a fighting chance of making it through the mines I will bestow you with your choice of a special talent. '
            'You can be a mighty warrior, a sneaky rogue, or an intelligent wizard.')

    print_char_stats('warrior')
    print_char_stats('rogue')
    print_char_stats('wizard')

    # class selection
    while True:
        character['job'] = input('Which would you prefer? [Warrior / Rogue / Wizard]: ').lower()
        if character['job'] in jobs:
            print('Please do take care. You will find no friends in the mines.')
            break
        else:
            print('Please select a class exactly as it appears idiot.')
            continue

    # setting character stats
    char_tuple = None
    if character['job'] == 'warrior':
        char_tuple = warrior_stats
    elif character['job'] == 'rogue':
        char_tuple = rogue_stats
    elif character['job'] == 'wizard':
        char_tuple = wizard_stats
    else:
        print('Invalid Job Type.')
        quit(-1)

    character['health'] = char_tuple[0]
    character['attack'] = char_tuple[1]
    character['dodge'] = char_tuple[2]
    character['special_atk'] = char_tuple[3]
    character['cs'] = char_tuple[4]

    # continuing into the cave
    print('As you venture into the cavern the light from the entrance fades from view. In front of you is 3 branching paths.')
    input('[Left / Middle / Right] ').lower()

    # 1st encounter setup
    while True:
        if character['health'] > 0:
            encounter_roller(character)
            continue
        elif character['health'] <= 0:
            break


start()

print('this is the end of the program.')
