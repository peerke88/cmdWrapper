# -*- coding: utf-8 -*-
"""
---------
MIT License

Copyright (c) 2021 Perry Leijten & Trevor van Hoof

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
---------

Thin wrapper around Maya API & cmds to make interacting with nodes more convenient.
Read more over at https://github.com/peerke88/cmdWrapper
"""

if __name__ == '__main__':
    from maya import standalone

    standalone.initialize(name='python')

from math import degrees
from maya import cmds as _cmds
from maya.api.OpenMaya import MMatrix, MVector, MTransformationMatrix, MGlobal, \
    MFnTypedAttribute, MDagPath, MFnDependencyNode, MDGModifier, MDagModifier, MObject
import warnings

from maya.OpenMaya import MSelectionList as _oldMSelectionList
from maya.OpenMaya import MGlobal as _oldMGlobal
from maya.OpenMaya import MObject as _oldMObject

_debug = False


class _Cmd(object):
    """
    We hijack maya.cmds to ensure we can call cmds functions with DependNode
    and _Attribute instance arguments instead of strings.
    """

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
        return_value = self.fn(*args, **kwargs)

        # wrap return value if it is a list of nodes
        if _isStringOrStringList(return_value):
            # we return the original value in case the wrapper is None,
            # this can happen when maya returns a str or str[] that does not represent nodes
            tmp = getNode(return_value)
            if tmp is None or (isinstance(tmp, (list, tuple)) and set(tmp) == {None}):
                return return_value
            return_value = tmp

        return return_value


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

    def __repr__(self):
        return '[%s] : %s' % (', '.join(str(self[i]) for i in range(16)), self.__class__.__name__)

    def __getitem__(self, index):
        if isinstance(index, slice):
            a = 0 if index.start is None else index.start
            b = len(self) if index.stop is None else index.stop
            c = 1 if index.step is None else index.step
            return list(super(Matrix, self).__getitem__(i) for i in range(a, b, c))
        return super(Matrix, self).__getitem__(index)

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            a = 0 if index.start is None else index.start
            b = len(self) if index.stop is None else index.stop
            c = 1 if index.step is None else index.step
            list(super(Matrix, self).__setitem__(i) for i, v in zip(range(a, b, c), value))
            return
        super(Matrix, self).__setitem__(index, value)

    def __iter__(self):
        for i in xrange(len(self)):
            yield self[i]


class Vector(MVector):
    def __repr__(self):
        return '[%s] : %s' % (', '.join(str(self[i]) for i in range(3)), self.__class__.__name__)

    def __getitem__(self, index):
        if isinstance(index, slice):
            a = 0 if index.start is None else index.start
            b = len(self) if index.stop is None else index.stop
            c = 1 if index.step is None else index.step
            return list(super(Vector, self).__getitem__(i) for i in range(a, b, c))
        return super(Vector, self).__getitem__(index)

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            a = 0 if index.start is None else index.start
            b = len(self) if index.stop is None else index.stop
            c = 1 if index.step is None else index.step
            for i, v in zip(range(a, b, c), value):
                super(Vector, self).__setitem__(i, v)
            return
        super(Vector, self).__setitem__(index, value)

    def __iter__(self):
        for i in xrange(len(self)):
            yield self[i]
            

class Euler(MEulerRotation):
    def asQuaternion(self): return QuaternionOrPoint(super(Euler, self).asQuaternion())
    def asMatrix(self): return Matrix(super(Euler, self).asMatrix())
    def asVector(self): return Vector(super(Euler, self).asVector())
    
    def __repr__(self):
        return '[%s] %s : %s' % (', '.join(str(self[i]) for i in range(3)), self.order, self.__class__.__name__)

    def __getitem__(self, index):
        if isinstance(index, slice):
            a = 0 if index.start is None else index.start
            b = len(self) if index.stop is None else index.stop
            c = 1 if index.step is None else index.step
            return list(super(Vector, self).__getitem__(i) for i in range(a, b, c))
        return super(Vector, self).__getitem__(index)

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            a = 0 if index.start is None else index.start
            b = len(self) if index.stop is None else index.stop
            c = 1 if index.step is None else index.step
            for i, v in zip(range(a, b, c), value):
                super(Vector, self).__setitem__(i, v)
            return
        super(Vector, self).__setitem__(index, value)
   
    def __iter__(self):
        for i in xrange(len(self)):
            yield self[i]


