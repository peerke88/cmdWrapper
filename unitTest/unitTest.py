import unittest, os, sys, logging, cProfile, random

_basePath = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not _basePath in sys.path:
    sys.path.insert(0, _basePath)

import maya.standalone

root_logger = logging.getLogger()
root_logger.disabled = True
for x, y in logging.Logger.manager.loggerDict.iteritems():
    try:
        y.setLevel(logging.CRITICAL)
    except Exception as e:
        pass

## disable the crash reporting window.
os.environ["MAYA_DEBUG_ENABLE_CRASH_REPORTING"] = "0"
os.environ["PYMEL_SKIP_MEL_INIT"] = "Temp"

maya.standalone.initialize(name='python')

# coverage needs to start BEFORE imports happen
# or else it reports all class definitions as "not covered"
_coverage = True
try:
    import coverage
    cov = coverage.Coverage(source=['cmdWrapper'])
    cov.start()
except Exception as err:
    _coverage = False

_canProfile = True
try:
    from cmdWrapper import pyprof2calltree
except:
    _canProfile = False

from cmdWrapper import cmds, Vector, Matrix

cmds.loadPlugin('matrixNodes',qt=True)
cmds.loadPlugin('quatNodes', qt=True)

class TestCmds(unittest.TestCase):
    
    def basics(self):
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
        self.assertEqual(cmds.xform(transform, q=True, ws=True, t=True), (2.0, 1.0, 0.0))
        self.assertEqual(cmds.xform(transform, q=True, ws=True, m=True),
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


    def attributes(self):
        nVec = (5*random.random(), 5*random.random(), 5*random.random())
        loc1 = cmds.spaceLocator()[0]
        loc1.translate = nVec
        self.assertEqual(Vector(nVec), loc1.translate)
        loc2 = cmds.spaceLocator()[0]
        loc2.translate.set(-1.56, 2.603, .556)
        vecA = loc1.translate()
        self.assertEqual(loc1.translate, vecA)
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
        self.assertEqual(Vector(origMat[12:15]), loc2.getT(ws=1))
        mat.setT(vecC)
        if cmds.about(v=1) > 2020:
            loc2.offsetParentMatrix.set(mat)

        vecE = vecA ^ vecC
        nMat = Matrix(vecA.normal()[:] + [0] + vecE.normal()[:] +[0] + vecC.normal()[:] + [0] + loc1.translate()[:] + [1] )
        loc.setM(nMat)
        euler1 = nMat.rotation()
        quat1.asQuaternion()
        euler2.asEulerRotation()
        self.assertEqual(euler1, euler2)

        a = nMat.rotation()
        self.assertEqual(tuple(math.degrees(b) for b in a), nMat.asR())

## \~english testing context that will fire the unitTests but can be used in a cProfile argument
def testctx():
    log_file = 'log_file.txt'
    curDirect = os.path.dirname(__file__)
    file = open(os.path.join(curDirect, log_file), "w")
    suite = unittest.TestSuite()
    result = unittest.TestResult()
    suite.addTest(unittest.makeSuite(TestCmds))
    runner = unittest.TextTestRunner(file)
    test = runner.run(suite)
    file.close()
    if _coverage:
        cov.stop()
        cov.save()
        cov.html_report()
        
    return test

def runctx(inDef):
    pr = cProfile.Profile()
    pr.enable()
    result = inDef()
    pr.disable()

    if not _canProfile:
        pr.print_stats()
        return result

    currentBaseFolder = os.path.dirname(__file__)

    baseLocation = os.path.normpath(os.path.join(currentBaseFolder, "qcachegrind"))
    inLocation = os.path.normpath(os.path.join(currentBaseFolder, "unitTest"))

    executable = os.path.normpath(os.path.join(baseLocation, "qcachegrind.exe"))
    callGrindProf = os.path.normpath(os.path.join(inLocation, 'callgrind.profile'))
    binaryData = os.path.normpath(os.path.join(inLocation, 'profiledRigSystem.profile'))

    for path in [callGrindProf, binaryData]:
        dirpath = os.path.dirname(path)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)

    pr.dump_stats(binaryData)

    pyprof2calltree.convert(pstats.Stats(binaryData), callGrindProf)
    pyprof2calltree.visualize(pstats.Stats(binaryData))
    subprocess.Popen([executable, callGrindProf])
    return result

    

if __name__ == '__main__':
    testObject = runctx(testctx)
    print(" ============================ ")
    print(testObject)
    print("Test was succesfull : {}".format(testObject.wasSuccessful()))
    print(" ============================ ")
    sys.exit()
