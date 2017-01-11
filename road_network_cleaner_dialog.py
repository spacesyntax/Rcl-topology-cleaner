# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RoadNetworkCleanerDialog
                                 A QGIS plugin
 This plugin clean a road centre line map.
                             -------------------
        begin                : 2016-11-10
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Space SyntaxLtd
        email                : i.kolovou@spacesyntax.com
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
from PyQt4.QtCore import pyqtSignal, Qt

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'road_network_cleaner_dialog_base.ui'))


class RoadNetworkCleanerDialog(QtGui.QDialog, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(RoadNetworkCleanerDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.outputCleaned.setPlaceholderText("Save as temporary layer...")
        self.browseCleaned.clicked.connect(self.setOutput)

        # Setup the progress bar
        self.cleaningProgress.setMinimum(0)
        self.cleaningProgress.setMaximum(100)

        self.decimalsSpin.setRange(1, 16)
        self.decimalsSpin.setSingleStep(1)
        self.decimalsSpin.setValue(6)

        self.idCombo.setDisabled(True)
        self.decimalsSpin.setDisabled(True)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def getNetwork(self):
        return self.inputCombo.currentText()

    def setOutput(self):
        file_name = QtGui.QFileDialog.getSaveFileName(self, "Save output file ", "cleaned_network", '*.shp')
        if file_name:
            self.outputCleaned.setText(file_name)

    def getOutput(self):
        print len(self.outputCleaned.text()) > 0
        if len(self.outputCleaned.text()) > 0:
            return self.outputCleaned.text()
        else:
            return None

    def getInput(self,iface):
        name = self.getNetwork()
        layer = None
        for i in iface.legendInterface().layers():
            if i.name() == name:
                layer = i
        return layer

    def popActiveLayers(self, layers_list):
        self.inputCombo.clear()
        self.inputCombo.addItems(layers_list)

    def getTolerance(self):
        return self.decimalsSpin.value()

    def get_errors(self):
        return self.errorsCheckBox.isChecked()

    def get_user_id(self):
        if self.errorsCheckBox.isChecked():
            return self.idCombo.currentText()
        else:
            return None

    def set_enabled_tolerance(self):
        if self.snapCheckBox.isChecked():
            self.decimalsSpin.setDisabled(False)
        else:
            self.decimalsSpin.setDisabled(True)

    def set_enabled_id(self):
        if self.errorsCheckBox.isChecked():
            self.idCombo.setDisabled(False)
        else:
            self.idCombo.setDisabled(True)

    def get_settings(self):
        settings = {'input': self.getNetwork(), 'output': self.getOutput(), 'tolerance': self.getTolerance(),
                    'errors': self.get_errors(), 'user_id': self.get_user_id()}
        return settings

