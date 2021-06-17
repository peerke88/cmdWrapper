import unittest
import os
import random
import math


class TestCmds(unittest.TestCase):
    def __init__(self, methodName='unitTest'):
        # disable the crash reporting window.
        os.environ["MAYA_DEBUG_ENABLE_CRASH_REPORTING"] = "0"
        os.environ["PYMEL_SKIP_MEL_INIT"] = "Temp"
        # init maya
        import maya.standalone
        maya.standalone.initialize(name='python')
        # continue
        super(TestCmds, self).__init__(methodName)

    def assertAlmostEqualIterable(self, a, b, msg=None):
        if len(a) == len(b):
            for ae, be in zip(a, b):
                self.assertAlmostEqual(ae, be, 3)
        else:
            msg = self._formatMessage(msg, '%s == %s' % (repr(a), repr(b)))
            raise self.failureException(msg)

    def test_basics(self):
        # import wrappers
        from cmdWrapper import cmds, createNode, getNode, DependNode, children, allDescendants, Matrix, selection
        from maya.api import OpenMaya
        transform = createNode('transform')
        self.assertEqual(str(transform), '|transform1')
        # get and set translate
        self.assertEqual(transform.tx(), 0.0)
        self.assertEqual(transform.translate.get(), (0.0, 0.0, 0.0))
        transform.translate = 10.0, 1.0, 0.0
        # noinspection PyCallingNonCallable
        self.assertEqual(transform.translate(), (10.0, 1.0, 0.0))
        transform.tx.set(2.0)
        self.assertEqual(transform.tx(), 2.0)
        # find a node & it's shape
        persp_transform = getNode('persp')
        persp_shape = persp_transform.shape()
        self.assertEqual(str(persp_shape), '|persp|perspShape')
        # reparent a node
        transform.setParent(persp_transform)
        self.assertEqual(str(transform), '|persp|transform1')
        self.assertEqual(transform.parent(), persp_transform)
        # even attributes should still work
        self.assertEqual(str(transform.translate), '|persp|transform1.translate')
        # cmds return type validation
        self.assertEqual(cmds.listRelatives(transform, ad=True), None)
        t = cmds.xform(transform, q=True, ws=True, t=True)
        self.assertAlmostEqualIterable(t, (2.0, 1.0, 0.0))
        self.assertAlmostEqualIterable(cmds.xform(transform, q=True, ws=True, m=True),
                                       (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 2.0, 1.0, 0.0, 1.0))
        self.assertEqual(cmds.file(rename='C:/Test.ma'), 'C:/Test.ma')
        self.assertEqual('C:/Test.ma', cmds.file(q=True, sn=True))
        self.assertEqual(['C:/Test.ma'], cmds.file(query=True, list=True))
        self.assertEqual(['scale', 'scaleX', 'scaleY', 'scaleZ', 'scalePivot', 'scalePivotX', 'scalePivotY', 'scalePivotZ',
                          'scalePivotTranslate', 'scalePivotTranslateX', 'scalePivotTranslateY', 'scalePivotTranslateZ'],
                         cmds.listAttr(transform, r=True, st='scale*'))
        self.assertEqual(True, cmds.objExists(transform))
        self.assertEqual(DependNode, type(cmds.createNode('curveInfo')))
        self.assertEqual(['|test', 'makeNurbCircle1'], [str(e) for e in cmds.circle(n='test')])
        self.assertEqual('untitled', cmds.file(f=True, new=True))
        self.assertEqual('y' or 'z', cmds.upAxis(q=True, axis=True))
        cmds.joint()
        cmds.joint()
        cmds.joint()
        self.assertEqual(children('|joint1'), {getNode('|joint1|joint2')})
        self.assertEqual(allDescendants('|joint1'), set(getNode(('|joint1|joint2', '|joint1|joint2|joint3'))))
        for inst in cmds.ls(sl=0)[::5]:
            assert isinstance(inst, DependNode)
        crc = cmds.circle()[0]
        self.assertEqual(cmds.ls('%s[*]' % crc.cv, fl=True), getNode(['|nurbsCircle1.cv[%i]' % i for i in range(8)]))

        circle = cmds.circle()[0]
        transform = cmds.createNode("transform", n="testing")
        self.assertEqual(transform.getM(), Matrix.identity)
        self.assertEqual(transform.shortName(), "testing")
        circle.shape().setParent(transform, shape=True)
        self.assertEqual(transform.shape(), circle.shape())
        cmds.delete(circle)
        self.assertEqual(transform.shape().name(), "nurbsCircleShape2")

        transform.translateX.setKeyable(False, leaf=True)
        transform.translateX.setChannelBox(False, leaf=True)
        transform.translateX.setLocked(True, leaf=True)
        self.assertEqual(len(transform), 8)

        self.assertEqual(transform.translateX.isKeyable(), False)
        self.assertEqual(transform.translateX.isLocked(), True)
        self.assertEqual(transform.translateX.isChannelBox(), False)

        self.assertTrue(transform.translateX in transform.plugs())

        transform.delete()

        self.assertFalse(cmds.objExists(transform))

        trs = cmds.polyCube()
        self.assertFalse(trs[0].isShape())
        self.assertTrue(trs[0].shape().isShape())
        self.assertEqual(len(trs[0].shapes()), trs[0].numChildren())
        self.assertEqual(trs[0].shapes(), trs[0].children())
        self.assertEqual(trs[0].shape(), trs[0].child())

        trs[0].addAttr("test", type="enum", en="Green:Blue:")
        trs[0].plug("test")

        mlist = OpenMaya.MSelectionList()
        mlist.add(trs[0].shortName())
        _dep = mlist.getDependNode(0)

        self.assertEqual(trs[0].asMObject(), _dep)

        trs[0].rename("newName")
        self.assertEqual(trs[0].shortName(), "newName")
        self.assertTrue(trs[0].hasAttr("translateX"))
        self.assertTrue(trs[0].type(), "transform")
        self.assertTrue(trs[0].shape().type(), "mesh")
        trs[0].addAttr("stringTest", type="string")
        trs[0].stringTest.set("myStringTest")
        self.assertTrue(trs[0].hasAttr("stringTest"))
        self.assertEqual(trs[0].stringTest.get(), "myStringTest")

        cmds.select(trs[0], r=1)
        print(cmds.ls(sl=1))
        print(selection())
        self.assertEqual(selection(), trs[0])

    def test_attributes(self):
        # import wrappers
        from cmdWrapper import cmds, Vector, Matrix

        nVec = Vector(5 * random.random(), 5 * random.random(), 5 * random.random())
        loc1 = cmds.spaceLocator()[0]
        loc1.translate = nVec
        self.assertEqual(nVec, loc1.translate())
        loc2 = cmds.spaceLocator()[0]
        loc2.translate.set(-1.56, 2.603, .556)
        vecA = loc1.translate()
        self.assertEqual(loc1.translate(), vecA)
        vecB = loc2.translate.get()
        vecA = vecA.normal()
        vecB.normalize()
        vecC = vecA ^ vecB
        vecD = vecA.cross(vecB)
        self.assertEqual(vecC, vecD)
        loc = cmds.spaceLocator()[0]
        loc.translate = vecC

        origMat = loc2.worldMatrix[0].get()
        mat = loc1.worldMatrix[0]()
        loc2.setM(mat)
        loc2.setT(origMat[12:15])
        self.assertEqual(Vector(origMat[12:15]), loc2.getT(ws=True))
        mat.setT(vecC)
        if cmds.about(v=True).startswith('2020'):
            loc2.offsetParentMatrix.set(mat)

        vecE = vecA ^ vecC
        nMat = Matrix(vecA.normal()[:] + [0] + vecE.normal()[:] + [0] + vecC.normal()[:] + [0] + loc1.translate()[:] + [1])
        loc.setM(nMat)
        a = nMat.rotation()
        self.assertEqual(tuple(math.degrees(b) for b in a), nMat.asR())

        jnt = cmds.createNode("joint", name="testerJoint")
        jnt.setJointOrientMatrix(nMat)

        self.assertAlmostEqualIterable(a.asMatrix(), jnt.getM())

        jnt.setJointOrientMatrix(nMat, ws=True)

        self.assertAlmostEqualIterable(a.asMatrix(), jnt.getM())

    def testMath(self):
        from cmdWrapper import cmds, QuaternionOrPoint, Euler, Matrix, Vector
        from maya.api.OpenMaya import MVector

        a = QuaternionOrPoint(0, 0, 0, 1)
        b = QuaternionOrPoint(0, 1, 0, 0)
        c = a * b

        rot = Euler(0, math.pi, 0)

        # make use of almost equal as we are dealing with pi rounding
        self.assertAlmostEqualIterable(c, rot.asQuaternion())
        self.assertEqual(c.asEulerRotation(), rot.asRadians())
        self.assertEqual(rot.asDegrees(), (0, 180, 0))

        self.assertEqual(rot.asVector(), Vector(0, math.pi, 0))

        vecA = Vector(-1, 0, 0)
        vecB = Vector(0, 1, 0)
        vecC = Vector(0, 0, -1)
        testMatrix = Matrix(vecA[:] + [0] + vecB[:] + [0] + vecC[:] + [0, 0, 0, 0, 1])
        writtenMatrix = Matrix([-1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1])
        self.assertAlmostEqualIterable(rot.asMatrix(), testMatrix)

        self.assertEqual(testMatrix.get(0, 0), -1)
        self.assertEqual(testMatrix.asRadians(), rot.asRadians())
        self.assertEqual(testMatrix.asT(), Vector(0, 0, 0))

        self.assertTrue(writtenMatrix == testMatrix)
        self.assertTrue(rot.asMatrix() != testMatrix)
        vecF = vecA / 2
        self.assertEqual(vecF, Vector(-.5, 0, 0))

        vecD = vecB + vecC
        self.assertEqual(vecD, Vector(0, 1, -1))
        dot90 = vecB * vecC
        self.assertEqual(dot90, 0.0)
        dot180 = vecB * MVector(0, -1, 0)
        self.assertEqual(dot180, -1.0)

        quatRot = vecB.rotateTo(vecC)
        self.assertAlmostEqualIterable(quatRot, QuaternionOrPoint(-0.707107, 0, 0, 0.707107))

        decomp = cmds.createNode("decomposeMatrix")
        mat = decomp.outputQuat().asMatrix()
        d = c * mat
        self.assertEqual(Vector(mat[12:15]), mat.asT())
        self.assertEqual(mat, Matrix())
        self.assertEqual(mat.axis(0), Vector(1, 0, 0))
        testVec = Vector(1, -2, 5)
        mat[12] = testVec.x
        mat[13] = testVec[1]
        mat[14] = testVec.z
        self.assertEqual(Vector(mat[12:15]), testVec)
        self.assertFalse(Vector() == 1)

        nVec = Vector(1, 0, 0) * Matrix()

        vec = Vector()
        vec[0:2] = (1, 1)
        self.assertEqual(vec - Vector(1, 1, 0), Vector())
        transform = cmds.createNode("transform", n="testTransform")
        transform1 = cmds.createNode("transform", n="testTransform1")
        transform.translate = (1.0, 2.0, 3.0)
        transform.translate.connect(transform1.translate)
        vec = transform1.translate()
        self.assertEqual(vec, Vector(1.0, 2.0, 3.0))
        self.assertTrue(transform1.translate.isDestination())
        self.assertFalse(transform.translate.isDestination())
        transform1.translate.disconnectInputs()
        self.assertFalse(transform1.translate.isConnected())
        self.assertFalse(transform.translate.isKeyable())
        self.assertTrue(transform.translateX.isKeyable())

        transform.translate.connect(transform1.translate)
        self.assertTrue(transform1.translate.isConnected())
        transform.translate.disconnect(transform1.translate)
        self.assertFalse(transform1.translate.isConnected())

        cmds.addAttr(transform1, ln="test", proxy=transform.translateX)
        self.assertTrue(transform1.test.isProxy())

        rot = transform.rotate()
        self.assertEqual(rot, Euler())


if __name__ == '__main__':
    unittest.main()
