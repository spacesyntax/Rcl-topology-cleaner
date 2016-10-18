
# imports
import networkx as nx
# import utilityFunctions as uF
# import shpFunctions as sF
# import superGraph

# ----- TRANSFORMATION TYPES -----

class transformer:

    def __init__(self, parameters, transformation_type):
        self.parameters = parameters
        self.transformation_type = transformation_type
        self.id_column = parameters['id_column']

        # ----- SHP TO SGRAPH

        if self.transformation_type == 'shp_to_pgr':
            # TODO: check the parallel lines (1 of the parallel edges is not correct connected)
            primal_graph = read_shp_to_multi_graph(parameters['layer_name'], parameters['tolerance'], parameters['simplify'])
            self.result = primal_graph

        # ----- prGRAPH TO QGSFEATURES

        elif self.transformation_type == 'prg_to_qf':
            attr_dict = parameters['prGraph'].get_attr_dict()
            features = []
            for k, v in attr_dict.items():
                feat = QgsFeature()
                feat.initAttributes(len(attr_dict[k].values()))
                feat.setAttributes(attr_dict[k].values())
                feat.setGeometry(QgsGeometry.fromWkt(attr_dict[k]['Wkt']))
                features.append(feat)
            self.result = features

        # ----- prGRAPH TO dlGRAPH

        elif self.transformation_type == 'prg_to_dlgr':
            dual_graph = nx.MultiGraph()
            dual_graph.add_edges_from(
                [edge for edge in parameters['prGraph'].dl_edges_from_pr_graph(parameters['break_at_intersections'])])
            # add nodes (some lines are not connected to others because they are pl)
            dual_graph.add_nodes_from(
                [node for node in parameters['prGraph'].dl_nodes_from_pr_graph(dual_graph, parameters ['id_column'])])
            self.result = dual_graph

        # ----- fGRAPH TO SHP

        elif self.transformation_type == 'fm_to_shp':
            if parameters['path'] is None:
                network = QgsVectorLayer('LineString?crs=' + parameters['crs'].toWkt(), parameters['name'], "memory")
            else:
                # provider.fields()
                file_writer = QgsVectorFileWriter(parameters['path'], parameters['encoding'], None,  parameters['geom_type'], parameters['crs'].crs(), "ESRI Shapefile")
                if file_writer.hasError() != QgsVectorFileWriter.NoError:
                    print "Error when creating shapefile: ", file_writer.errorMessage()
                del file_writer
                network = QgsVectorLayer(parameters['path'], parameters['name'], "ogr")
            QgsMapLayerRegistry.instance().addMapLayer(network)
            pr = network.dataProvider()
            network.startEditing()
            pr.addAttributes(parameters['fields'])
            pr.addFeatures(parameters['fMap'].obj)
            network.commitChanges()
            self.result = network

        # ----- match primal graph features to qgs feature types

        elif self.transformation_type == 'prflds_to_qgsfields':
            prflds = parameters['prfields'][0]
            qgsflds = parameters['qgsfields']
            new_fields = []
            # TODO: work with field type not name (for example you may have Integer64)
            for i in prflds:
                if i in qgsflds.keys():
                    new_fields.append(QgsField(i,qgsflds_types[qgsflds[i]]))
                else:
                    # make field of string type
                    new_fields.append(QgsField(i, qgsflds_types[u'String']))
            self.result = new_fields

        # ----- dlGRAPH TO SHP

        elif self.transformation_type == 'dlgr_to_qf':
            centroids = parameters['fMap'].make_centroids_dict(parameters['attr_index'])

            dual_graph_edges = []
            for i in parameters['dlGraph'].obj.edges(data='cost'):
                new_feat = QgsFeature()
                new_geom = QgsGeometry.fromPolyline(
                    [QgsPoint(centroids[i[0]][0], centroids[i[0]][1]), QgsPoint(centroids[i[1]][0], centroids[i[1]][1])])
                new_feat.setGeometry(new_geom)
                new_feat.setAttributes([i[0], i[1], i[2]])
                dual_graph_edges.append(new_feat)
            self.result = dual_graph_edges

