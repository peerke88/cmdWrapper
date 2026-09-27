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
from math import degrees
from json import JSONEncoder
import warnings, functools, sys, traceback, os
# noinspection PyUnresolvedReferences
from maya.api.OpenMaya import MMatrix, MVector, MTransformationMatrix, MGlobal, MDagPath, MFn, MTime, MSelectionList,\
    MFnDependencyNode, MDGModifier, MDagModifier, MObject, MEulerRotation, MPoint, MQuaternion, MFnAttribute, MObjectHandle
# noinspection PyUnresolvedReferences
from maya.api.OpenMayaAnim import MFnAnimCurve
# noinspection PyUnresolvedReferences
from maya import cmds as _cmds
# noinspection PyUnresolvedReferences
from maya.OpenMaya import MSelectionList as _oldMSelectionList
# noinspection PyUnresolvedReferences
from maya.OpenMaya import MGlobal as _oldMGlobal
# noinspection PyUnresolvedReferences
from maya.OpenMaya import MObject as _oldMObject


def _default(self, obj):
    return getattr(obj.__class__, "to_json", _default.default)(obj)


_default.default = JSONEncoder().default
JSONEncoder.default = _default
_debug = False

def _short_excepthook(etype, evalue, tb):
    frames = [f for f in traceback.extract_tb(tb) if not "cmdwrapper" in (f.filename or "").replace("/", os.sep).lower()]
    if _debug or not frames:
        traceback.print_exception(etype, evalue, tb)
        return

    data = ["\n## Traceback (most recent call last):"]
    for f in frames:
        data.append(f'#  File "{f.filename}", line {f.lineno}, in {f.name}')
        data.append(f"#    {f.line}")
    data.append(f"# {etype.__name__}: {evalue}")
    print("\n".join(data))

sys.excepthook = _short_excepthook

class CMDWrapperError(Exception):
    pass

class _Cmd(object):
    """
    We hijack maya.cmds to ensure we can call cmds functions with DependNode
    and _Attribute instance arguments instead of strings.
    """
    def __init__(self, fn):
        self.fn = fn

    def __call__(self, *args, **kwargs):
        def unwrap(v):
            if isinstance(v, str):
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


def _installMathFunctions(cls, size, wrap_return_attrs, ops):
    # type: (type, int, tuple, str)->None

    def __getstate__(self):
        # make sure this object returns a list so pickle works
        return [self[i] for i in range(size)]

    def __setstate__(self, inSettings):
        # make sure this sets the current list on the correct class
        super(cls, self).__init__(inSettings)

    def to_json(self):
        return [self[i] for i in range(size)]

    def __repr__(self):
        return f"[{', '.join(str(self[i]) for i in range(size))}] : {self.__class__.__name__}"

    def __getitem__(self, index):
        if isinstance(index, slice):
            a = 0 if index.start is None else index.start
            b = len(self) if index.stop is None else index.stop
            c = 1 if index.step is None else index.step
            # noinspection PyUnresolvedReferences
            return list(super(cls, self).__getitem__(i) for i in range(a, b, c))
        # noinspection PyUnresolvedReferences
        return super(cls, self).__getitem__(index)

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            a = 0 if index.start is None else index.start
            b = len(self) if index.stop is None else index.stop
            c = 1 if index.step is None else index.step
            # noinspection PyUnresolvedReferences
            list(super(cls, self).__setitem__(i, v) for i, v in zip(range(a, b, c), value))
            return
        # noinspection PyUnresolvedReferences
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
        if isinstance(maybeCast, cls.__bases__[0]) and not isinstance(maybeCast, cls):
            try:
                # prefer indexing; works for MVector, MMatrix, MEulerRotation, MQuaternion
                return cls(*[maybeCast[i] for i in range(size)])
            except Exception:
                # fallback for things that expose x/y/z/w but not __getitem__
                comps = []
                for name in ("x", "y", "z", "w"):
                    if hasattr(maybeCast, name) and len(comps) < size:
                        comps.append(getattr(maybeCast, name))
                if len(comps) == size:
                    return cls(*comps)
        return maybeCast

    def _make_wrapped_method(name):
        base_attr = getattr(cls.__bases__[0], name)  # descriptor from OpenMaya base

        def wrapped(self, *args, **kwargs):
            res = base_attr.__get__(self, cls)(*args, **kwargs)
            return cls._wrap(res)
        wrapped.__name__ = name
        wrapped.__qualname__ = f"{cls.__name__}.{name}"
        return wrapped

    for name in wrap_return_attrs:
        try:
            setattr(cls, name, _make_wrapped_method(name))
        except Exception:
            # if Maya API changes / attribute missing, just skip
            pass

    def __xor__(self, right):
        # noinspection PyUnresolvedReferences
        return _wrap(super(cls, self).__xor__(right))

    def __add__(self, right):
        # noinspection PyUnresolvedReferences
        return _wrap(super(cls, self).__add__(right))

    def __radd__(self, right):
        # noinspection PyUnresolvedReferences
        if right == 0:
            return self
        else:
            return self.__add__(right)

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

    cls.__getstate__ = __getstate__
    cls.__setstate__ = __setstate__
    cls.__repr__ = __repr__
    cls.__getitem__ = __getitem__
    cls.__setitem__ = __setitem__
    cls.__iter__ = __iter__
    cls.__eq__ = __eq__
    cls.__ne__ = __ne__
    cls.to_json = to_json
    cls._wrap = _wrap
    # cls.__getattribute__ = __getattribute__
    if ops:
        if '+' in ops:
            cls.__add__ = __add__
            cls.__radd__ = __radd__
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

    def asS(self):
        return Vector(self.axis(0).length(), self.axis(1).length(), self.axis(2).length())

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

    def quaternion(self):
        return QuaternionOrPoint().setValue(self)


