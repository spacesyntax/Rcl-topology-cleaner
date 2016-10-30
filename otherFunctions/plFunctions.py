
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


def edges_from_line_qgs(geom, attrs, tolerance=None, simplify=True):
    if simplify:
        edge_attrs = attrs.copy()
        wkt = geom.exportToWkt()
        if tolerance is not None:
            pt1 = geom.asPolyline()[0]
            pt1_snapped = QgsPoint(snap_coord(pt1[0], tolerance), snap_coord(pt1[1], tolerance))
            pt2 = geom.asPolyline()[-1]
            pt2_snapped = QgsPoint(snap_coord(pt2[0], tolerance), snap_coord(pt2[1], tolerance))
            line = QgsGeometry.fromPolyline([pt1_snapped , pt2_snapped])
            geom = line
            wkt = make_snapped_wkt(wkt, tolerance)
            del line
        edge_attrs["Wkt"] = wkt
        yield (geom.asPolyline()[0], geom.asPolyline()[-1], edge_attrs)
    else:
        for i in range(0, len(geom.asPolyline()) - 1):
            pt1 = geom.asPolyline()[i]
            pt2 = geom.asPolyline()[i + 1]
            if tolerance is not None:
                pt1 = QgsPoint(snap_coord(pt1[0], tolerance), snap_coord(pt1[1], tolerance))
                pt2 = QgsPoint(snap_coord(pt1[0], tolerance), snap_coord(pt1[1], tolerance))
            segment = QgsGeometry.fromPolyline([pt1 , pt2])
            edge_attrs = attrs.copy()
            edge_attrs["Wkt"] = segment.ExportToWkt()
            del segment
            yield (pt1, pt2, edge_attrs)