
# imports
# import generalFunctions as gF


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