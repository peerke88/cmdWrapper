import unittest, os, sys, logging, cProfile

_basePath = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if not _basePath in sys.path:
    sys.path.insert(0, _basePath)

import maya.standalone

root_logger = logging.getLogger()
root_logger.disabled = True
for x, y in logging.Logger.manager.loggerDict.items():
    try:
        y.setLevel(logging.CRITICAL)
    except Exception:
        pass

# disable the crash reporting window.
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
except Exception:
    _coverage = False

_canProfile = True
try:
    from cmdWrapper import pyprof2calltree
except:
    _canProfile = False

from cmdWrapper import cmds

cmds.loadPlugin('matrixNodes', qt=True)
cmds.loadPlugin('quatNodes', qt=True)

from cmdWrapper.unitTest.pyCharm_unitTest import TestCmds

# \~english testing context that will fire the unitTests but can be used in a cProfile argument


def testctx():
    log_file = 'log_file.txt'
    curDirect = os.path.dirname(__file__)
    file = open(os.path.join(curDirect, log_file), "w")
    suite = unittest.TestSuite()
    # result = unittest.TestResult()
    suite.addTest(unittest.makeSuite(TestCmds))
    runner = unittest.TextTestRunner(file)
    test = runner.run(suite)
    file.close()
    if _coverage:
        cov.stop()
        cov.save()
        cov.html_report()
    print(test)
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
