

# general imports
import itertools
from PyQt4.QtCore import QVariant
import networkx as nx
import ogr

# plugin module imports

from generalFunctions import angle_3_points, keep_decimals
from plFunctions import pl_midpoint, point_is_vertex, find_vertex_index
from shpFunctions import edges_from_line


qgsflds_types = {u'Real': QVariant.Double , u'String': QVariant.String}

class prGraph:

    def __init__(self, any_primal_graph, id_column, make_feat = True):
        self.obj = any_primal_graph
        self.uid = id_column
        self.n_attributes = len(self.obj.edges(data=True)[0][2].keys())
        self.uid_index = (self.obj.edges(data=True)[0][2].keys()).index(self.uid)
        self.prflds = self.obj.edges(data=True)[0][2].keys()
        # get features
        # these features do not have fields and feature ids
        if make_feat:
            features = []
            count = 1
            for edge in self.obj.edges(data=True):
                feat = QgsFeature()
                feat.setGeometry(QgsGeometry.fromWkt(edge[2]['Wkt']))
                feat.initAttributes(self.n_attributes)
                feat.setAttributes([edge[2][attr] for attr in self.prflds])
                feat.setFeatureId(count)
                features.append(feat)
                count += 1
            self.features = features
            self.fid_to_uid = {i.id(): i[self.uid_index] for i in self.features}
            self.uid_to_fid = {i[self.uid_index]: i.id() for i in self.features}

    # ----- ANALYSIS OPERATIONS -----

    # ----- geometry

    # dictionary uid: wkt representation
    def get_wkt_dict(self):
        return {edge[2][self.uid]: edge[2]['Wkt'] for edge in self.obj.edges(data=True)}

    # dictionary uid: qgs geometry
    def get_geom_dict(self):
        return {edge: QgsGeometry.fromWkt(wkt) for edge, wkt in self.get_wkt_dict().items()}

    # dictionary uid: geometry vertices
    def get_geom_vertices_dict(self):
        return {edge: edge_geom.asPolyline() for edge, edge_geom in self.get_geom_dict().items()}

    # dictionary uid: centroid
    # TODO: some of the centroids are not correct
    def get_centroids_dict(self):
        return {edge: pl_midpoint(edge_geom) for edge, edge_geom in self.get_geom_dict().items()}

    # ----- attributes

    # dictionary uid: attributes
    def get_attr_dict(self):
        return {edge[2][self.uid]: edge[2] for edge in self.obj.edges(data=True)}

    # ------ fields

    def get_qgs_fields(self, qgsflds):
        prflds = self.prflds
        new_fields = []

        # TODO: work with field type not name (for example you may have Integer64)

        for i in prflds:
            if i in qgsflds.keys():
                new_fields.append(QgsField(i, qgsflds_types[qgsflds[i]]))
            else:
                # make field of string type
                new_fields.append(QgsField(i, qgsflds_types[u'String']))
        return new_fields

    # ----- GEOMETRY ITERATORS -----

    # ----- intersecting lines

    # based on bounding box
    def inter_lines_bb_iter(self):
        fid = self.fid_to_uid
        spIndex = QgsSpatialIndex()  # create spatial index object
        # insert features to index
        for f in self.features:
            spIndex.insertFeature(f)
        # find lines intersecting other linesp
        for i in self.features:
            # bbox_points = find_max_bbox(i.geometry())
            inter_lines = spIndex.intersects(i.geometry().boundingBox())
            yield fid[i.id()], [fid[line] for line in inter_lines]

    # ----- TOPOLOGY OPERATIONS -----

    # topology iterator ( point_coord : [lines] )

    def topology_iter(self, break_at_intersections):
        if break_at_intersections:
            for i, j in self.obj.adjacency_iter():
                edges = [v.values()[0][self.uid] for k, v in j.items() if len(j) == 2]
                yield i, edges
        else:
            for i, j in self.obj.adjacency_iter():
                edges = [v.values()[0][self.uid] for k, v in j.items()]
                yield i, edges

    # iterator of dual graph edges from prGraph edges

    def dl_edges_from_pr_graph(self, break_at_intersections, angular_cost = True, polylines=False):
        geometries = self.get_geom_dict()
        for point, edges in self.topology_iter(break_at_intersections):
            for x in itertools.combinations(edges, 2):
                inter_point = geometries[x[0]].intersection(geometries[x[1]])
                if angular_cost:
                    if polylines:
                        vertex1 = geometries[x[0]].asPolyline()[-2]
                        if inter_point.asPoint() == geometries[x[0]].asPolyline()[0]:
                            vertex1 = geometries[x[0]].asPolyline()[1]
                        vertex2 = geometries[x[1]].asPolyline()[-2]
                        if inter_point.asPoint() == geometries[x[1]].asPolyline()[0]:
                            vertex2 = geometries[x[1]].asPolyline()[1]
                    else:
                        vertex1 = geometries[x[0]].asPolyline()[0]
                        if inter_point.asPoint() == geometries[x[0]].asPolyline()[0]:
                            vertex1 = geometries[x[0]].asPolyline()[-1]
                        vertex2 = geometries[x[1]].asPolyline()[0]
                        if inter_point.asPoint() == geometries[x[1]].asPolyline()[0]:
                            vertex2 = geometries[x[1]].asPolyline()[-1]
                    angle = angle_3_points(inter_point, vertex1, vertex2)
                    yield (x[0], x[1], {'cost': angle})
                else:
                    yield x

    # iterator of dual graph nodes from prGraph edges

    def dl_nodes_from_pr_graph(self, dlGrpah):
        for e in self.obj.edges_iter(data=self.uid):
            if e[2] not in dlGrpah.nodes():
                yield e[2]

    def features_to_multigraph(self, fields, tolerance=None, simplify=True):
        net = nx.MultiGraph()
        for f in self.features:
            flddata = f.attributes
            g = f.geometry()
            attributes = dict(zip(fields, flddata))
            # Note:  Using layer level geometry type
            if g.wkbType() == 2:
                for edge in edges_from_line(g, attributes, tolerance, simplify):
                    e1, e2, attr = edge
                    net.add_edge(e1, e2, attr_dict=attr)
            elif g.wkbType() == 5:
                for geom_i in range(g.asGeometryCollection()):
                    for edge in edges_from_line(geom_i, attributes, tolerance, simplify):
                        e1, e2, attr = edge
                        net.add_edge(e1, e2, attr_dict=attr)
        return net

    # ----- TRANSLATION OPERATIONS -----

    def to_shp(self, path, name, crs, encoding, geom_type, qgsflds):
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
        QgsMapLayerRegistry.instance().addMapLayer(network)
        pr = network.dataProvider()
        network.startEditing()
        pr.addAttributes(self.get_qgs_fields(qgsflds))
        pr.addFeatures(self.features)
        network.commitChanges()
        return network

    def to_dual(self, break_at_intersections, angular_cost=True, polylines=False):
        dual_graph = nx.MultiGraph()
        # TODO: check if add_edge is quicker
        dual_graph.add_edges_from(
            [edge for edge in self.dl_edges_from_pr_graph(break_at_intersections, angular_cost, polylines)])
        # add nodes (some lines are not connected to others because they are pl)
        # TODO: add node if node not in graph
        dual_graph.add_nodes_from(
            [node for node in self.dl_nodes_from_pr_graph(dual_graph)])
        return dual_graph

    # ----- ALTERATION OPERATIONS -----

    def find_breakages(self):
        geometries = self.get_geom_dict()
        for feat, inter_lines in self.inter_lines_bb_iter():
            f_geom = geometries[feat]
            breakages = []
            for line in inter_lines:
                g_geom = geometries[line]
                intersection = f_geom.intersection(g_geom)
                # intersecting geometries at point
                if intersection.wkbType() == 1 and point_is_vertex(intersection, f_geom):
                    breakages.append(intersection)
                # TODO: test multipoints
                #intersecting geometries at multiple points
                elif intersection.wkbType() == 4:
                    for point in intersection.asGeometryCollection():
                        if point_is_vertex(intersection, f_geom):
                            breakages.append(point)
                # overalpping geometries
                elif intersection.wkbType() == 2:
                    breakages += [QgsGeometry.fromPoint(QgsPoint(intersection.asPolyline()[0])), QgsGeometry.fromPoint(QgsPoint(intersection.asPolyline()[-1]))]
                elif intersection.wkbType() == 5:
                    breakages += [QgsGeometry.fromPoint(QgsPoint(intersection.asGeometryCollection()[0].asPolyline()[0])), QgsGeometry.fromPoint(QgsPoint(intersection.asGeometryCollection()[-1].asPolyline()[-1]))]
            if len(breakages) > 0:
                yield feat, set([vertex for vertex in find_vertex_index(breakages, feat, geometries)])

    def break_graph(self, tolerance, simplify):
        count = 1
        geom_vertices = self.get_geom_vertices_dict()
        attr_dict = self.get_attr_dict()
        edges = { edge[2][self.uid]: (edge[0], edge[1]) for edge in self.obj.edges(data=True)}
        edges_to_remove = []
        edges_to_add = []

        for k, v in self.find_breakages():
            attrs = attr_dict[k]
            # add first and last vertex
            v = list(v) + [0] + [len(geom_vertices[k]) - 1]
            v = list(set(v))
            v.sort()
            count_2 = 1
            edges_to_remove.append(edges[k])
            # delete primal graph edge
            for ind, index in enumerate(v):
                if ind != len(v) - 1:
                    points = [geom_vertices[k][i] for i in range(index, v[ind + 1] + 1)]
                    attrs['broken_id'] = attrs[self.uid] + '_br_' + str(count) + '_' + str(count_2)
                    ogr_geom = ogr.Geometry(ogr.wkbLineString)
                    for i in points:
                        ogr_geom.AddPoint_2D(i[0], i[1])
                    for edge in edges_from_line(ogr_geom, attrs, tolerance, simplify):
                       e1, e2, attr = edge
                       attr['Wkt'] = ogr_geom.ExportToWkt()
                       edges_to_add.append((e1, e2, attr))
                    del ogr_geom
                    count_2 += 1
            count += 1

        self.obj.remove_edges_from(edges_to_remove)

        # update new key attribute

        for edge in self.obj.edges(data=True):
            edge[2]['broken_id'] = edge[2][self.uid]

        self.obj.add_edges_from(edges_to_add)

        return prGraph(self.obj, 'broken_id', make_feat=True)

    def find_dupl_overlaps(self):
        geometries = self.get_geom_dict()
        uid = self.uid_to_fid
        for feat, inter_lines in self.inter_lines_bb_iter():
            f_geom = geometries[feat]
            for line in inter_lines:
                g_geom = geometries[line]
                intersection = f_geom.intersection(g_geom)
                if intersection.wkbType() == 2 and g_geom.length() < f_geom.length():
                    yield line, 'del overlap'
                elif g_geom.length() == f_geom.length() and uid[line] < uid[feat]:
                    yield feat, 'del duplicate'

    # SOURCE ess toolkit
    def find_dupl_overlaps_ssx(self):
        geometries = self.get_geom_dict()
        uid = self.uid_to_fid
        for feat, inter_lines in self.inter_lines_bb_iter():
            f_geom = geometries[feat]
            for line in inter_lines:
                g_geom = geometries[line]
                if uid[line] < uid[feat]:
                    # duplicate geometry
                    if f_geom.isGeosEqual(g_geom):
                        yield line, 'del duplicate'
                    # geometry overlaps
                    #if f_geom.overlaps(g_geom):
                    #    yield feat, 'del overlap'

    # TODO: test speed
    def get_invalid_duplicate_geoms_ids(self):
        geometries = self.get_geom_dict()
        dupl_geoms_ids = []
        list_lengths = [keep_decimals(i.geometry().length(), 6) for i in shp.getFeatures()]
        dupl_lengths = list(set([k for k, v in Counter(list_lengths).items() if v > 1]))
        for item in dupl_lengths:
            dupl_geoms_ids.append([i[0] for i in zip(count(), list_lengths) if i[1] == item])
        #for i in dupl_geoms_ids:
        #    i.remove(i[0])
        dupl_geoms_ids_to_rem = [x for x in dupl_geoms_ids[1:]]

        return dupl_geoms_ids_to_rem

    def rmv_dupl_overlaps(self):
        edges = {edge[2][self.uid]: (edge[0], edge[1]) for edge in self.obj.edges(data=True)}
        edges_to_remove = []

        # TODO: remove edge with sepcific attributes
        for edge, action in self.find_dupl_overlaps_ssx():
            edges_to_remove.append(edges[edge])

        # TODO: test reconstructing the graph for speed purposes
        self.obj.remove_edges_from(edges_to_remove)

        return prGraph(self.obj, self.uid, make_feat=True)

    def add_edges(self, edges_to_add):
        pass

    def move_node(self, node, point_to_move_to):
        pass
