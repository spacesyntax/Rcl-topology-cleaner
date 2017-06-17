# general imports
from os.path import expanduser
from qgis.core import QgsMapLayerRegistry, QgsVectorFileWriter, QgsVectorLayer, QgsFeature, QgsGeometry,QgsFields
import psycopg2
from psycopg2.extensions import AsIs

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

def qgs_to_postgis_fields(qgs_flds, crs, arrays = False):
    postgis_flds = []

    if arrays:
        for f in qgs_flds:
            if f.type() == 2:
                # bigint
                postgis_flds.append((AsIs('"f.name().lower()"'), ' bigint[]'))
            elif f.type() == 6:
                # numeric
                postgis_flds.append((AsIs('"f.name().lower()"'), ' numeric[]'))
            elif f.type() == 1:
                # numeric
                postgis_flds.append((AsIs('"f.name().lower()"'), ' bool[]'))
            else:
                # string
                postgis_flds.append((AsIs('"f.name().lower()"'), ' text[]'))
    else:
        for f in qgs_flds:
            if f.type() == 2:
                # bigint
                postgis_flds.append((AsIs('"f.name().lower()"'), ' bigint'))
            elif f.type() == 6:
                # numeric
                postgis_flds.append((AsIs('"f.name().lower()"'), ' numeric'))
            elif f.type() == 1:
                # numeric
                postgis_flds.append((AsIs('"f.name().lower()"'), ' bool'))
            else:
                # string
                postgis_flds.append((f.name().lower(), ' text'))
    postgis_flds.append(('geom', 'geometry(LINESTRING,' + str(crs_id) + ')'))
    return postgis_flds

def rmv_parenthesis(my_string):
    idx = my_string.find(',ST_GeomFromText') - 1
    return  my_string[:idx] + my_string[(idx+1):]

def to_dblayer(dbname, user, host, port, password, schema, table_name, qgs_flds, any_features_list, crs, arrays=False):

    crs_id = str(crs.postgisSrid())
    connstring = "dbname=%s user=%s host=%s port=%s password=%s" % (dbname, user, host, port, password)
    try:
        con = psycopg2.connect(connstring)
        cur = con.cursor()
        if arrays:
            post_q_flds = {2: 'bigint[]', 6: 'numeric[]', 1: 'bool[]', 'else':'text[]'}
        else:
            post_q_flds = {2: 'bigint', 6: 'numeric', 1: 'bool', 'else':'text'}

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

        if arrays:
            for (fid, attrs, wkt) in any_features_list:
                for idx, l_attrs in enumerate(attrs):
                    attrs[idx] = [i if i else None for i in l_attrs]
                data.append(tuple((attrs, wkt)))
            args_str = ','.join(
                [rmv_parenthesis(cur.mogrify("%s,ST_GeomFromText(%s,%s))", (tuple(attrs)[1:-1], wkt, AsIs(crs_id)))) for
                 (attrs, wkt) in tuple(data)])

        else:
            for (fid, attrs, wkt) in any_features_list:
                data.append(tuple(([i if i else None for i in attrs], wkt)))
            args_str = ','.join(
                [rmv_parenthesis(cur.mogrify("%s,ST_GeomFromText(%s,%s))", (tuple(attrs), wkt, AsIs(crs_id)))) for
                 (attrs, wkt) in tuple(data)])

        ins_str = cur.mogrify("""INSERT INTO %s.%s VALUES """, (AsIs(schema), AsIs(table_name)))
        cur.execute(ins_str + args_str)
        con.commit()
        con.close()

        print "success!"

    except psycopg2.DatabaseError, e:
        print 'Error %s' % e

    return




