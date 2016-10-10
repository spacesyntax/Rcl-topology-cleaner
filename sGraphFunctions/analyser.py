
# ----- ANALYSIS OPERATIONS -----

# find where features cross and intersect

def find_breakages(self, id_column):
    uid = self.getfGraph.features.fid_to_uid(id_column)
    geometries = self.getfGraph.features.make_geom_dict('feature_id')
    for feat, inter_lines in self.getfGraph.inter_lines_iter():
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


def break_sGraph(self, id_column):
    pass


def find_cont_lines(self, id_column):
    pass


def merge_sGraph(self, id_column):
    pass


def find_dupl(self, id_column):
    pass


def dupl_sGraph(self, id_column):
    pass