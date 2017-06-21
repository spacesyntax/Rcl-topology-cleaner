# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ClSettings_dialog_base.ui'
#
# Created: Mon Jun 19 12:33:49 2017
#      by: PyQt4 UI code generator 4.10.2
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName(_fromUtf8("Dialog"))
        Dialog.resize(214, 285)
        self.layoutWidget = QtGui.QWidget(Dialog)
        self.layoutWidget.setGeometry(QtCore.QRect(10, 10, 181, 259))
        self.layoutWidget.setObjectName(_fromUtf8("layoutWidget"))
        self.verticalLayout_2 = QtGui.QVBoxLayout(self.layoutWidget)
        self.verticalLayout_2.setMargin(0)
        self.verticalLayout_2.setObjectName(_fromUtf8("verticalLayout_2"))
        self.verticalLayout = QtGui.QVBoxLayout()
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.invalidsCheckBox = QtGui.QCheckBox(self.layoutWidget)
        self.invalidsCheckBox.setObjectName(_fromUtf8("invalidsCheckBox"))
        self.verticalLayout.addWidget(self.invalidsCheckBox)
        self.pointsCheckBox = QtGui.QCheckBox(self.layoutWidget)
        self.pointsCheckBox.setObjectName(_fromUtf8("pointsCheckBox"))
        self.verticalLayout.addWidget(self.pointsCheckBox)
        self.multipartsCheckBox = QtGui.QCheckBox(self.layoutWidget)
        self.multipartsCheckBox.setObjectName(_fromUtf8("multipartsCheckBox"))
        self.verticalLayout.addWidget(self.multipartsCheckBox)
        self.selfinterCheckBox = QtGui.QCheckBox(self.layoutWidget)
        self.selfinterCheckBox.setObjectName(_fromUtf8("selfinterCheckBox"))
        self.verticalLayout.addWidget(self.selfinterCheckBox)
        self.duplicatesCheckBox = QtGui.QCheckBox(self.layoutWidget)
        self.duplicatesCheckBox.setObjectName(_fromUtf8("duplicatesCheckBox"))
        self.verticalLayout.addWidget(self.duplicatesCheckBox)
        self.overlapsCheckBox = QtGui.QCheckBox(self.layoutWidget)
        self.overlapsCheckBox.setObjectName(_fromUtf8("overlapsCheckBox"))
        self.verticalLayout.addWidget(self.overlapsCheckBox)
        self.closedplCheckBox = QtGui.QCheckBox(self.layoutWidget)
        self.closedplCheckBox.setObjectName(_fromUtf8("closedplCheckBox"))
        self.verticalLayout.addWidget(self.closedplCheckBox)
        self.breakCheckBox = QtGui.QCheckBox(self.layoutWidget)
        self.breakCheckBox.setObjectName(_fromUtf8("breakCheckBox"))
        self.verticalLayout.addWidget(self.breakCheckBox)
        self.mergeCheckBox = QtGui.QCheckBox(self.layoutWidget)
        self.mergeCheckBox.setObjectName(_fromUtf8("mergeCheckBox"))
        self.verticalLayout.addWidget(self.mergeCheckBox)
        self.orphansCheckBox = QtGui.QCheckBox(self.layoutWidget)
        self.orphansCheckBox.setObjectName(_fromUtf8("orphansCheckBox"))
        self.verticalLayout.addWidget(self.orphansCheckBox)
        self.verticalLayout_2.addLayout(self.verticalLayout)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(_translate("Dialog", "Dialog", None))
        self.invalidsCheckBox.setText(_translate("Dialog", "invalids", None))
        self.pointsCheckBox.setText(_translate("Dialog", "points", None))
        self.multipartsCheckBox.setText(_translate("Dialog", "multiparts", None))
        self.selfinterCheckBox.setText(_translate("Dialog", "self intersecting", None))
        self.duplicatesCheckBox.setText(_translate("Dialog", "duplicates", None))
        self.overlapsCheckBox.setText(_translate("Dialog", "overlaps", None))
        self.closedplCheckBox.setText(_translate("Dialog", "closed polylines", None))
        self.breakCheckBox.setText(_translate("Dialog", "break at vertices", None))
        self.mergeCheckBox.setText(_translate("Dialog", "continuous lines", None))
        self.orphansCheckBox.setText(_translate("Dialog", "orphans", None))

