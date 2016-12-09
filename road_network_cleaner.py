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
from qgis.core import QgsMapLayer, QgsMapLayerRegistry, QgsMessageLog
from qgis.gui import QgsMessageBar

from qgis.utils import *
# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from road_network_cleaner_dialog import RoadNetworkCleanerDialog
import os.path


from sGraph.dual_graph import *
from sGraph.shpFunctions import *
import traceback


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
        self.dlg = RoadNetworkCleanerDialog()
        self.cleaning = None

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&RoadNetworkCleaner')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'RoadNetworkCleaner')
        self.toolbar.setObjectName(u'RoadNetworkCleaner')

        # Setup debugger
        if has_pydevd and is_debug:
            pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True, suspend=True)

        # setup GUI signals
        # self.dockwidget.cleanButton.clicked.connect(self.runCleaning)
        self.dlg.cleanButton.clicked.connect(self.startCleaning)
        self.dlg.cancelButton.clicked.connect(self.killCleaning)
        self.dlg.snapCheckBox.stateChanged.connect(self.dlg.set_enabled_tolerance)
        self.dlg.errorsCheckBox.stateChanged.connect(self.dlg.set_enabled_id)
        self.dlg.inputCombo.currentIndexChanged.connect(self.popIdColumn)

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

    def getActiveLayers(self, iface):
        layers_list = []
        for layer in iface.legendInterface().layers():
            if layer.isValid() and layer.type() == QgsMapLayer.VectorLayer:
                if layer.hasGeometryType() and (layer.geometryType() == 1):
                    layers_list.append(layer.name())
        return layers_list

    def popIdColumn(self):
        self.dlg.idCombo.clear()
        cols_list = []
        if self.dlg.getInput(self.iface):
            for col in self.dlg.getInput(self.iface).dataProvider().fields():
                cols_list.append(col.name())
        self.dlg.idCombo.addItems(cols_list)

    def render(self,vector_layer):
        QgsMapLayerRegistry.instance().addMapLayer(vector_layer)

    # SOURCE: Network Segmenter https://github.com/OpenDigitalWorks/NetworkSegmenter
    # SOURCE: https://snorfalorpagus.net/blog/2013/12/07/multithreading-in-qgis-python-plugins/

    def giveMessage(self, message, level):
        # Gives warning according to message
        self.iface.messageBar().pushMessage("Road network cleaner: ", "%s" % (message), level, duration=5)

    def cleaningError(self, e, exception_string):
        # Gives error according to message
        QgsMessageLog.logMessage('Cleaning thread raised an exception: %s' % exception_string, level=QgsMessageLog.CRITICAL)

    def startCleaning(self, settings):
        self.dlg.cleaningProgress.reset()
        settings = self.dlg.get_settings()
        cleaning = clean(settings, self.iface)

        # start the cleaning in a new thread
        thread = QThread()
        cleaning.moveToThread(thread)
        cleaning.finished.connect(self.cleaningFinished)
        cleaning.error.connect(self.cleaningError)
        cleaning.warning.connect(self.giveMessage)
        cleaning.progress.connect(self.dlg.cleaningProgress.setValue)
        thread.started.connect(cleaning.run)
        thread.start()
        self.thread = thread
        self.cleaning = cleaning

    def cleaningFinished(self, ret):
        # clean up  the worker and thread
        self.cleaning.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        self.cleaning = None

        if ret:
            # report the result
            # a, b = ret
            for i in ret:
                self.render(i)
            self.giveMessage('Process ended successfully!', QgsMessageBar.INFO)

        else:
            # notify the user that sth went wrong
            self.giveMessage('Something went wrong! See the message log for more information', QgsMessageBar.CRITICAL)

        self.dlg.cleaningProgress.reset()

    def killCleaning(self):
        if self.cleaning:
            # Disconnect signals
            self.cleaning.finished.disconnect(self.cleaningFinished)
            self.cleaning.error.disconnect(self.cleaningError)
            self.cleaning.warning.disconnect(self.giveMessage)
            self.cleaning.progress.disconnect(self.dlg.cleaningProgress.setValue)
            # Clean up thread and analysis
            self.cleaning.kill()
            self.cleaning.deleteLater()
            self.thread.quit()
            self.thread.wait()
            self.thread.deleteLater()
            self.cleaning = None
            self.dlg.cleaningProgress.reset()

    def startWorker(self,any_worker):
        thread = QThread()
        any_worker.moveToThread(thread)
        any_worker.finished.connect(self.finishWorker)
        any_worker.error.connect(self.cleaningError)
        any_worker.warning.connect(self.giveMessage)
        any_worker.progress.connect(self.changePB)
        thread.started.connect(any_worker.run)
        thread.start()
        self.thread = thread
        self.any_worker = any_worker

    def finishWorker(self, ret):
        # clean up  the worker and thread
        self.any_worker.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        self.any_worker = None

        if ret:
            # report the result
            # a, b = ret
            for i in ret:
                self.render(i)
            self.giveMessage('Process ended successfully!', QgsMessageBar.INFO)

        else:
            # notify the user that sth went wrong
            self.giveMessage('Something went wrong! See the message log for more information', QgsMessageBar.CRITICAL)

        self.dlg.cleaningProgress.reset()


    def run(self):
        """Run method that performs all the real work"""
        # show the dialog
        self.dlg.show()
        self.dlg.popActiveLayers(self.getActiveLayers(self.iface))
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass


# SOURCE: https://snorfalorpagus.net/blog/2013/12/07/multithreading-in-qgis-python-plugins/

class clean(QObject):

    # Setup signals
    finished = pyqtSignal(object)
    error = pyqtSignal(Exception, basestring)
    progress = pyqtSignal(float)
    warning = pyqtSignal(str)

    def __init__(self, settings, iface):
        QObject.__init__(self)
        self.settings = settings
        self.killed = False
        self.iface = iface

    def run(self):
        ret = None
        if self.settings:
            try:
                # cleaning settings
                layer_name = self.settings['input']
                path = self.settings['output']
                tolerance = self.settings['tolerance']
                user_id = self.settings['user_id']
                base_id = 'id_in'

                # project settings
                n = getLayerByName(layer_name)
                crs = n.dataProvider().crs()
                encoding = n.dataProvider().encoding()
                geom_type = n.dataProvider().geometryType()
                qgsflds = get_field_types(layer_name)

                self.progress.emit(10)

                # shp/postgis to prGraph instance
                transformation_type = 'shp_to_pgr'
                simplify = True
                get_invalids = False
                get_multiparts = False
                if self.settings['errors']:
                    get_invalids = True
                    get_multiparts = True
                parameters = {'layer_name': layer_name, 'tolerance': tolerance, 'simplify': simplify, 'id_column': base_id, 'user_id':user_id, 'get_invalids':get_invalids, 'get_multiparts':get_multiparts}
                # error cat: invalids, multiparts
                primal_graph, invalids, multiparts = transformer(parameters).run()
                any_primal_graph = prGraph(primal_graph, base_id, True)

                primal_cleaned, duplicates = any_primal_graph.rmv_dupl_overlaps()

                if self.killed is True: return
                self.progress.emit(20)

                # break at intersections and overlaping geometries
                # error cat: to_break
                broken_primal, to_break, overlaps = primal_cleaned.break_graph(tolerance, simplify, user_id)

                if self.killed is True: return
                self.progress.emit(30)

                # error cat: duplicates
                broken_clean_primal, duplicates_br = broken_primal.rmv_dupl_overlaps(user_id)

                if self.killed is True: return
                self.progress.emit(40)

                # transform primal graph to dual graph
                centroids = broken_clean_primal.get_centroids_dict()
                broken_dual = dlGraph(broken_clean_primal.to_dual(True, False, False), broken_clean_primal.uid, centroids, True)

                if self.killed is True: return
                self.progress.emit(50)

                # Merge between intersections
                # error cat: to_merge
                merged_primal, to_merge = broken_dual.merge(broken_clean_primal, tolerance, simplify, user_id)

                if self.killed is True: return
                self.progress.emit(60)

                # error cat: duplicates
                merged_clean_primal, duplicates_m = merged_primal.rmv_dupl_overlaps()

                if self.killed is True: return
                self.progress.emit(70)

                name = layer_name + '_cleaned'

                if self.settings['errors']:

                    centroids = merged_clean_primal.get_centroids_dict()
                    merged_dual = dlGraph(merged_clean_primal.to_dual(False, False, False), merged_clean_primal.uid, centroids,
                                          True)

                    if self.killed is True: return
                    self.progress.emit(80)

                    # error cat: islands, orphans
                    islands, orphans = merged_dual.find_islands_orphans(merged_clean_primal)

                    if self.killed is True: return
                    self.progress.emit(90)

                    # combine all errors
                    error_list = [['invalid', invalids], ['multipart', multiparts], ['intersecting at vertex', to_break],
                                  ['overlaping', overlaps],
                                  ['duplicate', duplicates], ['continuous line', to_merge],
                                  # ['islands', islands], ['orphans', orphans]
                                  ]
                    e_path = None
                    errors = errors_to_shp(error_list, e_path, 'errors', crs, encoding, geom_type)
                else:
                    errors = None

                if self.killed is False:
                    print "survived!"
                    self.progress.emit(100)
                    # return cleaned shapefile and errors
                    cleaned = merged_clean_primal.to_shp(path, name, crs, encoding, geom_type, qgsflds)
                    ret = (errors, cleaned,)

            except Exception, e:
                # forward the exception upstream
                self.error.emit(e, traceback.format_exc())

            self.finished.emit(ret)

    def kill(self):
        self.killed = True

