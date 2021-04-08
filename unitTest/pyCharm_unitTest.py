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
        from cmdWrapper import cmds, createNode, getNode, DependNode, children, allDescendants, Vector, Matrix

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
        euler1 = nMat.rotation()

        a = nMat.rotation()
        self.assertEqual(tuple(math.degrees(b) for b in a), nMat.asR())

    def testMath(self):
        from cmdWrapper import cmds, QuaternionOrPoint, Euler, Matrix, Vector
        from maya.api.OpenMaya import MVector

        a = QuaternionOrPoint(0,0,0,1)
        b = QuaternionOrPoint(0,1,0,0)
        c = a * b

        rot = Euler(0, math.pi, 0)

        # make use of almost equal as we are dealing with pi rounding 
        self.assertAlmostEqualIterable(c, rot.asQuaternion())
        self.assertEqual(c.asEulerRotation(), rot.asRadians())
        self.assertEqual(rot.asDegrees(), (0, 180, 0))

        self.assertEqual(rot.asVector(), Vector(0, math.pi, 0))
        
        vecA = Vector(-1,0,0)
        vecB = Vector(0,1,0)
        vecC = Vector(0,0,-1)
        testMatrix = Matrix(vecA[:]+[0]+vecB[:]+[0]+vecC[:]+[0,0,0,0,1])
        writtenMatrix = Matrix([-1,0,0,0,0,1,0,0,0,0,-1,0,0,0,0,1])
        self.assertAlmostEqualIterable(rot.asMatrix(), testMatrix)

        self.assertEqual(testMatrix.get(0,0), -1)
        self.assertEqual(testMatrix.asRadians(), rot.asRadians())
        self.assertEqual(testMatrix.asT(), Vector(0,0,0))

        self.assertTrue(writtenMatrix == testMatrix)
        self.assertTrue(rot.asMatrix() != testMatrix)

        vecD = vecB + vecC
        self.assertEqual(vecD, Vector(0,1,-1))
        dot90 = vecB * vecC
        self.assertEqual(dot90, 0.0)
        dot180 = vecB * MVector(0,-1, 0)
        self.assertEqual(dot180, -1.0)

        quatRot =  vecB.rotateTo(vecC)
        self.assertAlmostEqualIterable(quatRot, QuaternionOrPoint(-0.707107, 0, 0, 0.707107))

        decomp = cmds.createNode("decomposeMatrix")
        mat = decomp.outputQuat().asMatrix()
        d = c * mat
        self.assertEqual(mat, Matrix())
        self.assertEqual(mat.axis(0), Vector(1,0,0))


if __name__ == '__main__':
    unittest.main()
