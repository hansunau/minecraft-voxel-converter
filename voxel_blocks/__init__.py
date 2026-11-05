bl_info = {'name':'마인크래프트 복셀 변환기', 'author':'Codex', 'version':(0,5,0), 'blender':(4,2,0), 'location':'3D 뷰 > 사이드바 > 복셀', 'category':'Object'}
import bpy, math, time, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy.props import IntProperty, BoolProperty, EnumProperty, StringProperty, PointerProperty
from bpy_extras.io_utils import ExportHelper
from .schem import write_schem
from .litematic import write_litematic

from .palette_263 import BLOCKS
PALETTE=[(name,rgb) for name,rgb,safe in BLOCKS]
SAFE_NAMES={name for name,rgb,safe in BLOCKS if safe}

def srgb(x):
    x=max(0,min(1,x)); return 12.92*x if x <= .0031308 else 1.055*x**(1/2.4)-.055

def material_color(mesh, face, point, cache):
    poly=mesh.polygons[face]; mat=mesh.materials[poly.material_index] if poly.material_index < len(mesh.materials) else None
    col=tuple(mat.diffuse_color[:3]) if mat else (.8,.8,.8)
    image_srgb=False
    if mat and mat.use_nodes:
        bs=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
        if bs:
            inp=bs.inputs.get('Base Color'); col=tuple(inp.default_value[:3])
            if inp.is_linked:
                node=inp.links[0].from_node
                if node.type=='TEX_IMAGE' and node.image and mesh.uv_layers.active:
                    # Interpolate UV on triangulated evaluated geometry.
                    loops=list(poly.loop_indices)
                    if len(loops)==3:
                        a,b,c=[mesh.vertices[mesh.loops[i].vertex_index].co for i in loops]
                        from mathutils.geometry import barycentric_transform
                        uv=[mesh.uv_layers.active.data[i].uv for i in loops]
                        q=barycentric_transform(point,a,b,c,Vector((uv[0].x,uv[0].y,0)),Vector((uv[1].x,uv[1].y,0)),Vector((uv[2].x,uv[2].y,0)))
                        image=node.image; w,h=image.size
                        if w and h:
                            ix=int((q.x%1)*w)%w; iy=int((q.y%1)*h)%h; off=4*(iy*w+ix)
                            key=image.as_pointer()
                            if key not in cache:
                                from array import array
                                cache[key]=array('f',[0.0])*(len(image.pixels)); image.pixels.foreach_get(cache[key])
                            pixels=cache[key]; samples=[]
                            for dy in (-1,0,1):
                                for dx in (-1,0,1):
                                    o=4*(((iy+dy)%h)*w+((ix+dx)%w)); samples.append(pixels[o:o+3])
                            col=tuple(sum(p[i] for p in samples)/len(samples) for i in range(3))
                            image_srgb=image.colorspace_settings.name.lower() in ('srgb','s-rgb')
    return tuple(max(0,min(1,v)) for v in col) if image_srgb else tuple(srgb(v) for v in col)

def nearest(rgb, allowed):
    return min(allowed,key=lambda p:sum((p[1][i]-rgb[i])**2 for i in range(3)))[0]

class Settings(bpy.types.PropertyGroup):
    export_format: EnumProperty(name='저장 형식',items=[('SCHEM','WorldEdit (.schem)','Sponge v3'),('LITEMATIC','Litematica (.litematic)','Litematica v7')],default='SCHEM')
    height: IntProperty(name='높이 (블록)',default=32,min=1,max=512)
    large_height: IntProperty(name='대용량 높이',default=1000,min=1,max=2048)
    limit: IntProperty(name='최대 격자 수',default=250000,min=100,max=2000000)
    thickness: IntProperty(name='벽 두께',default=1,min=1,max=16)
    mode: EnumProperty(name='형태',items=[('SOLID','속 채우기',''),('SHELL','껍데기','')])
    data_version: IntProperty(name='Minecraft 데이터 버전',default=5023,min=1,description='기본값: Minecraft Java 26.3. 서버 버전에 맞게 변경')
    palette_mode: EnumProperty(name='재료 범위',items=[('SAFE','건축용 기본','일부 위험 블록 제외'),('ALL','모든 후보','단순 불투명 큐브 후보 전체'),('CUSTOM','직접 제한','블록 이름을 쉼표로 입력')],default='SAFE')
    palette: StringProperty(name='허용 블록',default='stone, gold_block',description='직접 제한할 블록 이름을 쉼표로 입력')
    status: StringProperty(name='상태',default='준비')

