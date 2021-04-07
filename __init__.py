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
import warnings
import functools

from math import degrees

# noinspection PyUnresolvedReferences
from maya.api.OpenMaya import MMatrix, MVector, MTransformationMatrix, MGlobal, MFnTypedAttribute, MDagPath, \
    MFnDependencyNode, MDGModifier, MDagModifier, MObject, MEulerRotation, MAngle, MPoint, MQuaternion
from maya import cmds as _cmds

from maya.OpenMaya import MSelectionList as _oldMSelectionList
from maya.OpenMaya import MGlobal as _oldMGlobal
from maya.OpenMaya import MObject as _oldMObject

import sys

if sys.version_info.major == 2:
    # Override python 2 with python 3 behaviour so the 'new' names are their faster, iterator based versions
    class dict(dict):
        def items(self):
            return super(dict, self).iteritems()


    range = xrange
else:
    basestring = str

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
        for k, a in kwargs.items():
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

        return _wrapMathObjects(return_value)


class _Cmds(object):
    def __getattr__(self, item):
        return _Cmd(getattr(_cmds, item))


cmds = _Cmds()


def _getMObject(nodeName):
    return MGlobal.getSelectionListByName(nodeName).getDependNode(0)


def _getMDagPath(nodeName):
    return MGlobal.getSelectionListByName(nodeName).getDagPath(0)


def _wrapReturnValue(cls, fn, *args, **kwargs):
    return cls(fn(*args, **kwargs))


def _installMathFunctions(cls, size, wrap_return_attrs=tuple(), ops=None):
    def __repr__(self):
        return '[%s] : %s' % (', '.join(str(self[i]) for i in range(size)), self.__class__.__name__)

    # noinspection PyUnresolvedReferences
    def __getitem__(self, index):
        if isinstance(index, slice):
            a = 0 if index.start is None else index.start
            b = len(self) if index.stop is None else index.stop
            c = 1 if index.step is None else index.step
            return list(super(cls, self).__getitem__(i) for i in range(a, b, c))
        return super(cls, self).__getitem__(index)

    # noinspection PyUnresolvedReferences
    def __setitem__(self, index, value):
        if isinstance(index, slice):
            a = 0 if index.start is None else index.start
            b = len(self) if index.stop is None else index.stop
            c = 1 if index.step is None else index.step
            list(super(cls, self).__setitem__(i) for i, v in zip(range(a, b, c), value))
            return
        super(cls, self).__setitem__(index, value)

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __eq__(self, other):
        if hasattr(other, '__iter__'):
            return tuple(self) == tuple(other)
        return False

    def __ne__(self, other):
        return not (self == other)

    def _wrap(maybeCast):
        if isinstance(maybeCast, cls.__bases__[0]):
            return cls(maybeCast)
        return maybeCast

    def __getattribute__(self, attr):
        result = super(cls, self).__getattribute__(attr)
        if attr in wrap_return_attrs:
            return functools.partial(_wrapReturnValue, self.__class__, result)
        return result

    def __xor__(self, right):
        # noinspection PyUnresolvedReferences
        return _wrap(super(cls, self).__xor__(right))

    def __add__(self, right):
        # noinspection PyUnresolvedReferences
        return _wrap(super(cls, self).__add__(right))

    def __mul__(self, right):
        # noinspection PyUnresolvedReferences
        return _wrap(super(cls, self).__mul__(right))

    def __sub__(self, right):
        # noinspection PyUnresolvedReferences
        return _wrap(super(cls, self).__sub__(right))

    def __div__(self, right):
        # noinspection PyUnresolvedReferences
        return _wrap(super(cls, self).__div__(right))

    def __truediv__(self, right):
        # noinspection PyUnresolvedReferences
        return _wrap(super(cls, self).__truediv__(right))

    def __floordiv__(self, right):
        # noinspection PyUnresolvedReferences
        return _wrap(super(cls, self).__floordiv__(right))

    cls.__repr__ = __repr__
    cls.__getitem__ = __getitem__
    cls.__setitem__ = __setitem__
    cls.__iter__ = __iter__
    cls.__eq__ = __eq__
    cls.__ne__ = __ne__
    cls._wrap = _wrap
    cls.__getattribute__ = __getattribute__
    if ops:
        if '+' in ops:
            cls.__add__ = __add__
        if '-' in ops:
            cls.__sub__ = __sub__
        if '*' in ops:
            cls.__mul__ = __mul__
        if '/' in ops:
            cls.__div__ = __div__
            cls.__truediv__ = __truediv__
            cls.__floordiv__ = __floordiv__
        if '^' in ops:
            cls.__xor__ = __xor__


