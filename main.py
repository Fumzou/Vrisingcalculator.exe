import re
import os
import subprocess
import PySimpleGUI as sg

# ---------------- Parsing Helpers -----------------

def parse_structures(path):
    stations = {}
    lines = open(path, encoding='utf-8').read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('# ') and not line.startswith('##'):
            name = line[2:].strip()
            # skip global title if present
            if name.lower().startswith('structures'):
                i += 1
                continue
            speed = 0
            floor = ''
            floor_bonus = 0
            j = i + 1
            while j < len(lines) and not lines[j].startswith('# '):
                if lines[j].startswith('## Perks') and j + 1 < len(lines):
                    perk_line = lines[j + 1]
                    m = re.search(r'Confined Castle Room: \+(\d+)%', perk_line)
                    if m:
                        speed = int(m.group(1))
                    m = re.search(r'Has Matching Floor\(([^)]+)\).*?(\d+)%', perk_line)
                    if m:
                        floor = m.group(1).strip()
                        floor_bonus = int(m.group(2))
                    break
                j += 1
            stations[name] = {
                'speed_bonus': speed,
                'floor': floor,
                'floor_bonus': floor_bonus,
            }
        i += 1
    return stations

def parse_floors(path):
    floors = {}
    lines = open(path, encoding='utf-8').read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('# '):
            name = line[2:].strip()
            stations = []
            j = i + 1
            while j < len(lines) and not lines[j].startswith('# '):
                if lines[j].startswith('- '):
                    stations = [s.strip() for s in lines[j].split('-') if s.strip()]
                    break
                j += 1
            floors[name] = stations
        i += 1
    return floors

def parse_time(tstr):
    tstr = tstr.split('(')[0]
    total = 0
    for part in re.findall(r'(\d+\s*[ms])', tstr):
        if 'm' in part:
            total += int(re.findall(r'\d+', part)[0]) * 60
        else:
            total += int(re.findall(r'\d+', part)[0])
    return total

def parse_materials(mstr):
    materials = {}
    for qty, name in re.findall(r'(\d+)\s*(?:\([^)]*\))?\s*([A-Za-z][A-Za-z \-]+)', mstr):
        materials[name.strip()] = materials.get(name.strip(), 0) + int(qty)
    return materials

def parse_items(path):
    lines = open(path, encoding='utf-8').read().splitlines()
    raw_categories = []
    components = {}
    consumables = {}
    in_raw = False
    in_components = False
    in_consumables = False
    for idx, line in enumerate(lines):
        if line.startswith('## Reagents & Resources'):
            in_raw = True
            continue
        if line.startswith('## Recipe Tables'):
            in_raw = False
        if in_raw and line.startswith('### '):
            name = line[4:].split('[')[0].strip()
            raw_categories.append(name)
        if line.startswith('## Item Recipes'):
            in_components = True
            continue
        if line.startswith('## Raw Resources'):
            in_components = False
        if line.startswith('## Consumable Recipes'):
            in_consumables = True
            continue
        if line.startswith('### Throwable'):
            in_consumables = False
        if in_components and line.startswith('|') and not line.startswith('| -'):
            parts = [p.strip() for p in line.strip('|').split('|')]
            if len(parts) >= 4:
                item, time, station, mats = parts[:4]
                components[item] = {
                    'time': parse_time(time),
                    'station': station.split()[0],
                    'materials': parse_materials(mats),
                }
        if in_consumables and line.startswith('|') and not line.startswith('| -'):
            parts = [p.strip() for p in line.strip('|').split('|')]
            if len(parts) >= 4:
                name, time, station, mats = parts[1:5]
                category = 'Other'
                if 'Brew' in name:
                    category = 'Brews'
                elif 'Potion' in name:
                    category = 'Potions'
                elif 'Elixir' in name:
                    category = 'Elixirs'
                elif 'Coating' in name:
                    category = 'Coatings'
                consumables.setdefault(category, {})[name] = {
                    'time': parse_time(time),
                    'station': station.split()[0] if station else '',
                    'materials': parse_materials(mats),
                }
    return raw_categories, components, consumables

