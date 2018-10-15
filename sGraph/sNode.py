# general imports
from qgis.core import QgsFeature, QgsGeometry, QgsField
from PyQt4.QtCore import QObject, QVariant

prototype_fields = QgsFields()
prototype_fields.append(QgsField('id', QVariant.Int))
prototype_fields.append(QgsField('connectivity', QVariant.Int))


class sNode(QObject):

    def __init__(self, id, topology, qgspoint):
        QObject.__init__(self)
        self.id = id
        self.topology = topology
        self.connectivity = len(topology)
        self.point = qgspoint
        self.geometry = QgsGeometry.fromPoint(self.point)
        self.closest_nodes = [id]

    def getFeature(self):
        f = QgsFeature()
        f.setFeatureId(self.id)
        f.setGeometry(self.geometry)
        f.setFields(prototype_fields)
        f.setAttributes([self.id, self.connectivity])
        return f