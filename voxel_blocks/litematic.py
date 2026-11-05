"""Litematica v7 writer, based on the public Litematica 26.3 format implementation."""
import gzip
import os
import struct
import time
from .schem import named


def write_litematic(path, dims, cells, data_version, position=(0,0,0)):
    w, h, length = map(int, dims)
    if min(w, h, length) < 1 or w*h*length > 2_147_483_647:
        raise ValueError('잘못된 영역 크기입니다')
    if not 1 <= data_version <= 2_147_483_647:
        raise ValueError('Minecraft 데이터 버전이 올바르지 않습니다')
    if any(not (0 <= x < w and 0 <= y < h and 0 <= z < length) for x, y, z in cells):
        raise ValueError('영역 밖에 블록이 있습니다')
    # Index zero must be air for Litematica's palette reader.
    palette = ['minecraft:air'] + sorted(set(cells.values()) - {'minecraft:air'})
    indexes = {name: i for i, name in enumerate(palette)}
    bits = max(2, (len(palette) - 1).bit_length())
    count = w*h*length
    words = [0] * ((count * bits + 63) // 64)
    mask = (1 << 64) - 1
    for (x, y, z), name in cells.items():
        value = indexes[name]
        offset = ((y*length + z)*w + x)*bits
        idx, shift = divmod(offset, 64)
        words[idx] |= (value << shift) & mask
        if shift + bits > 64:
            words[idx+1] |= value >> (64-shift)
    def integer(n): return struct.pack('>i', n)
    def long(n): return struct.pack('>q', n)
    def string(s):
        b=s.encode('utf-8')
        if len(b)>65535: raise ValueError('문자열이 너무 깁니다')
        return struct.pack('>H',len(b))+b
    def compound(name, body): return named(10,name,body+b'\0')
    def pos(name, xyz): return compound(name,b''.join(named(3,k,integer(v)) for k,v in zip(('x','y','z'),xyz)))
    def list_compound(name, payloads): return named(9,name,bytes([10])+integer(len(payloads))+b''.join(p+b'\0' for p in payloads))
    def state(name):
        # Current converter emits whole vanilla blocks without block properties.
        if '[' in name or not name.startswith('minecraft:'):
            raise ValueError('일반 바닐라 블록만 저장할 수 있습니다: '+name)
        return named(8,'Name',string(name))
    now=int(time.time()*1000)
    metadata=named(8,'Name',string(os.path.splitext(os.path.basename(path))[0]))
    metadata+=named(8,'Author',string('Voxel Blocks'))+named(8,'Description',string('Blender voxel export'))
    metadata+=named(3,'RegionCount',integer(1))+named(3,'TotalVolume',integer(count))
    metadata+=named(3,'TotalBlocks',integer(sum(v != 'minecraft:air' for v in cells.values())))
    metadata+=named(4,'TimeCreated',long(now))+named(4,'TimeModified',long(now))+pos('EnclosingSize',(w,h,length))
    region=pos('Position',position)+pos('Size',(w,h,length))
    region+=list_compound('BlockStatePalette',[state(name) for name in palette])
    region+=named(12,'BlockStates',integer(len(words))+b''.join(struct.pack('>Q',v) for v in words))
    for name in ('TileEntities','Entities','PendingBlockTicks','PendingFluidTicks'): region+=list_compound(name,[])
    root=named(3,'Version',integer(7))+named(3,'SubVersion',integer(1))+named(3,'MinecraftDataVersion',integer(data_version))
    root+=compound('Metadata',metadata)+compound('Regions',compound('Voxel',region))
    with gzip.open(path,'wb') as f: f.write(compound('',root))
