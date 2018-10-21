# general imports
import itertools
import operator
from PyQt4.QtCore import QObject, pyqtSignal, QVariant
from qgis.core import QgsGeometry, QgsSpatialIndex, QgsFields, QgsField, QgsFeature

# plugin module imports
try:
    from utilityFunctions import *
    from sNode import sNode
    from sEdge import sEdge
except ImportError:
    pass


prototype_fields = QgsFields()
prototype_fields.append(QgsField('id', QVariant.Int))
prototype_fields.append(QgsField('errors', QVariant.String))
prototype_error = QgsFeature()
prototype_error.setGeometry(QgsGeometry())
prototype_error.setFields(prototype_fields)
prototype_error.setAttributes([0, 'err'])

prototype_fields = QgsFields()
prototype_fields.append(QgsField('id', QVariant.Int))
prototype_unlink = QgsFeature()
prototype_unlink.setGeometry(QgsGeometry())
prototype_unlink.setFields(prototype_fields)
prototype_unlink.setAttributes([0])

class cleanTool(QObject):

    finished = pyqtSignal(object)
    error = pyqtSignal(Exception, basestring)
    progress = pyqtSignal(float)
    warning = pyqtSignal(str)
    killed = pyqtSignal(bool)

    def __init__(self, Snap, Break, Merge, Errors, Unlinks, Orphans):
        QObject.__init__(self)

        # settings
        self.Snap = Snap # - 1: no , any other > 0 : yes
        self.Break = Break # True/False
        self.Merge = Merge # 'between intersections', ('collinear', angle_threshold), None
        self.Errors = Errors # True/False
        self.Unlinks = Unlinks # True/False
        self.Orphans = Orphans # True/False

        # properties
        # sEdges
        self.sEdges = {}
        self.sEdgesId = 0
        self.sEdgesSpIndex = QgsSpatialIndex()

        # sNodes
        self.sNodes = {}
        self.sNodesId = 0
        self.sNodesQqgPoints = {}
        self.sNodesSpIndex = QgsSpatialIndex()

        self.total_progress = 0
        self.range = 6
        for i in [self.Orphans, self.Merge, self.Break, self.Snap]:
            if i is None or i is False:
                self.range -= 1
        self.range = 100/ float(self.range)
        self.step = 0

        # initiate errors
        # overlaps cannot be distinguished from breakages with this method

        # multilines
        #self.invalids, self.empty,
        self.duplicates, self.multiparts, self.points, self.orphans, self.closed_polylines, self.broken, self.merged, self.self_intersecting, self.snapped, self.unlinks =\
                 [], [], [], [], [], [], [], [], [], []
        self.errors_id = 0
        self.unlinks_id = 0


    # RUN --------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------

    def del_edge(self, edge_id):
        del self.sEdges[edge_id]
        return True

    def run(self, layer):

        # 0. LOAD GRAPH
        # errors: points, invalids, null, multiparts
        self.step = self.layer.featureCount()/ float(self.range)
        res = map(lambda f:self.sEdgesSpIndex.insertFeature(f), self.features_iter(layer))

        # 1. BREAK AT COMMON VERTICES
        # errors: duplicates, broken, self_intersecting (overlapping detected as broken)
        if self.Break:
            # update sEdges where necessary
            self.step = len(self.sEdges) / float(self.range)
            broken_edges = map(lambda (sedge, vertices): self.breakAtVertices(sedge, vertices), self.breakFeaturesIter())
            res = map(lambda edge_id: self.del_edge(edge_id), filter(lambda edge_id: edge_id is not None, broken_edges))

        # 2. SNAP
        # errors: snapped
        self.step = len(self.sEdges) / float(self.range)
        res = map(lambda (edgeid, qgspoint): self.createTopology(qgspoint, edgeid), self.endpointsIter())
        if self.Snap != -1:
            # group based on distance - create subgraph
            self.step = (len(self.sNodes) / float(self.range)) / float(2)
            subgraph_nodes = self.subgraph_nodes()
            self.step = (len(subgraph_nodes) / float(self.range))/ float(2)
            res = map(lambda nodes: self.mergeNodes(nodes), self.con_comp_iter(subgraph_nodes))

        # 3. MERGE
        # errors merged
        if self.Merge:
            if self.Merge == 'between_intersections':
                self.step = (len(self.sNodes) / float(self.range)) / float(2)
                subgraph_nodes = self.subgraph_con2_nodes()
                self.step = (len(subgraph_nodes) / float(self.range)) / float(2)
                res = map(lambda group_edges: self.merge_edges(group_edges), self.con_comp_iter(subgraph_nodes))
            elif self.Merge[0] == 'collinear':
                self.step = (len(self.sNodes) / float(self.range)) / float(2)
                subgraph_nodes = self.subgraph_collinear_nodes()
                self.step = (len(subgraph_nodes) / float(self.range)) / float(2)
                res = map(lambda (group_edges): self.merge_edges(group_edges), self.con_comp_iter(subgraph_nodes))

        # 4. ORPHANS
        # errors orphans, closed polylines
        if self.Orphans:
            self.step = len(self.sEdges) / float(self.range)
            res = map(lambda sedge: self.del_edge_w_nodes(sedge.id, sedge.getStartNode(), sedge.getEndNode()),
                      filter(lambda edge: self.sNodes[edge.getStartNode()].getConnectivity() ==
                            self.sNodes[edge.getEndNode()].getConnectivity() == 1, self.sEdges.values()))

        error_features = []
        if self.Errors:
            all_errors = []
            all_errors += zip(self.multiparts, ['multipart'] * len(self.multiparts))
            all_errors += zip(self.points, ['point'] * len(self.points))
            all_errors += zip(self.orphans, ['orphan'] * len(self.orphans))
            all_errors += zip(self.closed_polylines, ['closed polyline'] * len(self.closed_polylines))
            all_errors += zip(self.duplicates, ['duplicate'] * len(self.duplicates))
            all_errors += zip(self.broken, ['broken'] * len(self.broken))
            all_errors += zip(self.merged, ['pseudo'] * len(self.merged))
            all_errors += zip(self.self_intersecting, ['self intersection'] * len(self.self_intersecting))
            all_errors += zip(self.snapped, ['snapped'] * len(self.snapped))
            error_features = [self.create_error_feat(k, [i[1] for i in list(g)]) for k, g in itertools.groupby(sorted(all_errors), operator.itemgetter(0))]

        unlink_features = []
        if self.Unlinks:
            unlink_features = map(lambda p: self.create_unlink_feat(p), self.unlinks)

        return map(lambda e: e.feature, self.sEdges.values()), unlink_features, error_features

    def create_error_feat(self, p, errors):
        err_feat = QgsFeature(prototype_error)
        err_feat.setFeatureId(self.errors_id)
        err_feat.setAttributes([self.errors_id, errors])
        err_feat.setGeometry(QgsGeometry.fromPoint(p))
        self.errors_id += 1
        return err_feat

    def create_unlink_feat(self, p):
        unlink_feat = QgsFeature(prototype_unlink)
        unlink_feat.setFeatureId(self.unlinks_id)
        unlink_feat.setAttributes([self.unlinks_id])
        unlink_feat.setGeometry(QgsGeometry.fromPoint(p))
        self.unlinks_id += 1
        return unlink_feat

    # 0. LOAD GRAPH OPERATIONS -----------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------

    def features_iter(self, layer):

        # detecting errors:
        # NULL, point, invalid, multipart geometries - snap errors will be added later
        # updating sEdges

        for f in layer.getFeatures():

            self.total_progress += self.step
            self.progress.emit(self.total_progress)

            f_geom = f.geometry()

            # dropZValue if geometry is 3D
            if f.geometry().geometry().is3D():
                    f.geometry().geometry().dropZValue()

            f_geom_length = f_geom.length()

            if 0 < f_geom_length <= self.Snap: # if self.Snap == -1 never valid
                # do not add as error, it will be added later
                pass
            elif f_geom.wkbType() == 2:
                f.setFeatureId(self.sEdgesId)
                self.sEdges[self.sEdgesId] = sEdge(self.sEdgesId, f, []) # empty topology - topology is (end, start)
                self.sEdgesId += 1
                yield f
            elif f_geom is NULL:
                #self.empty_geometries.append()
                pass
            elif not f_geom.isGeosValid():
                #self.invalids.append(copy_feature(f, QgsGeometry(), f.id()))
                pass
            elif f_geom_length <= 0:
                self.points.append(f_geom.asPoint())
            elif f_geom.wkbType() == 5:
                ml_segms = f_geom.asMultiPolyline()
                for ml in ml_segms:
                    ml_geom = QgsGeometry(ml)
                    ml_feat = copy_feat(f, ml_geom, self.sEdgesId)
                    self.multiparts.append(ml_geom.asPolyline()[0])
                    self.multiparts.append(ml_geom.asPolyline()[-1])
                    self.sEdges[self.sEdgesId] = sEdge(self.sEdgesId, ml_feat, [])
                    self.sEdgesId += 1
                    yield ml_feat
            elif self.killed is True:
                break

    def createTopology(self, qgspoint, fid):
        try:
            exNodeId = self.sNodesQqgPoints[qgspoint]
            self.sNodes[exNodeId].topology.append(fid)
            self.sEdges[fid].nodes.append(exNodeId) # ATTENTION: order is controlled by endpointsIter -> order reversed
        except KeyError:
            self.sNodes[self.sNodesId] = sNode(self.sNodesId, [fid], qgspoint)
            self.sNodesQqgPoints[qgspoint] = self.sNodesId
            self.sEdges[fid].nodes.append(self.sNodesId)
            if self.Snap != -1:
                self.sNodesSpIndex.insertFeature(self.sNodes[self.sNodesId].getFeature())
            self.sNodesId += 1
        return True

    def endpointsIter(self):
        for edge in self.sEdges.values():

            self.total_progress += self.step
            self.progress.emit(self.total_progress)

            f = edge.feature
            pl = f.geometry().asPolyline()
            for end in (pl[0], pl[-1]): # keep order nodes = [startpoint, endpoint]
                yield edge.id, end

    # 1. BREAK AT COMMON VERTICES---------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------

    def breakAtVertices(self, sedge_feat, point_series):
        if len(point_series) > 1:
            for points in point_series:
                geom = QgsGeometry.fromPolyline(points)
                broken_feature = copy_feature(sedge_feat, QgsGeometry.fromPolyline(points), self.sEdgesId)
                if 0 < geom.length() < self.Snap:
                    pass
                else:
                    self.sEdges[self.sEdgesId] = sEdge(self.sEdgesId, broken_feature, [])
                    self.sEdgesId += 1
            # del after adding all
            return sedge_feat.id()
        else:
            return None


    def breakFeaturesIter(self):

        for id, sedge in self.sEdges.items():

            self.total_progress += self.step
            self.progress.emit(self.total_progress)

            f_geom = sedge.feature.geometry()
            f_pl = f_geom.asPolyline()
            f_pl_indices = dict(zip(f_pl, range(0, len(f_pl))))
            vertices = [0, len(f_pl)-1]

            for k, v in dict((x, duplicates(f_pl, x)) for x in set(f_pl) if f_pl.count(x) > 1).items():
                if len(v) > 1:
                    self.self_intersecting.append(f_pl[v[0]])
                    vertices += v

            intersecting_edges = filter(lambda inter_edge: self.sEdges[inter_edge].id != id
                                                   and f_geom.distance(self.sEdges[inter_edge].feature.geometry()) <= 0,
                                        self.sEdgesSpIndex.intersects(f_geom.boundingBox()))
            # check for common vertices
            common_points = set([])
            for unq_inter_id in intersecting_edges:
                g_geom = self.sEdges[unq_inter_id].feature.geometry()

                if f_geom.isGeosEqual(g_geom):
                    del self.sEdges[id]
                    self.duplicates.append(f_pl_indices[0])
                    self.duplicates.append(f_pl[-1])

                elif self.Unlinks and f_geom.crosses(g_geom):
                    crossing_point = f_geom.intersection(g_geom)
                    if crossing_point.wkbType() == 1:
                        p = crossing_point.asPoint()
                        #if p not in f_pl:
                        self.unlinks.append(p)
                    elif crossing_point.wkbType() == 4:
                        for cr_point in crossing_point.asMultiPoint(): #TODO if not end one or other 
                            #if cr_point not in f_pl:
                            self.unlinks.append(cr_point)
                    # TODO: unlink should not be a vertex in f_geom/g_geom what if OS? remove/move vertex?? if unlink not added in common _points

                common_points.update(set(f_pl[1:-1]).intersection(set(g_geom.asPolyline())))
                # TODO if self.Errors check for overlaps
                vertices += [f_pl_indices[p] for p in common_points]

            vertices = sorted(set(vertices))
            if len(common_points) > 0:
                self.broken += list(common_points)

            point_series = map(lambda (index_start, index_end): f_pl[index_start: index_end + 1], zip(vertices[:-1], vertices[1:]))

            yield sedge.feature, point_series

    # 2. SNAP ENDPOINTS ------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------

    def subgraph_nodes(self):

        closestNodes = {}
        for id, snode in self.sNodes.items():

            self.total_progress += self.step
            self.progress.emit(self.total_progress)
            # emit signal
            nd_geom = snode.geometry
            nd_buffer = nd_geom.buffer(self.Snap, 29)
            closest_nodes = self.sNodesSpIndex.intersects(nd_buffer.boundingBox())
            closest_nodes = set(filter(lambda id: nd_geom.distance(self.sNodes[id].geometry) <= self.Snap, closest_nodes))
            if len(closest_nodes) > 1:
                # create sNodes, incl. itself (snode)
                for node in closest_nodes:
                    topology = set(closest_nodes)
                    topology.remove(node)
                    try:
                        closestNodes[node].topology.update(topology)
                    except KeyError:
                        p = self.sNodes[node].point
                        closestNodes[node] = sNode(node, topology, p)
                        self.snapped.append(p)
        return closestNodes

    def con_comp_iter(self, any_nodes_dict):
        components_passed = set([])
        for id, node in any_nodes_dict.items():

            self.total_progress += self.step
            self.progress.emit(self.total_progress)

            if {id}.isdisjoint(components_passed):
                group = [[id]]
                candidates = ['dummy', 'dummy']
                while len(candidates) > 0:
                    flat_group = group[:-1] + group[-1]
                    candidates = map(lambda last_visited_node: set(any_nodes_dict[last_visited_node].topology).difference(set(flat_group)) , group[-1])
                    candidates = list(set(itertools.chain.from_iterable(candidates)))
                    group = flat_group + [candidates]
                    components_passed.update(set(candidates))
                yield group[:-1]

    def mergeNodes(self, nodes):
        self.snapped += [self.sNodes[node].point for node in nodes]
        connected_edges = list(itertools.chain.from_iterable([self.sNodes[node].topology for node in nodes]))
        qgspoints = [self.sNodes[node].point for node in nodes]
        mergedSNode = sNode(self.sNodesId, connected_edges, QgsGeometry.fromMultiPoint(qgspoints).centroid().asPoint())
        self.sNodes[self.sNodesId] = mergedSNode
        edges_to_rem = []
        for edge in connected_edges:
            # update edge #TODO
            if len((set(self.sEdges[edge].nodes)).intersection(set(nodes))) == 2:
                edges_to_rem.append(edge)
            else:
                self.sEdges[edge].replaceNodes(nodes, mergedSNode)
        self.sNodes[self.sNodesId].topology = [x for x in self.sNodes[self.sNodesId].topology if x not in edges_to_rem]
        for node in nodes:
            del self.sNodes[node]
        self.sNodesId += 1
        return edges_to_rem

    # 3. MERGE BETWEEN INTERSECTIONS -----------------------------------------------------------------------------------
    #    MERGE COLLINEAR SEGMENTS --------------------------------------------------------------------------------------

    def subgraph_con2_nodes(self):
        subgraph_nodes = {}
        for id, snode in self.sNodes.items():

            self.total_progress += self.step
            self.progress.emit(self.total_progress)

            con_edges = [e for e in snode.topology if len(self.sEdges[e].nodes) != 1]
            if len(con_edges) == 2:
                self.merged.append(snode.point)
                try:
                    subgraph_nodes[con_edges[0]].topology.append(con_edges[1])
                except KeyError:
                    centroid = self.sEdges[con_edges[0]].feature.geometry().centroid().asPoint()
                    subgraph_nodes[con_edges[0]] = sNode(con_edges[0], [con_edges[1]], centroid)
                try:
                    subgraph_nodes[con_edges[1]].topology.append(con_edges[0])
                except KeyError:
                    centroid = self.sEdges[con_edges[1]].feature.geometry().centroid().asPoint()
                    subgraph_nodes[con_edges[1]] = sNode(con_edges[1], [con_edges[0]], centroid)
        return subgraph_nodes

    def subgraph_collinear_nodes(self):
        subgraph_nodes = {}
        for id, snode in self.sNodes.items():

            self.total_progress += self.step
            self.progress.emit(self.total_progress)

            con_edges = [e for e in snode.topology if len(self.sEdges[e].nodes) != 1]
            if len(con_edges) == 2:
                sedge1 = self.sEdges[con_edges[0]]
                sedge2 = self.sEdges[con_edges[1]]
                nodes1 = sedge1.nodes
                nodes2 = sedge2.nodes
                n2 = [n for n in nodes1 if n in nodes2][0]
                n1 = [n for n in nodes1 if n != n2][0]
                n3 = [n for n in nodes2 if n != n2][0]
                p2 = self.sNodes[n2].point
                p1 = self.sNodes[n1].point
                p3 = self.sNodes[n3].point
                # if polyline
                if p1 == sedge1.feature.geometry().asPolyline()[0]:
                    p1 = sedge1.feature.geometry().asPolyline()[-2]
                else:
                    p1 = sedge1.feature.geometry().asPolyline()[1]
                if p3 == sedge2.feature.geometry().asPolyline()[0]:
                    p3 = sedge2.feature.geometry().asPolyline()[-2]
                else:
                    p3 = sedge2.feature.geometry().asPolyline()[1]
                if angle_3_points(p1, p2, p3) <= self.Merge[1]:
                    self.merged.append(snode.point)
                    try:
                        subgraph_nodes[con_edges[0]].topology.append(con_edges[1])
                    except KeyError:
                        centroid = sedge1.feature.geometry().centroid().asPoint()
                        subgraph_nodes[con_edges[0]] = sNode(con_edges[0], [con_edges[1]], centroid)
                    try:
                        subgraph_nodes[con_edges[1]].topology.append(con_edges[0])
                    except KeyError:
                        centroid = sedge2.feature.geometry().centroid().asPoint()
                        subgraph_nodes[con_edges[1]] = sNode(con_edges[1], [con_edges[0]], centroid)
        return subgraph_nodes

    def merge_edges(self, group_edges):
        group_nodes = [self.sEdges[e].nodes for e in group_edges]
        second_start = set(group_nodes[0]).intersection(set(group_nodes[1]))
        second_end = set(group_nodes[-2]).intersection(set(group_nodes[-1]))
        start = [n for n in group_nodes[0] if n != second_start].pop()
        end = [n for n in group_nodes[-1] if n != second_end].pop()
        merged_feat = merge_features([self.sEdges[edge].feature for edge in group_edges], self.sEdgesId)
        merged_sedge = sEdge(self.sEdgesId, merged_feat, [start, end])
        self.sEdges[self.sEdgesId] = merged_sedge
        self.sEdgesId += 1
        # topology not updated !
        for e in group_edges:
            del self.sEdges[e]
        return group_edges

    # 4. REMOVE ORPHANS -----------------------------------------------------------------------------------
    # -----------------------------------------------------------------------------------------------------

    def del_edge_w_nodes(self, edge_id, start, end):

        self.total_progress += self.step
        self.progress.emit(self.total_progress)

        del self.sEdges[edge_id]
        if start == end:
            self.closed_polylines.append(self.sNodes[start].point)
        else:
            self.orphans.append(self.sNodes[start].point)
            self.orphans.append(self.sNodes[end].point)
        del self.sNodes[start]
        del self.sNodes[end]
        return True

    def kill(self):
        self.killed = True