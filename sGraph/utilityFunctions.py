import collections
import math
from collections import defaultdict
from qgis.core import QgsMapLayerRegistry, QgsFields, QgsField, QgsGeometry, QgsFeature, QgsVectorLayer, QgsVectorFileWriter, QGis, NULL, QgsDataSourceURI, QgsVectorLayerImport
from PyQt4.QtCore import  QVariant
import itertools
import psycopg2
from qgis.gui import QgsMessageBar


# FEATURES -----------------------------------------------------------------

# detecting errors:
# (NULL), point, (invalids), multipart geometries, snap (will be added later)
points = []
multiparts = []
error_flds = QgsFields()
error_flds.append(QgsField('error type', QVariant.String))
error_feat = QgsFeature()
error_feat.setFields(error_flds)

# do not snap - because if self loop needs to break it will not

# FEATURES -----------------------------------------------------------------

def clean_features_iter(feat_iter):
    id = 0
    for f in feat_iter:

        # dropZValue if geometry is 3D
        if f.geometry().geometry().is3D():
                f.geometry().geometry().dropZValue()

        f_geom = f.geometry()

        # point
        if f_geom.length() <= 0:
            points.append(f_geom.asPoint())
            ml_error = QgsFeature(error_feat)
            ml_error.setGeometry(f_geom)
            ml_error.setAttributes(['point'])
            points.append(ml_error)
        elif f_geom.wkbType() == 2:
            f.setFeatureId(id)
            id += 1
            yield f
        # empty geometry
        elif f_geom is NULL:
            #self.empty_geometries.append()
            pass
        # invalid geometry
        elif not f_geom.isGeosValid():
            #self.invalids.append(copy_feature(f, QgsGeometry(), f.id()))
            pass
        # multilinestring
        elif f_geom.wkbType() == 5:
            ml_segms = f_geom.asMultiPolyline()
            for ml in ml_segms:
                ml_geom = QgsGeometry(QgsGeometry.fromPolyline(ml))
                ml_feat = QgsFeature(f)
                ml_feat.setFeatureId(id)
                id += 1
                ml_feat.setGeometry(ml_geom)
                ml_error = QgsFeature(error_feat)
                ml_error.setGeometry(QgsGeometry.fromPoint(ml_geom.asPolyline()[0]))
                ml_error.setAttributes(['multipart'])
                multiparts.append(ml_error)
                ml_error = QgsFeature(error_feat)
                ml_error.setGeometry(QgsGeometry.fromPoint(ml_geom.asPolyline()[-1]))
                ml_error.setAttributes(['multipart'])
                multiparts.append(ml_error)
                yield ml_feat

# GEOMETRY -----------------------------------------------------------------


def getSelfIntersections(polyline):
    return [item for item, count in collections.Counter(polyline).items() if count > 1] # points


def find_vertex_indices(polyline, points):
    indices = defaultdict(list)
    for idx, vertex in enumerate(polyline):
        indices[vertex].append(idx)
    break_indices = [indices[v] for v in set(points)] + [[0, (len(polyline) - 1)]]
    break_indices = [item for sublist in break_indices for item in sublist]
    return sorted(list(set(break_indices)))


def angular_change(geom1, geom2):
    pl1 = geom1.asPolyline()
    pl2 = geom2.asPolyline()
    points1 = {pl1[0], pl1[-1]}
    points2 = {pl2[0], pl2[-1]}
    inter_point = points1.intersection(points2)
    point1 = [p for p in points1 if p != inter_point]
    point2 = [p for p in points1 if p != inter_point]

    # find index in geom1
    # if index 0, then get first vertex
    # if index -1, then get the one before last vertex

    # find index in geom2

    return

def angle_3_points(geom1, geom2):
    pl1 = geom1.asPolyline()
    pl2 = geom2.asPolyline()
    p1 = [pl1[0], pl1[-1]]
    p3 = [pl2[0], pl2[-1]]
    p2 = set(p1).intersection(set(p3)).pop()
    p1.remove(p2)
    p3.remove(p2)
    p1 = p1.pop()
    p3 = p3.pop()
    inter_vertex1 = math.hypot(abs(float(p2.x()) - float(p1.x())), abs(float(p2.y()) - float(p1.y())))
    inter_vertex2 = math.hypot(abs(float(p2.x()) - float(p3.x())), abs(float(p2.y()) - float(p3.y())))
    vertex1_2 = math.hypot(abs(float(p1.x()) - float(p3.x())), abs(float(p1.y()) - float(p3.y())))
    A = ((inter_vertex1 ** 2) + (inter_vertex2 ** 2) - (vertex1_2 ** 2))
    B = (2 * inter_vertex1 * inter_vertex2)
    if B != 0:
        cos_angle = A / B
    else:
        cos_angle = NULL
    if cos_angle < -1:
        cos_angle = int(-1)
    if cos_angle > 1:
        cos_angle = int(1)
    return 180 - math.degrees(math.acos(cos_angle))

def merge_geoms(geoms, simpl_threshold):
    # get attributes from longest
    new_geom = geoms[0]
    for i in geoms[1:]:
        new_geom = new_geom.combine(i)
    if simpl_threshold != 0:
        new_geom = new_geom.simplify(simpl_threshold)
    return new_geom