class QuaternionOrPoint(MQuaternion):
    # TODO: add MPoint functionality where missing from MQuaternion
    def __repr__(self):
        return '[%s] : %s' % (', '.join(str(self[i]) for i in range(4)), self.__class__.__name__)

    def __getitem__(self, index):
        if isinstance(index, slice):
            a = 0 if index.start is None else index.start
            b = len(self) if index.stop is None else index.stop
            c = 1 if index.step is None else index.step
            return list(super(QuaternionOrPoint, self).__getitem__(i) for i in range(a, b, c))
        return super(QuaternionOrPoint, self).__getitem__(index)

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            a = 0 if index.start is None else index.start
            b = len(self) if index.stop is None else index.stop
            c = 1 if index.step is None else index.step
            list(super(QuaternionOrPoint, self).__setitem__(i) for i, v in zip(range(a, b, c), value))
            return
        super(QuaternionOrPoint, self).__setitem__(index, value)

    def __iter__(self):
        for i in xrange(len(self)):
            yield self[i]


def _wrapMathObjects(value):
    # This tries to wrap the value into a math object
    # only does something if the value is a list or tuple containing
    # a specific number of floats (and no other data)
    if not isinstance(value, (list, tuple)):
        return value
    for e in value:
        if not isinstance(e, float):
            return value
    if len(value) == 3:
        return Vector(*value)
    if len(value) == 4:
        return QuaternionOrPoint(*value)
    if len(value) == 16:
        return Matrix(value)
    return value


class _Attribute(object):
    """
    NOTE: This class implements __setattr__, as such any members assigned to self
    should be added as an exclusion inside the __setattr__ function.

    Wraps an attribute, use get() or __call__() to get it's value:
    print(attr.get())
    print(attr())
    Use the __getattr__ and __getitem__ operators to get child _Attribute objects.
    print(attr.subArrayAttr[0])
    Setting can be done using set, or by assigning on the parent object:
    attr.set(10.0)
    node.attr = 10.0
    """

    def __init__(self, path):
        self._path = path
        self._setterKwargs = {}

        try:
            t = cmds.getAttr(str(self._path), type=True)
        # noinspection PyBroadException
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

    def __call__(self, *args):
        if args:
            raise AttributeError('Attempting to get an attribute %s, but you are passing attributes into the getter.'
                                 'Are you trying to call a function and misspelled something?' % self)
        return self.get()

    def __getattr__(self, item):
        return _Attribute(self._path + '.' + item)

    def __setattr__(self, attr, value):
        if attr in ('_path', '_setterKwargs'):
            super(_Attribute, self).__setattr__(attr, value)
            return
        getattr(self, attr).set(value)

    def __getitem__(self, index):
        return _Attribute(self._path + '[%i]' % index)

    def __setitem__(self, index, value):
        self[index].set(value)

    def numElements(self):
        return cmds.getAttr(self._path, size=True)

    def name(self):
        return self._path.split('.', 1)[-1]

    def isKeyable(self):
        return cmds.getAttr(self._path, keyable=True)

    def isProxy(self):
        return cmds.getAttr(self._path, keyable=True)

    def isDestination(self):
        return bool(cmds.listConnections(self._path, s=True, d=False))

    def __str__(self):
        return self._path  # so we can easily throw Attribute() objects into maya functions

    def __repr__(self):
        return self._path + ' : ' + self.__class__.__name__  # so we can easily throw Attribute() objects into maya functions

    def connect(self, destination):
        cmds.connectAttr(self._path, str(destination), force=True)

    def disconnectInputs(self):
        for source in self.connections(s=True, d=False):
            cmds.disconnectAttr(str(source), self._path)

    def disconnect(self, destination):
        cmds.disconnectAttr(self._path, str(destination))

    def connections(self, s=True, d=True, asNode=False):
        return cmds.listConnections(self._path, s=s, d=d, p=not asNode, sh=True) or []

    def isConnected(self):
        return bool(cmds.listConnections(self._path, s=True, d=True))

    def get(self):
        ret = cmds.getAttr(self._path)
        # hacky solution around maya transform attributes returning a list of 1 tuple
        if isinstance(ret, list) and len(ret) == 1 and isinstance(ret[0], tuple):
            ret = ret[0]
        return _wrapMathObjects(ret)

    def set(self, *args, **kwargs):
        assert args
        if len(args) == 1 and hasattr(args[0], '__iter__') and not isinstance(args[0], basestring):
            args = tuple(args[0])
        kwargs.update(self._setterKwargs)
        cmds.setAttr(self._path, *args, **kwargs)

    def _recurse(self):
        stack = [self._path]
        cursor = 0
        while cursor < len(stack):
            item = stack.pop(cursor)
            cursor += 1
            nodeName, attributeName = item.split('.', 1)
            try:
                childAttributeNames = cmds.attributeQuery(attributeName, node=nodeName, lc=True)
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
        cmds.setAttr(self._path, lock=lock)

    def setKeyable(self, keyable, leaf=False):
        if leaf:
            for attr in self._recurse():
                attr.setKeyable(keyable, False)
                return
        cmds.setAttr(self._path, keyable=keyable)

    def setChannelBox(self, cb, leaf=False):
        if leaf:
            for attr in self._recurse():
                attr.setChannelBox(cb, False)
                return
        cmds.setAttr(self._path, channelBox=cb)


