
import math

def find_vertex_index(points,feat,geometries):
    for point in points:
        yield geometries[feat].asPolyline().index(point.asPoint())


def point_is_vertex(point,line):
    if point.asPoint() in line.asPolyline()[1:-1]:
        return True

# find midpoint of a polyline geometry , input geometry type


def pl_midpoint(pl_geom):
    vertices = pl_geom.asPolyline()
    length = 0
    mid_length = pl_geom.length() / 2
    for ind, vertex in enumerate(vertices):
        start_vertex = vertices[ind]
        end_vertex = vertices[(ind + 1) % len(vertices)]
        length += math.hypot(abs(start_vertex[0] - end_vertex[0]), abs(start_vertex[1] - end_vertex[1]))
        if length > mid_length:
            ind_mid_before = ind
            ind_mid_after = ind + 1
            midpoint = mid(vertices[ind_mid_before], vertices[ind_mid_after])
            break
    return midpoint