class Vector(MVector):
    def __init__(self, *args):
        if len(args) == 1 and isinstance(args[0], MQuaternion):
            args = args[0].x, args[0].y, args[0].z
        super().__init__(*args)

    def cross(self, other):
        return self ^ other

    def __mul__(self, right):
        if isinstance(right, MVector):
            # dot product, returns a float
            return super().__mul__(right)
        return self._wrap(super().__mul__(right))

    def rotateTo(self, other):
        return QuaternionOrPoint(super().rotateTo(other))

    def invert(self):
        return self * -1

    def isPositive(self):
        return (sum(self[::]) > 0)

    def isNegative(self):
        return (sum(self[::]) < 0)

    def isX(self):
        return (abs(self.normal() * Vector.xAxis) > .999)

    def isY(self):
        return (abs(self.normal() * Vector.yAxis) > .999)

    def isZ(self):
        return (abs(self.normal() * Vector.zAxis) > .999)


class Euler(MEulerRotation):
    def asQuaternion(self):
        return QuaternionOrPoint(super().asQuaternion())

    def asMatrix(self):
        return Matrix(super().asMatrix())

    def asVector(self):
        return Vector(super().asVector())

    def asRadians(self):
        return self.x, self.y, self.z

    def asDegrees(self):
        return degrees(self.x), degrees(self.y), degrees(self.z)

    def __repr__(self):
        return f"[{', '.join(str(self[i]) for i in range(3))}] {self.order} : {self.__class__.__name__}"


class QuaternionOrPoint(MQuaternion):
    def __init__(self, *args):
        if len(args) == 1 and isinstance(args[0], MVector):
            args = args[0].x, args[0].y, args[0].z, 1.0
        if len(args) == 3:
            args += (1,)
        super().__init__(*args)

    def __imul__(self, other):
        if isinstance(other, MMatrix):
            tmp = MPoint(self.x, self.y, self.z, self.w) * other
            self.x, self.y, self.z, self.w = tmp.x, tmp.y, tmp.z, tmp.w
            return self
        return super().__imul__(other)

    def __mul__(self, other):
        if isinstance(other, MMatrix):
            tmp = MPoint(self.x, self.y, self.z, self.w) * other
            return QuaternionOrPoint(tmp.x, tmp.y, tmp.z, tmp.w)
        return QuaternionOrPoint(super().__mul__(other))

    def asEulerRotation(self):
        return Euler(super().asEulerRotation())

    def asMatrix(self):
        return Matrix(super().asMatrix())

    @classmethod
    def slerp(cls, qA, qB, t):
        res = MQuaternion.slerp(qA, qB, t)
        return cls(res.x, res.y, res.z, res.w)


