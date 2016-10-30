
# plugin module imports
from shpFunctions import read_shp_to_multi_graph

# ----- TRANSFORMATION TYPES -----


class transformer:

    def __init__(self, parameters, transformation_type):
        self.parameters = parameters
        self.transformation_type = transformation_type
        self.id_column = parameters['id_column']

        # ----- SHP TO prGRAPH

        if self.transformation_type == 'shp_to_pgr':
            # TODO: check the parallel lines (1 of the parallel edges is not correct connected)
            primal_graph = read_shp_to_multi_graph(parameters['layer_name'], parameters['tolerance'], parameters['simplify'])
            self.result = primal_graph



