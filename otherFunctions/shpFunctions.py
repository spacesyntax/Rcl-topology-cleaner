
# plugin module imports
from utilityFunctions import getLayerByName, getLayerPath4ogr
from plFunctions import make_snapped_wkt, snap_coord

# other import
import networkx as nx
import os


# copy a temporary layer


def get_fields(layer_name):
    layer = getLayerByName(layer_name)
    return layer.dataProvider().fields()


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


def edges_from_line(geom, attrs, tolerance=None, simplify=True):
    """
    Generate edges for each line in geom
    Written as a helper for read_shp
    Parameters
    ----------
    geom:  ogr line geometry
        To be converted into an edge or edges
    attrs:  dict
        Attributes to be associated with all geoms
    simplify:  bool
        If True, simplify the line as in read_shp
    geom_attrs:  bool
        If True, add geom attributes to edge as in read_shp
    Returns
    -------
     edges:  generator of edges
        each edge is a tuple of form
        (node1_coord, node2_coord, attribute_dict)
        suitable for expanding into a networkx Graph add_edge call
    """
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


def inv_mlParts(name, uid):
    layer = getLayerByName(name)
    invalids = [i[uid] for i in layer.getFeatures() if not i.geometry().isGeosValid()]
    multiparts = [i[uid] for i in layer.getFeatures() if i.geometry().isMultipart()]
    return invalids, multiparts