# TODO: If this is slow to import maybe we need to write it all out so it's just all one big pyc instead of a bunch of dynamic changes
_installMathFunctions(Matrix, 16, ('transpose', 'inverse', 'adjoint', 'homogenize'), '+-*')
_installMathFunctions(Vector, 3, ('rotateBy', 'normal', 'transformAsNormal'), '+-*/^')
_installMathFunctions(Euler, 3, ('inverse', 'reorder', 'bound', 'alternateSolution', 'closestSolution', 'closestCut'), '+-*')
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

def _isAliveMObject(obj: MObject) -> bool:
    if obj is None or obj.isNull():
        return False
    h = MObjectHandle(obj)
    return h.isValid() and h.isAlive()

def _resolveHandle(nodeName):
    sel = MSelectionList()
    try:
        sel.add(nodeName)
    except Exception:
        return None

    try:
        dag, _ = sel.getDagPath(0)
        if dag and dag.isValid():
            return dag
    except Exception:
        pass

    try:
        obj = sel.getDependNode(0)
    except Exception:
        return None

    try:
        if obj.hasFn(MFn.kDagNode):
            try:
                return MDagPath.getAPathTo(obj)
            except Exception:
                return obj
    except Exception:
        pass
    return obj

def dec_undo(func):
    @functools.wraps(func)
    def _undo_func(*args, **kwargs):
        cmds.undoInfo(ock=True)
        try: return func(*args, **kwargs)
        finally: cmds.undoInfo(cck=True)
    return _undo_func

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
        except Exception:
            if _debug:
                warnings.warn('Unknown attr type at %s' % self._path)
            return

        if t in ('short2', 'short3', 'long2', 'long3', 'Int32Array', 'float2', 'float3', 'double2', 'double3',
                 'doubleArray', 'matrix', 'pointArray', 'vectorArray', 'string', 'stringArray', 'sphere', 'cone',
                 'reflectanceRGB', 'spectrumRGB', 'componentList', 'attributeAlias', 'nurbsCurve', 'nurbsSurface',
                 'nurbsTrimface', 'polyFace', 'mesh', 'lattice'):
            self._setterKwargs['type'] = t

    def __call__(self, *args, **kwargs):
        try:
            maybe_method = object.__getattribute__(self.node(), self._path.split('.', 1)[-1])
        except AttributeError:
            maybe_method = None
        if callable(maybe_method):
            return maybe_method(*args, **kwargs)
        raise CMDWrapperError(f'Attempting to get an attribute {self}, did you mean {self}.get()?')

    def __hash__(self):
        return self.name().__hash__()

    def __getattr__(self, item):
        return _Attribute(f"{self._path}.{item}")

    def __setattr__(self, attr, value):
        if attr in ('_path', '_setterKwargs'):
            super().__setattr__(attr, value)
            return
        getattr(self, attr).set(value)

    def __getitem__(self, index):
        return _Attribute(f"{self._path}[{index}]")

    def __setitem__(self, index, value):
        self[index].set(value)

    def __iter__(self):
        for index in cmds.getAttr(self._path, multiIndices=True) or []:
            yield self[index]

    def __lshift__(self, other):
        [self.connect(x) for x in other]

    def __rshift__(self, other):
        self.connect(other)

    def __le__(self, other):
        if not isinstance(other, type(self)):
            self.set(other)
            return
        self.set(other.get())

    def __floordiv__(self, other):
        if isinstance(other, (list, tuple)):
            [self.disconnect(x) for x in other]
            return
        self.disconnect(other)

    def to_json(self):
        return self._path

    def asPlug(self):
        try:
            _depNode = MFnDependencyNode(self.node().asMObject())
            return _depNode.findPlug(self.name(), False)
        except:
            sel = MSelectionList()
            sel.add(self._path)
            return sel.getPlug(0)

    def asMfnAttr(self):
        return MFnAttribute(self.asPlug().attribute())

    def numElements(self):
        return cmds.getAttr(self._path, size=True)

    def logicalIndex(self):
        _name = self.name()
        return int(_name[_name.index("[") + 1: -1])

    def node(self):
        return wrapNode(self._path.split('.', 1)[0])

    def name(self):
        return self._path.split('.', 1)[-1]

    def isKeyable(self):
        return cmds.getAttr(self._path, keyable=True)

    def isLocked(self):
        return cmds.getAttr(self._path, lock=True)

    def isProxy(self):
        return self.asMfnAttr().isProxyAttribute

    def isChannelBox(self):
        return cmds.getAttr(self._path, channelBox=True)

    def isDestination(self):
        return bool(cmds.listConnections(self._path, s=True, d=False))

    def type(self):
        return cmds.getAttr(self._path, type=True)

    def __str__(self):
        return self._path  # so we can easily throw Attribute() objects into maya functions

    def __repr__(self):
        return f"{self._path} : {self.__class__.__name__}"  # so we can easily throw Attribute() objects into maya functions

    def __eq__(self, other):
        if isinstance(other, _Attribute):
            return self._path == other._path
        return False

    def connect(self, destination):
        cmds.connectAttr(self._path, str(destination), force=True)

    def disconnectInputs(self):
        for source in self.connections(s=True, d=False):
            cmds.disconnectAttr(str(source), self._path)
 
    def disconnectOutputs(self):
        for target in self.connections(s=False, d=True):
            cmds.disconnectAttr(self._path, str(target))

    def disconnectAll(self):
        self.disconnectInputs()
        self.disconnectOutputs()

    def disconnect(self, destination):
        cmds.disconnectAttr(self._path, str(destination))

    def connections(self, s=True, d=True, asNode=False, skipConversion = True):
        return cmds.listConnections(self._path, s=s, d=d, p=not asNode, scn=skipConversion, sh=True) or []

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
            if hasattr(args[0], '__iter__') and not isinstance(args[0], str):
                args = tuple(args[0])
        kwargs.update(self._setterKwargs)
        cmds.setAttr(self._path, *args, **kwargs)

    def arrayName(self):
        return self.node().plug(self.asPlug().array().name().split('.')[-1])
    
    def children(self):
        for childAttr in cmds.attributeQuery(self.arrayName().name(), node=self.node(), lc=True):
            yield _Attribute(f"{self._path}.{childAttr}")

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
                    yield self.__class__(childAttributePath)


    def setLocked(self, lock, leaf=False):
        if leaf:
            for attr in self._recurse():
                attr.setLocked(lock, False)
        cmds.setAttr(self._path, lock=lock)

    def setKeyable(self, keyable, leaf=False):
        if leaf:
            for attr in self._recurse():
                attr.setKeyable(keyable, False)
        cmds.setAttr(self._path, keyable=keyable)

    def setChannelBox(self, cb, leaf=False):
        if leaf:
            for attr in self._recurse():
                attr.setChannelBox(cb, False)
        cmds.setAttr(self._path, channelBox=cb)


