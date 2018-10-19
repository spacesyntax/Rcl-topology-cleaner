# general imports
import itertools
import operator
from PyQt4.QtCore import QObject, pyqtSignal
from collections import Counter
from qgis.core import QgsGeometry, QgsSpatialIndex

# plugin module imports
try:
    from sGraph.ss.utilityFunctions import *
    from sNode import sNode
    from sEdge import sEdge
except ImportError:
    pass


class cleanTool(QObject):

    finished = pyqtSignal(object)
    error = pyqtSignal(Exception, basestring)
    progress = pyqtSignal(float)
    warning = pyqtSignal(str)
    killed = pyqtSignal(bool)

    def __init__(self, Snap, Break, Merge, Errors, Unlinks):
        QObject.__init__(self)

        # settings
        self.Snap = Snap # - 1: no , any other > 0 : yes
        self.Break = Break # True/False
        self.Merge = Merge # 'between intersections', ('collinear', angle_threshold), None
        self.Errors = Errors # True/False
        self.Unlinks = Unlinks # True/False

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

        # initiate errors
        # overlaps cannot be distinguished from breakages with this method
        self.points, self.invalids, self.empty, self.multiparts, self.orphans, self.closed_polylines, \
                self.broken, self.merged, self.self_intersecting, self.disconnections, self.unlinks =\
                [], [], [], [], [], [], [], [], [], [], []


    # RUN --------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------

    def del_edge(self, edge_id):
        del self.sEdges[edge_id]
        return True

    def del_edge_w_nodes(self, edge_id, start, end):
        del self.sEdges[edge_id]
        del self.sNodes[start]
        del self.sNodes[end]
        return True

    def run(self, layer):

        # 0. LOAD GRAPH
        # TODO: errors
        # points, snap, null
        res = map(lambda f:self.sEdgesSpIndex.insertFeature(f), self.features_iter(layer))

        # 1. BREAK AT COMMON VERTICES
        if self.Break:
            # update sEdges where necessary
            # TODO: errors - return vertices
            # duplicate points, broken points, overlapping points
            broken_edges = map(lambda (sedge, vertices): self.breakAtVertices(sedge, vertices), self.breakFeaturesIter())
            # delete broken edges
            res = map(lambda edge_id: self.del_edge(edge_id), filter(lambda edge_id: edge_id is not None, broken_edges))

        # 2. SNAP
        # create topology iter (in 0)
        res = map(lambda (edgeid, qgspoint): self.createTopology(qgspoint, edgeid), self.endpointsIter())

        if self.Snap != -1:
            # group based on distance - create subgraph
            # for every group create sNode, del sNodes, update sEdges
            # TODO: errors
            # snap
            res = map(lambda nodes: self.mergeNodes(nodes), self.con_comp_iter(self.subgraph_nodes()))

        if self.Orphans:
            # TODO: errors
            # orphans, closed polylines
            res = map(lambda edge_id: self.del_edge_w_nodes(edge_id, self.sEdges[edge_id].getStartNode(),  self.sEdges[edge_id].getEndNode(),),
                      filter(lambda edge: self.sNodes[self.sEdges[edge].getStartNode()].getConnectivity() ==
                            self.sNodes[self.sEdges[edge].getStartNode()].getConnectivity() == 1, self.sEdges.values()))
        # 3. MERGE
        if self.Merge:
            # TODO: errors
            # pseudo nodes, orphans
            if self.Merge == 'between_intersections':
                res = map(lambda group_edges: self.merge_edges(group_edges), self.con_comp_con_2_iter())
            elif self.Merge[0] == 'collinear':
                angle_threshold = self.Merge[1]
                res = map(lambda group_edges: self.merge_edges(group_edges), self.con_comp_con_collinear_iter(angle_threshold))

        return


    # 0. LOAD GRAPH OPERATIONS -----------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------

    def features_iter(self, layer):

        # detecting errors:
        # NULL, point, invalid, multipart geometries
        # updating sEdges

        for f in layer.getFeatures():

            # self.progress.emit(self.step)

            f_geom = f.geometry()

            # dropZValue if geometry is 3D
            if f.geometry().geometry().is3D():
                    f.geometry().geometry().dropZValue()

            f_geom_length = f_geom.length()

            if 0 < f_geom_length <= self.Snap: #if self.Snap == -1 never valid
                self.disconnections.append(f)
                pass # do not add to the graph - as it will be removed later
            elif f_geom.wkbType() == 2:
                f.setFeatureId(self.sEdgesId)
                self.sEdges[self.sEdgesId] = sEdge(self.sEdgesId, f, []) # empty topology - topology is (end, start)
                self.sEdgesId += 1
                yield f
            elif f_geom is NULL:
                self.empty_geometries.append(f)
            elif not f_geom.isGeosValid():
                self.invalids.append(f)
            elif f_geom_length <= 0:
                self.points.append(f)
            #
            elif f_geom.wkbType() == 5:
                ml_segms = f_geom.asMultiPolyline()
                for ml in ml_segms:
                    ml_geom = QgsGeometry(ml)
                    ml_feat = copy_feat(f, ml_geom, self.sEdgesId)
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
                    # sNodes do not need update as they are generated afterwards
            if self.Errors:
                # TODO
                pass
            # del after adding all
            #del self.sEdges[]
            return sedge_feat.id()
        else:
            return None

    def breakFeaturesIter(self):

        for id, sedge in self.sEdges.items():

            f_geom = sedge.feature.geometry()
            f_pl = f_geom.asPolyline()
            f_pl_indices = dict(zip(f_pl, range(0, len(f_pl))))
            vertices = [0, len(f_pl)-1]

            for k, v in dict((x, duplicates(f_pl, x)) for x in set(f_pl) if f_pl.count(x) > 1).items():
                if len(v) > 1:
                    vertices += v

            intersecting_edges = filter(lambda inter_edge: self.sEdges[inter_edge].id != id
                                                   and f_geom.distance(self.sEdges[inter_edge].feature.geometry()) <= 0,
                                        self.sEdgesSpIndex.intersects(f_geom.boundingBox()))
            # check for common vertices
            common_points = set([])
            for unq_inter_id in intersecting_edges:
                g_geom = self.sEdges[unq_inter_id].feature.geometry()

                if self.Unlinks:
                    if f_geom.crosses(g_geom):
                        crossing_point = f_geom.intersection(g_geom)
                        if crossing_point.wkbType() == 1:
                            self.unlinks.append(crossing_point.asPoint())
                        elif crossing_point.wkbType() == 4:
                            for cr_point in crossing_point.asMultiPoint():
                                self.unlinks.append(cr_point)
                    # TODO: unlink should not be a vertex in f_geom/g_geom what if OS? remove/move vertex??

                if f_geom.isGeosEqual(g_geom):
                    del self.sEdges[id]
                    self.duplicates.append()
                else:
                    common_points.update(set(f_pl[1:-1]).intersection(set(g_geom.asPolyline()[1:-1])))
                    # TODO if self.Errors check for overlaps
                    vertices += [f_pl_indices[p] for p in common_points]

            vertices = sorted(set(vertices))

            point_series = map(lambda (index_start, index_end): f_pl[index_start: index_end + 1], zip(vertices[:-1], vertices[1:]))

            yield sedge.feature, point_series

    # 2. SNAP ENDPOINTS ------------------------------------------------------------------------------------------------
    # ------------------------------------------------------------------------------------------------------------------

    def subgraph_nodes(self):

        # TODO: create separate class for sGraph - subgraph
        closestNodes = {}
        for id, snode in self.sNodes.items():
            # emit signal
            nd_geom = snode.geometry
            nd_buffer = nd_geom.buffer(self.Snap, 29)
            closest_nodes = self.sNodesSpIndex.intersects(nd_buffer.boundingBox())
            closest_nodes = set(
                filter(lambda id: nd_geom.distance(self.sNodes[id].geometry) <= self.Snap,
                       closest_nodes))
            if len(closest_nodes) > 1:
                # create sNodes
                # incl. itself (snode)
                for node in closest_nodes:
                    topology = set(closest_nodes)
                    topology.remove(node)
                    try:
                        closestNodes[node].topology.update(topology)
                    except KeyError:
                        closestNodes[node] = sNode(node, topology, self.sNodes[node].point)
        return closestNodes

    def con_comp_iter(self, any_nodes_dict):
        components_passed = set([])
        for id, node in any_nodes_dict.items():
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
        connected_edges = list(itertools.chain.from_iterable([self.sNodes[node].topology for node in nodes]))
        qgspoints = [self.sNodes[node].point for node in nodes]
        mergedSNode = sNode(self.sNodesId, connected_edges, QgsGeometry.fromMultiPoint(qgspoints).centroid().asPoint())
        self.sNodes[self.sNodesId] = mergedSNode
        for edge in connected_edges:
            # update edge
            self.sEdges[edge].replaceNodes(nodes, mergedSNode)
        for node in nodes:
            del self.sNodes[node]
        self.sNodesId += 1
        return True

    # 3. MERGE BETWEEN INTERSECTIONS -----------------------------------------------------------------------------------
    #    MERGE COLLINEAR SEGMENTS --------------------------------------------------------------------------------------
    def getConnectivity(self, edge):
        con_edges = filter(lambda _edge: _edge != edge.id, self.sNodes[edge.nodes[0]].topology + self.sNodes[edge.nodes[1]].topology)
        return len(con_edges)

    def hasPseudo(self, edge):
        if len(self.sNodes[edge.nodes[0]].topology) == 2 or len(self.sNodes[edge.nodes[1]].topology) == 2:
            return True

    def con_comp_con_2_iter(self):
        components_passed = set([])
        # dead end with connectivity 2 are excluded
        for (edge_id, edge) in filter(lambda (_id, _edge): self.getConnectivity(_edge) != 2 and len(set(_edge.nodes))!= 1, self.sEdges.items()):
            # statedge should not be a selfloop
            if {edge_id}.isdisjoint(components_passed): # prevent 2 ways
                startnode, endnode = edge.nodes
                if self.sNodes[endnode].getConnectivity() != 2:
                    startnode, endnode = edge.nodes[::-1]
                group_nodes = [startnode, endnode]
                group_edges = [edge_id]
                while self.sNodes[endnode].getConnectivity() == 2:
                    candidates = [e for e in self.sNodes[endnode].topology if e not in group_edges]
                    if len(set(self.sEdges[candidates[0]].nodes)) == 1:
                        break
                    else:
                        group_edges += candidates # selfloop/ parallels disregarded
                        endnode = (set(self.sEdges[candidates[0]].nodes).difference({endnode})).pop()
                        group_nodes += [endnode]
                components_passed.update(set(group_edges))
                if len(group_edges) > 1:
                    if self.Orphans and self.sNodes[startnode].getConnectivity() == self.sNodes[endnode].getConnectivity() == 1:
                        pass
                    else:
                        yield group_edges, group_nodes

    def con_comp_collinear_iter(self):
        components_passed = set([])
        # dead end with connectivity 2 are excluded
        for (edge_id, edge) in filter(lambda (_id, _edge): self.hasPseudo(_edge) and len(set(_edge.nodes))!= 1, self.sEdges.items()):
            # statedge should not be a selfloop
            if {edge_id}.isdisjoint(components_passed): # prevent 2 ways
                startnode, endnode = edge.nodes
                if self.sNodes[endnode].getConnectivity() != 2:
                    startnode, endnode = edge.nodes[::-1]
                group_nodes = [startnode, endnode]
                group_edges = [edge_id]
                while self.sNodes[endnode].getConnectivity() == 2:
                    candidates = [e for e in self.sNodes[endnode].topology if e not in group_edges]
                    endnode = (set(self.sEdges[candidates[0]].nodes).difference({endnode})).pop()
                    if len(set(self.sEdges[candidates[0]].nodes)) == 1 or \
                        angle_3_points(self.sNodes[group_nodes[-3]].point, self.sNodes[group_nodes[-2]].point, self.sNodes[group_nodes[-1]].point):
                        break
                    else:
                        group_edges += candidates # selfloop/ parallels disregarded
                        group_nodes += [endnode]
                components_passed.update(set(group_edges))
                if len(group_edges) > 1:
                    if self.Orphans and self.sNodes[startnode].getConnectivity() == self.sNodes[endnode].getConnectivity() == 1:
                        pass
                    else:
                        yield group_edges, group_nodes

    def merge_edges(self, group_edges, group_nodes):
        merged_feat = merge_features([self.sEdges[edge].feature for edge in group_edges], self.sEdgesId)
        merged_sedge = sEdge(self.sEdgesId, merged_feat, [group_nodes[0], group_nodes[-1]])
        self.sEdges[self.sEdgesId] = merged_sedge
        self.sEdgesId += 1
        # topology not updated !
        return group_edges