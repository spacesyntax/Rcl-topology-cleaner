from qgis.core import QgsFeature, QgsMapLayerRegistry, QgsVectorLayer, QgsVectorFileWriter
import math
import psycopg2
from psycopg2.extensions import AsIs


# GENERAL _______________________________________________________________

def duplicates(lst, item):
    return [i for i, x in enumerate(lst) if x == item]

# QGSFEATURES _______________________________________________________________


def copy_feature(prototype_feat, geom, id):
    f = QgsFeature(prototype_feat)
    f.setFeatureId(id)
    f.setGeometry(geom)
    return f


def merge_features(feature_list, new_id):
    # get attributes from longest
    geometries = [f.geometry() for f in feature_list]
    lengths = [geom.length() for geom in geometries]
    new_feat = QgsFeature(feature_list[lengths.index(max(lengths))])
    new_geom = geometries[0]
    for i in geometries[1:]:
        new_geom = new_geom.combine(i)
    new_feat.setGeometry(new_geom)
    new_feat.setFeatureId(new_id)
    return new_feat

# ANGLES _______________________________________________________________


def angle_3_points(p1, p2, p3):
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


# LAYER _______________________________________________________________

def getLayerByName(name):
    layer = None
    for i in QgsMapLayerRegistry.instance().mapLayers().values():
        if i.name() == name:
            layer = i
    return layer

def to_layer(features, crs, encoding, geom_type, layer_type, path, name):

    first_feat = features[0]
    fields = first_feat.fields()
    layer = None
    if layer_type == 'memory':
        geom_types = {1: 'Point', 2: 'Linestring', 3:'Polygon'}
        layer = QgsVectorLayer(geom_types[geom_type] + '?crs=' + crs.authid(), name, "memory")
        pr = layer.dataProvider()
        pr.addAttributes(fields.toList())
        layer.updateFields()
        layer.startEditing()
        pr.addFeatures(features)
        layer.commitChanges()

    elif layer_type == 'shapefile':
        file_writer = QgsVectorFileWriter(path, encoding, fields, geom_type, crs, "ESRI Shapefile")
        print path, encoding, fields, geom_type, crs
        if file_writer.hasError() != QgsVectorFileWriter.NoError:
            print "Error when creating shapefile: ", file_writer.errorMessage()
        del file_writer
        # TODO: get name from path
        layer = QgsVectorLayer(path, name, "ogr")
        pr = layer.dataProvider()
        layer.startEditing()
        pr.addFeatures(features)
        layer.commitChanges()

    elif layer_type == 'postgis':
        crs_id = crs.postgisSrid()
        geom_types = {1: 'Point', 2: 'Linestring', 3: 'Polygon', 4: 'MultiPoint', 5: 'MultiLineString', 6: 'MultiPolygon'}
        post_q_flds = {2: 'bigint', 6: 'numeric', 1: 'bool', 'else': 'text'}
        try:
            # crs = QgsCoordinateReferenceSystem(crs_id, QgsCoordinateReferenceSystem.EpsgCrsId)
            # mem_layer = to_layer(features, crs, encoding, geom_type, 'memory', path, name)
            # error = QgsVectorLayerImport.importLayer(mem_layer, path, "postgres", crs, False, False)
            # if error[0] != 0: print u'Error', error[1]

            (connstring, schema_name, table_name) = path

            uri = connstring + """ type=""" + geom_types[geom_type] + """ table=\"""" + schema_name + """\".\"""" + table_name + """\" (geom) """
            print uri , 'POSTGIS'

            con = psycopg2.connect(connstring)
            cur = con.cursor()

            postgis_flds_q = """"""
            for f in fields:
                f_name = '\"' + f.name() + '\"'
                try:
                    f_type = post_q_flds[f.type()]
                except KeyError:
                    f_type = post_q_flds['else']
                postgis_flds_q += cur.mogrify("""%s %s,""", (AsIs(f_name), AsIs(f_type)))

            query = cur.mogrify(
                """DROP TABLE IF EXISTS %s.%s; CREATE TABLE %s.%s(%s geom geometry(%s, %s))""", (
                AsIs(schema_name), AsIs(table_name), AsIs(schema_name), AsIs(table_name), AsIs(postgis_flds_q), geom_types[geom_type],  AsIs(crs_id)))
            cur.execute(query)
            con.commit()

            data = map(lambda f: (clean_nulls(f.attributes()), f.geometry().exportToWkt()), features)
            args_str = ','.join(
                map(lambda (attrs, wkt): rmv_parenthesis(cur.mogrify("%s,ST_GeomFromText(%s,%s))", (tuple(attrs), wkt, AsIs(crs_id)))), tuple(data)))

            ins_str = cur.mogrify("""INSERT INTO %s.%s VALUES """, (AsIs(schema_name), AsIs(table_name)))
            cur.execute(ins_str + args_str)
            con.commit()
            con.close()

            layer = QgsVectorLayer(uri, table_name, 'postgres')
        except psycopg2.DatabaseError, e:
            print e
    else:
        print "file type not supported"
    return layer


def clean_nulls(attrs):
    cleaned_attrs = []
    for attr in attrs:
        if attr:
            cleaned_attrs.append(attr)
        else:
            cleaned_attrs.append(None)
    return cleaned_attrs

def rmv_parenthesis(my_string):
    idx = my_string.find(',ST_GeomFromText') - 1
    return  my_string[:idx] + my_string[(idx+1):]

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
