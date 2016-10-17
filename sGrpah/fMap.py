
# imports
# import plFunctions as pF


class fMap:

    def __init__(self, features, count):
        self.obj = features
        for i in self.obj:
            i.setFeatureId(count)
            # fields are passed if a shp is constructed
            # i.setFields(fields, True)
            count += 1

    # ---- ANALYSIS OPERATIONS -----

    # get feature iterator

    def feat_iter(self):
        for i in self.obj:
            yield i

    # dictionary of feature_id: geometry key, values

    def get_geom_dict(self,attr_index):
        if attr_index == 'feature_id':
            return {i.id(): i.geometryAndOwnership() for i in self.obj}
        else:
            return {i.attributes()[attr_index]: i.geometryAndOwnership() for i in self.obj}

    # dictionary of feature_id: geometry points key, values

    def get_geom_vertices_dict(self, attr_index):
        if attr_index == 'feature_id':
            return {i.id(): i.geometry().asPolyline() for i in self.obj}
        else:
            return {i.attributes()[attr_index]: i.geometry().asPolyline() for i in self.obj}

    # dictionary of feature_id: feature_attribute key, values

    def get_attr_dict(self,attr_index):
        if attr_index == 'feature_id':
            return {i.id(): i.attributes() for i in self.obj}
        else:
            return {i.attributes()[attr_index]: i.attributes() for i in self.obj}

    # dictionary of feature_id: feature key, values

    def get_feat_dict(self,attr_index):
        if attr_index == 'feature_id':
            return {i.id(): i for i in self.obj}
        else:
            return {i.attributes()[attr_index]: i for i in self.obj}

    # dictionary of feature_id: attr_column key,values

    def fid_to_uid(self, attr_index):
        return {i.id(): i.attributes()[attr_index] for i in self.obj}

    # dictionary of feature_id: attr_column key,values

    def uid_to_fid(self, attr_index):
        return {i.attributes()[attr_index]: i.id() for i in self.obj}

    # dictionary of feature_id: centroid
    # TODO: some of the centroids are not correct
    def make_centroids_dict(self, attr_index):
        centroids = {i.attributes()[attr_index]: pl_midpoint(i.geometry()) for i in self.obj}
        return centroids

    # iterator of line and intersecting lines based on spatial index

    def inter_lines_bb_iter(self):
        spIndex = QgsSpatialIndex()  # create spatial index object
        # insert features to index
        for f in self.obj:
            spIndex.insertFeature(f)
        # find lines intersecting other lines
        for i in self.obj:
            inter_lines = spIndex.intersects(
                QgsRectangle(QgsPoint(i.geometry().asPolyline()[0]), QgsPoint(i.geometry().asPolyline()[-1])))
            yield i.id(), inter_lines

    # get primal graph from qgs features

    def features_to_multigraph(self, fields, tolerance=None, simplify=True):
        net = nx.MultiGraph()
        for f in self.obj:
            flddata = f.attributes
            g = f.geometry()
            attributes = dict(zip(fields, flddata))
            # Note:  Using layer level geometry type
            if g.wkbType() == 2:
                for edge in edges_from_line(g, attributes, tolerance, simplify):
                    e1, e2, attr = edge
                    net.add_edge(e1, e2, attr_dict=attr)
            elif g.wkbType() == 5:
                for geom_i in range(g.asGeometryCollection()):
                    for edge in edges_from_line(geom_i, attributes, tolerance, simplify):
                        e1, e2, attr = edge
                        net.add_edge(e1, e2, attr_dict=attr)




    def inter_lines_point_check(self):
        pass

    def inter_lines_vertex_check(self):
        pass


    # ----- ALTERATION OPERATIONS -----

    # add attribute id to features

    def update_uid(self, column_name, prfx):
        fid = 0
        for feat in self.obj:
            feat.setAttributes(feat.attributes() + [prfx + '_' + fid])
            fid += 1

    # remove features from list



    def rmv_features(self, ids):
        pass

    # add features to list

    def add_features(self, feat_to_add):
        pass