class _Transform_Rotate_Attribute(_Attribute):
    def get(self):
        angles = cmds.getAttr(self._path)[0]
        return Euler(angles[0], angles[1], angles[2], cmds.getAttr(self._path.split('.', 1)[0] + '.rotateOrder'))


class DependNode(object):
    """
    NOTE: This class implements __setattr__, as such any members assigned to self
    should be added as an exclusion inside the __setattr__ function.

    Wraps a Maya node, sub classes may introduce features more specific to the underlying node's type.
    Always use DependNode.pool() (or <subclass>.pool()) to get depend nodes, never construct them manually.

    Depend nodes use MObject and MDagPath handles so reparenting and renaming nodes should
    never invalidate your DependNode instance.
    """

    _instances = {}  # not sure if more efficient, but let's do some object pooling by UUID
    _MFnDependencyNode = MFnDependencyNode()  # I don't want to create new objects every time we get the name
    _apiObjectHelper = _oldMSelectionList()

    @staticmethod
    def fnInstance():
        return DependNode._MFnDependencyNode

    @classmethod
    def pool(cls, nodeName, nodeType):
        # Using internal Maya cmds to avoid recursive calls (wrapped cmds.ls() constructs DependNode objects when necessary)
        key = _cmds.ls(nodeName, uuid=True)[0]
        inst = DependNode._instances.get(key, None)
        if inst is None:
            inst = cls(nodeName, nodeType)
            DependNode._instances[key] = inst
        return inst

    def __init__(self, nodeName, nodeType):
        assert isinstance(nodeName, basestring)
        self.__type = nodeType
        # Using internal Maya cmds to avoid recursive calls (wrapped cmds.ls() constructs DependNode objects when necessary)
        if _cmds.ls(nodeName, l=True)[0][0] == '|':
            self.__handle = _getMDagPath(nodeName)
            assert self.__handle.isValid()
        else:
            self.__handle = _getMObject(nodeName)

    def __len__(self):
        return len(str(self))

    def __apiobject__(self):
        assert cmds.objExists(self._nodeName)
        _oldMGlobal.getSelectionListByName(self._nodeName, self._apiObjectHelper)
        o = _oldMObject()
        self._apiObjectHelper.getDependNode(0, o)
        return o

    def delete(self):
        cmds.delete(self._nodeName)

    def name(self):
        return self._nodeName.rsplit('|', 1)[-1]

    @property
    def _nodeName(self):
        if isinstance(self.__handle, MDagPath):
            return self.__handle.fullPathName()
        self._MFnDependencyNode.setObject(self.__handle)
        return self._MFnDependencyNode.name()

    def rename(self, newName):
        cmds.rename(self._nodeName, newName)

    def hasAttr(self, attr):
        return cmds.objExists(self._nodeName + '.' + attr)

    def __getattr__(self, attr):
        return _Attribute(self._nodeName + '.' + attr)

    def __setattr__(self, attr, value):
        if attr.startswith('_DependNode__'):
            super(DependNode, self).__setattr__(attr, value)
            return
        getattr(self, attr).set(value)

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
        cmds.addAttr(self._nodeName, ln=longName, **kwargs)

    def plugs(self, ud=False):
        return [_Attribute(self._nodeName + '.' + attr) for attr in cmds.listAttr(self._nodeName, ud=ud)]

    def isShape(self):
        return self.__type in ['nurbsCurve', 'nurbsSurface', 'mesh', 'follicle', 'RigSystemControl',
                               'distanceDimShape', 'cMuscleKeepOut', 'cMuscleObject']


class DagNode(DependNode):
    # Note the base class implements __setattr__, so we should not introduce new member variables, only functions.
    def parent(self):
        p = self._nodeName.rsplit('|', 1)[0]
        if p:
            return wrapNode(p)

    def setParent(self, parent, shape=False):
        if shape:
            cmds.parent(self._nodeName, parent, add=True, s=True)
            return
        cmds.parent(self._nodeName, parent)