class _Transform_Rotate_Attribute(_Attribute):
    def get(self):
        angles = cmds.getAttr(self._path)[0]
        return Euler(angles[0], angles[1], angles[2], cmds.getAttr(f"{self._path.split('.', 1)[0]}.rotateOrder"))


class DependNode(object):
    """
    NOTE: This class implements __setattr__, as such any members assigned to self
    should be added as an exclusion inside the __setattr__ function.

    Wraps a Maya node, sub classes may introduce features more specific to the underlying node's type.
    Always use DependNode.pool() (or <subclass>.pool()) to get depend nodes, never construct them manually.

    Depend nodes use MObject and MDagPath handles so reparenting and renaming nodes should
    never invalidate your DependNode instance.
    """
    # _instances = {}  # not sure if more efficient, but let's do some object pooling by UUID
    _MFnDependencyNode = MFnDependencyNode()  # I don't want to create new objects every time we get the name
    _apiObjectHelper = _oldMSelectionList()


    @staticmethod
    def fnInstance():
        return DependNode._MFnDependencyNode

    def __init__(self, nodeName, nodeType):
        assert isinstance(nodeName, str)
        self.__type = nodeType
        h = _resolveHandle(nodeName)
        self.__handle = h if h is not None else MObject()

    def valid(self):
        h = getattr(self, "_DependNode__handle", None)
        if isinstance(h, MDagPath):
            return bool(h) and h.isValid() and _isAliveMObject(h.node())
        return _isAliveMObject(h)

    def updateHandle(self, nodeName):
        h = _resolveHandle(nodeName)
        self.__handle = h if h is not None else MObject()

    def __len__(self):
        return len(str(self))

    def __apiobject__(self):
        if not self.valid():
            return _oldMObject()
        if not self._nodeName or not _cmds.objExists(self._nodeName):
            return _oldMObject()
        _oldMGlobal.getSelectionListByName(self._nodeName, self._apiObjectHelper)
        o = _oldMObject()
        self._apiObjectHelper.getDependNode(0, o)
        return o

    def delete(self, constructionHistory=False):
        cmds.delete(self._nodeName, ch=constructionHistory)

    def copy(self, newName = None):
       return cmds.duplicate(self._nodeName,rc=True, n=newName)[0]

    def name(self):
        return self._nodeName.rsplit('|', 1)[-1]

    def to_json(self):
        return self._nodeName

    @property
    def _nodeName(self):
        h = getattr(self, "_DependNode__handle", None)
        if isinstance(h, MDagPath):
            if not h or not h.isValid() or not _isAliveMObject(h.node()):
                return ''
            return h.fullPathName()   
        if not _isAliveMObject(h):
            return ''
        self._MFnDependencyNode.setObject(h)
        try:
            return self._MFnDependencyNode.name()  
        except Exception:
            return ''
    
    def __uuid__(self):
        return cmds.ls(self._nodeName, uuid=True)[0]

    def __eq__(self, other):
        if isinstance(other, DependNode):
            return self._nodeName == other._nodeName
        return False

    def __hash__(self):
        return self._nodeName.__hash__()

    def rename(self, newName):
        cmds.rename(self._nodeName, newName)

    def hasAttr(self, attr):
        return cmds.objExists(f"{self._nodeName}.{attr}")

    def __getnewargs__(self):
        # make sure pickle works, returning info to generate the boject from scratch
        return (self.__type, self._nodeName)

    def __getstate__(self):
        # make sure this object returns a string so pickle works
        return (self.__type, self._nodeName)

    def __setstate__(self, inSettings):
        inType, inNodeName = inSettings
        self.__type = inType
        h = _resolveHandle(inNodeName)
        self.__handle = h if h is not None else MObject()

    def __getattribute__(self, attr):
        if attr.startswith('_'):
            return object.__getattribute__(self, attr)

        try:
            nodeName = object.__getattribute__(self, '_nodeName')
        except Exception:
            nodeName = ''
        if nodeName:
            try:
                if _cmds.objExists(f"{nodeName}.{attr}"):
                    return _Attribute(f"{nodeName}.{attr}")
            except Exception:
                pass
        return super().__getattribute__(attr)

    def __getattr__(self, attr):
        if attr in ("node", "name", "valid"):
            raise CMDWrapperError(f"{attr} is not a dynamic plug attribute")
        return _Attribute(f"{self._nodeName}.{attr}")

    def __setattr__(self, attr, value):
        if attr.startswith('_DependNode__'):
            super().__setattr__(attr, value)
            return
        getattr(self, attr).set(value)

    def __bool__(self):
        return self.valid()
        
    def __str__(self):
        return self._nodeName  # so we can easily throw DependNode() objects into maya functions

    def __repr__(self):
        if not self._nodeName:
            return f"<deleted {getattr(self, '_DependNode__type', 'DependNode')} : {self.__class__.__name__}>"
        return f"{self._nodeName} : {self.__class__.__name__}" 

    def type(self):
        return self.__type

    def isType(self, inType):
        return inType == self.__type

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

    def deleteAttr(self, attrName):
        if self.hasAttr(attrName):
            cmds.deleteAttr(self._nodeName, at=attrName)

    def plugs(self, ud=False):
        return [_Attribute(f"{self._nodeName}.{attr}") for attr in (_cmds.listAttr(self._nodeName, ud=ud) or [])]

    def isShape(self):
        return self.asMObject().hasFn(MFn.kShape)

    def plug(self, attr):  # TODO: Refactor this away
        return _Attribute(f"{self._nodeName}.{attr}")

    def connections(self, s=True, d=True):
        return cmds.listConnections(self._nodeName, s=s, d=d, p=True, sh=True) or []

    def customPlugs(self):
        return [self.plug(attr) for attr in (cmds.listAttr(self._nodeName, ud=1) or [])]

    def asMObject(self):
        h = getattr(self, "_DependNode__handle", None)
        if isinstance(h, MDagPath):
            return h.node()
        return h if isinstance(h, MObject) else _getMObject(self._nodeName)


