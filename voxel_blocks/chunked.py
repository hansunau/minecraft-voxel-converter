"""Bounded chunk export; Blender world axes X,Y,Z map to Minecraft X,Z,Y."""
import os, math, json, time, random
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from . import PALETTE, SAFE_NAMES, material_color, make_matcher
from .schem import write_schem
from .litematic import write_litematic

XY=32
YCHUNK=128
MAX_GRID=150_000_000

def export_chunks(context,obj,s,parent,fmt):
    import bmesh
    selected={x.strip().removeprefix('minecraft:') for x in s.palette.split(',')}
    allowed=[p for p in PALETTE if s.palette_mode=='ALL' or (s.palette_mode=='SAFE' and p[0] in SAFE_NAMES) or (s.palette_mode=='CUSTOM' and p[0] in selected)]
    if not allowed: raise ValueError('사용할 블록을 하나 이상 선택하세요')
    match=make_matcher(allowed)
    deps=context.evaluated_depsgraph_get(); evaluated=obj.evaluated_get(deps); mesh=evaluated.to_mesh(preserve_all_data_layers=True,depsgraph=deps)
    try:
        mesh.transform(obj.matrix_world); bm=bmesh.new(); bm.from_mesh(mesh); check=bm.copy(); bmesh.ops.remove_doubles(check,verts=list(check.verts),dist=1e-7); open_edges=sum(e.is_boundary for e in check.edges); nonmanifold=sum(not e.is_manifold for e in check.edges); check.free(); bmesh.ops.triangulate(bm,faces=list(bm.faces)); bm.to_mesh(mesh); bm.free(); mesh.update()
        verts=[v.co for v in mesh.vertices]
        if not verts or not mesh.polygons: raise ValueError('면이 있는 메시가 필요합니다')
        low=Vector(tuple(min(v[i] for v in verts) for i in range(3))); high=Vector(tuple(max(v[i] for v in verts) for i in range(3))); span=high-low
        if min(span)<=1e-9: raise ValueError('세 축 모두 크기가 있는 닫힌 메시가 필요합니다')
        height=s.large_height; size=span.z/height; nx=max(1,math.ceil(span.x/size)); nz=max(1,math.ceil(span.y/size)); volume=nx*nz*height
        if volume>MAX_GRID: raise ValueError(f'전체 경계 격자 {volume:,}개가 안전 제한 {MAX_GRID:,}개를 초과합니다')
        if s.mode!='SOLID': raise ValueError('대용량 구역 내보내기는 현재 속 채우기만 지원합니다')
        if not os.path.isdir(parent): raise ValueError('저장할 폴더를 선택하세요')
        stamp=time.strftime('voxel_chunks_%Y%m%d_%H%M%S'); out=os.path.join(parent,stamp); suffix=1
        while os.path.exists(out): out=os.path.join(parent,stamp+'_'+str(suffix)); suffix+=1
        os.mkdir(out)
        manifest={'status':'incomplete','format':fmt,'height':height,'data_version':s.data_version,'dimensions':[nx,height,nz],'origin':'transformed bounding-box minimum; Blender X,Y,Z -> Minecraft X,Z,Y','chunk_size':[XY,YCHUNK,XY],'algorithm':'surface_three_axis' if nonmanifold else 'solid_parity','parts':[],'topology_check':{'weld_tolerance':1e-7,'boundary_edges':open_edges,'nonmanifold_edges':nonmanifold},'warnings':['열린 메시로 감지되어 내부를 채우지 않고 표면을 저장했습니다. 얇은 면은 누락될 수 있습니다.' if nonmanifold else '수밀성 검사는 겹치는 면 또는 자기 교차를 보장하지 않습니다.']}
        def save_manifest():
            with open(os.path.join(out,'manifest.json'),'w',encoding='utf8') as f: json.dump(manifest,f,ensure_ascii=False,indent=2)
        save_manifest()
        preview=[]; preview_seen=0; rng=random.Random(11)
        def record_preview(cells,pos):
            nonlocal preview_seen
            for (x,y,z),block in cells.items():
                preview_seen+=1; item=[x+pos[0],y+pos[1],z+pos[2],block]
                if len(preview)<6000: preview.append(item)
                else:
                    j=rng.randrange(preview_seen)
                    if j<6000: preview[j]=item
        tree=BVHTree.FromPolygons(verts,[list(p.vertices) for p in mesh.polygons],all_triangles=True); eps=size*1e-5; cache={}; tiles_x=math.ceil(nx/XY); tiles_z=math.ceil(nz/XY); ny=math.ceil(height/YCHUNK); tile_count=tiles_x*tiles_z; done=0; total_blocks=0
        for x0 in range(0,nx,XY):
            for z0 in range(0,nz,XY):
                w=min(XY,nx-x0); l=min(XY,nz-z0); columns={}
                if nonmanifold:
                    from .surface import surface_cells
                    for segment,y0 in enumerate(range(0,height,YCHUNK)):
                        h=min(YCHUNK,height-y0); cells={}
                        midpoint=low+Vector(((x0+w*.5)*size,(z0+l*.5)*size,(y0+h*.5)*size))
                        radius=size*(math.sqrt(w*w+l*l+h*h)*.5+1e-4)
                        if tree.find_nearest(midpoint,radius)[0] is None:
                            yield ('빈 구역 건너뛰기',(done+(segment+1)/ny)/tile_count); continue
                        g=surface_cells(tree,low,size,(nx,nz,height),(x0,z0,y0),(w,l,h))
                        while True:
                            try:
                                fraction=next(g); yield ('열린 메시 표면 계산',(done+(segment+.65*fraction)/ny)/tile_count)
                            except StopIteration as result:
                                points=result.value; break
                        for i,(x,z,y) in enumerate(points):
                            center=low+Vector(((x+.5)*size,(z+.5)*size,(y+.5)*size))
                            near,normal,face,dist=tree.find_nearest(center)
                            if face is not None: cells[(x-x0,y-y0,z-z0)]='minecraft:'+match(material_color(mesh,face,near,cache))
                            if i%256==0: yield ('표면 색상 선택',(done+(segment+.65+.35*i/max(1,len(points)))/ny)/tile_count)
                        if cells:
                            name=f'part_x{x0:04d}_y{y0:04d}_z{z0:04d}.'+fmt; path=os.path.join(out,name); pos=(x0,y0,z0)
                            if fmt=='litematic': write_litematic(path,(w,h,l),cells,s.data_version,position=pos)
                            else: write_schem(path,(w,h,l),cells,s.data_version,offset=pos)
                            record_preview(cells,pos)
                            manifest['parts'].append({'file':name,'offset':pos,'size':[w,h,l],'blocks':len(cells)}); total_blocks+=len(cells)
                        yield (f'구역 저장 · 블록 {total_blocks:,}개',(done+(segment+1)/ny)/tile_count)
                    done+=1; save_manifest(); continue
                for x in range(w):
                    for z in range(l):
                        origin=Vector((low.x+(x0+x+.5)*size,low.y+(z0+z+.5)*size,low.z-size)); hits=[]
                        for _ in range(len(mesh.polygons)+1):
                            hit,normal,face,dist=tree.ray_cast(origin,Vector((0,0,1)))
                            if hit is None: break
                            hits.append(hit.z); origin=hit+Vector((0,0,eps))
                        ranges=[]
                        for j in range(0,len(hits)-1,2):
                            a=max(0,math.ceil((hits[j]-low.z)/size-.5)); b=min(height,math.ceil((hits[j+1]-low.z)/size-.5))
                            if b>a:ranges.append((a,b))
                        if ranges: columns[(x,z)]=ranges
                    yield ('교차점 계산', (done+x/max(1,w)*.1)/tile_count)
                for segment,y0 in enumerate(range(0,height,YCHUNK)):
                    h=min(YCHUNK,height-y0); cells={}
                    for column_index,((x,z),ranges) in enumerate(columns.items()):
                        for a,b in ranges:
                            for y in range(max(a,y0),min(b,y0+h)):
                                center=Vector((low.x+(x0+x+.5)*size,low.y+(z0+z+.5)*size,low.z+(y+.5)*size))
                                near,normal,face,dist=tree.find_nearest(center)
                                if face is not None: cells[(x,y-y0,z)]='minecraft:'+match(material_color(mesh,face,near,cache))
                        if column_index%32==0: yield (f'구역 변환 · 블록 {total_blocks+len(cells):,}개', (done+(segment+column_index/max(1,len(columns)))/ny)/tile_count)
                    if cells:
                        name=f'part_x{x0:04d}_y{y0:04d}_z{z0:04d}.'+fmt; path=os.path.join(out,name); pos=(x0,y0,z0)
                        if fmt=='litematic': write_litematic(path,(w,h,l),cells,s.data_version,position=pos)
                        else: write_schem(path,(w,h,l),cells,s.data_version,offset=pos)
                        record_preview(cells,pos)
                        manifest['parts'].append({'file':name,'offset':pos,'size':[w,h,l],'blocks':len(cells)}); total_blocks+=len(cells)
                    yield (f'구역 저장 · 블록 {total_blocks:,}개', (done+(segment+1)/ny)/tile_count)
                done+=1; save_manifest()
        with open(os.path.join(out,'preview.json'),'w',encoding='utf8') as f: json.dump({'dims':[nx,height,nz],'cells':preview,'total':total_blocks},f,separators=(',',':'))
        manifest['status']='complete'; manifest['blocks']=total_blocks; save_manifest()
        with open(os.path.join(out,'배치안내.txt'),'w',encoding='utf8') as f:
            f.write('모든 조각의 기준점은 원본 경계 상자의 최소점입니다. 조각 이름과 manifest.json에는 Minecraft X,Y,Z 상대 위치가 있습니다.\n')
            if fmt=='litematic': f.write('각 파일의 영역 Position에 상대 위치가 포함되어 있습니다. 모든 파일을 같은 배치 원점에 놓으세요.\n')
            else: f.write('각 Sponge 파일의 Offset에 상대 위치가 포함되어 있습니다. WorldEdit 버전마다 Offset 처리 차이가 있을 수 있으므로 시험 후 같은 기준점에서 붙여넣으세요.\n')
            f.write(('열린 메시로 감지되어 속 채우기 대신 표면만 저장했습니다.\n' if nonmanifold else '')+'빈 조각은 생략했습니다. 일반 Minecraft 26.3 월드의 높이 범위를 넘어서는 구조물은 그대로 전부 배치할 수 없습니다. 높이 변경 모드 또는 축소가 필요합니다.\n')
        yield ('완료: '+out,1.0)
    finally: evaluated.to_mesh_clear()
