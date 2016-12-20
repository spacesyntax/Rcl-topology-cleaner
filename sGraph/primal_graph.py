
# general imports
import itertools
from qgis.core import QgsFeature, QgsGeometry, QgsField, QgsSpatialIndex, QgsVectorLayer, QgsVectorFileWriter, QgsPoint, QgsMapLayerRegistry, QgsFields
import networkx as nx
import ogr
from PyQt4.QtCore import QVariant, QObject, pyqtSignal

# plugin module imports

from generalFunctions import angle_3_points, keep_decimals
from plFunctions import pl_midpoint, point_is_vertex, find_vertex_index
from shpFunctions import edges_from_line

qgsflds_types = {u'Real': QVariant.Double , u'String': QVariant.String}

class prGraph(QObject):

    finished = pyqtSignal(object)
    error = pyqtSignal(Exception, basestring)
    progress = pyqtSignal(float)
    warning = pyqtSignal(str)

    def __init__(self, any_primal_graph, make_feat=True):
        QObject.__init__(self)
        self.obj = any_primal_graph
        keys = True
        self.n_attributes = len(self.obj.edges(data=True)[0][2].keys()) + 1
        self.uid_index = len(self.obj.edges(data=True)[0][2].keys())
        self.prflds = self.obj.edges(data=True, keys=True)[0][3].keys() + ['key']
        if make_feat:
            features = []
            count = 1
            for edge in self.obj.edges(data=True, keys= True):
                feat = QgsFeature()
                feat.setGeometry(QgsGeometry.fromWkt(edge[3]['Wkt']))
                feat.initAttributes(self.n_attributes)
                f_attr = edge[3]
                f_attr['key']= edge[2]
                feat.setAttributes([edge[3][attr] for attr in self.prflds])
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
        return { edge[2]: edge[3]['Wkt'] for edge in self.obj.edges(data=True, keys=True)}

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
        return {edge[2]: edge[3] for edge in self.obj.edges(data=True, keys=True)}

    # ------ fields

    def get_qgs_fields(self, qgsflds):
        prflds = self.prflds
        new_fields = []

        for i in prflds:
            if i in qgsflds.keys():
                new_fields.append(QgsField(i, qgsflds[i]))
            else:
                # make field of string type
                new_fields.append(QgsField(i, QVariant.String))
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

    # iterator of dual graph edges from prGraph edges

    def dl_edges_from_pr_graph(self, break_at_intersections, parallel_nodes, tolerance, angular_cost = False, polylines=False):
        geometries = self.get_geom_dict()

        f_count = 1
        feat_count = self.obj.__len__()

        for i, j in self.obj.adjacency_iter():

            is_parallel = False
            for n in parallel_nodes:
                if abs(i[0] - n[0]) < 10 ** (-(tolerance - 1)) and abs(i[1] - n[1]) < 10 ** (-(tolerance - 1)):
                    is_parallel = True

            if break_at_intersections and not is_parallel:
                if len(j.keys()) == 2:
                    edges = [g.keys().pop() for g in j.values()]
                else:
                    edges = []
            elif not break_at_intersections:
                # TODO restore connections
                edges = [v.keys().pop() for k, v in j.items()]
            else:
                edges = []

            self.progress.emit(10 * f_count / feat_count)
            f_count += 1

            for x in itertools.combinations(edges, 2):
                if angular_cost:
                    inter_point = geometries[x[0]].intersection(geometries[x[1]])
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
                    yield (x[0], x[1], {})

    # iterator of dual graph nodes from prGraph edges

    def dl_nodes_from_pr_graph(self, dlGrpah):
        for e in self.obj.edges_iter(keys=True):
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
            fields = QgsFields()
            for field in self.get_qgs_fields(qgsflds):
                fields.append(field)
            file_writer = QgsVectorFileWriter(path, encoding, fields, geom_type,
                                              crs, "ESRI Shapefile")
            if file_writer.hasError() != QgsVectorFileWriter.NoError:
                print "Error when creating shapefile: ", file_writer.errorMessage()
            del file_writer
            network = QgsVectorLayer(path, name, "ogr")
        # QgsMapLayerRegistry.instance().addMapLayer(network)
        pr = network.dataProvider()
        network.startEditing()
        if path is None:
            pr.addAttributes(self.get_qgs_fields(qgsflds))
        pr.addFeatures(self.features)
        network.commitChanges()
        return network

    def to_dual(self, break_at_intersections, parallel_nodes, tolerance, angular_cost=False, polylines=False):
        dual_graph = nx.MultiGraph()
        for edge in self.dl_edges_from_pr_graph(break_at_intersections, parallel_nodes, tolerance, angular_cost, polylines):
            e1, e2, attr = edge
            dual_graph.add_edge(e1, e2, attr_dict=attr)
        # add nodes (some lines are not connected to others because they are pl)
        for node in self.dl_nodes_from_pr_graph(dual_graph):
            dual_graph.add_node(node)

        return dual_graph

    # ----- ALTERATION OPERATIONS -----

    def find_breakages(self, col_id):
        geometries = self.get_geom_dict()
        geom_vertices = self.get_geom_vertices_dict()

        f_count = 1
        feat_count = self.obj.size()

        for feat, inter_lines in self.inter_lines_bb_iter():

            self.progress.emit(10 * f_count / feat_count)
            f_count += 1

            f_geom = geometries[feat]

            breakages = []
            type_error = []

            for i in f_geom.asPolyline():
                if f_geom.asPolyline().count(i) > 1:
                    point = QgsGeometry().fromPoint(QgsPoint(i[0],i[1]))
                    if point_is_vertex(point, f_geom):
                        breakages.append(point)

            is_closed = False
            if f_geom.asPolyline()[0] == f_geom.asPolyline()[-1]:
                is_closed = True

            is_orphan = True

            for line in inter_lines:
                g_geom = geometries[line]
                intersection = f_geom.intersection(g_geom)

                # intersecting geometries at point
                if intersection.wkbType() == 1 and point_is_vertex(intersection, f_geom):
                    breakages.append(intersection)
                    type_error.append('br')
                    is_orphan = False

                # TODO: test multipoints
                # intersecting geometries at multiple points
                elif intersection.wkbType() == 4:
                    for point in intersection.asGeometryCollection():
                        if point_is_vertex(point, f_geom):
                            breakages.append(point)
                            is_orphan = False
                            type_error.append('br')

                # overalpping geometries
                elif intersection.wkbType() == 2 and intersection.length() != f_geom.length():
                    point1 = QgsGeometry.fromPoint(QgsPoint(intersection.asPolyline()[0]))
                    point2 = QgsGeometry.fromPoint(QgsPoint(intersection.asPolyline()[-1]))
                    if point_is_vertex(point1, f_geom):
                        breakages.append(point1)
                        is_orphan = False
                        type_error.append('ovrlp')
                    if point_is_vertex(point2, f_geom):
                        breakages.append(point2)
                        is_orphan = False
                        type_error.append('ovrlp')

                # overalpping multi-geometries
                # every feature overlaps with itself as a multilinestring
                elif intersection.wkbType() == 5 and intersection.length() != f_geom.length():
                    point1 = QgsGeometry.fromPoint(QgsPoint(intersection.asGeometryCollection()[0].asPolyline()[0]))
                    point2 = QgsGeometry.fromPoint(QgsPoint(intersection.asGeometryCollection()[-1].asPolyline()[-1]))
                    if point_is_vertex(point1, f_geom):
                        is_orphan = False
                        breakages.append(point1)
                        type_error.append('ovrlp')
                    if point_is_vertex(point2, f_geom):
                        is_orphan = False
                        breakages.append(point2)
                        type_error.append('ovrlp')

            type_error = list(set(type_error))
            # add first and last vertex
            vertices = set([vertex for vertex in find_vertex_index(breakages, feat, geometries)])
            vertices = list(vertices) + [0] + [len(geom_vertices[feat]) - 1]
            vertices = list(set(vertices))
            vertices.sort()
            if len(vertices) > 2:
                if not col_id:
                    error = []
                else:
                    if len(type_error)==2:
                        error = ['br', 'ovrlp']
                    else:
                        error = type_error
                yield feat, vertices, error
            if is_orphan:
                vertices = []
                if is_closed:
                    if not col_id:
                        error = []
                    else:
                        error = ['closed polyline']
                    yield feat, vertices, error
                else:
                    if not col_id:
                        error = []
                    else:
                        error = ['orphan']
                    yield feat, vertices, error


    def break_graph(self, tolerance, simplify, col_id=None):
        count = 1
        geom_vertices = self.get_geom_vertices_dict()
        attr_dict = self.get_attr_dict()

        edges_to_remove = []
        edges_to_add = []

        breakages = []
        overlaps = []
        orphans = []
        closed_polylines = []

        for k, v, error in self.find_breakages(col_id):
            attrs = attr_dict[k]
            if col_id:
                if error == ['br', 'ovrlp']:
                    breakages.append(attrs[col_id])
                    overlaps.append(attrs[col_id])
                elif error == ['br']:
                    breakages.append(attrs[col_id])
                elif error == ['ovrlp']:
                    overlaps.append(attrs[col_id])
                elif error == ['orphan']:
                    orphans.append(attrs[col_id])
                elif error == ['closed polyline']:
                    closed_polylines.append(attrs[col_id])

            count_2 = 1
            edges_to_remove.append(k)

            # delete primal graph edge
            for ind, index in enumerate(v):
                if ind != len(v) - 1:
                    points = [geom_vertices[k][i] for i in range(index, v[ind + 1] + 1)]
                    new_key = k + '_br_' + str(count) + '_' + str(count_2)
                    ogr_geom = ogr.Geometry(ogr.wkbLineString)
                    for i in points:
                        ogr_geom.AddPoint_2D(i[0], i[1])
                    for edge in edges_from_line(ogr_geom, attrs, tolerance, simplify):
                        e1, e2, attr = edge
                        attr['Wkt'] = ogr_geom.ExportToWkt()
                        # TODO: check why breaking a graph results in nodes
                        edges_to_add.append((e1, e2, new_key, attr))
                    del ogr_geom
                    count_2 += 1
            count += 1

        pairs_to_rmv = [(i[0],i[1], i[2], i[3]) for i in self.obj.edges(data = True, keys=True) if i[2] in edges_to_remove]

        self.obj.remove_edges_from(pairs_to_rmv)

        self.obj.add_edges_from(edges_to_add)

        return prGraph(self.obj, make_feat=True), breakages, overlaps, orphans, closed_polylines

    # SOURCE ess toolkit
    def find_dupl_overlaps_ssx(self, parallel=True):
        geometries = self.get_geom_dict()
        uid = self.uid_to_fid

        f_count = 1
        feat_count = self.obj.size()

        for feat, inter_lines in self.inter_lines_bb_iter():

            self.progress.emit(10 * f_count / feat_count)
            f_count += 1

            parallels = []
            f_geom = geometries[feat]
            for line in inter_lines:
                g_geom = geometries[line]
                if uid[line] < uid[feat]:
                    # duplicate geometry
                    if f_geom.isGeosEqual(g_geom):
                        yield line, 'dupl'
                if line != feat:
                    endpoints = [g_geom.asPolyline()[0]] + [g_geom.asPolyline()[-1]] + [f_geom.asPolyline()[0]] + [f_geom.asPolyline()[-1]]
                    endpoints = list(set(endpoints))
                    if len(endpoints) == 2:
                        parallels.append(line)
                        matching_points = endpoints
            if len(parallels) > 0 and parallel:
                yield [matching_points, parallels + [feat]],  'parallel'

    def rmv_dupl_overlaps(self, col_id, parallel):
        edges_to_remove = []
        dupl = []
        attr_dict = self.get_attr_dict()
        parallel_con = {}
        parallel_nodes = []

        for edge, error in self.find_dupl_overlaps_ssx(parallel):
            if error == 'dupl':
                if col_id:
                    dupl.append(attr_dict[edge][col_id])
                edges_to_remove.append(edge)
            elif error == 'parallel' and parallel:
                endpoints = edge[0]
                for i in endpoints:
                    if i not in parallel_nodes:
                        parallel_nodes.append(i)
                parallels = edge[1]
                # TODO: add which connections to restore


        # TODO: test reconstructing the graph for speed purposes
        pairs_to_rmv = [(i[0], i[1], i[2], i[3]) for i in self.obj.edges(data=True, keys=True) if
                        i[2] in edges_to_remove]
        self.obj.remove_edges_from(pairs_to_rmv)

        return prGraph(self.obj, make_feat=True), dupl, parallel_con, parallel_nodes

    def add_edges(self, edges_to_add):
        pass

    def move_node(self, node, point_to_move_to):
        pass