# -------------------- UI & Logic -------------------

def build_ui(stations, floors, raw, components, consumables):
    station_checks = [[sg.Checkbox(s, key=f'station_{s}', tooltip=f"Speed {v['speed_bonus']}% - Floor {v['floor']}")]
                       for s, v in stations.items()]
    floor_checks = [[sg.Checkbox(f, key=f'floor_{f}')] for f in floors]

    raw_checks = [[sg.Checkbox(cat, key=f'raw_{cat}')] for cat in raw]
    comp_checks = [[sg.Checkbox(item, key=f'comp_{item}')] for item in components]

    consumable_frames = []
    for cat, items in consumables.items():
        checks = [[sg.Checkbox(name, key=f'cons_{name}')] for name in items]
        consumable_frames.append(sg.Frame(cat, checks, vertical_alignment='top'))

    layout = [
        [sg.Column(station_checks, scrollable=True, vertical_scroll_only=True, size=(250,300)),
         sg.Column(floor_checks, scrollable=True, vertical_scroll_only=True, size=(250,300)),
         sg.TabGroup([
             [sg.Tab('Raw Resources', raw_checks)],
             [sg.Tab('Components', comp_checks)],
             [sg.Tab('Consumables', consumable_frames)],
         ])],
        [sg.Checkbox('Confined Castle Room', key='confined')],
        [sg.Multiline(size=(80,15), key='summary', disabled=True)],
        [sg.Button('Export .exe'), sg.Button('Exit')]
    ]
    return sg.Window('V Rising Calculator', layout, finalize=True)

def calculate(values, stations, floors, components, consumables):
    selected_stations = [s for s in stations if values.get(f'station_{s}')]
    selected_floors = [f for f in floors if values.get(f'floor_{f}')]

    speed_bonus = 0
    cost_bonus = 0
    for s in selected_stations:
        if values.get('confined'):
            speed_bonus += stations[s]['speed_bonus']
        if stations[s]['floor'] in selected_floors:
            cost_bonus += stations[s]['floor_bonus']

    materials = {}
    total_time = 0

    for item, info in components.items():
        if values.get(f'comp_{item}'):
            time = info['time']
            mats = info['materials'].copy()
            station = info['station']
            if station in selected_stations and values.get('confined'):
                time = time * 100 / (100 + stations[station]['speed_bonus'])
            if stations.get(station) and stations[station]['floor'] in selected_floors:
                factor = (100 - stations[station]['floor_bonus'])/100
                mats = {k: int(v*factor) for k,v in mats.items()}
            total_time += time
            for k,v in mats.items():
                materials[k] = materials.get(k,0)+v

    for cat, items in consumables.items():
        for name, info in items.items():
            if values.get(f'cons_{name}'):
                time = info['time']
                mats = info['materials'].copy()
                station = info['station']
                if station in selected_stations and values.get('confined'):
                    time = time * 100 / (100 + stations[station]['speed_bonus'])
                if stations.get(station) and stations[station]['floor'] in selected_floors:
                    factor = (100 - stations[station]['floor_bonus'])/100
                    mats = {k: int(v*factor) for k,v in mats.items()}
                total_time += time
                for k,v in mats.items():
                    materials[k] = materials.get(k,0)+v

    summary = f"Speed Bonus: {speed_bonus}%\nCost Reduction: {cost_bonus}%\nTotal Craft Time: {int(total_time)}s\nResources:\n"
    for k,v in materials.items():
        summary += f"- {v} {k}\n"
    return summary


def main():
    stations = parse_structures('Structures.md')
    floors = parse_floors('Castle_Floors.md')
    raw, components, consumables = parse_items('Item.md')

    window = build_ui(stations, floors, raw, components, consumables)

    while True:
        event, values = window.read(timeout=500)
        if event in (sg.WIN_CLOSED, 'Exit'):
            break
        if event == 'Export .exe':
            subprocess.call(['pyinstaller', '--onefile', 'main.py'])
        summary = calculate(values, stations, floors, components, consumables)
        window['summary'].update(summary)

    window.close()

if __name__ == '__main__':
    main()
