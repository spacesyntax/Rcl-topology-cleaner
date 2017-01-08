
import itertools

def get_next_vertex(tree, all_con):
    last = tree[-1]
    return tree + [ i for i in all_con[last] if i not in tree]


class mergeTool(QObject):

    finished = pyqtSignal(object)
    error = pyqtSignal(Exception, basestring)
    progress = pyqtSignal(float)
    warning = pyqtSignal(str)

    def __init__(self, features, uid, errors):
        QObject.__init__(self)
        self.features = features
        self.last_fid = features[-1][0]
        self.errors = errors
        self.uid = uid

    def prepare(self):

        vertices_occur = {}
        edges_occur = {}
        f_dict = {}
        self_loops = []

        for i in broken_features:
            f_dict[i[0]] = [i[1], i[2]]
            for vertex in vertices_from_wkt_2(i[2]):
                break
            first = vertex
            for vertex in vertices_from_wkt_2(i[2]):
                pass
            last = vertex
            try:
                vertices_occur[first] += [i[0]]
            except KeyError, e:
                vertices_occur[first] = [i[0]]
            try:
                vertices_occur[last] += [i[0]]
            except KeyError, e:
                vertices_occur[last] = [i[0]]
            pair = (last, first)
            # strings are compared
            if first[0] > last[0]:
                pair = (first, last)
            try:
                edges_occur[pair] += [i[0]]
            except KeyError, e:
                edges_occur[pair] = [i[0]]

        con_2 = {k: v for k, v in vertices_occur.items() if len(v) == 2}
        all_con = {}
        for k, v in con_2.items():
            try:
                all_con[v[0]] += [v[1]]
            except KeyError, e:
                all_con[v[0]] = [v[1]]
            try:
                all_con[v[1]] += [v[0]]
            except KeyError, e:
                all_con[v[1]] = [v[0]]

        parallel = {k: v for k, v in edges_occur.items() if len(v) >= 2}
        duplicates = []
        for k, v in parallel.items():
            for x in itertools.combinations(v, 2):
                if x[0] < x[1]:
                    f_geom = QgsGeometry.fromWkt(f_dict[x[0]][1])
                    g_geom = QgsGeometry.fromWkt(f_dict[x[1]][1])
                    if f_geom.isGeosEqual(g_geom):
                        duplicates.append(f_geom)

        fids_to_merge = [fid for k, v in con_2.items() for fid in v]
        all_fids = [i[0] for i in self.features]
        copy_fids = list(set(all_fids) - set(fids_to_merge))
        feat_to_merge = [[i, f_dict[i][0], f_dict[i][1]] for i in fids_to_merge if i not in duplicates]

        feat_to_copy =[[i, f_dict[i][0], f_dict[i][1]] for i in copy_fids if i not in duplicates]


        vertices_occur = {}

        for i in feat_to_merge:
            for vertex in vertices_from_wkt_2(i[2]):
                break
            first = vertex
            for vertex in vertices_from_wkt_2(i[2]):
                pass
            last = vertex
            try:
                vertices_occur[first] += [i[0]]
            except KeyError, e:
                vertices_occur[first] = [i[0]]
            try:
                vertices_occur[last] += [i[0]]
            except KeyError, e:
                vertices_occur[last] = [i[0]]

        con_1 = list(set([v[0] for k, v in vertices_occur.items() if len(v) == 1]))

        return all_con, con_1, f_dict, feat_to_copy

    def merge(self):

        all_con, con_1, f_dict, feat_to_copy = self.prepare()

        merged_features = []

        edges_passed = []
        all_trees = []
        for edge in con_1:
            if edge not in edges_passed:
                edges_passed.append(edge)
                tree = [edge]
                n_iter = 0
                x = 0
                while True:
                    last = tree[-1]
                    n_iter += 1
                    x += 1
                    # TODO in con_1 or is self loop
                    if last in con_1 and n_iter != 1:
                        edges_passed.append(last)
                        n_iter = 0
                        break
                    else:
                        len_tree = len(tree)
                        tree = get_next_vertex(tree, all_con)
                        if len(tree) == len_tree:
                            n_iter = 0
                            break

                    #if len(tree) == 1 and n_iter > 1:
                    #    n_iter = 0
                    #    break
                    if x > 100:
                        print "infinite"
                        break
                all_trees.append(tree)
                f_attrs = f_dict[tree[0]][0]
                # new_geom = geom_dict[set_to_merge[0]]
                geom_to_merge = [QgsGeometry.fromWkt(f_dict[node][1]) for node in tree]
                for ind, line in enumerate(geom_to_merge[1:], start=1):
                    second_geom = line
                    first_geom = geom_to_merge[(ind - 1) % len(tree)]
                    new_geom = second_geom.combine(first_geom)
                    geom_to_merge[ind] = new_geom
                if new_geom.wkbType() == 5:
                    for linestring in new_geom.asGeometryCollection():
                        self.last_fid += 1
                        new_feat = [self.last_fid, f_attrs, linestring]
                        merged_features.append(new_feat)
                elif new_geom.wkbType() == 2:
                    self.last_fid += 1
                    new_feat = [self.last_fid, f_attrs, new_geom]
                    merged_features.append(new_feat)

        return merged_features + feat_to_copy

