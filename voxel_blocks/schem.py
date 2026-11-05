import gzip, struct

def named(t, name, payload):
    b=name.encode('utf8'); return bytes([t])+struct.pack('>H',len(b))+b+payload

def varint(n):
    out=bytearray()
    while n >= 128:
        out.append((n & 127)|128); n >>= 7
    out.append(n); return out

def write_schem(path, dims, cells, data_version, offset=(0,0,0)):
    w,h,l=dims
    if not all(0 < n <= 65535 for n in dims): raise ValueError('크기 제한 초과')
    palette={'minecraft:air':0}
    for block in cells.values():
        if block not in palette: palette[block]=len(palette)
    raw=bytearray()
    for y in range(h):
        for z in range(l):
            for x in range(w): raw.extend(varint(palette[cells.get((x,y,z),'minecraft:air')]))
    ints=lambda n: struct.pack('>i',n)
    pal=b''.join(named(3,k,ints(v)) for k,v in palette.items())+b'\0'
    blocks=named(10,'Palette',pal)+named(7,'Data',ints(len(raw))+raw)+b'\0'
    body=named(3,'Version',ints(3))+named(3,'DataVersion',ints(data_version))
    for key,n in zip(('Width','Height','Length'),dims): body+=named(2,key,struct.pack('>H',n))
    body+=named(11,'Offset',ints(3)+b''.join(ints(int(n)) for n in offset))
    body+=named(10,'Blocks',blocks)+b'\0'
    root=named(10,'',named(10,'Schematic',body)+b'\0')
    with gzip.open(path,'wb') as f: f.write(root)
