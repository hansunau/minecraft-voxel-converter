import io, os, gzip, struct, tempfile, unittest, importlib.util, types, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
pkg=types.ModuleType('voxel_blocks'); pkg.__path__=[str(ROOT/'voxel_blocks')]; sys.modules['voxel_blocks']=pkg
for name in ('schem','litematic'):
 spec=importlib.util.spec_from_file_location('voxel_blocks.'+name,ROOT/'voxel_blocks'/f'{name}.py'); mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
from voxel_blocks.schem import write_schem
from voxel_blocks.litematic import write_litematic

def read_nbt(path):
 f=io.BytesIO(gzip.decompress(Path(path).read_bytes()))
 def num(fmt):return struct.unpack(fmt,f.read(struct.calcsize(fmt)))[0]
 def string():return f.read(num('>H')).decode()
 def payload(t):
  if t==2:return num('>H')
  if t==3:return num('>i')
  if t==4:return num('>q')
  if t==7:return f.read(num('>i'))
  if t==8:return string()
  if t==9:
   typ=num('>B');return [payload(typ) for _ in range(num('>i'))]
  if t==10:
   d={}
   while True:
    typ=num('>B')
    if not typ:return d
    key=string();d[key]=payload(typ)
  if t==11:return [num('>i') for _ in range(num('>i'))]
  if t==12:return [num('>Q') for _ in range(num('>i'))]
  raise ValueError(t)
 assert num('>B')==10;string();return payload(10)
class ExportTests(unittest.TestCase):
 def test_formats_and_chunk_offsets(self):
  dims=(11,4,3);offset=(32,128,64);blocks=['minecraft:stone','minecraft:red_concrete','minecraft:gold_block','minecraft:blue_concrete','minecraft:oak_planks']
  cells={(x,y,z):blocks[(x+3*z+y)%len(blocks)] for y in range(4) for z in range(3) for x in range(11) if (x+y+z)%4}
  with tempfile.TemporaryDirectory() as tmp:
   a=os.path.join(tmp,'a.litematic');b=os.path.join(tmp,'b.schem');write_litematic(a,dims,cells,5023,offset);write_schem(b,dims,cells,5023,offset)
   lt=read_nbt(a); self.assertEqual((lt['Version'],lt['SubVersion'],lt['MinecraftDataVersion']),(7,1,5023));reg=lt['Regions']['Voxel'];self.assertEqual([reg['Position'][k] for k in 'xyz'],list(offset));pal=[p['Name'] for p in reg['BlockStatePalette']]; bits=max(2,(len(pal)-1).bit_length());words=reg['BlockStates']
   sp=read_nbt(b)['Schematic'];self.assertEqual((sp['Version'],sp['DataVersion']),(3,5023));self.assertEqual(sp['Offset'],list(offset)); ids=[];v=shift=0
   for byte in sp['Blocks']['Data']:
    v|=(byte&127)<<shift
    if byte&128:shift+=7
    else:ids.append(v);v=shift=0
   inv={i:n for n,i in sp['Blocks']['Palette'].items()}
   for y in range(dims[1]):
    for z in range(dims[2]):
     for x in range(dims[0]):
      i=(y*dims[2]+z)*dims[0]+x;start=i*bits;k,j=divmod(start,64);value=words[k]>>j
      if j+bits>64:value|=words[k+1]<<(64-j)
      expected=cells.get((x,y,z),'minecraft:air');self.assertEqual(pal[value&((1<<bits)-1)],expected);self.assertEqual(inv[ids[i]],expected)
if __name__=='__main__':unittest.main()