class DagNode(DependNode):
    # Note the base class implements __setattr__, so we should not introduce new member variables, only functions.
    def parent(self):
        p = self._nodeName.rsplit('|', 1)[0]
        if p:
            return wrapNode(p)

    def setParent(self, parent, shape=False, relative=False):
        if shape:
            if parent is None:
                raise CMDWrapperError("cannot parent shape to world!")
            cmds.parent(self._nodeName, parent, add=True, s=True, r=relative)
            return
        if parent is None:
            cmds.parent(self._nodeName, world=True, r=relative)
            return
        cmds.parent(self._nodeName, parent, r=relative)

    def shortName(self):
        return self._nodeName.rsplit('|', 1)[-1]

    def asDagPath(self):
        return _getMDagPath(self._nodeName)


class Transform(DagNode):
    # Note the base class implements __setattr__, so we should not introduce new member variables, only functions.
    def shape(self):
        return (cmds.listRelatives(self._nodeName, c=True, f=True, type='shape') or [None])[0]

    def shapes(self):
        return cmds.listRelatives(self._nodeName, c=True, f=True, type='shape') or []

    def _children(self, type=None):
        if type:
            return _cmds.listRelatives(self._nodeName, c=True, f=True, type=type) or []
        return _cmds.listRelatives(self._nodeName, c=True, f=True) or []

    def children(self, recursive=False):
        if recursive:
            hierarchy = [self]
            while self._children("transform") != []:
                child = getNode(self._children("transform")[0])
                hierarchy.append(child)
                self = child
                if child._children("transform") == []:
                    break
            return hierarchy
        return cmds.listRelatives(self._nodeName, c=True, f=True) or []

    def allDescendants(self):
        return cmds.listRelatives(self._nodeName, ad=True, f=True) or []

    def numChildren(self):
        return len(self._children())

    def child(self, index=0):
        children = self._children()
        if children:
            return wrapNode(children[index])
        return None

    def parents(self):
        return [wrapNode(node) for node in self._nodeName.split("|") if not node in ["", self.name()]]

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
            return _Transform_Rotate_Attribute(f"{self._nodeName}.{attr}")
        return super().__getattr__(attr)


