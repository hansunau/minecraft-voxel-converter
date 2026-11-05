# Minecraft Voxel Converter

3D 모델을 Minecraft Java용 블록으로 변환해 Litematica `.litematic` 또는 WorldEdit `.schem`으로 저장하는 Windows 프로그램 및 Blender 애드온입니다. 모델을 온라인으로 업로드하지 않습니다.

## 다운로드와 사용

GitHub 저장소의 **Releases**에서 `VoxelConverter-Windows.zip`을 내려받아 압축을 풀고 `VoxelConverter.exe`를 실행하세요. Windows에 Blender가 설치되어 있어야 합니다. Blender 5.2.3에서 확인했으며, Blender와 Python을 EXE에 포함하지 않습니다. Blender를 찾지 못하면 프로그램에서 `blender.exe`를 선택하세요.

1. BLEND, GLB, glTF, OBJ, STL, PLY, FBX 중 모델을 고르고 메시 오브젝트를 선택합니다.
2. 블록 높이와 속 채우기/껍데기를 고릅니다. **블록 직접 선택**에서 사용할 재료를 고릅니다.
3. Litematica 또는 WorldEdit 형식을 선택해 저장합니다. 큰 모델은 속 채우기와 **대용량 구역별 저장**을 선택합니다.

[실행 파일 안내](docs/EXE_사용안내.md) · [대용량 변환과 배치](docs/대용량_사용안내.md) · [블록 후보 목록](docs/블록_후보목록.txt)

Blender 애드온은 Releases의 `voxel_blocks.zip`을 Blender 환경설정의 애드온 설치 메뉴에서 설치하세요.

## 알아둘 점

- Minecraft Java 26.3 데이터 버전 5023, Sponge v3와 Litematica v7을 사용합니다. 실제 26.3 Litematica 또는 WorldEdit에서 가져오기는 아직 시험하지 않았습니다.
- 실제 모델의 3D 미리보기는 EXE에 없습니다. Blender 애드온의 일반 변환에서 미리보기를 볼 수 있습니다. 대용량은 별도 복셀 미리보기 메시를 만들지 않습니다.
- 닫힌 메시를 권장합니다. 열린 메시, 겹친 면, 얇은 형상은 줄이나 구멍 등 오류가 생길 수 있습니다. 기본 블록 색상과 이미지 텍스처의 근사치를 사용합니다.
- 블록 후보는 Minecraft 26.3의 단순 불투명 큐브를 중심으로 제한되어 있습니다. Minecraft의 모든 블록을 지원하지 않으며 계단과 반블록은 지원하지 않습니다.
- 기본 오버월드는 높이가 384블록이므로 높이 1,000블록 구조물을 그대로 세울 수 없습니다. 대용량 모드는 32×128×32 이하의 구역으로 나눕니다. 각 파일을 같은 기준점으로 배치해야 합니다.
- 서명되지 않은 Windows 실행 파일은 보안 확인 창이 나타날 수 있습니다. 출처가 확실한 파일만 실행하세요.

## 소스에서 실행

Windows의 Python 3에서 `python app.py`를 실행합니다. Tkinter가 필요하며 별도의 Blender를 변환 엔진으로 사용합니다. Blender 애드온은 `voxel_blocks` 폴더를 ZIP으로 묶어 설치할 수 있습니다. 프로그램이 파일을 자동으로 저장하는 위치는 사용자가 선택합니다.

## 라이선스와 출처

프로젝트 소스는 [GNU GPL v3.0 이상](LICENSE)입니다. Blender는 별도로 설치하는 독립 프로젝트이며 자체 라이선스를 따릅니다. Minecraft는 Mojang/Microsoft의 제품이며 이 프로젝트는 공식 제품이 아닙니다. 팔레트의 근사 색상은 Minecraft 26.3의 블록 텍스처를 분석한 수치이며 게임 텍스처나 게임 파일을 배포하지 않습니다.

포맷 참고: [Sponge Schematic v3](https://github.com/SpongePowered/Schematic-Specification/blob/master/versions/schematic-3.md), [Litematica 26.3 구현](https://github.com/sakura-ryoko/litematica/tree/64e74592f631cfa5b084bedb0eda5dac8a3b3cb8).

