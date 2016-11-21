from PyQt4.QtCore import *
import traceback
import networkx as nx
# source: http://stackoverflow.com/questions/20324804/how-to-use-qthread-correctly-in-pyqt-with-movetothread

# Putting *args and/ or **kwargs as the last items in your function definition's argument list
# allows that function to accept an arbitrary number of arguments and/or keyword arguments.

BaseClass = None

# http://stackoverflow.com/questions/15247075/how-can-i-dynamically-create-derived-classes-from-a-base-class
#class BaseClass(QObject):
#    def __init__(self, classtype):
#        self._type = classtype

#def classFactory(BaseClass=BaseClass):
#    class inheritedclass(BaseClass):
#        def __init__(self):
#            BaseClass.__init__(self)
#    return inheritedclass

def ClassFactory(name, argnames, BaseClass=BaseClass):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            # here, the argnames variable is the one passed to the
            # ClassFactory call
            if key not in argnames:
                raise TypeError("Argument %s not valid for %s"
                                % (key, self.__class__.__name__))
            setattr(self, key, value)
        BaseClass.__init__(self, name[:-len("Class")])

    newclass = type(name, (BaseClass,), {"__init__": __init__})

    return newclass

from sGraph.shpFunctions import transformer


class GenericWorker(transformer, object):

    def __init__(self, parameters,function, *args, **kwargs):
        super(GenericWorker, self).__init__(parameters)
        self.function = function
        self.args = args
        self.kwargs = kwargs
        print "par:", parameters

    start = pyqtSignal(str)

    #@pyqtSlot
    def any_run(self, some_string_arg):
        #ret = None
        print "running function"
        print 'test', nx.MultiGraph()
        self.function(*self.args, **self.kwargs)
