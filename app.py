import os,sys,json,tempfile,threading,subprocess,queue,shutil
import tkinter as tk
from tkinter import ttk,filedialog,messagebox

BASE=getattr(sys,'_MEIPASS',os.path.dirname(os.path.abspath(__file__)))
import importlib.util
_palette_spec=importlib.util.spec_from_file_location('palette_263',os.path.join(BASE,'voxel_blocks','palette_263.py'))
_palette_module=importlib.util.module_from_spec(_palette_spec); _palette_spec.loader.exec_module(_palette_module)
BLOCKS=_palette_module.BLOCKS
BLOCK_NAMES={name for name,rgb,safe in BLOCKS}
SAFE_NAMES={name for name,rgb,safe in BLOCKS if safe}

# Familiar Korean search words supplement the canonical Minecraft IDs.
KOREAN_TERMS={'light_gray':'회색 밝은 회색','light_blue':'하늘색 밝은 파랑','white':'흰색 하양','orange':'주황색 주황','magenta':'자홍색 자홍','yellow':'노란색 노랑','lime':'연두색 연두','pink':'분홍색 분홍','gray':'회색','cyan':'청록색 청록','purple':'보라색 보라','blue':'파란색 파랑','brown':'갈색','green':'초록색 초록','red':'빨간색 빨강','black':'검은색 검정','concrete':'콘크리트','terracotta':'테라코타','wool':'양털','stone':'돌 석재','deepslate':'심층암','copper':'구리','gold':'금','iron':'철','diamond':'다이아몬드','emerald':'에메랄드','planks':'판자','wood':'나무','oak':'참나무','bricks':'벽돌','brick':'벽돌','basalt':'현무암','quartz':'석영','ore':'광석','mud':'진흙','sandstone':'사암','obsidian':'흑요석','netherite':'네더라이트'}
def search_text(name):
    return name+' '+' '.join(value for key,value in KOREAN_TERMS.items() if key in name)

def configure_style(root):
    style=ttk.Style(root)
    style.theme_use('clam')
    root.configure(bg='#f2f5f9')
    style.configure('.',font=('Malgun Gothic',10),background='#f2f5f9',foreground='#263548')
    style.configure('TFrame',background='#f2f5f9')
    style.configure('TLabel',background='#f2f5f9',foreground='#263548')
    style.configure('Title.TLabel',font=('Malgun Gothic',20,'bold'),foreground='#14243a')
    style.configure('Subtitle.TLabel',font=('Malgun Gothic',10),foreground='#67778b')
    style.configure('Section.TLabelframe',background='#ffffff',bordercolor='#dce5ef',relief='solid',borderwidth=1)
    style.configure('Section.TLabelframe.Label',background='#f2f5f9',foreground='#425674',font=('Malgun Gothic',10,'bold'))
    style.configure('Card.TFrame',background='#ffffff')
    style.configure('Card.TLabel',background='#ffffff',foreground='#263548')
    style.configure('Card.TRadiobutton',background='#ffffff',foreground='#263548')
    style.map('Card.TRadiobutton',background=[('active','#ffffff')])
    style.configure('TButton',padding=(13,8),background='#ffffff',foreground='#31445f',bordercolor='#d6e0eb',focuscolor='#ffffff')
    style.map('TButton',background=[('active','#eaf1fb'),('pressed','#dce9fa')])
    style.configure('Accent.TButton',padding=(20,11),background='#426ee8',foreground='#ffffff',bordercolor='#426ee8',font=('Malgun Gothic',10,'bold'))
    style.map('Accent.TButton',background=[('disabled','#b9c7df'),('active','#315bcf'),('pressed','#264db9')],foreground=[('disabled','#edf1f8')])
    style.configure('TEntry',padding=6,fieldbackground='#ffffff',bordercolor='#d6e0eb')
    style.configure('TCombobox',padding=5,fieldbackground='#ffffff',bordercolor='#d6e0eb',arrowcolor='#516780')
    style.configure('TSpinbox',padding=5,fieldbackground='#ffffff',bordercolor='#d6e0eb')
    style.configure('TProgressbar',troughcolor='#e1e8f3',background='#426ee8',bordercolor='#e1e8f3',lightcolor='#426ee8',darkcolor='#426ee8',thickness=10)
    return style

