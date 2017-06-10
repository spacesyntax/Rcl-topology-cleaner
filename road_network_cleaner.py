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


from sGraph.break_tools import *
from sGraph.merge_tools import *
from sGraph.utilityFunctions import *
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
        #open file
        if self.dlg.getInput(self.iface):
            for i in self.dlg.getInput(self.iface).dataProvider().fields():
                cols_list.append(i.name())
        self.dlg.idCombo.addItems(cols_list)


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
        cleaning = self.clean(settings, self.iface)

        # start the cleaning in a new thread
        thread = QThread()
        cleaning.moveToThread(thread)
        cleaning.finished.connect(self.cleaningFinished)
        cleaning.error.connect(self.cleaningError)
        cleaning.warning.connect(self.giveMessage)
        cleaning.cl_progress.connect(self.dlg.cleaningProgress.setValue)
        thread.started.connect(cleaning.run)
        thread.start()
        self.thread = thread
        self.cleaning = cleaning

    def cleaningFinished(self, ret):
        # clean up  the worker and thread



        try:
            # report the result
            # a, b = ret
            for layer in ret:
                QgsMapLayerRegistry.instance().addMapLayer(layer)
            self.giveMessage('Process ended successfully!', QgsMessageBar.INFO)

        except Exception, e:
            # notify the user that sth went wrong
            self.cleaning.error.emit(e, traceback.format_exc())
            self.giveMessage('Something went wrong! See the message log for more information', QgsMessageBar.CRITICAL)

        self.cleaning.iface.mapCanvas().refresh()
        self.cleaning.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        self.dlg.cleaningProgress.reset()
        self.cleaning = None

        self.dlg.close()

    def killCleaning(self):
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
        finished = pyqtSignal(object)
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
                    user_id = self.settings['user_id']

                    # project settings
                    layer = getLayerByName(layer_name)
                    crs = layer.dataProvider().crs()
                    encoding = layer.dataProvider().encoding()
                    geom_type = layer.dataProvider().geometryType()

                    # if unique id is specified use it as keys
                    # else create new
                    # check uid before

                    self.cl_progress.emit(2)

                    self.br = breakTool(layer, tolerance, user_id, self.settings['errors'])

                    if self.cl_killed is True or self.br.killed is True: return

                    self.br.add_edges()
                    if self.cl_killed is True or self.br.killed is True: return

                    self.cl_progress.emit(5)
                    self.total = 5

                    step = 45/ self.br.feat_count
                    self.br.progress.connect(lambda incr=self.add_step(step): self.cl_progress.emit(incr))

                    broken_features, breakages, overlaps, orphans, closed_polylines, self_intersecting, duplicates = self.br.break_features()

                    if self.cl_killed is True or self.br.killed is True: return
                    self.cl_progress.emit(45)

                    self.mrg = mergeTool(broken_features, user_id, True)

                    step = 45/ len(self.mrg.con_1)
                    self.mrg.progress.connect(lambda incr=self.add_step(step): self.cl_progress.emit(incr))

                    result = self.mrg.merge()

                    if self.cl_killed is True or self.mrg.killed is True: return

                    fields = self.br.layer_fields
                    final = to_shp(path, result, fields, crs, 'cleaned', encoding, geom_type)

                    if self.settings['errors']:

                        errors_list = {
                                       'breakages': breakages,
                                       'overlaps': overlaps,
                                       'orphans': orphans,
                                       'closed_polylines': closed_polylines,
                                       'self_intersecting': self_intersecting,
                                       'duplicates': duplicates,
                                       'multiparts': [int(i) for i in self.br.multiparts],
                                       'invalids': self.br.invalids,
                                       'points': self.br.points,
                                       'continuous line': self.mrg.fids_to_merge
                                       }
                        uf = self.br.uid_to_fid
                        input_geometries_wkt = self.br.geometries_wkt

                        errors = QgsVectorLayer('MultiLineString?crs=' + crs.toWkt(), 'errors', "memory")
                        pr = errors.dataProvider()
                        pr.addAttributes([QgsField('id_input', QVariant.String), QgsField('errors', QVariant.String)])
                        new_features = []
                        combined_errors = {}
                        for k, v in errors_list.items():
                            for item in v:
                                try:
                                    combined_errors[item] += ', ' + k
                                except KeyError, e:
                                    combined_errors[item] = k

                        # TODO: fix why it throws KeyError
                        for k, v in combined_errors.items():
                            new_feat = QgsFeature()
                            try:
                                if v == 'invalids' or v == 'points':
                                    new_geom = QgsGeometry()
                                else:
                                    new_geom = QgsGeometry.fromWkt(input_geometries_wkt[uf[k]])
                                new_feat.setAttributes([k, v])
                                new_feat.setGeometry(new_geom)
                                new_features.append(new_feat)
                            except KeyError, e:
                                new_feat.setAttributes(['could not find id', v])
                                new_feat.setGeometry(QgsGeometry())
                                new_features.append(new_feat)

                        errors.startEditing()
                        pr.addFeatures(new_features)
                        errors.commitChanges()
                    else:
                        errors = None

                    #if self.cl_killed is False:
                    print "survived!"
                    self.cl_progress.emit(100)
                    # return cleaned shapefile and errors
                    ret = (errors, final, )
                    #cleaned_network, broken_network, to_merge, to_start

                except Exception, e:
                    # forward the exception upstream
                    self.error.emit(e, traceback.format_exc())

                self.finished.emit(ret)

        def kill(self):
            self.cl_killed = True


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