def generate(context, obj, s):
    selected={x.strip().removeprefix('minecraft:') for x in s.palette.split(',')}
    allowed=[p for p in PALETTE if s.palette_mode=='ALL' or (s.palette_mode=='SAFE' and p[0] in SAFE_NAMES) or (s.palette_mode=='CUSTOM' and p[0] in selected)]
    if not allowed: raise ValueError('허용 블록을 하나 이상 입력하세요')
    deps=context.evaluated_depsgraph_get(); evaluated=obj.evaluated_get(deps); mesh=evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=deps)
    try:
        # Work in evaluated world coordinates, preserving the source object.
        mesh.transform(obj.matrix_world)
        import bmesh
        bm=bmesh.new(); bm.from_mesh(mesh); bmesh.ops.triangulate(bm,faces=list(bm.faces)); bm.to_mesh(mesh); bm.free(); mesh.update()
        if not mesh.polygons: raise ValueError('면이 있는 메시를 선택하세요')
        verts=[v.co for v in mesh.vertices]; low=Vector(tuple(min(v[i] for v in verts) for i in range(3))); high=Vector(tuple(max(v[i] for v in verts) for i in range(3)))
        span=high-low
        if min(span) <= 1e-9: raise ValueError('세 축 모두 크기가 있는 닫힌 메시가 필요합니다')
        size=span.z/s.height; nx=max(1,math.ceil(span.x/size)); ny=max(1,math.ceil(span.y/size)); nz=s.height
        total=nx*ny*nz
        if total>s.limit: raise ValueError(f'격자 {total:,}개가 제한 {s.limit:,}개를 초과합니다. 높이를 줄이세요')
        tree=BVHTree.FromPolygons(verts,[list(p.vertices) for p in mesh.polygons],all_triangles=True)
        cells={}; image_cache={}; eps=size*1e-5
        # Vertical parity ray casting; intersections delimit solid intervals.
        for x in range(nx):
            for y in range(ny):
                origin=Vector((low.x+(x+.5)*size,low.y+(y+.5)*size,low.z-size)); hits=[]
                for _ in range(len(mesh.polygons)+1):
                    hit,normal,face,dist=tree.ray_cast(origin,Vector((0,0,1)))
                    if hit is None: break
                    hits.append(hit.z); origin=hit+Vector((0,0,eps))
                for z in range(nz):
                    center=Vector((low.x+(x+.5)*size,low.y+(y+.5)*size,low.z+(z+.5)*size))
                    if sum(h<center.z for h in hits)%2:
                        near,normal,face,dist=tree.find_nearest(center)
                        if face is not None: cells[(x,z,y)]='minecraft:'+nearest(material_color(mesh,face,near,image_cache),allowed)
            yield ('복셀화', (x+1)/nx*.8)
        if not cells: raise ValueError('결과가 비어 있습니다. 닫힌 메시인지 확인하거나 해상도를 높이세요')
        # Replace isolated color matches only where at least four neighbors agree
        # and the candidate colors are already close. Keep sharp color accents.
        from collections import Counter
        colors=dict(PALETTE); smoothed={}
        directions=((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
        for p,block in cells.items():
            neighbors=Counter(cells.get((p[0]+a,p[1]+b,p[2]+c)) for a,b,c in directions)
            neighbors.pop(None,None)
            if neighbors:
                candidate,count=neighbors.most_common(1)[0]
                a=colors[block.split(':')[1]]; b=colors[candidate.split(':')[1]]
                if count>=4 and sum((a[i]-b[i])**2 for i in range(3))<0.025: smoothed[p]=candidate
        cells.update(smoothed)
        if s.mode=='SHELL':
            original=set(cells); layer=set(original); boundary=set(); directions=((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
            for _ in range(s.thickness):
                edge={p for p in layer if any((p[0]+a,p[1]+b,p[2]+c) not in layer for a,b,c in directions)}
                boundary.update(edge); layer-=edge
                yield ('껍데기 추출',.85)
            cells={p:cells[p] for p in boundary}
        yield ('미리보기 생성',.9)
        # One combined mesh avoids one Blender object per block.
        vs=[]; fs=[]; mids=[]; names=sorted(set(cells.values())); indices={n:i for i,n in enumerate(names)}
        corners=((0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1))
        faces=((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7))
        for (x,z,y),block in cells.items():
            base=len(vs); vs.extend([(low.x+(x+a)*size,low.y+(y+b)*size,low.z+(z+c)*size) for a,b,c in corners]); fs.extend([tuple(base+i for i in f) for f in faces]); mids.extend([indices[block]]*6)
        outmesh=bpy.data.meshes.new('복셀 메시'); outmesh.from_pydata(vs,[],fs); outmesh.update()
        result=bpy.data.objects.new('복셀 미리보기',outmesh)
        for name in names:
            mat=bpy.data.materials.new(name); rgb=dict(PALETTE)[name.split(':')[1]]; mat.diffuse_color=(*rgb,1); outmesh.materials.append(mat)
        for p,i in zip(outmesh.polygons,mids): p.material_index=i
        collection=bpy.data.collections.new('복셀 결과'); context.scene.collection.children.link(collection); collection.objects.link(result)
        result['voxel_dims']=json.dumps([nx,nz,ny]); result['voxel_cells']=json.dumps([[*p,b] for p,b in cells.items()],separators=(',',':')); result['voxel_data_version']=s.data_version
        context.view_layer.objects.active=result; result.select_set(True); obj.select_set(False)
        yield ('완료',1)
    finally: evaluated.to_mesh_clear()

class Convert(bpy.types.Operator):
    bl_idname='voxel_blocks.convert'; bl_label='복셀 미리보기 만들기'; bl_options={'REGISTER','UNDO'}
    _timer=None; _gen=None
    def execute(self,context):
        obj=context.active_object
        if not obj or obj.type!='MESH': self.report({'ERROR'},'메시 오브젝트를 선택하세요'); return {'CANCELLED'}
        self._gen=generate(context,obj,context.scene.voxel_settings); self._timer=context.window_manager.event_timer_add(.05,window=context.window); context.window_manager.modal_handler_add(self); context.window_manager.progress_begin(0,100); return {'RUNNING_MODAL'}
    def modal(self,context,event):
        if event.type=='ESC':
            self._gen.close(); self.finish(context); context.scene.voxel_settings.status='취소됨'; return {'CANCELLED'}
        if event.type=='TIMER':
            try:
                label,progress=next(self._gen); context.scene.voxel_settings.status=f'{label} {progress:.0%} (Esc 취소)'; context.window_manager.progress_update(progress*100); context.area.tag_redraw()
            except StopIteration:
                self.finish(context); context.scene.voxel_settings.status='완료'; return {'FINISHED'}
            except Exception as e:
                self.finish(context); context.scene.voxel_settings.status='오류: '+str(e); self.report({'ERROR'},str(e)); return {'CANCELLED'}
        return {'PASS_THROUGH'}
    def finish(self,context):
        context.window_manager.event_timer_remove(self._timer); context.window_manager.progress_end()

class Export(bpy.types.Operator,ExportHelper):
    bl_idname='voxel_blocks.export'; bl_label='Sponge .schem 저장'; filename_ext='.schem'
    filter_glob: StringProperty(default='*.schem',options={'HIDDEN'})
    def execute(self,context):
        obj=context.active_object
        if not obj or 'voxel_cells' not in obj: self.report({'ERROR'},'복셀 미리보기 오브젝트를 선택하세요'); return {'CANCELLED'}
        try:
            dims=json.loads(obj['voxel_dims']); cells={(v[0],v[1],v[2]):v[3] for v in json.loads(obj['voxel_cells'])}; write_schem(self.filepath,dims,cells,obj['voxel_data_version'])
        except Exception as e: self.report({'ERROR'},str(e)); return {'CANCELLED'}
        self.report({'INFO'},'Sponge v3 저장 완료'); return {'FINISHED'}

class ExportLitematic(bpy.types.Operator,ExportHelper):
    bl_idname='voxel_blocks.export_litematic'; bl_label='Litematica .litematic 저장'; filename_ext='.litematic'
    filter_glob: StringProperty(default='*.litematic',options={'HIDDEN'})
    def execute(self,context):
        obj=context.active_object
        if not obj or 'voxel_cells' not in obj: self.report({'ERROR'},'복셀 미리보기 오브젝트를 선택하세요'); return {'CANCELLED'}
        try:
            dims=json.loads(obj['voxel_dims']); cells={(v[0],v[1],v[2]):v[3] for v in json.loads(obj['voxel_cells'])}; write_litematic(self.filepath,dims,cells,obj['voxel_data_version'])
        except Exception as e: self.report({'ERROR'},str(e)); return {'CANCELLED'}
        self.report({'INFO'},'Litematica 저장 완료'); return {'FINISHED'}

class ExportChunks(bpy.types.Operator):
    bl_idname='voxel_blocks.export_chunks'; bl_label='구역별 대용량 내보내기'; bl_options={'REGISTER'}
    directory: StringProperty(name='저장 폴더',subtype='DIR_PATH')
    _timer=None; _gen=None
    def invoke(self,context,event):
        context.window_manager.fileselect_add(self); return {'RUNNING_MODAL'}
    def execute(self,context):
        from .chunked import export_chunks
        obj=context.active_object
        if not obj or obj.type!='MESH' or 'voxel_cells' in obj:
            self.report({'ERROR'},'원본 메시 오브젝트를 선택하세요'); return {'CANCELLED'}
        s=context.scene.voxel_settings
        self._gen=export_chunks(context,obj,s,self.directory,'litematic' if s.export_format=='LITEMATIC' else 'schem')
        self._timer=context.window_manager.event_timer_add(.05,window=context.window); context.window_manager.modal_handler_add(self); context.window_manager.progress_begin(0,100); return {'RUNNING_MODAL'}
    def modal(self,context,event):
        if event.type=='ESC':
            self._gen.close(); self.finish(context); context.scene.voxel_settings.status='취소됨 (부분 파일은 incomplete)'; return {'CANCELLED'}
        if event.type=='TIMER':
            try:
                label,p=next(self._gen); context.scene.voxel_settings.status=f'{label} {p:.1%} · Esc 취소'; context.window_manager.progress_update(p*100)
                if context.area: context.area.tag_redraw()
            except StopIteration:
                self.finish(context); context.scene.voxel_settings.status='대용량 내보내기 완료'; return {'FINISHED'}
            except Exception as e:
                self.finish(context); context.scene.voxel_settings.status='오류: '+str(e); self.report({'ERROR'},str(e)); return {'CANCELLED'}
        return {'PASS_THROUGH'}
    def finish(self,context):
        context.window_manager.event_timer_remove(self._timer); context.window_manager.progress_end()

class Panel(bpy.types.Panel):
    bl_label='마인크래프트 복셀'; bl_idname='VIEW3D_PT_voxel_blocks'; bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='복셀'
    def draw(self,context):
        l=self.layout; s=context.scene.voxel_settings
        for p in ('height','limit','mode'): l.prop(s,p)
        if s.mode=='SHELL': l.prop(s,'thickness')
        l.prop(s,'palette_mode')
        if s.palette_mode=='CUSTOM': l.prop(s,'palette')
        l.label(text=f'후보 {len(PALETTE)}종 · 건축용 {len(SAFE_NAMES)}종')
        l.prop(s,'data_version')
        l.label(text='예상 메모리: 격자당 약 1~3 KB'); l.operator('voxel_blocks.convert'); l.label(text=s.status)
        l.prop(s,'export_format')
        l.operator('voxel_blocks.export' if s.export_format=='SCHEM' else 'voxel_blocks.export_litematic')
        box=l.box(); box.label(text='대용량: 원본 메시 선택 · 속 채우기')
        box.prop(s,'large_height'); box.label(text='32×128×32 구역 · 약 400MB + 텍스처')
        box.operator('voxel_blocks.export_chunks')
classes=(Settings,Convert,Export,ExportLitematic,ExportChunks,Panel)
def register():
    for c in classes: bpy.utils.register_class(c)
    bpy.types.Scene.voxel_settings=PointerProperty(type=Settings)
def unregister():
    del bpy.types.Scene.voxel_settings
    for c in reversed(classes): bpy.utils.unregister_class(c)
if __name__=='__main__': register()
