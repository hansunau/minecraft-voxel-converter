"""Run: blender --background --factory-startup --python tests/blender_geometry.py"""
import bpy,bmesh,sys,os,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
import voxel_blocks as v
from voxel_blocks.chunked import export_chunks
from test_export import read_nbt
v.register()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);bpy.ops.mesh.primitive_cube_add();source=bpy.context.object
bm=bmesh.new();bm.from_mesh(source.data);bm.faces.ensure_lookup_table();bm.faces.remove(bm.faces[0]);bm.to_mesh(source.data);bm.free();source.data.update()
s=bpy.context.scene.voxel_settings;s.height=40;s.large_height=40;s.mode='SOLID';s.palette_mode='CUSTOM';s.palette='stone';s.data_version=3955
for _ in v.generate(bpy.context,source,s):pass
result=bpy.context.active_object;assert result['voxel_surface_only'];expected={(x,y,z):b for x,y,z,b in json.loads(result['voxel_cells'])};assert len(expected)>7000, 'surface boundary face missing'
bpy.context.view_layer.objects.active=source
with tempfile.TemporaryDirectory() as tmp:
 for label,p in export_chunks(bpy.context,source,s,tmp,'litematic'):pass
 folder=Path(label[4:]);manifest=json.loads((folder/'manifest.json').read_text(encoding='utf8'));assert manifest['algorithm']=='surface_three_axis';actual={}
 for part in manifest['parts']:
  nbt=read_nbt(folder/part['file']);assert nbt['MinecraftDataVersion']==3955;region=nbt['Regions']['Voxel'];palette=[p['Name'] for p in region['BlockStatePalette']];bits=max(2,(len(palette)-1).bit_length());words=region['BlockStates'];w,h,l=part['size'];ox,oy,oz=part['offset']
  for i in range(w*h*l):
   k,j=divmod(i*bits,64);n=words[k]>>j
   if j+bits>64:n|=words[k+1]<<(64-j)
   name=palette[n&((1<<bits)-1)]
   if name!='minecraft:air':
    p=(i%w+ox,i//(w*l)+oy,(i//w)%l+oz);assert p not in actual;actual[p]=name
 assert actual==expected,(len(actual),len(expected)); assert (folder/'preview.json').is_file()
print('PASS: open surface and chunk seams',len(expected))
