# general imports
import networkx as nx
from networkx import connected_components, all_simple_paths
import ogr

from PyQt4.QtCore import QVariant, pyqtSignal, QObject
from qgis.core import QgsField, QgsFeature, QgsGeometry, QgsPoint, QgsVectorLayer, QgsVectorFileWriter, QgsMapLayerRegistry

# plugin module imports
from primal_graph import prGraph
from shpFunctions import edges_from_line

class dlGraph(QObject):

    # Setup signals
    finished = pyqtSignal(object)
    error = pyqtSignal(Exception, basestring)
    progress = pyqtSignal(float)
    warning = pyqtSignal(str)

    def __init__(self, dlGraph, id_column, centroids, make_feat=True):
        QObject.__init__(self)
        self.obj = dlGraph
        self.uid = id_column
        self.attributes = ['line1', 'line2', 'cost']
        self.n_attributes = 3
        self.qgs_fields = [QgsField('line1',QVariant.String), QgsField('line2',QVariant.String), QgsField('cost',QVariant.Int)]

        if make_feat:
            features = []
            count = 1
            for edge in self.obj.edges(data='cost'):
                feat = QgsFeature()
                feat.setGeometry(QgsGeometry.fromPolyline(
                    [QgsPoint(centroids[edge[0]][0], centroids[edge[0]][1]), QgsPoint(centroids[edge[1]][0], centroids[edge[1]][1])]))
                feat.initAttributes(self.n_attributes)
                feat.setAttributes([edge[0], edge[1], edge[2]])
                feat.setFeatureId(count)
                features.append(feat)
                count += 1
            self.features = features


    # ----- TRANSLATION OPERATIONS

    # ----- dlGRAPH TO SHP

    def to_shp(self, path, name, crs, encoding, geom_type):
        if path is None:
            network = QgsVectorLayer('LineString?crs=' + crs.toWkt(), name, "memory")
        else:
            # provider.fields()
            file_writer = QgsVectorFileWriter(path, encoding, None, geom_type,
                                              crs.crs(), "ESRI Shapefile")
            if file_writer.hasError() != QgsVectorFileWriter.NoError:
                print "Error when creating shapefile: ", file_writer.errorMessage()
            del file_writer
            network = QgsVectorLayer(path, name, "ogr")
        #QgsMapLayerRegistry.instance().addMapLayer(network)
        pr = network.dataProvider()
        network.startEditing()
        pr.addAttributes(self.qgs_fields)
        pr.addFeatures(self.features)
        network.commitChanges()
        return network

    def to_shp_vertices(self):
        pass

    # Code source: ESS TOOLKIT https://github.com/SpaceGroupUCL/qgisSpaceSyntaxToolkit.git

    def find_islands_orphans(self, primal_graph):
        wkt_dict = primal_graph.get_wkt_dict()
        # order based on length
        components = sorted(connected_components(self.obj), key=len, reverse=True)
        islands = []
        orphans = []
        count = 1
        orph_count = 1
        if len(components) > 1:
            islands = []
            # get vertex ids
            for cluster in components[1:len(components)]:  # excludes the first giant component
                # identify orphans
                if len(cluster) == 1:
                    orphan = cluster.pop()
                    orphans.append(('orph_' + str(orph_count), wkt_dict[orphan]))
                    orph_count += 1
                # identify islands
                elif len(cluster) > 1:
                    island = list(cluster)
                    geom_col = QgsGeometry.fromWkt('GEOMETRYCOLLECTION EMPTY')
                    for i in island:
                        geom_col = geom_col.combine(QgsGeometry.fromWkt(wkt_dict[i]))
                    geom_wkt = geom_col.exportToWkt()
                    islands.append(('isl_' + str(count), geom_wkt))
                    count += 1

        return islands, orphans

    def find_cont_lines(self):
        # 2. merge lines from intersection to intersection
        # Is there a grass function for QGIS 2.14???
        # sets of connected nodes (edges of primary graph)
        sets = []
        for j in connected_components(self.obj):
            sets.append(list(j))
        sets_in_order = [set_con for set_con in sets if len(set_con) == 2 or len(set_con) == 1]
        for set in sets:
            if len(set) > 2:
                edges = []
                for n in set:
                    if len(self.obj.neighbors(n)) > 2 or len(self.obj.neighbors(n)) == 1:
                        edges.append(n)
                        # find all shortest paths and keep longest between edges
                if len(edges) == 0:
                    edges = [set[0], set[0]]
                list_paths = [i for i in all_simple_paths(self.obj, edges[0], edges[1])]
                if len(list_paths) == 1:
                    set_in_order = list_paths[0]
                else:
                    set_in_order = max(enumerate(list_paths), key=lambda tup: len(tup[1]))[1]
                    del set_in_order[-1]
                sets_in_order.append(set_in_order)

        return sets_in_order

    def merge(self, primal_graph, tolerance, simplify):
        geom_dict = primal_graph.get_geom_dict()
        wkt_dict = primal_graph.get_wkt_dict()
        attr_dict = primal_graph.get_attr_dict()
        merged = []
        primal_merged = nx.MultiGraph()

        count = 0
        for set_to_merge in self.find_cont_lines():
            if len(set_to_merge) == 1:
                attrs = attr_dict[set_to_merge[0]]
                attrs['merged_id'] = attrs['broken_id']
                ogr_geom = ogr.Geometry(ogr.wkbLineString)
                for i in geom_dict[set_to_merge[0]].asPolyline():
                    ogr_geom.AddPoint_2D(i[0], i[1])
                for edge in edges_from_line(ogr_geom, attrs, tolerance, simplify):
                    e1, e2, attr = edge
                    attr['Wkt'] = ogr_geom.ExportToWkt()
                    primal_merged.add_edge(e1, e2, attr_dict=attr)
            else:
                for i in set_to_merge:
                    merged.append((i, wkt_dict[i]))
                attrs = attr_dict[set_to_merge[0]]
                attrs['merged_id'] = attrs['broken_id'] + '_mr_' + str(count)
                new_geom = geom_dict[set_to_merge[0]]
                geom_to_merge = [geom_dict[i] for i in set_to_merge]
                # TODO: check when combining with multipolyline
                for ind, line in enumerate(geom_to_merge[1:], start=1):
                    second_geom = geom_dict[set_to_merge[ind]]
                    first_geom = geom_to_merge[(ind - 1) % len(set_to_merge)]
                    new_geom = second_geom.combine(first_geom)
                    geom_to_merge[ind] = new_geom
                if new_geom.wkbType() == 5:
                    for linestring in new_geom.asGeometryCollection():
                        ogr_geom = ogr.Geometry(ogr.wkbLineString)
                        for i in linestring.asPolyline():
                            ogr_geom.AddPoint_2D(i[0], i[1])
                        for edge in edges_from_line(ogr_geom, attrs, tolerance, simplify):
                            e1, e2, attr = edge
                            attr['Wkt'] = ogr_geom.ExportToWkt()
                            primal_merged.add_edge(e1, e2, attr_dict=attr)
                elif new_geom.wkbType() == 2:
                    ogr_geom = ogr.Geometry(ogr.wkbLineString)
                    for i in new_geom.asPolyline():
                        ogr_geom.AddPoint_2D(i[0], i[1])
                    for edge in edges_from_line(ogr_geom, attrs, tolerance, simplify):
                        e1, e2, attr = edge
                        attr['Wkt'] = ogr_geom.ExportToWkt()
                        primal_merged.add_edge(e1, e2, attr_dict=attr)

        return prGraph(primal_merged, 'merged_id', make_feat=True), merged




