# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RoadNetworkCleaner
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
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt, QThread
from PyQt4.QtGui import QAction, QIcon
from PyQt4 import QtGui, uic

from qgis.core import QgsMapLayer, QgsMapLayerRegistry, QgsMessageLog, QgsDataSourceURI
from qgis.gui import QgsMessageBar
from qgis.utils import *

import db_manager.db_plugins.postgis.connector as con
import os.path
import traceback

# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from road_network_cleaner_dialog import RoadNetworkCleanerDialog
from DbSettings_dialog import DbSettingsDialog
from ClSettings_dialog import ClSettingsDialog
from sGraph.break_tools import *  # better give these a name to make it explicit to which module the methods belong
from sGraph.merge_tools import *
from sGraph.utilityFunctions import *


# Import the debug library
# set is_debug to False in release version
is_debug = False
try:
    import pydevd
    has_pydevd = True
except ImportError, e:
    has_pydevd = False
    is_debug = False

class RoadNetworkCleaner:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        self.legend = self.iface.legendInterface()

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'RoadNetworkCleaner_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        # load the dialog from the run method otherwise the objects gets created multiple times
        self.dlg = None
        self.dbsettings_dlg = None
        self.clsettings_dlg = None

        self.cleaning = None
        self.thread = None

        self.available_dbs = None

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&RoadNetworkCleaner')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'RoadNetworkCleaner')
        self.toolbar.setObjectName(u'RoadNetworkCleaner')

        # Setup debugger
        if has_pydevd and is_debug:
            pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True, suspend=True)

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('RoadNetworkCleaner', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/RoadNetworkCleaner/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Road network cleaner'),
            callback=self.run,
            parent=self.iface.mainWindow())


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&RoadNetworkCleaner'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

        self.unloadGUI()

    def getActiveLayers(self):
        layers_list = []
        for layer in self.iface.legendInterface().layers():
            if layer.isValid() and layer.type() == QgsMapLayer.VectorLayer:
                if layer.hasGeometryType() and (layer.geometryType() == 1):
                    layers_list.append(layer.name())
        return layers_list

    def updateLayers(self):
        layers = self.getActiveLayers()
        self.dlg.popActiveLayers(layers)

    def popSchemas(self):
        self.dbsettings_dlg.schemaCombo.clear()
        schemas = []
        selected_db = self.dbsettings_dlg.getSelectedDb()
        if len(self.dbsettings_dlg.getSelectedDb()) > 1:
            try:
                print 'tries'
                uri = QgsDataSourceURI()
                db_info = self.available_dbs[selected_db]
                print db_info, selected_db
                conname = selected_db
                dbname = db_info['database']
                user = db_info['username']
                host = db_info['host']
                port = db_info['port']
                password = db_info['password']
                uri.setConnection(host, port, dbname, user, password)
                #c = con.PostGisDBConnector(uri)
                #schemas = sorted(list(set([i[2] for i in c.getTables()])))
                connstring = "dbname=%s user=%s host=%s port=%s password=%s" % (dbname, user, host, port, password)
                schemas = getPostgisSchemas(connstring)
            except:
                print 'error'
                pass
        self.dbsettings_dlg.schemaCombo.addItems(schemas)

    def setOutput(self):
        if self.dlg.shpRadioButton.isChecked():
            self.file_name = QtGui.QFileDialog.getSaveFileName(self.dlg, "Save output file ", "cleaned_network", '*.shp')
            if self.file_name:
                self.dlg.outputCleaned.setText(self.file_name)
            else:
                self.dlg.outputCleaned.clear()
        elif self.dlg.postgisRadioButton.isChecked():
            self.dbsettings_dlg.show()
            # Run the dialog event loop
            result2 = self.dbsettings_dlg.exec_()
            self.dbsettings = self.dbsettings_dlg.getDbSettings(self.available_dbs)
        return

    def setDbOutput(self):
        self.dlg.disable_browse()
        if self.dlg.postgisRadioButton.isChecked():
            self.dlg.outputCleaned.clear()
            try:
                self.dbsettings = self.dbsettings_dlg.getDbSettings(self.available_dbs)
                db_layer_name = "%s:%s:%s" % (self.dbsettings['dbname'], self.dbsettings['schema'], self.dbsettings['table_name'])
                self.dlg.outputCleaned.setText(db_layer_name)
            except:
                self.dlg.outputCleaned.clear()
            self.dlg.outputCleaned.setDisabled(True)

    def setTempOutput(self):
        self.dlg.disable_browse()
        temp_name = 'cleaned'
        self.dlg.outputCleaned.setText(temp_name)
        self.dlg.outputCleaned.setDisabled(False)

    def setShpOutput(self):
        self.dlg.disable_browse()
        try:
            self.dlg.outputCleaned.setText(self.file_name)
        except :
            self.dlg.outputCleaned.clear()
        self.dlg.outputCleaned.setDisabled(True)

    def openClSettings(self):
        self.clsettings_dlg.show()
        result1 = self.clsettings_dlg.exec_()

    # SOURCE: Network Segmenter https://github.com/OpenDigitalWorks/NetworkSegmenter
    # SOURCE: https://snorfalorpagus.net/blog/2013/12/07/multithreading-in-qgis-python-plugins/

    def giveMessage(self, message, level):
        # Gives warning according to message
        self.iface.messageBar().pushMessage("Road network cleaner: ", "%s" % (message), level, duration=5)

    def cleaningError(self, e, exception_string):
        # Gives error according to message
        QgsMessageLog.logMessage('Cleaning thread raised an exception: %s' % exception_string, level=QgsMessageLog.CRITICAL)
        self.dlg.close()

    def startCleaning(self):
        self.dlg.cleaningProgress.reset()
        settings = self.dlg.get_settings()
        if settings['output_type'] == 'postgis':
            db_settings = self.dbsettings_dlg.getDbSettings(self.available_dbs)
            settings.update(db_settings)

        if settings['input']:

            cleaning = self.clean(settings, self.iface)
            # start the cleaning in a new thread
            thread = QThread()
            cleaning.moveToThread(thread)
            cleaning.finished.connect(self.cleaningFinished)
            cleaning.error.connect(self.cleaningError)
            cleaning.warning.connect(self.giveMessage)
            cleaning.cl_progress.connect(self.dlg.cleaningProgress.setValue)

            thread.started.connect(cleaning.run)
            # thread.finished.connect(self.cleaningFinished)

            self.thread = thread
            self.cleaning = cleaning

            self.thread.start()

            print 'started'
        else:
            self.giveMessage('Missing user input!', QgsMessageBar.INFO)
            return

    def cleaningFinished(self, ret):
        print 'trying to finish'
        # load the cleaning results layer
        try:
            # report the result
            #for layer in ret:
            #    if layer:
            #        QgsMapLayerRegistry.instance().addMapLayer(layer)
            #        layer.updateExtents()
            #        self.iface.mapCanvas().refresh()

            self.giveMessage('Process ended successfully!', QgsMessageBar.INFO)

        except Exception, e:
            # notify the user that sth went wrong
            self.cleaning.error.emit(e, traceback.format_exc())
            self.giveMessage('Something went wrong! See the message log for more information', QgsMessageBar.CRITICAL)

        # clean up the worker and thread
        #self.cleaning.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()

        print 'thread running', self.thread.isRunning()
        print 'has finished', self.thread.isFinished()

        self.thread = None
        self.cleaning = None

        if self.dlg:
            self.dlg.cleaningProgress.reset()
            self.dlg.close()


    def killCleaning(self):
        print 'trying to cancel'
        # add emit signal to breakTool or mergeTool only to stop the loop
        if self.cleaning:

            try:
                dummy = self.cleaning.br
                del dummy
                self.cleaning.br.killed = True
            except AttributeError:
                pass
            try:
                dummy = self.cleaning.mrg
                del dummy
                self.cleaning.mrg.killed = True
            except AttributeError:
                pass
            # Disconnect signals
            self.cleaning.finished.disconnect(self.cleaningFinished)
            self.cleaning.error.disconnect(self.cleaningError)
            self.cleaning.warning.disconnect(self.giveMessage)
            self.cleaning.cl_progress.disconnect(self.dlg.cleaningProgress.setValue)
            # Clean up thread and analysis
            self.cleaning.kill()
            # kill process of breaking if it is running
            # kill process of merging if it is running

            self.cleaning.deleteLater()
            self.thread.quit()
            self.thread.wait()
            self.thread.deleteLater()
            self.cleaning = None
            self.dlg.cleaningProgress.reset()
            self.dlg.close()
        else:
            self.dlg.close()


    # SOURCE: https://snorfalorpagus.net/blog/2013/12/07/multithreading-in-qgis-python-plugins/
    class clean(QObject):

        # Setup signals
        finished = pyqtSignal(bool)
        error = pyqtSignal(Exception, basestring)
        cl_progress = pyqtSignal(float)
        warning = pyqtSignal(str)
        cl_killed = pyqtSignal(bool)

        def __init__(self, settings, iface):
            QObject.__init__(self)
            self.settings = settings
            self.iface = iface
            self.total =0

        def add_step(self,step):
            self.total += step
            return self.total

        def run(self):
            ret = None
            if self.settings:
                try:
                    # cleaning settings
                    layer_name = self.settings['input']
                    path = self.settings['output']
                    tolerance = self.settings['tolerance']
                    output_type = self.settings['output_type']

                    # project settings
                    layer = getLayerByName(layer_name)
                    crs = layer.dataProvider().crs()
                    encoding = layer.dataProvider().encoding()
                    geom_type = layer.dataProvider().geometryType()

                    self.cl_progress.emit(2)

                    self.br = breakTool(layer, tolerance, None, self.settings['errors'], self.settings['unlinks'])

                    if self.cl_killed is True or self.br.killed is True: return

                    self.br.add_edges()

                    if self.cl_killed is True or self.br.killed is True: return

                    self.cl_progress.emit(5)
                    self.total = 5
                    step = 40/ self.br.feat_count
                    self.br.progress.connect(lambda incr=self.add_step(step): self.cl_progress.emit(incr))

                    broken_features = self.br.break_features()

                    if self.cl_killed is True or self.br.killed is True: return

                    self.cl_progress.emit(45)

                    self.mrg = mergeTool(broken_features, None, True)

                    # TODO test
                    try:
                        step = 40/ len(self.mrg.con_1)
                        self.mrg.progress.connect(lambda incr=self.add_step(step): self.cl_progress.emit(incr))
                    except ZeroDivisionError:
                        pass

                    merged_features = self.mrg.merge()

                    if self.cl_killed is True or self.mrg.killed is True: return

                    fields = self.br.layer_fields

                    (final, errors, unlinks) = (None, None, None)
                    if output_type in ['shp', 'memory']:
                        final = to_shp(path, merged_features, fields, crs, 'cleaned', encoding, geom_type)
                    else:
                        final = to_dblayer(self.settings['dbname'], self.settings['user'], self.settings['host'], self.settings['port'],self.settings['password'], self.settings['schema'], self.settings['table_name'], fields, merged_features, crs)
                        try:
                            # None will be emitted if db layer is not created
                            self.error.emit(final, traceback.format_exc())
                        except :
                            pass

                    if self.settings['errors']:
                        self.br.updateErrors(self.mrg.errors_features)
                        errors_list = [[k, [[k], [v[0]]], v[1]] for k, v in self.br.errors_features.items()]
                        errors = to_shp(None, errors_list, [QgsField('id_input', QVariant.Int), QgsField('errors', QVariant.String)], crs, 'errors', encoding, geom_type)

                    if self.settings['unlinks']:
                        unlinks = to_shp(None, self.br.unlinked_features, [QgsField('id', QVariant.Int), QgsField('line_id1', QVariant.Int), QgsField('line_id2', QVariant.Int), QgsField('x', QVariant.Double), QgsField('y', QVariant.Double)], crs,'unlinks', encoding, 0)

                    print "survived!"
                    self.cl_progress.emit(100)
                    # return cleaned shapefile and errors
                    ret = (errors, final, unlinks)

                    for l in ret:
                        if l:
                            print "adding layer"
                            QgsMapLayerRegistry.instance().addMapLayer(l)

                except Exception, e:
                    # forward the exception upstream
                    self.error.emit(e, traceback.format_exc())

            self.finished.emit(True)

        def kill(self):
            self.cl_killed = True

    def run(self):
        """Run method that performs all the real work"""

        self.dlg = RoadNetworkCleanerDialog()
        self.dbsettings_dlg = DbSettingsDialog()
        self.clsettings_dlg = ClSettingsDialog()
        self.available_dbs = self.dbsettings_dlg.getQGISDbs()

        # show the dialog
        self.dlg.show()
        print 'clicked'

        self.dlg.closingPlugin.connect(self.unloadGUI)

        # setup GUI signals
        self.dlg.cleanButton.clicked.connect(self.startCleaning)
        self.dlg.cancelButton.clicked.connect(self.killCleaning)

        self.dlg.snapCheckBox.stateChanged.connect(self.dlg.set_enabled_tolerance)
        self.dlg.browseCleaned.clicked.connect(self.setOutput)
        self.dlg.settingsButton.clicked.connect(self.openClSettings)

        self.dbsettings_dlg.dbCombo.currentIndexChanged.connect(self.setDbOutput)
        self.dbsettings_dlg.schemaCombo.currentIndexChanged.connect(self.setDbOutput)
        self.dbsettings_dlg.nameLineEdit.textChanged.connect(self.setDbOutput)

        self.dlg.memoryRadioButton.clicked.connect(self.setTempOutput)
        self.dlg.memoryRadioButton.clicked.connect(self.dlg.update_output_text)
        self.dlg.shpRadioButton.clicked.connect(self.setShpOutput)
        self.dlg.postgisRadioButton.clicked.connect(self.setDbOutput)

        self.dlg.popActiveLayers(self.getActiveLayers())

        self.dbsettings_dlg.popDbs(self.available_dbs)

        if self.dbsettings_dlg.dbCombo.currentText() in self.available_dbs.keys():
            self.popSchemas()

        if self.dlg.memoryRadioButton.isChecked():
            self.dlg.outputCleaned.setText('temporary layer')

        self.dbsettings_dlg.dbCombo.currentIndexChanged.connect(self.popSchemas)

        self.legend.itemAdded.connect(self.updateLayers)
        self.legend.itemRemoved.connect(self.updateLayers)

        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass

    def unloadGUI(self):

        if self.dlg:
            self.dlg.closingPlugin.disconnect(self.unloadGUI)

            self.dlg.cleanButton.clicked.disconnect(self.startCleaning)
            self.dlg.cancelButton.clicked.disconnect(self.killCleaning)

            # settings popup
            self.dlg.snapCheckBox.stateChanged.disconnect(self.dlg.set_enabled_tolerance)

            self.dlg.browseCleaned.clicked.disconnect(self.setOutput)
            self.dlg.settingsButton.clicked.disconnect(self.openClSettings)

            self.dlg.memoryRadioButton.clicked.disconnect(self.setTempOutput)
            self.dlg.memoryRadioButton.clicked.disconnect(self.dlg.update_output_text)
            self.dlg.shpRadioButton.clicked.disconnect(self.setShpOutput)
            self.dlg.postgisRadioButton.clicked.disconnect(self.setDbOutput)

        if self.dbsettings_dlg:
            self.dbsettings_dlg.dbCombo.currentIndexChanged.disconnect(self.setDbOutput)
            self.dbsettings_dlg.schemaCombo.currentIndexChanged.disconnect(self.setDbOutput)
            self.dbsettings_dlg.nameLineEdit.textChanged.disconnect(self.setDbOutput)

            self.dbsettings_dlg.dbCombo.currentIndexChanged.disconnect(self.popSchemas)

        try:
            self.legend.itemAdded.disconnect(self.updateLayers)
            self.legend.itemRemoved.disconnect(self.updateLayers)
        except TypeError:
            pass

        self.dlg = None