# ITERATORS -----------------------------------------------------------------


# connected components iterator from group_dictionary e.g. { A: [B,C,D], B: [D,E,F], ...}
def con_comp_iter(group_dictionary):
    components_passed = set([])
    for id in group_dictionary.keys():
        if {id}.isdisjoint(components_passed):
            group = [[id]]
            candidates = ['dummy', 'dummy']
            while len(candidates) > 0:
                flat_group = group[:-1] + group[-1]
                candidates = map(lambda last_visited_node: set(group_dictionary[last_visited_node]).difference(set(flat_group)), group[-1])
                candidates = list(set(itertools.chain.from_iterable(candidates)))
                group = flat_group + [candidates]
                components_passed.update(set(candidates))
            yield group[:-1]

gr = [[29, 27, 26, 28], [31, 11, 10, 3, 30], [71, 51, 52, 69],
      [78, 67, 68, 39, 75], [86, 84, 81, 82, 83, 85], [84, 67, 78, 77, 81],
      [86, 68, 67, 84]]


def grouper(sequence):
    result = []  # will hold (members, group) tuples
    for item in sequence:
        for members, group in result:
            if members.intersection(item):  # overlap
                members.update(item)
                group.append(item)
                break
        else:  # no group found, add new
            result.append((set(item), [item]))
    return [group for members, group in result]

# WRITE -----------------------------------------------------------------

# geom_type allowed: 'Point', 'Linestring', 'Polygon'
def to_layer(features, crs, encoding, geom_type, layer_type, path, name):

    first_feat = features[0]
    fields = first_feat.fields()
    layer = None
    if layer_type == 'memory':
        layer = QgsVectorLayer(geom_type + '?crs=' + crs.authid(), name, "memory")
        pr = layer.dataProvider()
        pr.addAttributes(fields.toList())
        layer.updateFields()
        layer.startEditing()
        pr.addFeatures(features)
        layer.commitChanges()

    elif layer_type == 'shapefile':

        wkbTypes = { 'Point': QGis.WKBPoint, 'Linestring': QGis.WKBLineString, 'Polygon': QGis.WKBPolygon }
        file_writer = QgsVectorFileWriter(path, encoding, fields, wkbTypes[geom_type], crs, "ESRI Shapefile")
        if file_writer.hasError() != QgsVectorFileWriter.NoError:
            print "Error when creating shapefile: ", file_writer.errorMessage()
        del file_writer
        layer = QgsVectorLayer(path, name, "ogr")
        pr = layer.dataProvider()
        layer.startEditing()
        pr.addFeatures(features)
        layer.commitChanges()

    elif layer_type == 'postgis':

        layer = QgsVectorLayer(geom_type + '?crs=' + crs.authid(), name, "memory")
        pr = layer.dataProvider()
        pr.addAttributes(fields.toList())
        layer.updateFields()
        layer.startEditing()
        pr.addFeatures(features)
        layer.commitChanges()
        uri = QgsDataSourceURI()
        # passwords, usernames need to be empty if not provided or else connection will fail
        if path['service']:
            uri.setConnection(path['service'], path['database'], '', '')
        elif path['password']:
            uri.setConnection(path['host'], path['port'], path['database'], path['user'], path['password'])
        else:
            uri.setConnection(path['host'], path['port'], path['database'], path['user'], '')
        #uri = "dbname='test' host=localhost port=5432 user='user' password='password' key=gid type=POINT table=\"public\".\"test\" (geom) sql="
        #crs = QgsCoordinateReferenceSystem(int(crs.postgisSrid()), QgsCoordinateReferenceSystem.EpsgCrsId)
        # layer - QGIS vector layer
        uri.setDataSource(path['schema'], path['table_name'], "geom")
        error = QgsVectorLayerImport.importLayer(layer, uri.uri(), "postgres", crs, False, False)
        if error[0] != 0:
            print "Error when creating postgis layer: ", error[1]

        print uri.uri()
        layer = QgsVectorLayer(uri.uri(), name, "postgres")

    return layer


# LAYER -----------------------------------------------------------------


def getLayerByName(name):
    layer = None
    for i in QgsMapLayerRegistry.instance().mapLayers().values():
        if i.name() == name:
            layer = i
    return layer


# POSTGIS -----------------------------------------------------------------

def getPostgisSchemas(connstring, commit=False):
    """Execute query (string) with given parameters (tuple)
    (optionally perform commit to save Db)
    :return: result set [header,data] or [error] error
    """

    try:
        connection = psycopg2.connect(connstring)
    except psycopg2.Error, e:
        print e.pgerror
        connection = None

    schemas = []
    data = []
    if connection:
        query = unicode("""SELECT schema_name from information_schema.schemata;""")
        cursor = connection.cursor()
        try:
            cursor.execute(query)
            if cursor.description is not None:
                data = cursor.fetchall()
            if commit:
                connection.commit()
        except psycopg2.Error, e:
            connection.rollback()
        cursor.close()

    # only extract user schemas
    for schema in data:
        if schema[0] not in ('topology', 'information_schema') and schema[0][:3] != 'pg_':
            schemas.append(schema[0])
    #return the result even if empty
    return sorted(schemas)