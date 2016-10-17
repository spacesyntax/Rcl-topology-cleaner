
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


    def find_cont_lines(self, id_column):
        pass

    def find_islands(self, id_column):
        pass

    def find_orphans(self, id_column):
        pass


