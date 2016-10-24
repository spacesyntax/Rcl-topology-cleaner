


class dlGraph:

    def __init__(self, dlGraph, id_column, centroids, make_feat = True):
        self.obj = dlGraph
        self.uid = id_column
        self.attributes = ['line1', 'line2', 'cost']
        self.n_attributes = 3
        self.qgs_fields = [QgsField('line1',QVariant.String), QgsField('line2',QVariant.String), QgsField('cost',QVariant.Int)]

        if make_feat:
            features = []
            count = 1
            for edge in self.obj.edges(data='cost'):
                feat = QgsFeature()
                feat.setGeometry(QgsGeometry.fromPolyline(
                    [QgsPoint(centroids[edge[0]][0], centroids[edge[0]][1]), QgsPoint(centroids[edge[1]][0], centroids[edge[1]][1])]))
                feat.initAttributes(self.n_attributes)
                feat.setAttributes([edge[0], edge[1], edge[2]])
                feat.setFeatureId(count)
                features.append(feat)
                count += 1
            self.features = features


    # ----- TRANSLATION OPERATIONS

    # ----- dlGRAPH TO SHP

    def to_shp(self, path, name, crs, encoding, geom_type):
        if path is None:
            network = QgsVectorLayer('LineString?crs=' + crs.toWkt(), name, "memory")
        else:
            # provider.fields()
            file_writer = QgsVectorFileWriter(path, encoding, None, geom_type,
                                              crs.crs(), "ESRI Shapefile")
            if file_writer.hasError() != QgsVectorFileWriter.NoError:
                print "Error when creating shapefile: ", file_writer.errorMessage()
            del file_writer
            network = QgsVectorLayer(path, name, "ogr")
        QgsMapLayerRegistry.instance().addMapLayer(network)
        pr = network.dataProvider()
        network.startEditing()
        pr.addAttributes(self.qgs_fields)
        pr.addFeatures(self.features)
        network.commitChanges()
        return network

    # Code source: ESS TOOLKIT https://github.com/SpaceGroupUCL/qgisSpaceSyntaxToolkit.git

    # only orphans not islands ?

    def find_islands_orphans(self, id_column):
        # order based on length
        components = sorted(connected_components(self.settings['dlGraph']), key=len, reverse=True)
        if len(components) > 1:
            islands = []
            # get vertex ids
            for cluster in components[1:len(components)]:  # excludes the first giant component
                # identify orphans
                if len(cluster) == 1:
                    node = cluster.pop()
                    # TODO: change
                    self.axial_errors['orphan'].append(node)
                    self.problem_nodes.append(node)
                # identify islands
                elif len(cluster) > 1:
                    nodes = list(cluster)
                    islands.append(nodes)
                    # TODO: change
                    self.problem_nodes.extend(nodes)

    def find_cont_lines(self):
        # 2. merge lines from intersection to intersection
        # Is there a grass function for QGIS 2.14???
        # sets of connected nodes (edges of primary graph)
        sets = []
        for j in connected_components(self.obj):
            sets.append(list(j))
        sets_in_order = [set_con for set_con in sets if len(set_con) == 2 or len(set_con) == 1]
        for set in sets:
            if len(set) > 2:
                edges = []
                for n in set:
                    if len(self.obj.neighbors(n)) > 2 or len(self.obj.neighbors(n)) == 1:
                        edges.append(n)
                        # find all shortest paths and keep longest between edges
                if len(edges) == 0:
                    edges = [set[0], set[0]]
                list_paths = [i for i in all_simple_paths(self.obj, edges[0], edges[1])]
                if len(list_paths) == 1:
                    set_in_order = list_paths[0]
                else:
                    set_in_order = max(enumerate(list_paths), key=lambda tup: len(tup[1]))[1]
                    del set_in_order[-1]
                sets_in_order.append(set_in_order)

        return sets_in_order


    def to_shp_vertices():
        pass