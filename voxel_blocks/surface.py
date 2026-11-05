"""Conservative surface sampling for open meshes, in Blender XYZ grid coordinates."""
import math
from mathutils import Vector

def surface_cells(tree,low,size,dims,start,extent):
    points=set(); eps=size*1e-5; completed=0; total=sum(extent[[a for a in range(3) if a!=axis][0]] for axis in range(3))
    for axis in range(3):
        other=[a for a in range(3) if a!=axis]
        direction=Vector((0,0,0)); direction[axis]=1
        for a in range(start[other[0]],start[other[0]]+extent[other[0]]):
            for b in range(start[other[1]],start[other[1]]+extent[other[1]]):
                origin=Vector(low);origin[axis]-=size
                origin[other[0]]=low[other[0]]+(a+.5)*size
                origin[other[1]]=low[other[1]]+(b+.5)*size
                for _ in range(8192):
                    hit,normal,face,distance=tree.ray_cast(origin,direction)
                    if hit is None:break
                    n=math.floor((hit[axis]-low[axis])/size)
                    if n==dims[axis] and abs(hit[axis]-(low[axis]+dims[axis]*size))<=size*1e-5: n-=1
                    if start[axis]<=n<start[axis]+extent[axis] and 0<=n<dims[axis]:
                        p=[0,0,0];p[axis]=n;p[other[0]]=a;p[other[1]]=b;points.add(tuple(p))
                    origin=hit+direction*eps
            completed+=1
            yield completed/max(1,total)
    return points