class Joint(Transform):
    # Note the base class implements __setattr__, so we should not introduce new member variables, only functions.
    def setJointOrientMatrix(self, m, ws=False):
        if ws:
            parentInverseMatrix = cmds.getAttr(f"{self._nodeName}.parentInverseMatrix")
        else:
            s = cmds.getAttr(f"{self._nodeName}.is")[0]
            parentInverseMatrix = [s[0], 0.0, 0.0, 0.0,
                                   0.0, s[1], 0.0, 0.0,
                                   0.0, 0.0, s[2], 0.0,
                                   0.0, 0.0, 0.0, 1.0]
        m *= Matrix(parentInverseMatrix)
        cmds.setAttr(f"{self._nodeName}.jointOrient", *m.asDegrees(), type='double3')


class AnimCurve(DependNode):
    _MFnAnimCurve = MFnAnimCurve()

    def _fnAnimCurve(self):
        self._MFnAnimCurve.setObject(self.asMObject())
        return self._MFnAnimCurve

    def getAnimCurveType(self):
        return self._fnAnimCurve().animCurveType
    
    def numKeys(self):
        return self._fnAnimCurve().numKeys

    def keys(self):
        return {self.getKeyTime(i) :self.getKeyValue(i) for i in range(self.numKeys())}
    
    def firstkey(self):
        return min(self.keys().keys())
    
    def lastkey(self):
        return max(self.keys().keys())

    def length(self):
        return self.lastkey() - self.firstkey()

    def evaluate(self, time):
        return self._fnAnimCurve().evaluate(MTime(time, MTime.uiUnit()))

    def addKeyframe(self, time, value, tangentIn=MFnAnimCurve.kTangentGlobal, tangentOut=MFnAnimCurve.kTangentGlobal):
        self._fnAnimCurve().addKey(MTime(time, MTime.uiUnit()), value, tangentIn, tangentOut)

    def removeKeyframe(self, time):
        fnAnimCurve = self._fnAnimCurve()
        index = fnAnimCurve.find(MTime(time, MTime.uiUnit()))
        fnAnimCurve.remove(index)   

    def getKeyTime(self, keyIndex):
        return self._fnAnimCurve().input(keyIndex).asUnits(MTime.uiUnit())

    def getKeyValue(self, keyIndex):
        return self._fnAnimCurve().value(keyIndex)
    
    def isLocked(self, keyIndex):
        return self._fnAnimCurve().tangentsLocked(keyIndex)

    def getTangentTypes(self, keyIndex):
        fnAnimCurve = self._fnAnimCurve()
        return (fnAnimCurve.inTangentType(keyIndex), fnAnimCurve.outTangentType(keyIndex))

    def getTangents(self, keyIndex):
        fnAnimCurve = self._fnAnimCurve()
        return (fnAnimCurve.getTangentXY(keyIndex, True), fnAnimCurve.getTangentXY(keyIndex, False))

    def setLocked(self, keyIndex, state):
        self._fnAnimCurve().setTangentsLocked(keyIndex, state)

    def setTangentTypes(self, keyIndex, tangentTypes):
        fnAnimCurve = self._fnAnimCurve()
        fnAnimCurve.setInTangentType(keyIndex, tangentTypes[0]) 
        fnAnimCurve.setOutTangentType(keyIndex, tangentTypes[1]) 
        
    def setTangent(self, keyIndex, inTangent, outTangent):
        self.setLocked(keyIndex, False)
        fnAnimCurve = self._fnAnimCurve()
        fnAnimCurve.setTangent(keyIndex, inTangent[0], inTangent[1], True, convertUnits=False) 
        fnAnimCurve.setTangent(keyIndex, outTangent[0], outTangent[1], False, convertUnits=False) 
       
    def clearCurve(self):
        fnAnimCurve = self._fnAnimCurve()
        for i in reversed(range(fnAnimCurve.numKeys)):
            fnAnimCurve.remove(i)

    def removeKeysInRange(self, startTime, endTime):
        for i in reversed(range(self.numKeys())):
            time = self.getKeyTime(i)
            if startTime <= time <= endTime:
                self.removeKeyframe(time)

    def getAllKeyData(self):
        keyData = []
        for i in range(self.numKeys()):
            tangentTypes = self.getTangentTypes(i)
            tangents = self.getTangents(i)
            keyData.append({ 'time': self.getKeyTime(i), 'value': self.getKeyValue(i),
                             'inTangentType': tangentTypes[0], 'outTangentType': tangentTypes[1],
                             'inTangent': tangents[0], 'outTangent': tangents[1] })
        return keyData

    def scaleCurve(self, timeScale=1.0, valueScale=1.0, pivotTime=0.0, pivotValue=0.0, timeRange=None):
        params = {}
        if timeRange:
            params["time"] = tuple(timeRange)
        cmds.scaleKey(self._nodeName, timePivot = pivotTime, timeScale = timeScale, valueScale=valueScale, valuePivot=pivotValue, **params)

    def shiftCurve(self, timeShift=0.0, valueShift=0.0, timeRange=None):
        params = {}
        if timeRange:
            params['time'] = tuple(timeRange)
        if timeShift: cmds.keyframe( self._nodeName, edit=True, relative=True, timeChange=timeShift, **params )
        if valueShift: cmds.keyframe( self._nodeName, edit=True, relative=True, valueChange=valueShift, **params )

    @dec_undo
    def remapTime(self, inputMin, inputMax, outputMin, outputMax):
        inputRange = inputMax - inputMin
        if inputRange == 0: raise CMDWrapperError("Input range cannot be zero.")
        timeScale = (outputMax - outputMin) / inputRange

        self.scaleCurve(timeScale=timeScale, valueScale=1.0, pivotTime=inputMin)  
        self.shiftCurve(timeShift=outputMin - inputMin)

    @dec_undo
    def remapValue(self, inputMin, inputMax, outputMin, outputMax):
        inputRange = inputMax - inputMin
        if inputRange == 0: raise CMDWrapperError("Input range cannot be zero.")
        valueScale = (outputMax - outputMin) / inputRange

        self.scaleCurve(valueScale=valueScale, pivotValue=inputMin)  
        self.shiftCurve(valueShift=outputMin - inputMin)

    def setLocked(self, setLocked):
        locklist = ['ktv', 'ktl', 'kwl', 'kix', 'kiy', 'kox', 'koy', 'kit', 'ktl', 'kot', 'pre', 'pst']
        for lock in locklist:
            self.plug(lock).setLocked(setLocked)

