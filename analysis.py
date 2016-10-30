# other imports


# plugin module imports

from sGraph import dual_graph

from otherFunctions.utilityFunctions import getLayerByName
from otherFunctions.shpFunctions import get_field_types
from otherFunctions.transformationFunctions import transformer

class clean:

    def __init__(self, settings):

        self.settings = settings

    def run(self):
        # cleaning settings
        layer_name = self.settings['input']
        path = self.settings['output']
        tolerance = self.settings['tolerance']
        base_id = 'id_in'

        # project settings
        n = getLayerByName(layer_name)
        crs = n.dataProvider().crs()
        encoding = n.dataProvider().encoding()
        geom_type = n.dataProvider().geometryType()
        qgsflds = get_field_types(layer_name)

        # shp/postgis to prGraph instance
        transformation_type = 'shp_to_pgr'
        simplify = True
        parameters = {'layer_name': layer_name, 'tolerance': tolerance, 'simplify': simplify, 'id_column': base_id}
        primal_graph = transformer(parameters, transformation_type).result
        any_primal_graph = primal_graph.prGraph(primal_graph, base_id, True)

        # break at intersections and overlaping geometries
        broken_primal = any_primal_graph.break_graph(tolerance, simplify)
        broken_clean_primal = broken_primal.rmv_dupl_overlaps()

        # transform primal graph to dual graph
        centroids = broken_clean_primal.get_centroids_dict()
        broken_dual = dual_graph.dlGraph(broken_clean_primal.to_dual(True, False, False), broken_clean_primal.uid, centroids, True)

        # Merge between intersections
        merged_primal = broken_dual.merge(broken_clean_primal, tolerance, simplify)
        merged_clean_primal = merged_primal.rmv_dupl_overlaps()
        name = layer_name + '_cleaned'

        # return shapefile
        return merged_clean_primal.to_shp(path, name, crs, encoding, geom_type, qgsflds)