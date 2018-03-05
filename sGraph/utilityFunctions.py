# general imports
from qgis.core import QgsMapLayerRegistry, QgsVectorFileWriter, QgsVectorLayer, QgsFeature, QgsGeometry,QgsFields, QgsDataSourceURI
import psycopg2
from psycopg2.extensions import AsIs
import math

# source: ess utility functions


def getLayerByName(name):
    layer = None
    for i in QgsMapLayerRegistry.instance().mapLayers().values():
        if i.name() == name:
            layer = i
    return layer

def point_is_vertex(point, line):
    if point in line.asPolyline():
        return True

def self_intersects(geom_pl):
    self_intersections = []
    for i in geom_pl:
        if geom_pl.count(i) > 1:
            self_intersections.append(i)
    return self_intersections


def to_shp(path, any_features_list, layer_fields, crs, name, encoding, geom_type):
    if path is None:
        if geom_type == 0:
            network = QgsVectorLayer('Point?crs=' + crs.toWkt(), name, "memory")
        else:
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
    network.startEditing()
    pr.addFeatures(any_features_list)
    network.commitChanges()
    return network

def rmv_parenthesis(my_string):
    idx = my_string.find(',ST_GeomFromText') - 1
    return  my_string[:idx] + my_string[(idx+1):]

def to_dblayer(dbname, user, host, port, password, schema, table_name, qgs_flds, any_features_list, crs):

    crs_id = str(crs.postgisSrid())
    connstring = "dbname=%s user=%s host=%s port=%s password=%s" % (dbname, user, host, port, password)
    try:
        con = psycopg2.connect(connstring)
        cur = con.cursor()
        post_q_flds = {2: 'bigint[]', 6: 'numeric[]', 1: 'bool[]', 'else':'text[]'}
        postgis_flds_q = """"""
        for f in qgs_flds:
            f_name = '\"'  + f.name()  + '\"'
            try: f_type = post_q_flds[f.type()]
            except KeyError: f_type = post_q_flds['else']
            postgis_flds_q += cur.mogrify("""%s %s,""", (AsIs(f_name), AsIs(f_type)))

        query = cur.mogrify("""DROP TABLE IF EXISTS %s.%s; CREATE TABLE %s.%s(%s geom geometry(LINESTRING, %s))""", (AsIs(schema), AsIs(table_name), AsIs(schema), AsIs(table_name), AsIs(postgis_flds_q), AsIs(crs_id)))
        cur.execute(query)
        con.commit()

        data = []

        for (fid, attrs, wkt) in any_features_list:
            for idx, l_attrs in enumerate(attrs):
                if l_attrs:
                    attrs[idx] = [i if i else None for i in l_attrs]
                    if attrs[idx] == [None]:
                        attrs[idx] = None
                    else:
                        attrs[idx] = [a for a in attrs[idx] if a]
            data.append(tuple((attrs, wkt)))

        args_str = ','.join(
            [rmv_parenthesis(cur.mogrify("%s,ST_GeomFromText(%s,%s))", (tuple(attrs), wkt, AsIs(crs_id)))) for
             (attrs, wkt) in tuple(data)])

        ins_str = cur.mogrify("""INSERT INTO %s.%s VALUES """, (AsIs(schema), AsIs(table_name)))
        cur.execute(ins_str + args_str)
        con.commit()
        con.close()

        print "success!"
        uri = QgsDataSourceURI()
        # set host name, port, database name, username and password
        uri.setConnection(host, port, dbname, user, password)
        # set database schema, table name, geometry column and optionally
        uri.setDataSource(schema, table_name, "geom")
        return QgsVectorLayer(uri.uri(), table_name, "postgres")

    except psycopg2.DatabaseError, e:
        return e

# SOURCE: ESS TOOLKIT
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

def angle_3_points(inter_point, vertex1, vertex2):
    inter_vertex1 = math.hypot(abs(float(inter_point[0]) - float(vertex1[0])),
                               abs(float(inter_point[1]) - float(vertex1[1])))
    inter_vertex2 = math.hypot(abs(float(inter_point[0]) - float(vertex2[0])),
                               abs(float(inter_point[1]) - float(vertex2[1])))
    vertex1_2 = math.hypot(abs(float(vertex1[0]) - float(vertex2[0])), abs(float(vertex1[1]) - float(vertex2[1])))
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
    return math.degrees(math.acos(cos_angle))