class Matrix(MMatrix):
    def __init__(self, *args):
        if len(args) == 16:
            super(Matrix, self).__init__(args)
        else:
            super(Matrix, self).__init__(*args)

    def get(self, r, c):
        return self[r * 4 + c]

    def setT(self, t):
        self[12] = t[0]
        self[13] = t[1]
        self[14] = t[2]

    def asR(self):
        return self.asDegrees()

    def asT(self):
        return Vector(self[12], self[13], self[14])

    def axis(self, index):
        i = index * 4
        return Vector(self[i], self[i + 1], self[i + 2])

    def asRadians(self):
        rx, ry, rz, ro = MTransformationMatrix(self).rotationComponents(asQuaternion=False)
        return rx, ry, rz

    def asDegrees(self):
        rx, ry, rz, ro = MTransformationMatrix(self).rotationComponents(asQuaternion=False)
        return degrees(rx), degrees(ry), degrees(rz)

    def rotation(self):
        return Euler(MTransformationMatrix(self).rotation())


class Vector(MVector):
    def __init__(self, *args):
        if len(args) == 1 and isinstance(args[0], MQuaternion): args = args[0].x, args[0].y, args[0].z
        super(Vector, self).__init__(*args)

    def cross(self, other):
        return self ^ other

    def __mul__(self, right):
        if isinstance(right, MVector):
            # dot product, returns a float
            return super(Vector, self).__mul__(right)
        return self._wrap(super(Vector, self).__mul__(right))

    def rotateTo(self, other):
        return QuaternionOrPoint(super(Vector, self).rotateTo(other))


class Euler(MEulerRotation):
    def asQuaternion(self):
        return QuaternionOrPoint(super(Euler, self).asQuaternion())

    def asMatrix(self):
        return Matrix(super(Euler, self).asMatrix())

    def asVector(self):
        return Vector(super(Euler, self).asVector())

    def asRadians(self):
        return self.x, self.y, self.z

    def asDegrees(self):
        return degrees(self.x), degrees(self.y), degrees(self.z)

    def __repr__(self):
        return '[%s] %s : %s' % (', '.join(str(self[i]) for i in range(3)), self.order, self.__class__.__name__)


class QuaternionOrPoint(MQuaternion):
    def __init__(self, *args):
        if len(args) == 1 and isinstance(args[0], MVector): args = args[0].x, args[0].y, args[0].z, 1.0
        if len(args) == 3: args += (1,)
        super(QuaternionOrPoint, self).__init__(*args)

    def __imul__(self, other):
        if isinstance(other, MMatrix):
            tmp = MPoint(self.x, self.y, self.z, self.w) * other
            self.x, self.y, self.z, self.w = tmp.x, tmp.y, tmp.z, tmp.w
            return self
        return super(QuaternionOrPoint, self).__imul__(other)

    def __mul__(self, other):
        if isinstance(other, MMatrix):
            tmp = MPoint(self.x, self.y, self.z, self.w) * other
            return QuaternionOrPoint(tmp.x, tmp.y, tmp.z, tmp.w)
        return QuaternionOrPoint(super(QuaternionOrPoint, self).__mul__(other))

    def asEulerRotation(self):
        return Euler(super(QuaternionOrPoint, self).asEulerRotation())

    def asMatrix(self):
        return Matrix(super(QuaternionOrPoint, self).asMatrix())


# TODO: If this is slow to import maybe we need to write it all out so it's just all one big pyc instead of a bunch of dynamic changes
# noinspection PyTypeChecker
_installMathFunctions(Matrix, 16, ('transpose', 'inverse', 'adjoint', 'homogenize'), '+-*')
# noinspection PyTypeChecker
_installMathFunctions(Vector, 3, ('rotateBy', 'normal', 'transformAsNormal'), '+-*/^')
# noinspection PyTypeChecker
_installMathFunctions(Euler, 3, ('inverse', 'reorder', 'bound', 'alternateSolution', 'closestSolution', 'closestCut'), '+-*')
# noinspection PyTypeChecker
_installMathFunctions(QuaternionOrPoint, 4, ('normal', 'conjugate', 'inverse', 'log', 'exp'), '+-')