class Transform(DagNode):
    # Note the base class implements __setattr__, so we should not introduce new member variables, only functions.
    def shape(self):
        return (cmds.listRelatives(self._nodeName, c=True, f=True, type='shape') or [None])[0]

    def shapes(self):
        return cmds.listRelatives(self._nodeName, c=True, f=True, type='shape') or []

    def _children(self):
        return _cmds.listRelatives(self._nodeName, c=True, f=True) or []

    def children(self):
        return cmds.listRelatives(self._nodeName, c=True, f=True) or []

    def allDescendants(self):
        return cmds.listRelatives(self._nodeName, ad=True, f=True) or []

    def numChildren(self):
        return len(self._children())

    def child(self, index):
        return wrapNode(self._children()[index])

    def getT(self, ws=False):
        return MVector(*cmds.xform(self._nodeName, q=True, ws=ws, t=True))

    def getM(self, ws=False):
        return Matrix(cmds.xform(self._nodeName, q=True, ws=ws, m=True))

    def setT(self, t, ws=False):
        return cmds.xform(self._nodeName, ws=ws, t=(t[0], t[1], t[2]))

    def setM(self, m, ws=False):
        return cmds.xform(self._nodeName, ws=ws, m=[m[i] for i in xrange(16)])

    def __getattr__(self, attr):
        if attr == 'rotate':
            return _Transform_Rotate_Attribute(self._nodeName + '.' + attr)
        return _Attribute(self._nodeName + '.' + attr)


class Joint(Transform):
    # Note the base class implements __setattr__, so we should not introduce new member variables, only functions.
    def setJointOrientMatrix(self, m, ws=False):
        if ws:
            parentInverseMatrix = cmds.getAttr(self._nodeName + '.parentInverseMatrix')
        else:
            s = cmds.getAttr(self._nodeName + '.is')
            parentInverseMatrix = [s[0], 0.0, 0.0, 0.0,
                                   0.0, s[1], 0.0, 0.0,
                                   0.0, 0.0, s[2], 0.0,
                                   0.0, 0.0, 0.0, 1.0]
        m *= Matrix(parentInverseMatrix)
        cmds.setAttr(self._nodeName + '.jointOrient', *m.asDegrees(), type='double3')


class Shape(DagNode):
    # Note the base class implements __setattr__, so we should not introduce new member variables, only functions.
    pass


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
    'locator': Shape,
    'cMuscleKeepOut': Shape,
    'cMuscleObject': Shape,
    'camera': Shape,
}


def wrapNode(nodeName):
    if isinstance(nodeName, basestring) and '.' in nodeName:
        nodeName, suffix = nodeName.split('.', 1)
        result = wrapNode(nodeName)
        if result is None:
            return None
        return getattr(result, suffix)
    if not cmds.objExists(nodeName):
        return None
    nodeType = _cmds.nodeType(nodeName)
    return _wrapperTypes.get(nodeType, DependNode).pool(nodeName, nodeType)


def createNode(nodeType):
    # Cmds:
    # node = cmds.createNode(nodeType)
    # return wrapNode(node)

    # Api:
    # This one is much faster
    # node = MFnDependencyNode()
    # node.create(nodeType)
    # node = node.name()
    # return wrapNode(node)

    # Api with undo/redo support:
    # It is untested if this is faster or slower
    # TODO: profile!
    try:
        mod = MDGModifier()
        obj = mod.createNode(nodeType)
    # noinspection PyBroadException
    except:
        mod = MDagModifier()
        obj = mod.createNode(nodeType)
    mod.doIt()
    DependNode.fnInstance().setObject(obj)
    node = DependNode.fnInstance().name()
    return wrapNode(node)


def _isStringOrStringList(inObject):
    if isinstance(inObject, (str, unicode, bytes)):
        return True
    if not isinstance(inObject, (list, tuple)):
        return False
    if all(_isStringOrStringList(elem) for elem in inObject):
        return True
    return False


def getNode(nodeName=None):
    if nodeName is None:
        curSelection = cmds.ls(sl=True)
        if not curSelection:
            warnings.warn('no nodeName given and no object selected in maya!')
            return []
        nodeName = curSelection

    nodeNames = []
    _singleNode = False
    if isinstance(nodeName, (str, unicode, bytes)):
        nodeNames = [nodeName]
        _singleNode = True
    elif isinstance(nodeName, MObject):  # _oldMObject):
        nodeFn = OpenMaya.MFnDependencyNode(nodeName)
        nodeNames = [nodeFn.name()]
        _singleNode = True
    elif _isStringOrStringList(nodeName):
        nodeNames = nodeName

    wrapped = []
    for nodeName in nodeNames:
        wrapped.append(wrapNode(nodeName))

    if _singleNode:
        return wrapped[0]
    return wrapped