class PaletteDialog:
    def __init__(self, app):
        self.app=app; self.window=tk.Toplevel(app.root); self.window.title('블록 직접 선택'); self.window.geometry('750x710'); self.window.minsize(600,520); self.window.configure(bg='#f2f5f9'); self.window.transient(app.root)
        self.selected=set(app.selected_blocks); self.query=tk.StringVar(); self.count=tk.StringVar()
        outer=ttk.Frame(self.window,padding=14); outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='사용할 블록을 선택하세요',font=('Malgun Gothic',15,'bold')).pack(anchor='w')
        ttk.Label(outer,text='블록 ID 또는 색상·재료 이름으로 검색하세요. 색상은 근사치입니다.').pack(anchor='w',pady=(2,8))
        search=ttk.Frame(outer); search.pack(fill='x'); ttk.Label(search,text='검색').pack(side='left'); entry=ttk.Entry(search,textvariable=self.query); entry.pack(side='left',fill='x',expand=True,padx=(8,0))
        actions=ttk.Frame(outer); actions.pack(fill='x',pady=7)
        ttk.Button(actions,text='기본 목록',command=lambda:self.preset('safe')).pack(side='left'); ttk.Button(actions,text='전체 후보',command=lambda:self.preset('all')).pack(side='left',padx=4); ttk.Button(actions,text='전부 해제',command=lambda:self.preset('none')).pack(side='left')
        ttk.Button(actions,text='검색 결과 선택',command=lambda:self.visible_set(True)).pack(side='left',padx=(12,4)); ttk.Button(actions,text='검색 결과 해제',command=lambda:self.visible_set(False)).pack(side='left')
        frame=ttk.Frame(outer); frame.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(frame,highlightthickness=0,bg='#f2f5f9'); scrollbar=ttk.Scrollbar(frame,orient='vertical',command=self.canvas.yview); self.canvas.configure(yscrollcommand=scrollbar.set); scrollbar.pack(side='right',fill='y'); self.canvas.pack(side='left',fill='both',expand=True)
        self.rows=ttk.Frame(self.canvas); self.canvas_window=self.canvas.create_window((0,0),window=self.rows,anchor='nw'); self.rows.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all'))); self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.canvas_window,width=e.width)); self.canvas.bind('<MouseWheel>',self.wheel)
        ttk.Label(outer,textvariable=self.count).pack(anchor='w',pady=7)
        buttons=ttk.Frame(outer); buttons.pack(fill='x'); ttk.Button(buttons,text='선택 적용',style='Accent.TButton',command=self.apply).pack(side='right'); ttk.Button(buttons,text='취소',command=self.window.destroy).pack(side='right',padx=8)
        self.query.trace_add('write',lambda *args:self.refresh()); self.refresh(); entry.focus_set()
        self.window.grab_set()
    def wheel(self,event): self.canvas.yview_scroll(-int(event.delta/120),'units')
    def visible(self):
        q=self.query.get().strip().lower().removeprefix('minecraft:')
        return [b for b in BLOCKS if all(word in search_text(b[0]) for word in q.split())]
    def toggle(self,name,var):
        if var.get(): self.selected.add(name)
        else: self.selected.discard(name)
        self.update_count()
    def update_count(self): self.count.set(f'선택 {len(self.selected)} / {len(BLOCKS)}종 · 표시 {len(self.visible())}종')
    def refresh(self):
        for child in self.rows.winfo_children(): child.destroy()
        for i,(name,rgb,safe) in enumerate(self.visible()):
            row=ttk.Frame(self.rows); row.grid(row=i//2,column=i%2,sticky='w',padx=4,pady=1)
            swatch='#%02x%02x%02x'%tuple(max(0,min(255,round(c*255))) for c in rgb)
            tk.Label(row,bg=swatch,width=2,relief='solid',borderwidth=1).pack(side='left',padx=(0,4))
            var=tk.BooleanVar(value=name in self.selected); cb=ttk.Checkbutton(row,text=name,variable=var,command=lambda n=name,v=var:self.toggle(n,v)); cb.pack(side='left'); cb._palette_var=var
            for widget in (row,cb): widget.bind('<MouseWheel>',self.wheel)
        self.update_count(); self.canvas.yview_moveto(0)
    def preset(self,which):
        self.selected=set(SAFE_NAMES if which=='safe' else BLOCK_NAMES if which=='all' else ()); self.refresh()
    def visible_set(self,checked):
        names={name for name,rgb,safe in self.visible()}
        if checked:self.selected.update(names)
        else:self.selected.difference_update(names)
        self.refresh()
    def apply(self):
        if not self.selected: messagebox.showerror('블록 선택','블록을 하나 이상 선택하세요.',parent=self.window); return
        self.app.selected_blocks=set(self.selected); self.app.palette_summary.set(f'{len(self.selected)}종 선택됨'); self.window.destroy()

def find_blender():
    choices=[shutil.which('blender'),os.path.join(os.environ.get('ProgramFiles','C:/Program Files'),'Blender Foundation','Blender 5.2','blender.exe')]
    try:
        import winreg
        for root in (winreg.HKEY_LOCAL_MACHINE,winreg.HKEY_CURRENT_USER):
            with winreg.OpenKey(root,r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall') as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        with winreg.OpenKey(key,winreg.EnumKey(key,i)) as sub:
                            name=winreg.QueryValueEx(sub,'DisplayName')[0]
                            if 'blender' in name.lower(): choices.append(os.path.join(winreg.QueryValueEx(sub,'InstallLocation')[0],'blender.exe'))
                    except OSError: pass
    except OSError: pass
    return next((p for p in choices if p and os.path.isfile(p)), '')

class App:
    def __init__(self,root):
        self.root=root; root.title('마인크래프트 복셀 변환기'); root.geometry('760x750'); root.minsize(690,690); configure_style(root)
        self.blender=tk.StringVar(value=find_blender()); self.model=tk.StringVar(); self.obj=tk.StringVar(); self.height=tk.IntVar(value=32); self.mode=tk.StringVar(value='SHELL'); self.thickness=tk.IntVar(value=1); self.format=tk.StringVar(value='litematic'); self.chunked=tk.BooleanVar(value=False); self.status=tk.StringVar(value='1. Blender와 모델 파일을 선택하세요.'); self.progress=tk.DoubleVar(); self.proc=None; self.q=queue.Queue(); self.selected_blocks=set(SAFE_NAMES); self.palette_summary=tk.StringVar(value=f'{len(SAFE_NAMES)}종 선택됨')
        main=ttk.Frame(root,padding=(28,24)); main.pack(fill='both',expand=True)
        ttk.Label(main,text='모델을 블록으로',style='Title.TLabel').pack(anchor='w')
        ttk.Label(main,text='Minecraft Java 26.3  ·  파일은 내 컴퓨터에서 안전하게 변환됩니다',style='Subtitle.TLabel').pack(anchor='w',pady=(3,20))
        self.file_row(main,'Blender 실행 파일',self.blender,self.choose_blender)
        self.file_row(main,'변환할 모델 파일',self.model,self.choose_model)
        line=ttk.Frame(main); line.pack(fill='x',pady=5); ttk.Label(line,text='메시 오브젝트',width=18).pack(side='left'); self.objects=ttk.Combobox(line,textvariable=self.obj,state='readonly'); self.objects.pack(side='left',fill='x',expand=True); ttk.Button(line,text='목록 불러오기',command=self.scan).pack(side='left',padx=(8,0))
        box=ttk.LabelFrame(main,text='  변환 설정  ',padding=16,style='Section.TLabelframe'); box.pack(fill='x',pady=8)
        row=ttk.Frame(box,style='Card.TFrame'); row.pack(fill='x'); ttk.Label(row,text='높이 (블록)',style='Card.TLabel').pack(side='left'); ttk.Spinbox(row,from_=1,to=2048,textvariable=self.height,width=7).pack(side='left',padx=8); ttk.Radiobutton(row,text='껍데기',style='Card.TRadiobutton',variable=self.mode,value='SHELL').pack(side='left'); ttk.Radiobutton(row,text='속 채우기',style='Card.TRadiobutton',variable=self.mode,value='SOLID').pack(side='left'); ttk.Label(row,text='벽 두께',style='Card.TLabel').pack(side='left',padx=(15,2)); ttk.Spinbox(row,from_=1,to=16,textvariable=self.thickness,width=4).pack(side='left')
        row=ttk.Frame(box,style='Card.TFrame'); row.pack(fill='x',pady=(14,0))
        ttk.Label(row,text='사용할 블록',style='Card.TLabel').pack(side='left'); ttk.Label(row,textvariable=self.palette_summary,style='Card.TLabel').pack(side='left',padx=10)
        ttk.Button(row,text='블록 직접 선택…',command=lambda:PaletteDialog(self)).pack(side='left')
        ttk.Label(box,text=f'{len(BLOCKS)}종의 후보에서 원하는 블록을 직접 고를 수 있어요.',style='Card.TLabel').pack(anchor='w',pady=(4,0))
        ttk.Checkbutton(main,text='대용량 구역별 저장 (속 채우기, 높이 최대 2048)',variable=self.chunked).pack(anchor='w',pady=(8,0))
        row=ttk.Frame(main); row.pack(fill='x',pady=8); ttk.Label(row,text='저장 형식',width=18).pack(side='left'); ttk.Radiobutton(row,text='Litematica',variable=self.format,value='litematic').pack(side='left'); ttk.Radiobutton(row,text='WorldEdit',variable=self.format,value='schem').pack(side='left',padx=14)
        ttk.Progressbar(main,variable=self.progress,maximum=100).pack(fill='x',pady=(10,2)); ttk.Label(main,textvariable=self.status,wraplength=650).pack(anchor='w')
        row=ttk.Frame(main); row.pack(fill='x',pady=12); self.start=ttk.Button(row,text='변환하고 저장하기  →',style='Accent.TButton',command=self.convert); self.start.pack(side='left'); ttk.Button(row,text='작업 취소',command=self.cancel).pack(side='left',padx=8)
        ttk.Label(main,text='닫힌 메시를 사용하세요. 원본 파일은 수정하지 않습니다.\n대용량: 구역당 최대 131,072격자 · 약 400MB + 텍스처',foreground='#555').pack(anchor='w')
        root.protocol('WM_DELETE_WINDOW',self.close); root.after(100,self.poll)
    def file_row(self,parent,label,var,cmd):
        row=ttk.Frame(parent); row.pack(fill='x',pady=5); ttk.Label(row,text=label,width=18).pack(side='left'); ttk.Entry(row,textvariable=var).pack(side='left',fill='x',expand=True); ttk.Button(row,text='찾기',command=cmd).pack(side='left',padx=(8,0))
    def choose_blender(self):
        p=filedialog.askopenfilename(title='blender.exe 선택',filetypes=[('Blender','blender.exe'),('실행 파일','*.exe')]);
        if p:self.blender.set(p)
    def choose_model(self):
        p=filedialog.askopenfilename(title='변환할 3D 모델',filetypes=[('3D 모델','*.blend *.glb *.gltf *.obj *.stl *.ply *.fbx'),('모든 파일','*.*')]);
        if p:self.model.set(p); self.obj.set(''); self.scan()
    def validate(self):
        if self.proc: messagebox.showinfo('진행 중','현재 작업이 끝나거나 취소될 때까지 기다려 주세요.'); return False
        if not os.path.isfile(self.blender.get()): messagebox.showerror('Blender 필요','Blender를 설치한 후 blender.exe를 선택해 주세요.'); return False
        if not os.path.isfile(self.model.get()) or os.path.splitext(self.model.get())[1].lower() not in ('.blend','.glb','.gltf','.obj','.stl','.ply','.fbx'): messagebox.showerror('파일 필요','지원하는 3D 모델 파일을 선택해 주세요.'); return False
        return True
    def scan(self):
        if self.validate(): self.launch({'action':'list'}); self.status.set('메시 목록 불러오는 중...')
    def convert(self):
        if not self.validate():return
        try:
            h=int(self.height.get()); t=int(self.thickness.get()); assert 1<=h<=2048 and 1<=t<=16
        except (ValueError,tk.TclError,AssertionError): messagebox.showerror('설정 오류','높이는 1~2048, 두께는 1~16이어야 합니다.'); return
        if not self.obj.get() or not self.selected_blocks: messagebox.showerror('설정 오류','메시와 사용할 블록을 선택하세요.'); return
        if not self.chunked.get() and h>512: messagebox.showerror('높이 제한','512보다 큰 높이는 대용량 구역별 저장을 선택하세요.'); return
        if self.chunked.get() and self.mode.get()!='SOLID': messagebox.showerror('형태 선택','대용량 구역별 저장은 현재 속 채우기만 지원합니다.'); return
        fmt=self.format.get()
        path=filedialog.askdirectory(title='구역 결과를 저장할 폴더') if self.chunked.get() else filedialog.asksaveasfilename(title='변환 결과 저장',defaultextension='.'+fmt,filetypes=[('Litematica 파일','*.litematic')] if fmt=='litematic' else [('WorldEdit 파일','*.schem')])
        if not path:return
        if os.path.abspath(path).lower()==os.path.abspath(self.model.get()).lower(): messagebox.showerror('저장 오류','원본 파일과 다른 경로를 선택하세요.'); return
        self.launch({'action':'chunks' if self.chunked.get() else 'convert','object':self.obj.get(),'height':h,'thickness':t,'limit':250000,'mode':self.mode.get(),'palette_mode':'CUSTOM','palette':','.join(sorted(self.selected_blocks)),'format':fmt,'output':path}); self.status.set('변환 준비 중...')
    def launch(self,cfg):
        fd,path=tempfile.mkstemp(prefix='voxel_',suffix='.json'); os.close(fd)
        with open(path,'w',encoding='utf-8') as f: json.dump(cfg,f,ensure_ascii=False)
        env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'
        cmd=[self.blender.get(),'--background','--factory-startup','--disable-autoexec']
        if self.model.get().lower().endswith('.blend'): cmd.append(self.model.get())
        cmd += ['--python',os.path.join(BASE,'worker.py'),'--',path]; cfg['model']=self.model.get()
        with open(path,'w',encoding='utf-8') as f: json.dump(cfg,f,ensure_ascii=False)
        try:
            self.proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)); self.progress.set(0); self.start.config(state='disabled')
        except Exception as e:
            os.unlink(path); messagebox.showerror('실행 오류',str(e)); return
        proc=self.proc
        def run():
            try:
                for line in proc.stdout:
                    if line.startswith('VOXEL_EVENT '):
                        try:self.q.put(json.loads(line[12:]))
                        except ValueError:pass
                code=proc.wait(); self.q.put({'kind':'exit','code':code})
            finally:
                try:os.unlink(path)
                except OSError:pass
        threading.Thread(target=run,daemon=True).start()
    def poll(self):
        try:
            while True:
                e=self.q.get_nowait(); kind=e.get('kind')
                if kind=='objects':
                    names=e['names']; self.objects['values']=names; self.obj.set(names[0] if names else ''); self.status.set(f'메시 {len(names)}개를 찾았습니다.' if names else '메시가 없습니다.')
                elif kind=='progress':self.progress.set(e['value']*100); self.status.set(e['label']+f" {e['value']:.0%}")
                elif kind=='done':self.status.set(f"완료: {e['blocks']:,}개 블록 · 크기 {e['dims']}"); messagebox.showinfo('변환 완료',f"저장했습니다:\n{e['path']}\n\n블록 {e['blocks']:,}개")
                elif kind=='chunks_done':self.status.set('구역별 저장 완료: '+e['path']); messagebox.showinfo('변환 완료','구역별 결과를 저장했습니다:\n'+e['path'])
                elif kind=='error':self.status.set('오류: '+e['message']); messagebox.showerror('변환 오류',e['message'])
                elif kind=='exit':
                    self.proc=None; self.start.config(state='normal')
                    if e['code'] and not self.status.get().startswith(('오류','취소')): self.status.set('Blender 실행 실패. Blender 버전과 파일을 확인하세요.')
        except queue.Empty:pass
        self.root.after(100,self.poll)
    def cancel(self):
        if self.proc:self.proc.terminate(); self.status.set('취소됨')
    def close(self):
        if self.proc:self.proc.terminate()
        self.root.destroy()
if __name__=='__main__':
    root=tk.Tk(); App(root); root.mainloop()

