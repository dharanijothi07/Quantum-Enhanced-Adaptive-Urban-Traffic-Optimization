import os

file_path = os.path.join('frontend', 'dist', 'assets', 'index-BhvAwiix.js')
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = 'const n=(e==null?void 0:e.map_center)||[12.9716,77.5946]'
replacement = 'const apiKey=(e==null?void 0:e.map_api_key)||"rc_aa67a6ad9f7b854e105e085bfa3c4197e1488db27aaf891fe93ded2ce2accb78",n=(e==null?void 0:e.map_center)||[12.9716,77.5946]'

if target in content:
    content = content.replace(target, replacement, 1)

badge_target = 'children:[k.jsxs("div",{className:"absolute bottom-3 left-3'
badge_replacement = 'children:[k.jsxs("div",{className:"absolute top-3 right-3 z-[1000] bg-slate-900/90 backdrop-blur border border-cyan-500/40 rounded-xl px-3 py-1.5 text-xs text-slate-200 flex items-center gap-2 shadow-2xl",children:[k.jsx("span",{className:"w-2 h-2 rounded-full bg-emerald-400 animate-pulse"}),k.jsx("span",{className:"text-cyan-300 font-semibold",children:"Map API:"}),k.jsx("span",{className:"font-mono text-slate-300",children:apiKey?apiKey.slice(0,10)+"..."+apiKey.slice(-6):"Connected"})]}),k.jsxs("div",{className:"absolute bottom-3 left-3'

if badge_target in content:
    content = content.replace(badge_target, badge_replacement, 1)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated dist bundle with Map API key successfully.')
