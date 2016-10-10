
# imports
# import plFunctions as pF


class fMap:

    def __init__(self, features, fields, count):
        self.features = features
        for i in self.features:
            i.setFeatureId(count)
            i.setFields(fields, True)
            count += 1

    # ---- ANALYSIS OPERATIONS -----

    # dictionary of feature_id: geometry key, values

    def get_geom_dict(self,id_column):
        if id_column == 'feature_id':
            return {i.id(): i.geometryAndOwnership() for i in self.features}
        else:
            return {i[id_column]: i.geometryAndOwnership() for i in self.features}

    # dictionary of feature_id: feature_attribute key, values

    def get_attr_dict(self,id_column):
        if id_column == 'feature_id':
            return {i.id(): i.attributes() for i in self.features}
        else:
            return {i[id_column]: i.attributes() for i in self.features}

    # dictionary of feature_id: feature key, values

    def get_feat_dict(self,id_column):
        if id_column == 'feature_id':
            return {i.id(): i for i in self.features}
        else:
            return {i[id_column]: i for i in self.features}

    # dictionary of feature_id: attr_column key,values

    def fid_to_uid(self, id_column):
        return {i.id(): i[id_column] for i in self.features}

    # dictionary of feature_id: centroid
    # TODO: some of the centroids are not correct
    def make_centroids_dict(self, attr_index):
        centroids = {i.attributes()[attr_index]: pl_midpoint(i.geometry()) for i in self.features}
        return centroids

    # iterator of line and intersecting lines based on spatial index

    def inter_lines_iter(self,features):
        spIndex = QgsSpatialIndex()  # create spatial index object
        # insert features to index
        for f in self.features:
            spIndex.insertFeature(f)
        # find lines intersecting other lines
        for i in self.features:
            inter_lines = spIndex.intersects(
                QgsRectangle(QgsPoint(i.geometry().asPolyline()[0]), QgsPoint(i.geometry().asPolyline()[-1])))
            yield i.id(), inter_lines

    # ----- ALTERATION OPERATIONS -----

    # add attribute id to features

    def update_uid(self, column_name, prfx):
        fid = 0
        for feat in self.features:
            feat.setAttributes(feat.attributes() + [prfx + '_' + fid])
            fid += 1

    # remove features from list

    def rmv_features(self, ids):
        pass

    # add features to list

    def add_features(self, feat_to_add):
        pass


