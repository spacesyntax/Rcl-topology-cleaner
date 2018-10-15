import itertools
from PyQt4.QtCore import QObject, pyqtSignal, QVariant
from qgis.core import QgsSpatialIndex, QgsGeometry, QgsDistanceArea, QgsFeature, QgsField, QgsFields
from collections import Counter

# read graph - as feat
class break_tools(QObject):

    finished = pyqtSignal(object)
    error = pyqtSignal(Exception, basestring)
    progress = pyqtSignal(float)
    warning = pyqtSignal(str)
    killed = pyqtSignal(bool)

    def __init__(self, layer, snap_threshold, angle_threshold, break_com_vertices, merge_method, collinear_threshold, remove_orphans, remove_islands, create_unlinks, create_errors):
        QObject.__init__(self)
        self.layer = layer
        self.snap_threshold = snap_threshold
        self.angle_threshold = angle_threshold
        self.break_com_vertices = break_com_vertices
        self.merge_method = merge_method
        self.collinear_threshold = collinear_threshold
        self.remove_orphans = remove_orphans
        self.remove_islands = remove_islands
        self.create_errors = create_errors
        self.create_unlinks = create_unlinks

        # internal
        self.spIndex = QgsSpatialIndex()
        self.ndSpIndex = QgsSpatialIndex()
        self.feats = {}
        self.topology = {}
        self.nodes_coords = {}

        self.edges_id = 0
        self.node_id = 0
        self.step = self.layer.featureCount()

        # errors (points and lines)
        self.empty_geometries = []
        self.points = [] #
        self.invalids = []
        self.mlparts = []
        self.orphans = []
        self.islands = []
        self.duplicates = []
        self.overlaps = [] # TODO if overlap not matching vertices of polyline
        self.snaps = [] #
        self.self_intersections = [] #
        self.closed_polylines = []
        self.break_points = [] #
        self.merges = [] #
        self.collinear = [] #

        # unlinks feats
        self.unlinks = {}

        self.node_prototype = QgsFeature()
        node_fields = QgsFields()
        node_fields.append(QgsField('id', QVariant.Int))
        self.node_prototype.setFields(node_fields)
        self.node_prototype.setAttributes([0])
        self.node_prototype.setGeometry(QgsGeometry())

        self.step = 20 / float(len(self.layer.featureCount()))


    def nodes_closest_iter(self):
        for k, v in self.nodes_coords.items():
            nd_geom = QgsGeometry.fromPoint(k)
            nd_buffer = nd_geom.buffer(self.snap_threshold, 29)
            closest_nodes = self.ndSpIndex.intersects(nd_buffer.boundingBox())
            closest_nodes = set(filter(lambda id: nd_geom.distance(self.nodes[id].geometry()) <= self.snap_threshold , closest_nodes))
            yield closest_nodes

    def con_comp(self, subset):
        for candidate in self.combined:
            if not candidate.isdisjoint(subset):
                candidate.update(subset)
                break
        else:
            self.combined.append(subset)
        return True

    def copy_feat(self, f, geom, id):
        copy_feat = QgsFeature(f)
        copy_feat.setGeometry(geom)
        copy_feat.setFeatureId(id)
        return copy_feat


    # 0. LOAD GRAPH FUNCTION -------------------------------------
    # only 1 time execution permitted

    def load_graph(self):
        self.nodes_coords = {}
        self.load_features_iter()
        self.clean_orphans_duplicates()

        if self.snap_threshold:
            res = map(lambda snode: self.ndSpIndex.insert(snode.feature), self.sNodes.values())

            # group based on distance
            self.combined = []
            res = map(lambda i: self.con_comp(i), self.nodes_closest_iter())
            new_node_ids = range(self.nodes_id, len(self.combined) + self.nodes_id)
            self.combined = dict(zip(new_node_ids, self.combined))
            self.nodes_id += len(self.combined)
            res = map(lambda (merged_node_id, group_nodes): self.snap_edges(group_nodes, merged_node_id),
                      self.combined.items())
            del res

        # del self.nodes_coords  # do not update self.nodes_coords
        return

    # 1. REMOVE ORPHANS/ DUPLICATES ------------------------------

    def clean_orphans_duplicates(self):
        # {frozenset} : edge
        node_node_dict, duplicates = {}, []
        for sedge in self.sEdges.values():
            delete = False
            if len(self.sNodes[self.sedge.startid]) == len(self.sNodes[self.sedge.endid]) == 1:
                self.orphans.append(sedge.id)
                del self.sNodes[self.sedge.startid]
                del self.sNodes[self.sedge.endid]
                delete = True
            else:
                try:
                    node_node_dict[frozenset({sedge.startid, sedge.endid})].append(sedge.id)
                    self.duplicates.append(sedge.id)
                    delete = True
                except KeyError:
                    node_node_dict[frozenset({sedge.startid, sedge.endid})] = [sedge.id]
            if delete:
                # if orphan nodes have been deleted - if duplicate nodes are managed by set structure
                del self.sEdges[sedge.id]
        return

    # 2. SNAP FUNCTION -------------------------------------------

    def snap_edges(self, group_nodes, merged_node_id):
        # create merged_node
        group_edges = map(lambda node: self.sNodes[node], group_nodes)
        group_edges = itertools.chain.from_iterable(group_edges)
        centroid = QgsGeometry.fromMultiPoint(
            [self.sNodes[node_id].feature.geometry().asPoint() for node_id in group_nodes]).centroid()
        merged_node = sNode(
            self.copy_feat(self.node_prototype, QgsGeometry.fromPoint(centroid), merged_node_id),
            merged_node_id, group_edges)
        self.sNodes[merged_node_id] = merged_node
        for edge in group_edges:
            edge_copy = self.sEdges(edge)
            if {edge_copy.startid}.intersection(group_nodes) == {edge_copy.startid}:
                edge_copy.updateStartNode(merged_node)
            if {edge_copy.endid}.intersection(group_nodes) == {edge_copy.endid}:
                edge_copy.updateEndNode(merged_node)
        # TODO: del self.sNodes
        return

    # 3. BREAK FUNCTION -------------------------------------------
    # break at common vertices
    # overlaps
    # closed polylines

    def break_edges(self):
        broken_sedges = {}
        for sedge in list(self.sEdges.values()):
            res = map(lambda broken_pl, broken_id: self.add_edge(self.copy_feat(sedge.feature, QgsGeometry.fromPolyline(broken_pl), broken_id)), self.break_edge_iter(sedge) )

    def add_edge(self, feature):
        pl = feature.geometry().asPolyline()
        startid, endid = self.create_topology(pl[0], pl[-1])
        self.sEdges[feature.id()] = sEdge(feature, startid, endid)
        return True

    def break_edge_iter(self, sedge):
        f_geom = sedge.feature.geometry()
        f_geom_pl = f_geom.asPolyline()
        interlines = filter(lambda line: f_geom.distance(self.sEdges[line].feature.geometry()) <= 0,
                            self.spIndex.intersects(f_geom.boundingBox()))
        break_points = []
        for line in interlines:
            inter = f_geom.intersection(self.sEdges[line].feature.geometry())
            if inter.wkbType() == 1:
                if len({inter.asPoint()}.intersection(set(f_geom_pl))) > 0:
                    break_points.append(inter.asPoint())
            elif inter.wkbType() == 4:
                for p in inter.asMultiPoint():
                    if len({p}.intersection(set(f_geom_pl))) > 0:
                        break_points += p
            elif inter.wkbType() == 2:
                for p in inter.asPolyline():
                    if len({p}.intersection(set(f_geom_pl))) > 0:
                        break_points += p
                        self.overlaps.update({line, sedge.id})
            elif inter.wkbType() == 5:
                for pl in inter.asMultiPolyline():
                    for p in pl:
                        if len({p}.intersection(set(f_geom_pl))) > 0:
                            break_points += p
                            self.overlaps.update({line, sedge.id})

        self.break_points.update(set(break_points))
        # TODO remove edge
        for points in :
            self.edges_id += 1
            yield broken_pl, self.edges_id - 1

    # 4. MERGE FUNCTION -------------------------------------------
    # merge between intersections OR
    # merge collinear

    def create_topology(self, startpoint, endpoint):
        try:
            start_id = self.nodes_coords[startpoint]
        except KeyError:
            self.nodes_coords[startpoint] = self.nodes_id
            start_id = self.nodes_id
            self.sNodes[start_id] = sNode(self.copy_feat(self.node_prototype, QgsGeometry.fromPoint(startpoint), start_id), start_id, {})
            self.nodes_id += 1
        try:
            end_id = self.nodes_coords[endpoint]
        except KeyError:
            self.nodes_coords[endpoint] = self.nodes_id
            end_id = self.nodes_id
            self.sNodes[end_id] = sNode(self.copy_feat(self.node_prototype, QgsGeometry.fromPoint(endpoint), end_id), end_id, {})
            self.nodes_id += 1

        self.sNodes[start_id].update({self.edges_id})
        self.sNodes[end_id].update({self.edges_id})

        return start_id, end_id

    def load_features(self):

        # NULL, points, invalids, mlparts # TODO: add dropZValue()
        for f in self.layer.getFeatures():

            #self.progress.emit(self.step)

            f_geom = f.geometry()
            f_geom_length = f_geom.length()

            if self.killed is True:
                break
            elif f_geom is NULL:
                self.empty_geometries.append(f.id())
            elif not f_geom.isGeosValid():
                self.invalids.append(f.id())
            elif f_geom_length == 0:
                self.points.append(f.id())
            elif 0 < f_geom_length < self.snap_threshold:
                pass # do not add to the graph - as it will be removed later
            elif f_geom.wkbType() == 2:
                f.setFeatureId(self.edges_id)
                f_pl = f_geom.asPolyline()
                self.spIndex.insertFeature(f)
                start_id, end_id = self.create_topology(f_pl[0], f_pl[-1])
                self.sEdges = sEdge(f, self.edges_id, start_id, end_id)
                self.edges_id += 1
            elif f_geom.wkbType() == 5:
                ml_segms = f_geom.asMultiPolyline()
                for ml in ml_segms:
                    ml_geom = QgsGeometry(ml)
                    ml_feat = self.copy_feat(f, ml_geom, self.edges_id)
                    self.spIndex.insertFeature(ml_feat)
                    f_pl = ml_geom.asPolyline()
                    start_id, end_id = self.create_topology(f_pl[0], f_pl[-1])
                    self.sEdges = sEdge(ml_feat, self.edges_id, start_id, end_id)
                    self.edges_id += 1

    def kill(self):
        self.killed = True