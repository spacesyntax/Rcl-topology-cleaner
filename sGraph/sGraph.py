# general imports
import itertools
import operator
from PyQt4.QtCore import QObject, pyqtSignal, QVariant
from qgis.core import QgsGeometry, QgsSpatialIndex, QgsFields, QgsField, QgsFeature

# plugin module imports
try:
    from sGraph.utilityFunctions import *
    from sNode import sNode
    from sEdge import sEdge
except ImportError:
    pass


class sGraph(QObject):

    finished = pyqtSignal(object)
    error = pyqtSignal(Exception, basestring)
    progress = pyqtSignal(float)
    warning = pyqtSignal(str)
    killed = pyqtSignal(bool)

    def __init__(self, edges={}, nodes={}):
        QObject.__init__(self)
        self.sEdges = edges
        self.sNodes = nodes # can be empty

        if len(self.sEdges) == 0:
            self.edge_id = 0
            self.sNodesCoords = {}
            self.node_id = 0
        else:
            print len(self.sEdges)
            self.edge_id = max(self.sEdges.keys())
            self.node_id = max(self.sNodes.keys())
            self.sNodesCoords = {snode.getCoords(): snode.id for snode in self.sNodes.values()}

        self.edgeSpIndex = QgsSpatialIndex()
        self.ndSpIndex = QgsSpatialIndex()
        res = map(lambda sedge: self.edgeSpIndex.insertFeature(sedge.feature), self.sEdges.values())
        res = map(lambda snode: self.ndSpIndex.insertFeature(snode.feature), self.sNodes.values())
        del res

        self.errors = []
        self.unlinks = []

    # graph from feat iter
    # updates the id
    def load_edges(self, feat_iter):

        for f in feat_iter:
            # add edge
            geometry = f.geometry().asPolyline()
            startpoint = geometry[0]
            endpoint = geometry[-1]
            snodes = self.load_point(startpoint), self.load_point(endpoint)
            self.edge_id += 1
            self.update_topology(snodes[0], snodes[1], self.edge_id)

            f.setFeatureId(self.edge_id)
            sedge = sEdge(self.edge_id, f, snodes)
            self.sEdges[self.edge_id] = sedge
            self.edgeSpIndex.insertFeature(f)
        return

    # pseudo graph from feat iter (only clean features - ids are fixed)
    def load_edges_w_o_topology(self, clean_feat_iter):

        for f in clean_feat_iter:
            # add edge
            sedge = sEdge(f.id(), f, [])
            self.sEdges[f.id()] = sedge
            self.edgeSpIndex.insertFeature(f)

        self.edge_id = f.id()
        return

    # find existing or generate new node
    def load_point(self, point):
        try:
            node_id = self.sNodesCoords[(point[0], point[1])]
        except KeyError:
            self.node_id += 1
            node_id = self.node_id
            feature = QgsFeature()
            feature.setFeatureId(node_id)
            feature.setAttributes([node_id])
            feature.setGeometry(QgsGeometry.fromPoint(point))
            self.sNodesCoords[(point[0], point[1])] = node_id
            snode = sNode(node_id, feature, [], [])
            self.sNodes[self.node_id] = snode
            self.ndSpIndex.insertFeature(feature)
        return node_id

    # create topology
    def update_topology(self, node1, node2, edge):
        self.sNodes[node1].topology.append(node2)
        self.sNodes[node1].adj_edges.append(edge)
        self.sNodes[node2].topology.append(node1)
        self.sNodes[node2].adj_edges.append(edge)
        return

    # delete point
    def delete_node(self, node_id):
        del self.sNodes[node_id]
        self.ndSpIndex.removeFeature(node_id)
        return True

    # create graph (broken_features_iter)
    # can be applied to edges w-o topology for speed purposes
    def break_features_iter(self, getUnlinks):
        for sedge in self.sEdges.values():
            f = sedge.feature
            f_geom = f.geometry()
            pl = f_geom.asPolyline()
            lines = filter(lambda line: line!= f.id(), self.edgeSpIndex.intersects(f_geom.boundingBox()))

            # self intersections
            # include first and last
            self_intersections = getSelfIntersections(pl)

            # common vertices
            intersections = list(itertools.chain.from_iterable(map(lambda line: set(pl[1:-1]).intersection(set(self.sEdges[line].feature.geometry().asPolyline())), lines)))
            intersections += self_intersections
            intersections = list(set(intersections))

            # unlinks
            if getUnlinks:
                lines = filter(lambda line: f_geom.crosses(self.sEdges[line].feature.geometry()), lines)
                # TODO: exclude vertices - might be in one of the lines
                # TODO: os open roads
                self.unlinks += map(lambda line: f_geom.intersection(self.sEdges[line].feature.geometry()), lines)

            # errors
            self.errors += intersections
            if len(intersections) > 0:
                # broken features iterator
                vertices_indices = find_vertex_indices(pl, intersections)
                for start, end in zip(vertices_indices[:-1], vertices_indices[1:]):
                    broken_feat = QgsFeature(f)
                    broken_feat.setGeometry(QgsGeometry.fromPolyline(pl[start:end + 1]))
                    yield broken_feat
            else:
                yield f

    # group points based on proximity
    def snap_endpoints(self, snap_threshold):
        # TODO: test when loading points
        filtered_nodes = {}
        for node in self.sNodes.values():
            # find nodes within x distance
            node_geom = node.feature.geometry()
            nodes = filter(lambda nd: nd != node.id and node_geom.distance(self.sNodes[nd].feature.geometry()) <= snap_threshold,
                           self.ndSpIndex.intersects(node_geom.buffer(snap_threshold, 10).boundingBox()))
            if len(nodes) > 0:
                filtered_nodes[node.id] = nodes

        for group in con_comp_iter(filtered_nodes):

            # find con nodes
            con_nodes = set(
                itertools.chain.from_iterable([self.sNodes[node].topology for node in group]))
            con_nodes = con_nodes.difference(group)

            # find con_edges
            con_edges = set(
                itertools.chain.from_iterable([self.sNodes[node].adj_lines for node in group]))
            short_edges = set([])
            for e in con_edges:
                nds = set(self.sEdges[e].snodes)
                if len(nds.intersection(group)) == len(nds):
                    short_edges.update(e)

            con_edges = con_edges.difference(short_edges)

            # collapse nodes to node
            merged_node_id, centroid_point = self.collapse_to_node(group, list(con_nodes), list(con_edges))

            # update connected edges and their topology
            for edge in con_edges:
                self.edgeSpIndex.removeFeature(edge)
                start, end = self.sEdges[edge].snodes
                # two ifs to account for self loops
                if start in group:
                    self.sEdges[edge] = self.sEdges[edge].replace_start(self.node_id, centroid_point)
                    self.sNodes[end].topology.remove(start)
                    self.sNodes[end].topology.append(merged_node_id)
                if end in group:
                    self.sEdges[edge] = self.sEdges[edge].replace_end(self.node_id, centroid_point)
                    self.sNodes[start].topology.remove(end)
                    self.sNodes[start].topology.append(merged_node_id)
                self.edgeSpIndex.insertFeature(self.sEdges[edge].feature)

            # remove short edges
            for edge in short_edges:
                self.edgeSpIndex.removeFeature(edge)
                del self.sEdges[edge]
        return

    # TODO add agg_cost
    def route_nodes(self, group, step):
        count = 1
        group = [group]
        while count <= step:
            last_visited = group[-1]
            group = group[:-1] + group[-1]
            con_nodes = set(itertools.chain.from_iterable([self.sNodes[last_node].topology for last_node in last_visited])).difference(group)
            group += [con_nodes]
            count += 1
            for nd in con_nodes:
                yield count -1, nd

    def route_edges(self, group, step):
        count = 1
        group = [group]
        while count <= step:
            last_visited = group[-1]
            group = group[:-1] + group[-1]
            con_edges = set(
                itertools.chain.from_iterable([self.sNodes[last_node].topology for last_node in last_visited]))
            con_nodes = filter(lambda con_node: con_node not in group, con_nodes)
            group += [con_nodes]
            count += 1
            # TODO: return circles
            for dg in con_edges:
                yield count - 1, nd, dg

    # TODO: snap_geometries
    # TODO: extend

    # find duplicate geometries
    # find orphans

    def clean_dupl_orpans(self):
        return

    # merge

    def merge(self, parameter):
        if parameter == 'intersections':
            polylines_iter = NULL
        else:
            polylines_iter = NULL

        for group in polylines_iter:
            pass

            # delete edges , spIndex
            # middle nodes del
            # end_nodes update
        return

    def simplify_circles(self):
        roundabouts = NULL
        short = NULL
        res = map(lambda group: self.collapse_to_node(group), con_components(roundabouts + short))
        return

    def simplify_parallel_lines(self):
        dual_car = NULL
        res = map(lambda group: self.collapse_to_medial_axis(group), con_components(dual_car))
        pass

    def collapse_to_node(self, group, con_nodes, con_edges):
        # delete old nodes
        map(lambda item: self.delete_node(item), group)

        # create new node, coords
        self.node_id += 1
        feat = QgsFeature()
        centroid = (
            QgsGeometry.fromMultiPoint([self.sNodes[nd].feature.geometry().asPoint() for nd in group])).centroid()
        feat.setGeometry(centroid)
        feat.setAttributes([self.node_id])
        feat.setFeatureId(self.node_id)
        snode = sNode(self.node_id, feat, con_nodes, con_edges)
        self.sNodes[self.node_id] = snode
        self.ndSpIndex.insertFeature(feat)

        return centroid.asPoint()

    def collapse_to_medial_axis(self):
        pass

    def simplify_angle(self):
        pass
