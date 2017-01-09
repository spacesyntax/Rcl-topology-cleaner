
from qgis.networkanalysis import *

layer_name = 'broken'
layer = getLayerByName(layer_name)
director = QgsLineVectorLayerDirector(layer, -1, '', '', '', 3)
director = QgsLineVectorLayerDirector(layer, 5, 'yes', '1', 'no', 3)

properter = QgsDistanceArcProperter()

properter = QgsAbgleArcProperter()

director.addProperter(properter)

otf = False
crs =

epsg = crs.authid()[5:]
# get endpoints
pStart=QgsPoint(, )

builder = QgsGraphBuilder(crs, otf, tolerance, epsg)

for f in features_to_merge:
    f


tiedPoints = director.makeGraph(builder, (startpoint, endpoint))

graph = builder.graph()


startId = graph.findVertex(pstart)

tree = QgsGraphAnalyser.shortestTree(graph, startId, 0)

(tree, cost) = QgsGraphAnalyser.dijkstra(graph, startId, 0)

