import os

# 1. Patch CSS in dist
css_path = os.path.join('frontend', 'dist', 'assets', 'index-BxUqK_O5.css')
with open(css_path, 'r', encoding='utf-8') as f:
    css_content = f.read()

dark_tile_css = "\n.leaflet-tile{filter:brightness(0.6) invert(1) contrast(3) hue-rotate(200deg) saturate(0.25) brightness(0.75)!important;}\n"
if ".leaflet-tile{filter:brightness" not in css_content:
    css_content += dark_tile_css
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(css_content)
    print("Patched CSS in dist with dark mode tile filter.")

# 2. Patch JS in dist
js_path = os.path.join('frontend', 'dist', 'assets', 'index-BhvAwiix.js')
with open(js_path, 'r', encoding='utf-8') as f:
    js_content = f.read()

old_tile_url = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
new_tile_url = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'

if old_tile_url in js_content:
    js_content = js_content.replace(old_tile_url, new_tile_url)
    print("Replaced Carto tile URL with OpenStreetMap in JS bundle.")

old_attr = 'attribution:\'© <a href="https://carto.com/">CARTO</a>\''
new_attr = 'attribution:\'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>\''
if old_attr in js_content:
    js_content = js_content.replace(old_attr, new_attr)
    print("Updated attribution to OpenStreetMap.")

with open(js_path, 'w', encoding='utf-8') as f:
    f.write(js_content)

print("Finished patching dist bundle for watermarked tile fix.")
