# -*- coding: utf-8 -*-
from math import degrees
from maya import cmds as _cmds
from maya.api.OpenMaya import MMatrix, MVector, MTransformationMatrix, MGlobal, MFnTypedAttribute, MDagPath, MFnDependencyNode, MFnDependencyNode
import warnings

from maya.OpenMaya import MSelectionList as _oldMSelectionList
from maya.OpenMaya import MGlobal as _oldMGlobal
from maya.OpenMaya import MObject as _oldMObject

""" We hijack maya cmds to ensure we can call cmds functions with DependNode and _Attribute instance arguments instead of strings. """

_debug = False
class _Cmd(object):
    def __init__(self, fn):
        self.fn = fn

    def __call__(self, *args, **kwargs):
        def unwrap(v):
            if isinstance(v, basestring):
                return v
            if isinstance(v, (_Attribute, DependNode)):
                return str(v)
            if hasattr(v, '__iter__'):
                return type(v)(unwrap(e) for e in v)
            return v

        args = tuple(unwrap(a) for a in args)
        for k, a in kwargs.iteritems():
            if isinstance(a, (_Attribute, DependNode)):
                kwargs[k] = unwrap(a)
        _func = self.fn(*args, **kwargs)
        if isStringList(_func):
            _func = getNode(_func)
        return _func


class _Cmds(object):
    def __getattr__(self, item):
        return _Cmd(getattr(_cmds, item))


cmds = _Cmds()


def _getMObject(nodeName):
    return MGlobal.getSelectionListByName(nodeName).getDependNode(0)


def _getMDagPath(nodeName):
    return MGlobal.getSelectionListByName(nodeName).getDagPath(0)


class Matrix(MMatrix):
    def __mul__(self, other):
        return Matrix(super(Matrix, self).__mul__(other))

    def get(self, r, c):
        return self[r * 4 + c]

    def setT(self, t):
        self[12] = t[0]
        self[13] = t[1]
        self[14] = t[2]

    def asR(self):
        return self.asDegrees()

    def asT(self):
        return MVector(self[12], self[13], self[14])

    def axis(self, index):
        i = index * 4
        return MVector(self[i], self[i + 1], self[i + 2])

    def asRadians(self):
        rx, ry, rz, ro = MTransformationMatrix(self).rotationComponents(asQuaternion=False)
        return rx, ry, rz

    def asDegrees(self):
        return tuple(degrees(e) for e in self.asRadians())

    def rotation(self):
        return MTransformationMatrix(self).rotation()


class _Attribute(object):
    def __init__(self, path):
        self._path = path
        self._setterKwargs = {}

        try:
            t = _cmds.getAttr(str(self._path), type=True)
        except:
            if _debug:
                wanings.warn('Unknown attr type at %s' % self._path)
            return
        if t in ('short2',
                 'short3',
                 'long2',
                 'long3',
                 'Int32Array',
                 'float2',
                 'float3',
                 'double2',
                 'double3',
                 'doubleArray',
                 'matrix',
                 'pointArray',
                 'vectorArray',
                 'string',
                 'stringArray',
                 'sphere',
                 'cone',
                 'reflectanceRGB',
                 'spectrumRGB',
                 'componentList',
                 'attributeAlias',
                 'nurbsCurve',
                 'nurbsSurface',
                 'nurbsTrimface',
                 'polyFace',
                 'mesh',
                 'lattice'):
            self._setterKwargs['type'] = t

    def __call__(self):
        a, b = self._path.split('.', 1)
        raise AttributeError('%s has no function %s' % (wrapNode(a), b))

    def __getattr__(self, item):
        return _Attribute(self._path + '.' + item)

    def __getitem__(self, index):
        return _Attribute(self._path + '[%i]' % index)

    def numElements(self):
        return _cmds.getAttr(self._path, size=True)

    def name(self):
        return self._path.split('.', 1)[-1]

    def isKeyable(self):
        return _cmds.getAttr(self._path, keyable=True)

    def isProxy(self):
        return _cmds.getAttr(self._path, keyable=True)

    def isDestination(self):
        return bool(_cmds.listConnections(self._path, s=True, d=False))

    def __str__(self):
        return self._path  # so we can easily throw Attribute() objects into maya functions

    def __repr__(self):
        return self._path + ' : ' + self.__class__.__name__  # so we can easily throw Attribute() objects into maya functions

    def connect(self, destination):
        _cmds.connectAttr(self._path, str(destination), force=True)

    def disconnectInputs(self):
        for source in self.connections(s=True, d=False):
            _cmds.disconnectAttr(str(source), self._path)

    def disconnect(self, destination):
        _cmds.disconnectAttr(self._path, str(destination))

    def connections(self, s=True, d=True, asNode=False):
        return [_Attribute(at) for at in _cmds.listConnections(self._path, s=s, d=d, p=not asNode, sh=True) or []]

    def isConnected(self):
        return bool(_cmds.listConnections(self._path, s=True, d=True))

    def get(self):
        return _cmds.getAttr(self._path)

    def set(self, *args, **kwargs):
        assert args
        if len(args) == 1 and hasattr(args[0], '__iter__') and not isinstance(args[0], basestring):
            args = tuple(args[0])
        kwargs.update(self._setterKwargs)
        _cmds.setAttr(self._path, *args, **kwargs)

    def _recurse(self):
        stack = [self._path]
        cursor = 0
        while cursor < len(stack):
            item = stack.pop(cursor)
            cursor += 1
            nodeName, attributeName = item.split('.', 1)
            try:
                childAttributeNames = _cmds.attributeQuery(attributeName, node=nodeName, lc=True)
            except RuntimeError:
                childAttributeNames = None
            if childAttributeNames:
                for childAttributeName in childAttributeNames:
                    childAttributePath = nodeName + '.' + childAttributeName
                    assert childAttributePath not in stack
                    stack.append(childAttributePath)
            else:
                yield self.__class__(item)

    def setLocked(self, lock, leaf=False):
        if leaf:
            for attr in self._recurse():
                attr.setLocked(lock, False)
                return
        _cmds.setAttr(self._path, lock=lock)

    def setKeyable(self, keyable, leaf=False):
        if leaf:
            for attr in self._recurse():
                attr.setKeyable(keyable, False)
                return
        _cmds.setAttr(self._path, keyable=keyable)

    def setChannelBox(self, cb, leaf=False):
        if leaf:
            for attr in self._recurse():
                attr.setChannelBox(cb, False)
                return
        _cmds.setAttr(self._path, channelBox=cb)