class Shape(DagNode):
    # Note the base class implements __setattr__, so we should not introduce new member variables, only functions.
    pass


def wrapNode(nodeName):
    if isinstance(nodeName, str) and '.' in nodeName:
        base, suffix = nodeName.split('.', 1)
        baseWrapped = wrapNode(base)
        return None if baseWrapped is None else getattr(baseWrapped, suffix)

    if not _cmds.objExists(nodeName):
        return None

    h = _resolveHandle(nodeName)
    if h is None:
        return None

    obj = h.node() if isinstance(h, MDagPath) else h
    _type = DependNode
    if obj.hasFn(MFn.kShape):         _type = Shape
    elif obj.hasFn(MFn.kJoint):       _type = Joint
    elif obj.hasFn(MFn.kTransform):   _type = Transform
    elif obj.hasFn(MFn.kAnimCurve):   _type = AnimCurve

    try:
        inst = _type(nodeName, _cmds.nodeType(nodeName))
    except Exception:
        inst = object.__new__(_type)
        setattr(inst, f"_DependNode__type", _cmds.nodeType(nodeName))
    try:
        setattr(inst, f"_DependNode__handle", h)
    except Exception:
        pass
    return inst


def createNode(nodeType):
    # Api with undo/redo support, we profiled this to be faster than cmds.createNode:
    # noinspection PyBroadException
    try:
        mod = MDGModifier()
        obj = mod.createNode(nodeType)
    except Exception:
        mod = MDagModifier()
        obj = mod.createNode(nodeType)
    mod.doIt()
    DependNode.fnInstance().setObject(obj)
    node = DependNode.fnInstance().name()
    return wrapNode(node)


def _isStringOrStringList(inObject):
    if isinstance(inObject, str):
        return True
    if not isinstance(inObject, (list, tuple)):
        return False
    if all(_isStringOrStringList(elem) for elem in inObject):
        return True
    return False


def getNode(nodeName=None):
    if nodeName is None:
        cur = _cmds.ls(sl=True)
        if not cur: return []
        if len(cur) == 1:
            return wrapNode(cur[0]) or cur[0]
        out = []
        for n in cur:
            w = wrapNode(n)
            out.append(w if w is not None else n)
        return out

    names = []
    single = False
    if isinstance(nodeName, str):
        names = [nodeName]; single = True
    elif isinstance(nodeName, MObject):
        fn = MFnDependencyNode(nodeName)
        names = [fn.name()]; single = True
    elif isinstance(nodeName, (list, tuple)):
        names = nodeName
    else:
        return None

    wrapped = []
    for n in names:
        w = wrapNode(n)
        wrapped.append(w if w is not None else None)

    return wrapped[0] if single else wrapped
