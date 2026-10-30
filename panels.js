// The two side panels: the party (one tab per hero, with stats, gear and
// skills) on the left, and the enemy, the journey and supplies on the right.
// Both redraw from the same details kobold_cave.py sends to show().
import { SPRITES, PALETTE } from './sprites.js';

const partyPanel = document.getElementById('party-panel');
const infoPanel = document.getElementById('info-panel');
let selected = null;  // name of the hero whose tab is open
let latest = null;  // the last party details, so a tab click can redraw
let openSlot = null;  // the slot whose Equip list is showing, as "hero|slot"
let equipHandler = () => {};

// index.html supplies what an Equip choice does (answer the game with it).
export function onEquip(handler) {
  equipHandler = handler;
}

function element(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function sprite(name) {
  const rows = SPRITES[name] || [];
  const canvas = document.createElement('canvas');
  canvas.width = rows[0]?.length || 16;
  canvas.height = rows.length || 16;
  canvas.className = 'sprite';
  const ctx = canvas.getContext('2d');
  rows.forEach((row, y) => [...row].forEach((ch, x) => {
    if (ch === '.') return;
    ctx.fillStyle = PALETTE[ch];
    ctx.fillRect(x, y, 1, 1);
  }));
  return canvas;
}

function section(title, ...children) {
  const box = element('section', 'panel-section');
  box.append(element('h2', '', title), ...children);
  return box;
}

function definitions(rows) {
  const list = element('dl', 'stats');
  rows.forEach(([label, value]) => list.append(element('dt', '', label), element('dd', '', value)));
  return list;
}

function memberView(member) {
  const view = element('div', 'member');

  const head = element('div', 'member-head');
  const portrait = element('div', 'portrait small');
  portrait.append(sprite(member.job.toLowerCase()));
  const title = element('div');
  title.append(element('div', 'who', member.name),
               element('div', 'what', `Level ${member.level} ${member.job}`));
  head.append(portrait, title);
  view.append(head);
  if (member.health <= 0) view.append(element('p', 'fallen-note', 'Fallen. They stay down.'));

  const xp = member.xp_to ? `${member.xp} / ${member.xp_to}` : `${member.xp} (max level)`;
  const rows = [['Health', `${Math.max(0, member.health)} / ${member.max_health}`]];
  if (member.max_mana) rows.push(['Mana', `${member.mana} / ${member.max_mana}`]);
  rows.push(['Attack', member.attack], ['Dodge', member.dodge]);
  if (member.max_mana) rows.push(['Spell power', member.spell_power]);
  rows.push(['XP', xp]);
  view.append(section('Stats', definitions(rows)));
  if (member.effects.length) {
    const chips = element('div', 'effects');
    member.effects.forEach(effect => chips.append(element('span', 'chip', effect)));
    view.lastChild.append(chips);
  }

  const gear = element('ul', 'gear');
  member.gear.forEach(({ slot, name, describe, candidates, forged, forge_limit, forge_gains }) => {
    const row = element('li');
    const key = `${member.name}|${slot}`;
    const top = element('div', 'gear-top');
    top.append(name ? element('span', 'item', name) : element('span', 'empty', 'empty'));
    if (candidates.length && member.health > 0) {
      const button = element('button', 'equip', openSlot === key ? 'Close' : `Equip (${candidates.length})`);
      button.type = 'button';
      button.setAttribute('aria-expanded', String(openSlot === key));
      if (latest.in_fight) {
        button.disabled = true;
        button.title = 'No changing gear in the middle of a fight';
      }
      button.addEventListener('click', () => {
        openSlot = openSlot === key ? null : key;
        drawPartyPanel();
      });
      top.append(button);
    }
    row.append(element('span', 'slot', slot), top);
    if (describe) row.append(element('span', 'what', describe));
    if (forged) {
      row.append(element('span', 'what forged', `Reforged ${forged} of ${forge_limit}: ${forge_gains}`));
    }
    if (openSlot === key && !latest.in_fight) {
      const options = element('div', 'equip-options');
      candidates.forEach(item => {
        const pick = element('button', 'equip-option');
        pick.type = 'button';
        pick.append(element('span', 'item', item.name), element('span', 'what', item.describe));
        pick.addEventListener('click', () => {
          openSlot = null;
          equipHandler(member.name, slot, item.index);
        });
        options.append(pick);
      });
      row.append(options);
    }
    gear.append(row);
  });
  view.append(section('Gear', gear));

  const skills = element('ul', 'skills');
  const allSkills = [
    { name: 'Attack', kind: 'basic', description: 'Hit with your weapons.' },
    { name: 'Defend', kind: 'basic', description: 'Parry, and maybe counter, if the enemy comes for you.' },
    ...member.skills,
  ];
  allSkills.forEach(skill => {
    const row = element('li', `skill ${skill.kind}`);
    const top = element('div', 'skill-top');
    top.append(element('span', 'skill-name', skill.name));
    const tags = [];
    if (skill.kind === 'signature') tags.push('Signature');
    if (skill.kind === 'boon') tags.push('Boon');
    if (skill.mana) tags.push(`${skill.mana} mana`);
    tags.forEach(tag => top.append(element('span', 'tag', tag)));
    const state = skill.used ? 'Used this fight'
      : skill.waiting ? `${skill.waiting} round${skill.waiting > 1 ? 's' : ''}` : '';
    if (state) top.append(element('span', 'tag waiting', state));
    row.append(top, element('div', 'what', skill.description));
    skills.append(row);
  });
  view.append(section('Skills', skills));

  if (member.boons.length) view.append(section('Hoard boons', element('p', 'what', member.boons.join(', '))));
  return view;
}

export function drawPartyPanel(details) {
  if (details?.party) latest = details;
  if (!latest) return;
  const { party, active } = latest;
  if (!party.some(member => member.name === selected)) selected = party[0].name;

  const tabs = element('div', 'tabs');
  tabs.setAttribute('role', 'tablist');
  party.forEach((member, i) => {
    const tab = element('button', 'tab', member.name);
    tab.type = 'button';
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-selected', String(member.name === selected));
    if (i === active) tab.classList.add('acting');
    if (member.health <= 0) tab.classList.add('down');
    tab.addEventListener('click', () => { selected = member.name; drawPartyPanel(); });
    tabs.append(tab);
  });
  const member = party.find(m => m.name === selected);
  partyPanel.replaceChildren(element('h2', 'panel-title', 'Party'), tabs, memberView(member));
}

export function drawInfoPanel(details) {
  if (!details?.stages) return;
  const blocks = [element('h2', 'panel-title', 'Field notes')];

  const { enemy } = details;
  if (enemy) {
    const abilities = element('ul', 'skills');
    enemy.abilities.forEach(ability => {
      const row = element('li', `skill ${ability.signature ? 'boon' : 'skill'}`);
      const top = element('div', 'skill-top');
      top.append(element('span', 'skill-name', ability.name));
      if (ability.signature) top.append(element('span', 'tag', 'Signature'));
      if (enemy.effects.some(effect => effect === `Winding up: ${ability.name}`)) {
        top.append(element('span', 'tag warning', 'Next turn!'));
      }
      row.append(top, element('div', 'what', ability.description));
      abilities.append(row);
    });
    const facts = definitions([['Health', `${Math.max(0, enemy.health)} / ${enemy.max_health}`],
                               ['Attack', enemy.attack]]);
    blocks.push(section(enemy.name, facts, abilities));
  } else {
    blocks.push(section('Enemy', element('p', 'what', 'Nothing in sight. Yet.')));
  }

  const journey = element('ol', 'journey');
  details.stages.forEach((stage, i) => {
    const row = element('li', i < details.depth ? 'done' : i === details.depth ? 'here' : 'ahead');
    row.append(element('span', 'skill-name', stage.name));
    const note = i < details.depth ? `${stage.boss} slain`
      : i === details.depth ? `${Math.min(details.kills, stage.fights)} of ${stage.fights} kobolds, then ${stage.boss}`
      : stage.boss;
    row.append(element('span', 'what', note));
    if (i === details.depth) {
      const track = element('div', 'bar stat');
      const fill = element('i');
      fill.style.width = `${Math.min(100, (details.kills / stage.fights) * 100)}%`;
      track.append(fill);
      row.append(track);
    }
    journey.append(row);
  });
  blocks.push(section('Journey', journey, element('p', 'what', `Kobolds slain: ${details.cs}`)));

  const bag = element('ul', 'gear');
  if (details.bag.length) {
    details.bag.forEach(item => {
      const row = element('li');
      row.append(element('span', 'item', item.name), element('span', 'what', item.describe));
      bag.append(row);
    });
  } else {
    bag.append(element('li', 'empty', 'The bag is empty.'));
  }
  blocks.push(section('Supplies', definitions([['Gold', details.gold], ['Scrap', details.scrap],
                                               ['Bandages', details.bandages],
                                               ['Bag', `${details.bag.length} / ${details.bag_size}`]]), bag));
  infoPanel.replaceChildren(...blocks);
}

export function clearPanels() {
  selected = latest = openSlot = null;
  partyPanel.replaceChildren(element('h2', 'panel-title', 'Party'),
                             element('p', 'what', 'Your hero appears here once you choose a class.'));
  infoPanel.replaceChildren(element('h2', 'panel-title', 'Field notes'),
                            element('p', 'what', 'Notes on the mines and whatever lives in them.'));
}
