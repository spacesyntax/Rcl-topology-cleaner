# general imports
from qgis.core import QgsFeature, QgsGeometry, QgsField, QgsFields
from PyQt4.QtCore import QObject, QVariant

prototype_fields = QgsFields()
prototype_fields.append(QgsField('id', QVariant.Int))
prototype_fields.append(QgsField('connectivity', QVariant.Int))


class sNode(QObject):

    def __init__(self, id, feature, topology, adj_edges):
        QObject.__init__(self)
        self.id = id
        self.topology = topology
        self.adj_edges = adj_edges
        self.feature = feature

    def getCoords(self):
        coords = self.feature.geometry().asPoint()
        return coords[0], coords[1]