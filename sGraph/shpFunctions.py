# general import
import networkx as nx
import os
from qgis.core import QgsMapLayerRegistry, QgsVectorFileWriter, QgsVectorLayer, QgsDataSourceURI, QgsField

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
    return {i.name(): i.typeName() for i in layer.dataProvider().fields()}


# delete saved copy of temporary layer


def del_shp(path):
    # deleteShapeFile
    os.remove(path)
    for ext in ['dbf', 'prj', 'qpj', 'shx']:
        os.remove(path[0:-3] + ext)


# shp to nx multiGraph


def read_shp_to_multi_graph(layer_name, tolerance=None, simplify=True):
    # 1. open shapefiles from directory/filename
    try:
        from osgeo import ogr
    except ImportError:
        raise ImportError("read_shp requires OGR: http://www.gdal.org/")

    # find if the table with the give table_name is a shapefile or a postgis file
    layer = getLayerByName(layer_name)
    path, provider_type = getLayerPath4ogr(layer)

    # TODO: push error message when path is empty/does not exist/connection with db does not exist
    if path == '':  # or not os.path.exists(path)
        return

    # construct a multi-graph
    net = nx.MultiGraph()
    lyr = ogr.Open(path)

    if provider_type == 'postgres':
        layer = [table for table in lyr if table.GetName() == layer_name][0]
        fields = [x.GetName() for x in layer.schema]
    elif provider_type in ('ogr', 'memory'):
        layer = lyr[0]
        fields = [x.GetName() for x in layer.schema]
    for f in layer:
        flddata = [f.GetField(f.GetFieldIndex(x)) for x in fields]
        g = f.geometry()
        attributes = dict(zip(fields, flddata))
        attributes["LayerName"] = lyr.GetName()
        # Note:  Using layer level geometry type
        if g.GetGeometryType() == ogr.wkbLineString:
            for edge in edges_from_line(g, attributes, tolerance, simplify):
                e1, e2, attr = edge
                net.add_edge(e1, e2, attr_dict=attr)
        elif g.GetGeometryType() == ogr.wkbMultiLineString:
            for i in range(g.GetGeometryCount()):
                geom_i = g.GetGeometryRef(i)
                for edge in edges_from_line(geom_i, attributes, tolerance, simplify):
                    e1, e2, attr = edge
                    net.add_edge(e1, e2, attr_dict=attr)
            # TODO: push message x features not included

    if provider_type == 'postgres':
        # destroy connection with db
        lyr.Destroy()
    elif provider_type == 'memory':
        # delete shapefile
        del_shp(path)

    return net


# TODO check if any of the edge created is a point
# source : networkx
# TODO: add unique id column

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
            edge_attrs = attrs.copy()
            edge_attrs["Wkt"] = segment.ExportToWkt()
            del segment
            yield (pt1, pt2, edge_attrs)


# identify invalids multiparts of a layer


def inv_mlParts(name, uid):
    layer = getLayerByName(name)
    invalids = [i[uid] for i in layer.getFeatures() if not i.geometry().isGeosValid()]
    multiparts = [i[uid] for i in layer.getFeatures() if i.geometry().isMultipart()]
    return invalids, multiparts


# ----- TRANSFORMATION OPERATIONS -----

# layer to primal graph


class transformer:

    def __init__(self, parameters, transformation_type):
        self.parameters = parameters
        self.transformation_type = transformation_type
        self.id_column = parameters['id_column']

        # ----- SHP TO prGRAPH

        if self.transformation_type == 'shp_to_pgr':
            # TODO: check the parallel lines (1 of the parallel edges is not correct connected)
            primal_graph = read_shp_to_multi_graph(parameters['layer_name'], parameters['tolerance'], parameters['simplify'])
            self.result = primal_graph



