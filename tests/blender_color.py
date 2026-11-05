"""Run with Blender in background to check image pixels and palette matching."""
import bpy,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import voxel_blocks as v
mesh=bpy.data.meshes.new('test');mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)]);mesh.update();uv=mesh.uv_layers.new()
for datum in uv.data:datum.uv=(.5,.5)
mat=bpy.data.materials.new('test');mat.use_nodes=True;nodes=mat.node_tree.nodes;bs=next(n for n in nodes if n.type=='BSDF_PRINCIPLED');tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ROOT/'tests'/'color_sample.png'));mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color']);mesh.materials.append(mat)
rgb=v.material_color(mesh,0,Vector((.25,.25,0)),{});expected=(128/255,64/255,32/255)
assert all(abs(a-b)<.005 for a,b in zip(rgb,expected)),(rgb,expected)
palette=[p for p in v.PALETTE if p[0] in ('red_concrete','blue_concrete','gold_block')];match=v.make_matcher(palette)
assert all(match(color)==name for name,color in palette)
print('PASS: sRGB texture and color match',rgb)
