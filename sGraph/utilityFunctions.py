# general imports
from os.path import expanduser
from qgis.core import QgsMapLayerRegistry, QgsVectorFileWriter, QgsVectorLayer, QgsFeature, QgsGeometry,QgsFields

# source: ess utility functions


def getLayerByName(name):
    layer = None
    for i in QgsMapLayerRegistry.instance().mapLayers().values():
        if i.name() == name:
            layer = i
    return layer


def get_next_vertex(tree, all_con):
    last = tree[-1]
    return tree + [i for i in all_con[last] if i not in tree]


def keep_decimals_string(string, number_decimals):
    integer_part = string.split(".")[0]
    # if the input is an integer there is no decimal part
    if len(string.split("."))== 1:
        decimal_part = str(0)*number_decimals
    else:
        decimal_part = string.split(".")[1][0:number_decimals]
    if len(decimal_part) < number_decimals:
        zeros = str(0) * int((number_decimals - len(decimal_part)))
        decimal_part = decimal_part + zeros
    decimal = integer_part + '.' + decimal_part
    return decimal


def find_vertex_index(points, f_geom):
    for point in points:
        yield f_geom.asPolyline().index(point.asPoint())


def point_is_vertex(point, line):
    if point.asPoint() in line.asPolyline():
        return True


def vertices_from_wkt_2(wkt):
    # the wkt representation may differ in other systems/ QGIS versions
    # TODO: check
    nums = [i for x in wkt[11:-1:].split(', ') for i in x.split(' ')]
    if wkt[0:12] == u'LineString (':
        nums = [i for x in wkt[12:-1:].split(', ') for i in x.split(' ')]
    coords = zip(*[iter(nums)] * 2)
    for vertex in coords:
        yield vertex


def make_snapped_wkt(wkt, number_decimals):
    # TODO: check in different system if '(' is included
    snapped_wkt = 'LINESTRING('
    for i in vertices_from_wkt_2(wkt):
        new_vertex = str(keep_decimals_string(i[0], number_decimals)) + ' ' + str(
            keep_decimals_string(i[1], number_decimals))
        snapped_wkt += str(new_vertex) + ', '
    return snapped_wkt[0:-2] + ')'


def to_shp(path, any_features_list, layer_fields, crs, name, encoding, geom_type):
    if path is None:
        network = QgsVectorLayer('LineString?crs=' + crs.toWkt(), name, "memory")
    else:
        fields = QgsFields()
        for field in layer_fields:
            fields.append(field)
        file_writer = QgsVectorFileWriter(path, encoding, fields, geom_type, crs, "ESRI Shapefile")
        if file_writer.hasError() != QgsVectorFileWriter.NoError:
            print "Error when creating shapefile: ", file_writer.errorMessage()
        del file_writer
        network = QgsVectorLayer(path, name, "ogr")
    pr = network.dataProvider()
    if path is None:
        pr.addAttributes(layer_fields)
    new_features = []
    for i in any_features_list:
        new_feat = QgsFeature()
        new_feat.setFeatureId(i[0])
        new_feat.setAttributes(i[1])
        new_feat.setGeometry(QgsGeometry.fromWkt(i[2]))
        new_features.append(new_feat)
    network.startEditing()
    pr.addFeatures(new_features)
    network.commitChanges()
    return network