# general imports
from qgis.core import QgsFeature, QgsGeometry, QgsField
from PyQt4.QtCore import QObject, QVariant

class sEdge(QObject):
    def __init__(self, id, feature, nodes):
        QObject.__init__(self)
        self.id = id
        self.feature = feature
        self.nodes = nodes

    # function because nodes might change
    def getStartNode(self):
        return self.nodes[0]

    def getEndNode(self):
        return self.nodes[-1]

    def setStartNode(self, node_id):
        self.nodes[0] = node_id

    def setEndNode(self, node_id):
        self.nodes[-1] = node_id

    def replaceNodes(self, candidate_nodes, newSNode):
        if {self.getEndNode()}.intersection(set(candidate_nodes)) == {self.getEndNode()}:
            self.setEndNode(newSNode.id)
            polyline = self.feature.geometry().asPolyline()[:-1] + [newSNode.point]
            self.feature.setGeometry(QgsGeometry.fromPolyline(polyline))
        if {self.getStartNode()}.intersection(set(candidate_nodes)) == {self.getStartNode()}:
            polyline = [newSNode.point] + self.feature.geometry().asPolyline()[1:]
            self.feature.setGeometry(QgsGeometry.fromPolyline(polyline))
            self.setStartNode(newSNode.id)
        return True




