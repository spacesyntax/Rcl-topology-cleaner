
# imports
import networkx as nx
# import utilityFunctions as uF
# import shpFunctions as sF
# import superGraph

# ----- TRANSFORMATION TYPES -----

# shp_to_sg = shapefile to super graph
#




class transformer:

    def __init__(self, parameters, transformation_type):
        self.parameters = parameters
        self.transformation_type = transformation_type
        self.id_column = parameters['id_column']

        # ----- SHP TO SGRAPH

        if self.transformation_type == 'shp_to_pgr':
            primal_graph = read_shp_to_multi_graph(parameters['layer_name'], parameters['tolerance'], parameters['simplify'])
            self.result = primal_graph

        # ----- prGRAPH TO QGSFEATURES

        elif self.transformation_type == 'prg_to_qf':
            attr_dict = parameters['prGraph'].get_attr_dict()
            features = []
            for k, v in attr_dict.items():
                feat = QgsFeature()
                feat.setAttributes(attr_dict[k].values())
                feat.setGeometry(QgsGeometry.fromWkt(attr_dict[k]['Wkt']))
                features.append(feat)
            self.result = features

        # ----- prGRAPH TO dlGRAPH

        elif self.transformation_type == 'prg_to_dlgr':
            dual_graph = nx.MultiGraph()
            id_column = parameters['sGraph'].getprGraph.id_column
            dual_graph.add_edges_from(
                [edge for edge in (parameters['sGraph'].getprGraph).dl_edges_from_pr_graph(parameters['break_at_intersections'])])
            # add nodes (some lines are not connected to others because they are pl)
            dual_graph.add_nodes_from(
                [node for node in (parameters['sGraph'].getprGraph).dl_nodes_from_pr_graph(dual_graph, parameters ['id_column'])])
            self.result = dual_graph

        # ----- fGRAPH TO SHP

        # TODO: limitation only temp, add path

        elif self.transformation_type == 'fgr_to_shp':
            network = QgsVectorLayer('LineString?crs=' + crs.toWkt(), "network", "memory")
            QgsMapLayerRegistry.instance().addMapLayer(network)
            pr = network.dataProvider()
            network.startEditing()
            pr.addAttributes([QgsField(i.name(), i.type()) for i in parameters['sGraph'].getfields])
            pr.addFeatures((parameters['sGraph'].getprGraph).features)
            network.commitChanges()
            self.result = network

        # ----- match primal graph features to qgs feature types

        elif self.transformation_type == 'prflds_to_qgsfields':
            prflds = parameters['prfields'][0]
            qgsflds = parameters['qgsfields']
            new_fields = {}
            for i in prflds:
                if i in qgsflds.keys():
                    new_fields[i] = qgsflds[i]
                else:
                    # make field of string type
                    new_fields[str(i)] = 10
            self.result = new_fields

        # ----- dlGRAPH TO SHP

        elif self.transformation_type == 'dlgr_to_shp':
            fGraph = parameters['sGraph'].getfGraph
            id_column = parameters['sGraph'].id_column
            centroids = fGraph.make_centroids_dict('feat_id')

            # new point layer with centroids
            points = QgsVectorLayer('Point?crs=' + crs.toWkt(), "dual_graph_nodes", "memory")
            QgsMapLayerRegistry.instance().addMapLayer(points)
            pr = points.dataProvider()
            points.startEditing()
            pr.addAttributes([QgsField("id", QVariant.Int)])
            points.commitChanges()
            id = int(0)
            features = []

            for i in centroids.values():
                feat = QgsFeature()
                p = QgsPoint(i[0], i[1])
                feat.setGeometry(QgsGeometry().fromPoint(p))
                feat.setAttributes([id, i[0], i[1]])
                features.append(feat)
                id += int(1)
            points.startEditing()
            pr.addFeatures(features)
            points.commitChanges()

            # new line layer with edge-edge connections
            lines = QgsVectorLayer('LineString?crs=' + crs.toWkt(), "dual_graph_edges", "memory")
            QgsMapLayerRegistry.instance().addMapLayer(lines)
            pr = lines.dataProvider()

            lines.startEditing()
            pr.addAttributes([QgsField("id", QVariant.Int), QgsField("cost", QVariant.Int)])
            lines.commitChanges()

            id = -1
            New_feat = []
            for i in parameters['dlGraph'].edges(data='cost'):
                id += 1
                new_feat = QgsFeature()
                new_geom = QgsGeometry.fromPolyline(
                    [QgsPoint(centroids[i[0]][0], centroids[i[0]][1]), QgsPoint(centroids[i[1]][0], centroids[i[1]][1])])
                new_feat.setGeometry(new_geom)
                new_feat.setAttributes([id, i[2]])
                New_feat.append(new_feat)

            lines.startEditing()
            pr.addFeatures(New_feat)
            lines.commitChanges()