class DependNode(object):
    _instances = {}  # not sure if more efficient, but let's do some object pooling by UUID
    _MFnDependencyNode = MFnDependencyNode()  # I don't want to create new objects every time we get the name
    _apiObjectHelper = _oldMSelectionList()

    @classmethod
    def pool(cls, nodeName, nodeType):
        key = _cmds.ls(nodeName, uuid=True)[0]
        inst = DependNode._instances.get(key, None)
        if inst is None:
            inst = cls(nodeName, nodeType)
            DependNode._instances[key] = inst
        return inst

    def __init__(self, nodeName, nodeType):
        assert isinstance(nodeName, basestring)
        self.__type = nodeType
        if _cmds.ls(nodeName, l=True)[0][0] == '|':
            self.__handle = _getMDagPath(nodeName)
            assert self.__handle.isValid()
        else:
            self.__handle = _getMObject(nodeName)

    def __apiobject__(self):
        _oldMGlobal.getSelectionListByName(self._nodeName, self._apiObjectHelper)
        o = _oldMObject()
        self._apiObjectHelper.getDependNode(0, o)
        return o

    def delete(self):
        _cmds.delete(self._nodeName)

    def name(self):
        return self._nodeName.rsplit('|', 1)[-1]

    @property
    def _nodeName(self):
        if isinstance(self.__handle, MDagPath):
            return self.__handle.fullPathName()
        self._MFnDependencyNode.setObject(self.__handle)
        return self._MFnDependencyNode.name()

    def rename(self, newName):
        _cmds.rename(self._nodeName, newName)

    def hasAttr(self, attr):
        return _cmds.objExists(self._nodeName + '.' + attr)

    def __getattr__(self, attr):
        return _Attribute(self._nodeName + '.' + attr)

    def plug(self, attr):  # TODO: Refactor this away
        return getattr(self, attr)

    def __str__(self):
        return self._nodeName  # so we can easily throw DependNode() objects into maya functions

    def __repr__(self):
        return self._nodeName + ' : ' + self.__class__.__name__  # so we can easily throw DependNode() objects into maya functions

    def asMObject(self):  # TODO: Refactor this away by making getMObject public
        return _getMObject(self._nodeName)

    def type(self):
        return self.__type

    def addAttr(self, longName, **kwargs):
        if 'type' in kwargs:
            t = kwargs['type']
            del kwargs['type']
            if t in ['string',
                     'stringArray',
                     'matrix',
                     'reflectanceRGB',
                     'spectrumRGB',
                     'doubleArray',
                     'floatArray',
                     'Int32Array',
                     'vectorArray',
                     'nurbsCurve',
                     'nurbsSurface',
                     'mesh',
                     'lattice',
                     'pointArray']:
                kwargs['dt'] = t
            else:
                kwargs['at'] = t
        _cmds.addAttr(self._nodeName, ln=longName, **kwargs)

    def plugs(self, ud=False):
        return [_Attribute(self._nodeName + '.' + attr) for attr in _cmds.listAttr(self._nodeName, ud=ud)]

    def isShape(self):
        return self.__type in ["nurbsCurve", "nurbsSurface", "mesh", "follicle", "RigSystemControl", "distanceDimShape", "cMuscleKeepOut", "cMuscleObject"]

