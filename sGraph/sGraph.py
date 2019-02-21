# general imports
import itertools
import operator
from PyQt4.QtCore import QObject, pyqtSignal, QVariant
from qgis.core import QgsGeometry, QgsSpatialIndex, QgsFields, QgsField, QgsFeature
from collections import defaultdict

# plugin module imports
try:
    from sGraph.utilityFunctions import *
    from sNode import sNode
    from sEdge import sEdge
except ImportError:
    pass

# special cases:
# SELF LOOPS
#   - topology of self loop node would include itself

# DUPLICATE
#   - topology of n1 would include n2 many times

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
            start = self.load_point(startpoint)
            end = self.load_point(endpoint)
            snodes = [start, end]
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
        # self.ndSpIndex.deleteFeature(self.sNodes[node_id].feature)
        del self.sNodes[node_id]
        return True

    def remove_edge(self, nodes, e):
        self.sNodes[nodes[0]].adj_edges.remove(e)
        self.sNodes[nodes[0]].topology.remove(nodes[1])
        self.sNodes[nodes[1]].adj_edges.remove(e) # if self loop - removed twice
        try:
            self.sNodes[nodes[1]].topology.remove(nodes[0])
        except ValueError:
            pass # if self loop node has been removed
        del self.sEdges[e]
        return

    # create graph (broken_features_iter)
    # can be applied to edges w-o topology for speed purposes
    def break_features_iter(self, getUnlinks, angle_threshold, fix_unlinks=False):
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
            intersections = (set(intersections))

            # unlinks
            if getUnlinks:
                lines = filter(lambda line: f_geom.crosses(self.sEdges[line].feature.geometry()), lines)

                unlinks = []
                for line in lines:
                    crossing_points = f_geom.intersection(self.sEdges[line].feature.geometry())
                    if crossing_points.wkbType() == 1:
                        unlinks.append(crossing_points)
                    else:
                        for p in crossing_points.asMultiPoint():
                            unlinks.append(p)
                self.unlinks += unlinks
                if fix_unlinks:
                    # find vertices
                    unlinks = map(lambda p: self.fix_unlink(p, pl, sedge.id), unlinks)
                    intersections = list(intersections.difference(set(unlinks)))
                else: # TODO: exclude vertices - might be in one of the lines
                    pass

            # errors
            self.errors += intersections
            if len(intersections) > 0:
                # broken features iterator
                vertices_indices = find_vertex_indices(pl, intersections)
                for start, end in zip(vertices_indices[:-1], vertices_indices[1:]):
                    broken_feat = QgsFeature(f)
                    broken_geom = QgsGeometry.fromPolyline(pl[start:end + 1]).simplify(angle_threshold)
                    broken_feat.setGeometry(broken_geom)
                    yield broken_feat
            else:
                simpl_geom = f.geometry().simplify(angle_threshold)
                f.setGeometry(simpl_geom)
                yield f

    def fix_unlink(self, point, polyline, e):
        if point in polyline:
            self.sEdges[e].feature.geometry().moveVertex(point.x() + 1, point.y() + 1, polyline.index(point))
        return

    # group points based on proximity - spatial index is not updated
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
                itertools.chain.from_iterable([self.sNodes[node].adj_edges for node in group]))
            short_edges = set([])
            for e in con_edges:
                sedge = self.sEdges[e]
                nds = set(sedge.nodes)
                # TODO if self loop and one intermediate vertex, it turns back on itself
                if len(nds.intersection(group)) == len(nds) and (len(sedge.feature.geometry().asPolyline()) <= 3 or sedge.feature.geometry().length() <= snap_threshold):
                    short_edges.update({e})
                    # remove short edges
                    del self.sEdges[e]

            con_edges = con_edges.difference(short_edges)

            # collapse nodes to node
            merged_node_id, centroid_point = self.collapse_to_node(group, list(con_nodes), [])

            # update connected edges and their topology
            for edge in con_edges:
                start, end = self.sEdges[edge].nodes
                # two ifs to account for self loops
                if start in group:
                    self.sEdges[edge].replace_start(self.node_id, centroid_point)
                    self.update_topology(merged_node_id, end, edge)
                    self.sNodes[end].topology.remove(start)
                if end in group:
                    self.sEdges[edge].replace_end(self.node_id, centroid_point)
                    self.update_topology(merged_node_id, start, edge)
                    self.sNodes[start].topology.remove(end)

            # delete old nodes
            res = map(lambda item: self.delete_node(item), group)

        return

    def collapse_to_node(self, group, con_nodes, con_edges):

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

        return self.node_id, centroid.asPoint()

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
                yield count - 1, nd

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

    # TODO: snap_geometries (not endpoints)
    # TODO: extend

    def clean_dupl(self, nodes, group_edges, snap_threshold):
        # keep line with minimum length
        # TODO: add distance centroids
        lengths = [self.sEdges[e].feature.geometry().length() for e in group_edges]
        sorted_edges = [x for _, x in sorted(zip(lengths, group_edges))]
        min_len = min(lengths)

        for e in sorted_edges[1:]:
            # delete line
            if abs(self.sEdges[e].feature.geometry().length() - min_len) <= snap_threshold:
                self.remove_edge(nodes, e)
        return

    def clean_orphan(self, e):
        nds = e.nodes
        snds = self.sNodes[nds[0]], self.sNodes[nds[1]]
        # connectivity of both endpoints 1
        # second condition to account for 2 self loops connecting two one point
        if len(set(snds[0].topology)) == len(set(snds[1].topology)) == 1 : # can be parallel or selfloop to line - 2 items
            # if nds[0] == nds[1]:
            # if len(snds[0].adj_edges) in [[], [e.id]]:
            del self.sEdges[e.id]
            for nd in set(nds):
                del self.sNodes[nd]
        return True

    # find duplicate geometries
    # find orphans

    def clean_dupl_orphans(self, orphans, snap_threshold):
        # group duplicate edges (same length or snap_threshold)
        # delete longest edges & update topology
        input = [(e.id, frozenset(e.nodes)) for e in graph.sEdges.values()]
        groups = defaultdict(list)
        for v, k in input: groups[k].append(v)

        dupl_candidates = dict(filter(lambda (nodes, edges): len(edges) > 1, groups.items()))
        res = map(lambda (nodes, group_edges): self.clean_dupl(nodes, group_edges, snap_threshold), dupl_candidates.items())

        # clean orphans
        if orphans:
            res = map(lambda e: self.clean_orphan(e), self.sEdges.values())
        return

    # merge

    def merge(self, parameter, angle_threshold=None):

        if parameter == 'angle':
            con2 = filter(lambda (line1, line2): angular_change(self.sEdges[line1].feature.geometry(),
                                                                self.sEdges[line2].feature.geometry()) <= angle_threshold, con2)

        edges_passed = set([])
        for e in self.edge_edges_iter():
            if {e}.isdisjoint(edges_passed):
                edges_passed.update({e})
                group_nodes, group_edges = self.route_polylines(e)
                if group_edges:
                    edges_passed.update({group_edges[-1]})
                    self.merge_edges(group_nodes, group_edges)
        return

    def edge_edges_iter(self):
        # what if two parallel edges at the edge - should become self loop
        for nd_id, nd in self.sNodes.items():
            con_edges = nd.adj_edges
            if len(nd.topology) != 2 and len(con_edges) != 2:  # not set to include parallels and self loops
                for e in con_edges:
                    yield e

    def route_polylines(self, startedge):
        # if edge has been passed
        startnode, endnode = self.sEdges[startedge].nodes
        if len(self.sNodes[endnode].topology) != 2: # not set to account for self loops
            startnode, endnode = endnode, startnode
        group_nodes = [startnode, endnode]
        group_edges = [startedge]
        while len(self.sNodes[group_nodes[-1]].adj_edges) == 2 and not group_nodes[0] == group_nodes[-1]: # not topology to account for self loops ??
            last_visited = group_nodes[-1]
            con_node = set(self.sNodes[last_visited].topology).difference(set(group_nodes[1:])).pop() # group_nodes[1:] so that self loops are allowed to merge
            con_edge = set(self.sNodes[last_visited].adj_edges).difference(set(group_edges)).pop()
            group_nodes.append(con_node)
            group_edges.append(con_edge)
        if len(group_nodes) > 2:
            return group_nodes, group_edges
        else:
            return None, None

    def merge_edges(self, group_nodes, group_edges):

        geoms = map(lambda e: self.sEdges[e].feature.geometry(), group_edges)
        lengths = map(lambda g: g.length(), geoms)
        max_len = max(lengths)

        # merge edges
        self.edge_id += 1
        feat = QgsFeature()
        # attributes from longest
        longest_feat = self.sEdges[group_edges[lengths.index(max_len)]].feature
        feat.setAttributes(longest_feat.attributes())
        feat.setGeometry(merge_geoms(geoms))
        feat.setFeatureId(self.edge_id)

        merged_edge = sEdge(self.edge_id, feat, [group_nodes[0], group_nodes[-1]])
        self.sEdges[self.edge_id] = merged_edge

        # del edges
        #for e in group_edges:
        #    del self.sEdges[e]

        # update ends
        #self.sNodes[group_nodes[0]].topology.remove(group_nodes[1])
        #self.sNodes[group_nodes[-1]].topology.remove(group_nodes[-2])
        #self.sNodes[group_nodes[0]].adj_edges.remove(group_edges[0])
        #self.sNodes[group_nodes[-1]].adj_edges.remove(group_edges[-1])

        # middle nodes del
        #for nd in group_nodes[1:-1]:
            #del self.sNodes[nd]

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

    def collapse_to_medial_axis(self):
        pass

    def simplify_angle(self):
        pass

    def kill(self):
        self.killed = True
