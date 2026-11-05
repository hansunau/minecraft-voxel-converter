import bpy,sys,json,os,traceback
sys.path.insert(0,os.path.dirname(__file__))
import voxel_blocks as vb

def send(**data): print('VOXEL_EVENT '+json.dumps(data,ensure_ascii=True),flush=True)
try:
    cfg=json.load(open(sys.argv[sys.argv.index('--')+1],encoding='utf-8'))
    model=cfg.get('model',''); ext=os.path.splitext(model)[1].lower()
    if ext and ext != '.blend':
        bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
        if ext in ('.glb','.gltf'): bpy.ops.import_scene.gltf(filepath=model)
        elif ext=='.fbx': bpy.ops.import_scene.fbx(filepath=model)
        elif ext=='.obj': bpy.ops.wm.obj_import(filepath=model)
        elif ext=='.stl': bpy.ops.wm.stl_import(filepath=model)
        elif ext=='.ply': bpy.ops.wm.ply_import(filepath=model)
        else: raise ValueError('지원하지 않는 파일 형식입니다: '+ext)
    if cfg['action']=='list':
        meshes=[o.name for o in bpy.context.scene.objects if o.type=='MESH']
        send(kind='objects',names=meshes)
    else:
        vb.register(); obj=bpy.context.scene.objects.get(cfg['object'])
        if not obj or obj.type!='MESH': raise ValueError('선택한 메시를 찾을 수 없습니다. 파일을 다시 불러오세요.')
        s=bpy.context.scene.voxel_settings; s.limit=cfg['limit']; s.mode=cfg['mode']; s.thickness=cfg['thickness']; s.palette_mode=cfg.get('palette_mode','CUSTOM'); s.palette=cfg.get('palette',''); s.data_version=5023
        if cfg['action']=='chunks':
            from voxel_blocks.chunked import export_chunks
            s.large_height=cfg['height']; out=''
            for label,progress in export_chunks(bpy.context,obj,s,cfg['output'],cfg['format']):
                send(kind='progress',label=label,value=progress)
                if label.startswith('완료: '): out=label[4:]
            send(kind='chunks_done',path=out)
            sys.exit(0)
        s.height=cfg['height']
        for label,progress in vb.generate(bpy.context,obj,s): send(kind='progress',label=label,value=progress)
        result=bpy.context.active_object; dims=json.loads(result['voxel_dims']); cells={(v[0],v[1],v[2]):v[3] for v in json.loads(result['voxel_cells'])}
        dest=cfg['output']; tmp=dest+'.voxel-tmp'
        try:
            if cfg['format']=='litematic': vb.write_litematic(tmp,dims,cells,5023)
            else: vb.write_schem(tmp,dims,cells,5023)
            os.replace(tmp,dest)
        finally:
            if os.path.isfile(tmp): os.remove(tmp)
        send(kind='done',dims=dims,blocks=len(cells),path=dest)
except Exception as e:
    send(kind='error',message=str(e)); traceback.print_exc(); sys.exit(1)