def selection():
    # alias for getNode with no arguments
    return getNode()


def _iter_transforms(nodeList):
    if not isinstance(nodeList, (list, tuple)):
        nodeList = [nodeList]
    for node in nodeList:
        node = wrapNode(node)
        if not isinstance(node, Transform):
            continue
        yield node


def parents(nodeList):
    return list({node.parent() for node in _iter_transforms(nodeList)})


def children(nodeList):
    unique_children = set()
    for node in _iter_transforms(nodeList):
        for ch in node.children():
            unique_children.add(ch)
    return unique_children
    #     unique_children |= set(node.children())
    # return sorted(list(unique_children), key=len)


def allDescendants(nodeList):
    unique_children = set()
    for node in _iter_transforms(nodeList):
        for ch in node.allDescendants():
            unique_children.add(ch)
    return unique_children
    #    unique_children |= set(node.allDescendants())
    # return sorted(list(unique_children), key=len)


if __name__ == '__main__':
    # do some tests
    def validate(a, b):
        if a != b:
            print('Error: (%s) != (%s)' % (a, b))

    def validate_as_strs(a, b):
        if len(a) != len(b):
            print('Error: (%s) != (%s)' % (a, b))
            return
        for ae, be in zip(a, b):
            if str(ae) != str(be):
                print('Error: (%s) != (%s)' % (a, b))
                return

    def validate_floats(a, b):
        if len(a) != len(b):
            print('Error: (%s) != (%s)' % (a, b))
            return
        epsilon = 1e-9
        for ae, be in zip(a, b):
            if abs(ae - be) > epsilon:
                print('Error: (%s) != (%s)' % (a, b))
                return


    def tests():
        print('Running tests.')
        print('Initializing maya standalone, make sure to run using mayapy.exe.')
        # create a nod
        transform = createNode('transform')
        validate(str(transform), '|transform1')
        # get and set translate
        validate(transform.tx(), 0.0)
        validate(transform.translate.get(), (0.0, 0.0, 0.0))
        transform.translate = 10.0, 1.0, 0.0
        # noinspection PyCallingNonCallable
        validate(transform.translate(), (10.0, 1.0, 0.0))
        transform.tx.set(2.0)
        validate(transform.tx(), 2.0)
        # find a node & it's shape
        persp_transform = getNode('persp')
        persp_shape = persp_transform.shape()
        validate(str(persp_shape), '|persp|perspShape')
        # reparent a node
        transform.setParent(persp_transform)
        validate(str(transform), '|persp|transform1')
        validate(transform.parent(), persp_transform)
        # even attributes should still work
        validate(str(transform.translate), '|persp|transform1.translate')
        # cmds return type validation
        validate(cmds.listRelatives(transform, ad=True), None)
        validate_floats(cmds.xform(transform, q=True, ws=True, t=True), (2.0, 1.0, 0.0))
        validate_floats(cmds.xform(transform, q=True, ws=True, m=True),
                        (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 2.0, 1.0, 0.0, 1.0))
        validate(cmds.file(rename='C:/Test.ma'), 'C:/Test.ma')
        validate('C:/Test.ma', cmds.file(q=True, sn=True))
        validate(['C:/Test.ma'], cmds.file(query=True, list=True))
        validate(['scale', 'scaleX', 'scaleY', 'scaleZ', 'scalePivot', 'scalePivotX', 'scalePivotY', 'scalePivotZ',
                  'scalePivotTranslate', 'scalePivotTranslateX', 'scalePivotTranslateY', 'scalePivotTranslateZ'],
                 cmds.listAttr(transform, r=True, st='scale*'))
        validate(True, cmds.objExists(transform))
        validate(DependNode, type(cmds.createNode('curveInfo')))
        validate(['|test', 'makeNurbCircle1'], [str(e) for e in cmds.circle(n='test')])
        validate('untitled', cmds.file(f=True, new=True))
        validate('y' or 'z', cmds.upAxis(q=True, axis=True))
        cmds.joint()
        cmds.joint()
        cmds.joint()
        validate(children('|joint1'), {getNode('|joint1|joint2')})
        validate(allDescendants('|joint1'), set(getNode(('|joint1|joint2', '|joint1|joint2|joint3'))))
        for inst in cmds.ls(sl=0)[::5]:
            assert isinstance(inst, DependNode)
        crc = cmds.circle()[0]
        validate_as_strs(cmds.ls('%s[*]' % crc.cv, fl=True), getNode(['|nurbsCircle1.cv[%i]' % i for i in range(8)]))


    tests()
