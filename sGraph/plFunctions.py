# general imports
import math
from qgis.core import QgsPoint, QgsGeometry

# plugin module imports
from generalFunctions import mid, snap_coord, keep_decimals_string


# -------------- POLYLINE FUNCTIONS ---------------

# iterate over indeces from a list of points


def find_vertex_index(points,feat,geometries):
    for point in points:
        yield geometries[feat].asPolyline().index(point.asPoint())


# test if a point is a vertex of a linestring


def point_is_vertex(point,line):
    if point.asPoint() in line.asPolyline():
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
        ind_mid_before = ind
        ind_mid_after = ind + 1
        if length > mid_length:
            midpoint = mid(vertices[ind_mid_before], vertices[ind_mid_after])
            break
        elif length == mid_length:
            midpoint = vertices[ind_mid_after]
            break
        #    print vertices
        #    midpoint = vertices[ind_mid_after]
        #    break
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

# -------------- WKT FUNCTIONS ---------------

# read wkt of line and return vertices iterator


def vertices_from_wkt(wkt):
    # the wkt representation may differ in other systems/ QGIS versions
    # TODO: check
    nums = [i for x in wkt[11:-1:].split(',') for i in x.split(' ')]
    coords = zip(*[iter(nums)] * 2)
    for vertex in coords:
        yield vertex


# convert a wkt to a snapped wkt to specified number of decimals


def make_snapped_wkt(wkt, number_decimals):
    # TODO: check in different system if '(' is included
    snapped_wkt = 'LINESTRING'
    for i in vertices_from_wkt(wkt):
        new_vertex = str(keep_decimals_string(i[0], number_decimals)) + ' ' + str(
            keep_decimals_string(i[1], number_decimals))
        snapped_wkt += str(new_vertex) + ', '
    return snapped_wkt[0:-2] + ')'


# read a wkt for a point and return QgsGeometry object
# TODO test

def make_point_from_wkt(wkt, number_decimals):
    point = wkt[7:-1]
    wkt = str(keep_decimals_string(point[0], number_decimals)) + ' ' + str(
            keep_decimals_string(point[1], number_decimals))
    return wkt


# read a wkt for a polyline and return QgsGeometry object
# TODO test

def make_pl_from_wkt(wkt, number_decimals):
    wkt = make_snapped_wkt(wkt, number_decimals)
    points = []
    for i in vertices_from_wkt(wkt):
        point = QgsPoint(i[0],i[1])
        points.append(point)
    return points