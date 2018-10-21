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
from PyQt4 import QtGui, uic
from PyQt4.QtCore import pyqtSignal, Qt

import os.path
import resources

from DbSettings_dialog import DbSettingsDialog

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'road_network_cleaner_dialog_base.ui'))


class RoadNetworkCleanerDialog(QtGui.QDialog, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, available_dbs, parent=None):
        """Constructor."""
        super(RoadNetworkCleanerDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        #self.outputCleaned.setText("cleaned")

        # Setup the progress bar
        self.cleaningProgress.setMinimum(0)
        self.cleaningProgress.setMaximum(100)
        # Setup some defaults
        self.meterSpin.setRange(1, 30)
        self.meterSpin.setSingleStep(1)
        self.meterSpin.setValue(5)
        self.meterSpin.setDisabled(True)

        self.memoryRadioButton.setChecked(True)
        self.shpRadioButton.setChecked(False)
        self.postgisRadioButton.setChecked(False)
        self.browseCleaned.setDisabled(True)

        self.outputCleaned.setDisabled(False)
        if available_dbs:
            self.postgisRadioButton.setDisabled(False)
            self.dbsettings_dlg = DbSettingsDialog(available_dbs)
            self.dbsettings_dlg.setDbOutput.connect(self.setDbOutput)
            self.postgisRadioButton.clicked.connect(self.setDbOutput)
        else:
            self.postgisRadioButton.setDisabled(True)

        # add GUI signals
        self.snapCheckBox.stateChanged.connect(self.set_enabled_tolerance)
        self.browseCleaned.clicked.connect(self.setOutput)
        self.mergeCheckBox.stateChanged.connect(self.toggleMergeSettings)
        self.mergeCollinearCheckBox.stateChanged.connect(self.toggleMergeCollinearSettings)

        self.memoryRadioButton.clicked.connect(self.setTempOutput)
        self.memoryRadioButton.clicked.connect(self.update_output_text)
        self.shpRadioButton.clicked.connect(self.setShpOutput)

        if self.memoryRadioButton.isChecked():
            self.outputCleaned.setText(self.getNetwork() + "_cl")

        self.dataSourceCombo.addItems(['OpenStreetMap', 'OrdnanceSurvey', 'other'])
        self.setClSettings()
        self.dataSourceCombo.currentIndexChanged.connect(self.setClSettings)

        self.errorsCheckBox.setCheckState(2)
        self.unlinksCheckBox.setCheckState(2)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def toggleMergeCollinearSettings(self):
        # untick the self.mergeCollinearCheckBox
        if self.mergeCollinearCheckBox.isChecked():
            self.mergeCheckBox.setCheckState(0)
        return

    def toggleMergeSettings(self):
        if self.mergeCheckBox.isChecked():
            self.mergeCollinearCheckBox.setCheckState(0)
        return

    def setClSettings(self):
        if self.dataSourceCombo.currentText() == 'OpenStreetMap':
            self.snapCheckBox.setCheckState(2)
            self.meterSpin.setValue(5)
            self.breakCheckBox.setCheckState(2)
            self.mergeCheckBox.setCheckState(2)
            self.orphansCheckBox.setCheckState(2)

            self.snapCheckBox.setDisabled(True)
            self.meterSpin.setDisabled(False)
            self.breakCheckBox.setDisabled(True)
            self.mergeCheckBox.setDisabled(True)
            self.mergeCollinearCheckBox.setDisabled(True)
            # self.orphansCheckBox.setDisabled(True)

        elif self.dataSourceCombo.currentText() == 'OrdnanceSurvey':
            self.snapCheckBox.setCheckState(2)
            self.meterSpin.setValue(5)
            self.breakCheckBox.setCheckState(0)
            self.mergeCheckBox.setCheckState(2)
            self.orphansCheckBox.setCheckState(2)

            self.snapCheckBox.setDisabled(True)
            self.meterSpin.setDisabled(False)
            self.breakCheckBox.setDisabled(True)
            self.mergeCheckBox.setDisabled(True)
            self.mergeCollinearCheckBox.setDisabled(True)

        else:
            self.snapCheckBox.setDisabled(False)
            self.meterSpin.setDisabled(False)
            self.breakCheckBox.setDisabled(False)
            self.mergeCheckBox.setDisabled(False)
            self.mergeCollinearCheckBox.setDisabled(False)

        return

    def getNetwork(self):
        return self.inputCombo.currentText()

    def getOutput(self):
        if self.outputCleaned.text() != 'cleaned':
            return self.outputCleaned.text()
        else:
            return None

    def popActiveLayers(self, layers_list):
        self.inputCombo.clear()
        if layers_list:
            self.inputCombo.addItems(layers_list)
            self.lockGUI(False)
        else:
            self.lockGUI(True)

    def lockGUI(self, onoff):
        # self.snapCheckBox.setDisabled(onoff)
        self.set_enabled_tolerance()
        self.memoryRadioButton.setDisabled(onoff)
        self.shpRadioButton.setDisabled(onoff)
        self.postgisRadioButton.setDisabled(onoff)
        self.outputCleaned.setDisabled(onoff)
        self.disable_browse()
        self.unlinksCheckBox.setDisabled(onoff)
        self.errorsCheckBox.setDisabled(onoff)
        self.cleanButton.setDisabled(onoff)

    def getTolerance(self):
        if self.snapCheckBox.isChecked():
            return self.meterSpin.value()
        else:
            return None

    def getBreakages(self):
        if self.breakCheckBox.isChecked():
            return True
        else:
            return False

    def getMerge(self):
        if self.mergeCheckBox.isChecked():
            return 'between intersections'
        elif self.mergeCollinearCheckBox.isChecked():
            return ['collinear', self.collinearSpinBox.value()]
        else:
            return None

    def getOrphans(self):
        if self.orphansCheckBox.isChecked():
            return True
        else:
            return False

    def disable_browse(self):
        if self.memoryRadioButton.isChecked():
            self.browseCleaned.setDisabled(True)
        else:
            self.browseCleaned.setDisabled(False)

    def get_errors(self):
        return self.errorsCheckBox.isChecked()

    def get_unlinks(self):
        return self.unlinksCheckBox.isChecked()

    def update_output_text(self):
        if self.memoryRadioButton.isChecked():
            return "cleaned"
        else:
            return

    def get_output_type(self):
        if self.shpRadioButton.isChecked():
            return 'shp'
        elif self.postgisRadioButton.isChecked():
            return 'postgis'
        else:
            return 'memory'

    def set_enabled_tolerance(self):
        if self.snapCheckBox.isChecked():
            self.meterSpin.setDisabled(False)
        else:
            self.meterSpin.setDisabled(True)

    def get_settings(self):
        settings = {'input': self.getNetwork(), 'output': self.getOutput(), 'snap': self.getTolerance(), 'break': self.getBreakages(), 'merge':self.getMerge(), 'orphans':self.getOrphans(),
                    'errors': self.get_errors(), 'unlinks': self.get_unlinks(),  'user_id': None, 'output_type': self.get_output_type()}
        return settings

    def get_dbsettings(self):
        settings = self.dbsettings_dlg.getDbSettings()
        return settings

    def setOutput(self):
        if self.shpRadioButton.isChecked():
            self.file_name = QtGui.QFileDialog.getSaveFileName(self, "Save output file ", "cleaned_network", '*.shp')
            if self.file_name:
                self.outputCleaned.setText(self.file_name)
            else:
                self.outputCleaned.clear()
        elif self.postgisRadioButton.isChecked():
            self.dbsettings_dlg.show()
            # Run the dialog event loop
            result2 = self.dbsettings_dlg.exec_()
            self.dbsettings = self.dbsettings_dlg.getDbSettings()
        return

    def setDbOutput(self):
        self.disable_browse()
        if self.postgisRadioButton.isChecked():
            self.outputCleaned.clear()
            table_name = self.getNetwork() + "_cl"
            self.dbsettings_dlg.nameLineEdit.setText(table_name)
            try:
                self.dbsettings = self.dbsettings_dlg.getDbSettings()
                db_layer_name = "%s:%s:%s" % (self.dbsettings['dbname'], self.dbsettings['schema'], self.dbsettings['table_name'])
                self.outputCleaned.setText(db_layer_name)
            except:
                self.outputCleaned.clear()
            self.outputCleaned.setDisabled(True)

    def setTempOutput(self):
        self.disable_browse()
        temp_name = self.getNetwork() + "_cl"
        self.outputCleaned.setText(temp_name)
        self.outputCleaned.setDisabled(False)

    def setShpOutput(self):
        self.disable_browse()
        try:
            self.outputCleaned.setText(self.file_name)
        except :
            self.outputCleaned.clear()
        self.outputCleaned.setDisabled(True)
