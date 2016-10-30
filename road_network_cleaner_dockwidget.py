# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RoadNetworkCleanerDockWidget
                                 A QGIS plugin
 This plugin cleans the road centre line topology
                             -------------------
        begin                : 2016-10-10
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Spece Syntax Ltd
        email                : I.Kolovou@spacesyntax.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from PyQt4 import QtGui, uic
from PyQt4.QtCore import pyqtSignal

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'road_network_cleaner_dockwidget_base.ui'))


class RoadNetworkCleanerDockWidget(QtGui.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(RoadNetworkCleanerDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.outputText.setPlaceholderText("Save as temporary layer...")
        self.browseButton.clicked.connect(self.setOutput)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def getNetwork(self):
        return self.inputCombo.currentText()

    def setOutput(self):
        file_name = QtGui.QFileDialog.getSaveFileName(self, "Save output file ", "cleaned_network", '*.shp')
        if file_name:
            self.outputText.setText(file_name)

    def getOutput(self):
        return self.outputText.text()

    def getInput(self):
        name = self.getNetwork()
        layer = None
        for i in self.iface.legendInterface().layers():
            if i.name() == name:
                layer = i
        return layer

    def popActiveLayers(self, layers_list):
        self.inputCombo.clear()
        self.inputCombo.addItems(layers_list)

    def popTolerance(self):
        self.toleranceCombo.clear()
        self.toleranceCombo.addItems(['mm', 'cm', 'dm', 'm'])

    def getTolerance(self):
        return self.toleranceCombo.currentText()

    def get_settings(self):
        decimal_tolerance = {'m': 1,'dm': 2, 'cm': 3, 'mm': 4}
        settings = {'input': self.getNetwork(), 'output': self.getOutput(), 'tolerance': decimal_tolerance[self.getTolerance()]}
        return settings

    def giveWarningMessage(self, message):
        # Gives warning according to message
        self.iface.messageBar().pushMessage(
            "Rcl simplification: ",
            "%s" % (message),
            level=QgsMessageBar.WARNING,
            duration=5)

    def cancel(self):
        pass

    def diagnose(self):
        pass

    def clean(self):
        pass
