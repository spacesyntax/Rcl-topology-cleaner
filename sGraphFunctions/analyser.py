
# ----- ANALYSIS OPERATIONS -----


class analyser:

    def __init__(self, settings, analysis_type):
        self.settings = settings
        self.analysis_type = analysis_type
        self.id_column = settings['id_column']

        # ----- Identify multiparts and invalids from initial shp

    def inv_mlParts(self):
        shp = settings['shp']
        invalids = [i[self.id_column] for i in shp.getFeatures() if not i.geometry().isGeosValid()]
        multiparts = [i[self.id_column] for i in shp.getFeatures() if i.geometry().isMultipart()]
        return invalids, multiparts

    # ----- From intersecting lines identify breakages, duplicates, overlaps

    def find_breakages(self):
        uid = self.settings['fMap'].fid_to_uid(self.settings['attr_index'])
        geometries = self.settings['fMap'].get_geom_dict('feature_id')
        for feat, inter_lines in self.settings['fMap'].inter_lines_bb_iter():
            f_geom = geometries[feat]
            breakages = []
            for line in inter_lines:
                intersection = f_geom.intersection(geometries[line])
                if intersection.wkbType() == 1 and point_is_vertex(intersection, f_geom):
                    breakages.append(intersection)
                # TODO: test multipoints
                elif intersection.wkbType() == 4:
                    for point in intersection.asGeometryCollection():
                        if point_is_vertex(intersection, f_geom):
                            breakages.append(point)
            if len(breakages) > 0:
                yield uid[feat], set([vertex for vertex in find_vertex_index(breakages, feat, geometries)])

    def find_dupl_overlaps(self, id_column):
        uid = self.settings['fMap'].fid_to_uid(self.settings['attr_index'])
        geometries = self.settings['fMap'].get_geom_dict('feature_id')
        duplicates = []
        overlaps = []
        for feat, inter_lines in self.settings['fMap'].inter_lines_bb_iter():
            f_geom = geometries[feat]
            for line in inter_lines:
                g_geom = geometries[line]
                if g_geom == f_geom :
                    duplicates.append(feat)
                elif f_geom.intersection(g_geom):
                    pass

    def find_islands_orphans(self, id_column):
        pass

    def find_cont_lines(self, dGraph):
        # 2. merge lines from intersection to intersection
        # Is there a grass function for QGIS 2.14???
        # sets of connected nodes (edges of primary graph)
        sets = []
        for j in connected_components(dGraph):
            sets.append(list(j))
        sets_in_order = [set_con for set_con in sets if len(set_con) == 2 or len(set_con) == 1]
        for set in sets:
            if len(set) > 2:
                edges = []
                for n in set:
                    if len(dGraph.neighbors(n)) > 2 or len(dGraph.neighbors(n)) == 1:
                        edges.append(n)
                        # find all shortest paths and keep longest between edges
                if len(edges) == 0:
                    edges = [set[0], set[0]]
                list_paths = [i for i in nx.all_simple_paths(dGraph, edges[0], edges[1])]
                if len(list_paths) == 1:
                    set_in_order = list_paths[0]
                else:
                    set_in_order = max(enumerate(list_paths), key=lambda tup: len(tup[1]))[1]
                    del set_in_order[-1]
                sets_in_order.append(set_in_order)

        return sets_in_order



