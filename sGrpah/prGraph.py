
# imports
import itertools


class prGraph:

    def __init__(self, prGraph, id_column):
        self.obj = prGraph
        self.id_column = id_column

    # ----- ANALYSIS OPERATIONS -----

    # make feat_id: wkt_geom dictionary
    def get_wkt_dict(self):
        return {edge[2][self.id_column]: edge[2]['Wkt'] for edge in self.obj.edges(data=True)}

    # make feat_id: attributes dictionary
    def get_attr_dict(self):
        return {edge[2][self.id_column]: edge[2] for edge in self.obj.edges(data=True)}

    # get fields
    def get_fields(self):
        fields_names = None
        fields_types = None
        for edge in self.obj.edges(data=True):
            fields_names = edge[2].keys()
            fields_types = [type(attr) for attr in edge[2].values()]
            break
        return fields_names, fields_types

    # get features
    # these features do not have fields and feature ids
    def get_features(self):
        features = []
        for edge in self.obj.edges(data=True):
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromWkt(edge[2]['Wkt']))
            feat.setAttributes(edge[2].values())
            features.append(feat)
        self.features = features

    # ----- TOPOLOGY OPERATIONS -----

    # make topology iterator ( point_coord : [lines] )

    def topology_iter(self, break_at_intersections):
        if break_at_intersections:
            for i, j in self.obj.adjacency_iter():
                edges = [v[0][self.id_column] for k, v in j.items() if len(j) == 2]
                yield i, edges
        else:
            for i, j in self.obj.adjacency_iter():
                edges = [v[0][self.id_column] for k, v in j.items()]
                yield i, edges

    # make iterator of dual graph edges from prGraph edges

    def dl_edges_from_pr_graph(self, break_at_intersections):
        for point, edges in self.topology_iter(break_at_intersections):
            for x in itertools.combinations(edges, 2):
                yield x

    # make iterator of dual graph nodes from prGraph edges

    def dl_nodes_from_pr_graph(self, dlGrpah, id_column):
        for e in self.obj.edges_iter(data=id_column):
            if e[2] not in dlGrpah.nodes():
                yield e[2]

    # ----- ALTERATION OPERATIONS -----

    def rmv_edges(self, edges_to_rmv):
        pass

    def add_edges(self, edges_to_add):
        pass

    def move_node(self, node, point_to_move_to):
        pass