class DagNode(DependNode):
    def parent(self):
        p = self._nodeName.rsplit('|', 1)[0]
        if p:
            return wrapNode(p)

    def setParent(self, parent, shape = False):
        if shape:
            _cmds.parent(self._nodeName, parent, add=1, s=1)
            return
        _cmds.parent(self._nodeName, parent)


class Transform(DagNode):
    def shape(self):
        c = _cmds.listRelatives(self._nodeName, c=True, f=True, type='shape') or []
        if c:
            return wrapNode(c[0])

    def shapes(self):
        return [wrapNode(c) for c in (_cmds.listRelatives(self._nodeName, c=True, f=True, type='shape') or [])]

    def _children(self):
        return _cmds.listRelatives(self._nodeName, c=True, f=True) or []

    def numChildren(self):
        return len(self._children())

    def child(self, index):
        return wrapNode(self._children()[index])

    def getT(self, ws=False):
        return MVector(*_cmds.xform(self._nodeName, q=True, ws=ws, t=True))

    def getM(self, ws=False):
        return Matrix(_cmds.xform(self._nodeName, q=True, ws=ws, m=True))

    def setT(self, t, ws=False):
        return _cmds.xform(self._nodeName, ws=ws, t=(t[0], t[1], t[2]))

    def setM(self, m, ws=False):
        return _cmds.xform(self._nodeName, ws=ws, m=[m[i] for i in xrange(16)])


class Joint(Transform):
    def setJOM(self, m, ws=False, safe=False):
        if ws:
            parentInverseMatrix = _cmds.getAttr(self._nodeName + '.parentInverseMatrix')
        else:
            s = _cmds.getAttr(self._nodeName + '.is')
            parentInverseMatrix = [s[0], 0.0, 0.0, 0.0,
                                   0.0, s[1], 0.0, 0.0,
                                   0.0, 0.0, s[2], 0.0,
                                   0.0, 0.0, 0.0, 1.0]
        m *= Matrix(parentInverseMatrix)
        _cmds.setAttr(self._nodeName + '.jointOrient', *m.asDegrees(), type='double3')


class Shape(DagNode):
    def isShape(self):
        return True

    def isType(self, typeName):
        return self.type() == typeName


_wrapperTypes = {
    'dagContainer': Transform,
    'transform': Transform,
    'ikEffector': Transform,
    'ikHandle': Transform,
    'joint': Joint,
    'nurbsCurve': Shape,
    'nurbsSurface': Shape,
    'mesh': Shape,
    'follicle': Shape,
    'RigSystemControl': Shape,
    'distanceDimShape': Shape,
    'locator': DagNode,
    'cMuscleKeepOut': Shape,
    'cMuscleObject':Shape,
    'camera':Shape,
}


def wrapNode(nodeName):
    if not _cmds.objExists(nodeName):
        return None
    nodeType = _cmds.nodeType(nodeName)
    return _wrapperTypes.get(nodeType, DependNode).pool(nodeName, nodeType)


def createNode(nodeType):
    # note: this is the older version:
    #      return wrapNode(cmds.createNode(nodeType))
    # its replaced because openMaya is slightly faster, making gains in speed on big rig creations
    node = MFnDependencyNode()
    node.create(nodeType)
    return wrapNode(node.name())

def isStringList(inObject):
    if type(inObject) in [str, unicode, bytes]:
        return True
    if type(inObject) not in [list, tuple]:
        return False
    if all(isStringList(elem) for elem in inObject):
        return True
    return False

def getNode(nodeName=None):
    if nodeName is None:
        curSelection = _cmds.ls(sl=1)
        if not curSelection:
            warnings.warn("no nodeName given and no object selected in maya!")
            return 
        nodeName = curSelection

    nodeNames = []
    _singleNode = False
    if type(nodeName) in [str, unicode, bytes]:
        nodeNames = [nodeName]
        _singleNode = True
    elif isinstance(nodeName, _oldMObject):
        nodeFn = OpenMaya.MFnDependencyNode(nodeName)
        nodeNames = [nodeFn.name()]
        _singleNode = True
    elif isStringList(nodeName):
        nodeNames = nodeName
    
    wrapped = []
    for nodeName in nodeNames:
        wrapped.append(wrapNode(nodeName))

    if _singleNode:
        return wrapped[0]
    return wrapped