# TODO: Maybe these should all be properties that return a copy to avoid user error in changing these 'constants'
Euler.decompose = lambda matrix, order: Euler(MEulerRotation.decompose(matrix, order))
Euler.identity = Euler(0, 0, 0)
QuaternionOrPoint.identity = QuaternionOrPoint(0, 0, 0, 1)
QuaternionOrPoint.origin = QuaternionOrPoint.identity
Matrix.identity = Matrix(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
Vector.zero = Vector(0, 0, 0)
Vector.xAxis = Vector(1, 0, 0)
Vector.yAxis = Vector(0, 1, 0)
Vector.zAxis = Vector(0, 0, 1)
Vector.xNegAxis = Vector(-1, 0, 0)
Vector.yNegAxis = Vector(0, -1, 0)
Vector.zNegAxis = Vector(0, 0, -1)
Vector.one = Vector(1, 1, 1)


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

        # noinspection PyBroadException
        try:
            t = cmds.getAttr(str(self._path), type=True)
        except:
            if _debug:
                warnings.warn('Unknown attr type at %s' % self._path)
            return

        if t in ('short2', 'short3', 'long2', 'long3', 'Int32Array', 'float2', 'float3', 'double2', 'double3',
                 'doubleArray', 'matrix', 'pointArray', 'vectorArray', 'string', 'stringArray', 'sphere', 'cone',
                 'reflectanceRGB', 'spectrumRGB', 'componentList', 'attributeAlias', 'nurbsCurve', 'nurbsSurface',
                 'nurbsTrimface', 'polyFace', 'mesh', 'lattice'):
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

    def __iter__(self):
        raise NotImplementedError

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

    def __eq__(self, other):
        if isinstance(other, _Attribute):
            return self._path == other._path
        return False

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
        if len(args) == 1:
            if isinstance(args[0], _Attribute):
                args = self.unpack(args[0])
            elif hasattr(args[0], '__iter__') and not isinstance(args[0], basestring):
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

    @classmethod
    def unpack(cls, value):
        return value() if isinstance(value, cls) else value

    def __iadd__(self, other):
        other = self.unpack(other)
        self.set(self() + other)
        return self

    def __isub__(self, other):
        other = self.unpack(other)
        self.set(self() - other)
        return self

    def __imul__(self, other):
        other = self.unpack(other)
        self.set(self() * other)
        return self

    def __idiv__(self, other):
        other = self.unpack(other)
        self.set(self() / other)
        return self

    def __itruediv__(self, other):
        other = self.unpack(other)
        self.set(self() / other)
        return self

    def __ifloordiv__(self, other):
        other = self.unpack(other)
        self.set(self() // other)
        return self

    def __ipow__(self, other):
        other = self.unpack(other)
        self.set(self() ** other)
        return self

    def __imod__(self, other):
        other = self.unpack(other)
        self.set(self() % other)
        return self

    def __ixor__(self, other):
        other = self.unpack(other)
        self.set(self() ^ other)
        return self

    def __ior__(self, other):
        other = self.unpack(other)
        self.set(self() ^ other)
        return self

    def __iand__(self, other):
        other = self.unpack(other)
        self.set(self() ^ other)
        return self

    def __ilshift__(self, other):
        other = self.unpack(other)
        self.set(self() << other)
        return self

    def __irshift__(self, other):
        other = self.unpack(other)
        self.set(self() << other)
        return self


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
        # noinspection PyUnresolvedReferences
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
        # noinspection PyUnresolvedReferences
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

    def __eq__(self, other):
        if isinstance(other, DependNode):
            return self._nodeName == other._nodeName
        return False

    def __hash__(self):
        return self._nodeName.__hash__()

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
            if t in ('string', 'stringArray', 'matrix', 'reflectanceRGB', 'spectrumRGB', 'doubleArray', 'floatArray',
                     'Int32Array', 'vectorArray', 'nurbsCurve', 'nurbsSurface', 'mesh', 'lattice', 'pointArray'):
                kwargs['dt'] = t
            else:
                kwargs['at'] = t
        cmds.addAttr(self._nodeName, ln=longName, **kwargs)

    def plugs(self, ud=False):
        return [_Attribute(self._nodeName + '.' + attr) for attr in cmds.listAttr(self._nodeName, ud=ud)]

    def isShape(self):
        return self.__type in (
            'nurbsCurve', 'nurbsSurface', 'mesh', 'follicle', 'RigSystemControl', 'distanceDimShape', 'cMuscleKeepOut',
            'cMuscleObject')


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
        # noinspection PyUnresolvedReferences
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
        return Vector(*cmds.xform(self._nodeName, q=True, ws=ws, t=True))

    def getM(self, ws=False):
        return Matrix(cmds.xform(self._nodeName, q=True, ws=ws, m=True))

    def setT(self, t, ws=False):
        return cmds.xform(self._nodeName, ws=ws, t=(t[0], t[1], t[2]))

    def setM(self, m, ws=False):
        return cmds.xform(self._nodeName, ws=ws, m=[m[i] for i in range(16)])

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
    'annotationShape': Shape,
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
    # noinspection PyUnresolvedReferences
    nodeType = _cmds.nodeType(nodeName)
    return _wrapperTypes.get(nodeType, DependNode).pool(nodeName, nodeType)


def createNode(nodeType):
    # Api with undo/redo support, we profiled this to be faster than cmds.createNode:
    # noinspection PyBroadException
    try:
        mod = MDGModifier()
        obj = mod.createNode(nodeType)
    except:
        mod = MDagModifier()
        obj = mod.createNode(nodeType)
    mod.doIt()
    DependNode.fnInstance().setObject(obj)
    node = DependNode.fnInstance().name()
    return wrapNode(node)


def _isStringOrStringList(inObject):
    if isinstance(inObject, basestring):
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
    if isinstance(nodeName, basestring):
        nodeNames = [nodeName]
        _singleNode = True
    elif isinstance(nodeName, MObject):
        nodeFn = MFnDependencyNode(nodeName)
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


def allDescendants(nodeList):
    unique_children = set()
    for node in _iter_transforms(nodeList):
        for ch in node.allDescendants():
            unique_children.add(ch)
    return unique_children
