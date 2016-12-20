# general import
import networkx as nx
import os
from qgis.core import QgsMapLayerRegistry, QgsVectorFileWriter, QgsVectorLayer, QgsDataSourceURI, QgsField, QgsFeature, QgsGeometry
from PyQt4.QtCore import QVariant, QObject, pyqtSignal

# plugin module imports
from utilityFunctions import getLayerByName, getLayerPath4ogr, getAllFeatures
from plFunctions import make_snapped_wkt, snap_coord

# ----- SHAPEFILE OPERATIONS -----

# copy a temporary layer

def copy_shp(temp_layer, path):
    features_to_copy = getAllFeatures(temp_layer)
    provider = temp_layer.dataProvider()
    writer = QgsVectorFileWriter(path, provider.encoding(), provider.fields(), provider.geometryType(), provider.crs(),
                                 "ESRI Shapefile")

    # TODO: push message
    if writer.hasError() != QgsVectorFileWriter.NoError:
        print "Error when creating shapefile: ", writer.errorMessage()

    for fet in features_to_copy.values():
        writer.addFeature(fet)

    del writer
    layer = QgsVectorLayer(path, temp_layer.name(), "ogr")
    return layer

# get fields of a layer


def get_fields(layer_name):
    layer = getLayerByName(layer_name)
    return layer.dataProvider().fields()

# get fields_names: fields_types of a layer


def get_field_types(layer_name):
    layer = getLayerByName(layer_name)
    return {i.name(): i.type() for i in layer.dataProvider().fields()}


# delete saved copy of temporary layer


def del_shp(path):
    # deleteShapeFile
    os.remove(path)
    for ext in ['dbf', 'prj', 'qpj', 'shx']:
        os.remove(path[0:-3] + ext)


# TODO check if any of the edge created is a point
# source : networkx

def edges_from_line(geom, attrs, tolerance=None, simplify=True):
    try:
        from osgeo import ogr
    except ImportError:
        raise ImportError("edges_from_line requires OGR: http://www.gdal.org/")
    if simplify:
        edge_attrs = attrs.copy()
        last = geom.GetPointCount() - 1
        wkt = geom.ExportToWkt()
        if tolerance is not None:
            pt1 = geom.GetPoint_2D(0)
            pt2 = geom.GetPoint_2D(last)
            line = ogr.Geometry(ogr.wkbLineString)
            line.AddPoint_2D(snap_coord(pt1[0], tolerance), snap_coord(pt1[1], tolerance))
            line.AddPoint_2D(snap_coord(pt2[0], tolerance), snap_coord(pt2[1], tolerance))
            geom = line
            wkt = make_snapped_wkt(wkt, tolerance)
            last = 1
            del line
        edge_attrs["Wkt"] = wkt
        yield (geom.GetPoint_2D(0), geom.GetPoint_2D(last), edge_attrs)
    else:
        for i in range(0, geom.GetPointCount() - 1):
            pt1 = geom.GetPoint_2D(i)
            pt2 = geom.GetPoint_2D(i + 1)
            if tolerance is not None:
                pt1 = (snap_coord(pt1[0], tolerance), snap_coord(pt1[1], tolerance))
                pt2 = (snap_coord(pt2[0], tolerance), snap_coord(pt2[1], tolerance))
            segment = ogr.Geometry(ogr.wkbLineString)
            segment.AddPoint_2D(pt1[0], pt1[1])
            segment.AddPoint_2D(pt2[0], pt2[1])
            if segment.Length() > 0:
                edge_attrs = attrs.copy()
                edge_attrs["Wkt"] = segment.ExportToWkt()
                del segment
                yield (pt1, pt2, edge_attrs)
            else:
                del segment

# identify invalids multi-parts of a layer


def inv_mlParts(name):
    layer = getLayerByName(name)
    invalids = []
    multiparts = []
    for i in layer.getFeatures():
        if not i.geometry().isGeosValid():
            invalids.append((i.id(), i.geometry().exportToWkt()))
        elif i.geometry().isMultipart():
            multiparts.append((i.id(), i.geometry().exportToWkt()))

    return invalids, multiparts


