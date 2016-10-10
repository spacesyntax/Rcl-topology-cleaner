
# super graph object
# properties:
# prGRpah primal graph
# fGraph features
# dlGraph (incl. topology) dual graph
# specification: column with id_attribute

#import prGraph
#import fGraph
#import transformFunctions as trF
# import globalVariables as gl_var

# setup global variables

# ----- GLOBAL CHARACTERISTICS -----

# set up fields
# get fields from initial shp and add variables from multi-graph
# dictionary of field name
# id column
# crs


#if topology is True:
#    self.topology = {point: edge for point, edge in self.prGraph.topology_iter(False)}

#self.fields = self.prGraph.get_fields()

#id_column


class SuperGraph:

    def __init__(self, feature_map, primal_graph, dual_graph, id_column):

        # default values setup up to None
        self.prGraph = primal_graph
        self.fMap = feature_map
        self.dlGraph = dual_graph
        self.id_column = id_column
