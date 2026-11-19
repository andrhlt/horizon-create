#!/usr/bin/env python3
"""Craft Sticker's original Java recipe through the real survival crafting menu."""
import argparse,json
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT,fixture_world
machine=import_module('test-machine-crafting')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['ctl','client','resources']:p.add_argument(key,type=lambda x:Path(x).resolve(strict=True))
    p.add_argument('--pack',type=Path);a=p.parse_args()
    recipe=json.loads((ROOT/'.local/java-reference/src/generated/resources/data/create/recipe/crafting/kinetics/sticker.json').read_text())
    assert recipe['pattern']==['ISI','CRC'] and recipe['result']=={'count':1,'id':'create:sticker'}
    ingredients={'I':'create:andesite_alloy','S':'minecraft:slime_ball','C':'minecraft:cobblestone','R':'minecraft:redstone'}
    with fixture_world(a,'StickerCrafting',render=True,pack=a.pack,env={'HORIZON_NO_AUDIO':'1'}) as w:
        w.commands(['/fill 8 169 22 16 169 28 minecraft:stone','/setblock 12 170 24 minecraft:crafting_table','/tp @s 12.5 170 26.5','/gamemode survival'])
        machine.replay(w,{'recipe':'crafting/kinetics/sticker','width':'3','slots':','.join(ingredients[key] for row in recipe['pattern'] for key in row),'output':'create:sticker','count':'1','remainder':''})
        w.commands(['/setblock 12 170 24 create:sticker[facing=up,extended=true]','/item replace entity @s hotbar.0 with create:wrench','/tp @s 14.5 170 24.5'])
        import_module('test-multiplayer').until('the held wrench',lambda:w.call('inventory')['counts'].get('create:wrench')==1)
        w.call('select','create:wrench');w.call('interact',12,170,24,'east');w.call('wait',3)
        state=w.call('block',12,170,24)['state']
        assert 'facing=north' in state and 'extended=true' in state,state
        before=w.call('inventory')['counts'].get('create:sticker',0)
        import_module('test-wrench').sneak_click(w,(12.5,170.5,24.5))
        import_module('test-multiplayer').until('Sticker pickup',lambda:w.call('block',12,170,24)['state']=='minecraft:air')
        import_module('test-multiplayer').until('picked up Sticker',lambda:w.call('inventory')['counts'].get('create:sticker',0)==before+1)
    print('Original Sticker recipe crafted in survival with exact output and ingredient consumption; actual wrench rotates and sneaking retrieves the extended Sticker. Hidden offscreen client.')
if __name__=='__main__':main()