def errors_to_shp(input_layer, user_id, error_list, path, name, crs, encoding, geom_type):
    geom_input = {feat[user_id]: feat.geometryAndOwnership() for feat in input_layer.getFeatures()}
    if path is None:
        network = QgsVectorLayer('LineString?crs=' + crs.toWkt(), name, "memory")
    else:
        file_writer = QgsVectorFileWriter(path, encoding,[QgsField('error_id', QVariant.Int),QgsField('input_id', QVariant.String), QgsField('errors', QVariant.String)], geom_type,
                                          crs, "ESRI Shapefile")
        if file_writer.hasError() != QgsVectorFileWriter.NoError:
            print "Error when creating shapefile: ", file_writer.errorMessage()
        del file_writer
        network = QgsVectorLayer(path, name, "ogr")
    #QgsMapLayerRegistry.instance().addMapLayer(network)
    pr = network.dataProvider()
    network.startEditing()
    if path is None:
        pr.addAttributes([QgsField('error_id', QVariant.Int), QgsField('input_id', QVariant.String), QgsField('errors', QVariant.String)])
    errors_feat = []
    error_count = 0
    attr_dict = {error : '' for errors in error_list for error in errors[1]}
    for errors in error_list:
        for error in errors[1]:
            if len(attr_dict[error]) == 0:
                attr_dict[error] += str(errors[0])
            else:
                attr_dict[error] += ', ' + str(errors[0])
    for k, v in attr_dict.items():
        new_feat = QgsFeature()
        new_feat.initAttributes(3)
        new_feat.setAttributes([error_count, k, v])
        new_feat.setGeometry(geom_input[k])
        errors_feat.append(new_feat)
        error_count += 1
    pr.addFeatures(errors_feat)
    network.commitChanges()
    return network


# ----- TRANSFORMATION OPERATIONS -----

# layer to primal graph


class transformer(QObject):

    # Setup signals
    finished = pyqtSignal(object)
    error = pyqtSignal(Exception, basestring)
    progress = pyqtSignal(float)
    warning = pyqtSignal(str)

    def __init__(self, parameters):
        QObject.__init__(self)
        self.parameters = parameters
        # self.id_column = parameters['id_column']
        # ----- SHP TO prGRAPH

    def read_shp_to_multi_graph(self):
        # TODO: check the parallel lines (1 of the parallel edges is not correct connected)
        layer_name = self.parameters['layer_name']
        col_id = self.parameters['user_id']
        tolerance = self.parameters['tolerance']
        simplify = self.parameters['simplify']
        get_invalids = self.parameters['get_invalids']
        get_multiparts = self.parameters['get_multiparts']

        # 1. open shapefiles from directory/filename
        try:
            from osgeo import ogr
        except ImportError:
            raise ImportError("read_shp requires OGR: http://www.gdal.org/")

        invalids = []
        multiparts = []
        # find if the table with the give table_name is a shapefile or a postgis file
        layer = getLayerByName(layer_name)
        path, provider_type, provider = getLayerPath4ogr(layer)

        # TODO: push error message when path is empty/does not exist/connection with db does not exist
        if path == '':  # or not os.path.exists(path)
            return

        # construct a multi-graph
        net = nx.MultiGraph()
        lyr = ogr.Open(path)

        if provider_type == 'postgres':
            uri = QgsDataSourceURI(provider.dataSourceUri())
            databaseSchema = uri.schema().encode('utf-8')
            if databaseSchema == 'public':
                layer = [table for table in lyr if table.GetName() == layer_name][0]
            else:
                layer = [table for table in lyr if table.GetName() == databaseSchema + '.' + layer_name][0]
            fields = [x.GetName() for x in layer.schema]
        elif provider_type in ('ogr', 'memory'):
            layer = lyr[0]
            fields = [x.GetName() for x in layer.schema]
        count = 0
        f_count = 1
        feat_count = layer.GetFeatureCount()
        inv_count = 1

        for f in layer:

            self.progress.emit(10*f_count/feat_count)
            f_count += 1

            flddata = [f.GetField(f.GetFieldIndex(x)) for x in fields]
            g = f.geometry()
            g.FlattenTo2D()
            attributes = dict(zip(fields, flddata))
            attributes["LayerName"] = lyr.GetName()
            # Note:  Using layer level geometry type
            if g.GetGeometryType() == ogr.wkbLineString:
                for edge in edges_from_line(g, attributes, tolerance, simplify):
                    e1, e2, attr = edge
                    new_key = 'in_' + str(count)
                    count += 1
                    net.add_edge(e1, e2, key=new_key, attr_dict=attr)
            elif g.GetGeometryType() == ogr.wkbMultiLineString:
                if get_multiparts and col_id:
                    multiparts.append(attributes[col_id])
                inv_count += 1
                for i in range(g.GetGeometryCount()):
                    geom_i = g.GetGeometryRef(i)
                    for edge in edges_from_line(geom_i, attributes, tolerance, simplify):
                        e1, e2, attr = edge
                        new_key = 'in_' + str(count)
                        count += 1
                        net.add_edge(e1, e2, key=new_key, attr_dict=attr)
            else:
                if get_invalids and col_id:
                    invalids.append(attributes[col_id])

        if provider_type == 'postgres':
            # destroy connection with db
            lyr.Destroy()
        elif provider_type == 'memory':
            # delete shapefile
            del_shp(path)

        return net, invalids, multiparts



