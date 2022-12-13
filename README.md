# cmd wrapper

A simple & light-wight wrapper for maya cmds and OpenMaya (api2.0) functionality
Find the latest version at https://github.com/peerke88/cmdWrapper

## Authors

* [Trevor van Hoof](http://trevorius.com/scrapbook/)
* [Perry Leijten](https://www.perryleijten.com/)


## Prerequisites

```
 - Maya 2017+
 - Python 2.7 (3.7)
```

## Todo:

- convert attribute values to correct OpenMaya type


## launch

Place the cmdWrapper folder with the ```'__init__.py'``` in the Documents/maya/scripts folder to install it for all Maya versions.
(On Windows you can go copy %USERPROFILE%/Documents/maya/scripts into the explorer address bar to get there) 

```python
from cmdWrapper import cmds
```

Create a new (wrapped) transform node node:

```python
from cmdWrapper import cmds
transform = cmds.createNode("transform")
```

Get the selection from the current scene (as wrapped nodes):

```python
from cmdWrapper import cmds, getNode
nodes = getNode()
```

Specify which node name(s) you would like to wrap (can give it 1 node name or a list of strings):

```python
from cmdWrapper import cmds, getNode
nodes = getNode('persp')
```

Attributes can be used as python attributes directly:

```python
from cmdWrapper import createNode
node = createNode("transform")
mat = node.worldMatrix[0]() # alternatively use: node.worldMatrix[0].get()
# vector function
pos = node.translate() # alternatively use: node.translate.get()
node.translate = pos # alternatively use: node.translate.set(pos)
```

Or as math-wrapped attributes:
```python
from cmdWrapper import createNode
node = createNode("transform")
pos = node.getT() # returns an MVector
pos.normalize()
node.translate.setT(pos) # must set MVector explicitly (we are aware that this has room for improvement)
```

Connecting works as follows: 

```python
from cmdWrapper import cmds, getNode
# maya commands can be accessed from here as well
sphere = getNode(cmds.polySphere()[0])
loc = getNode(cmds.spaceLocator()[0])
loc.translate.connect(sphere.translate)
```

---

# Use cmdsWrapper.cmds instead of maya.cmds
```python
from maya import cmds, OpenMaya

loc = cmds.spaceLocator()[0]
sphere = cmds.polySphere()[0]
cmds.connectAttr("{0}.translate".format(loc), "{0}.translate".format(sphere))
trsValue = cmds.getAttr("{0}.translate".format(loc))

loc1 = cmds.spaceLocator()[0]
cmds.setAttr("{0}.translate".format(loc1), 1.303, 2.231, -2.647, type="double3")
loc2 = cmds.spaceLocator()[0]
cmds.setAttr("{0}.translate".format(loc2), -1.56, 2.603, .556, type="double3")
vecA = OpenMaya.MVector(*cmds.xform(loc1, q=1, ws=1, t=1))
vecB = OpenMaya.MVector(*cmds.xform(loc2, q=1, ws=1, t=1))
vecA = vecA.normal() 
vecB.normalize() 
vecC = vecA ^ vecB  
loc = cmds.spaceLocator()[0] 
cmds.setAttr("{0}.translateX".format(loc), vecC[0] )
cmds.xform(loc, ws=1, t=(vecC[0], vecC[1], vecC[2]))

vecE = vecA ^ vecC

nMat = [0] * 16
nMat[15] = 1
for i, vector in enumerate( [vecA, vecE, vecC, OpenMaya.MVector(*cmds.xform(loc1, q=1, ws=1, t=1))] ):
    for j in xrange( 3 ):
        nMat[(i*4) + j] =  vector[ j ]

cmds.xform(loc, ws=1, m=nMat)

```

This becomes:

```python
from cmdWrapper import cmds, getNode, Vector, Matrix

loc = cmds.spaceLocator()[0]
sphere = cmds.polySphere()[0]
loc.translate.connect(sphere.translate) #connection of attributes
trsValue = loc.translate()

loc1 = cmds.spaceLocator()[0]
loc1.translate = (1.303, 2.231, -2.647) #assign as variable
loc2 = cmds.spaceLocator()[0]
loc2.translate.set(-1.56, 2.603, .556) # set function on attribute
vecA = loc1.translate() # get attribute as function
vecB = loc2.translate.get() # get function on attribute
vecA = vecA.normal() # returned attribute is a tuple as well as an MVector
vecB.normalize() 
vecC = vecA ^ vecB # MVector cross
vecD = vecA.cross(vecB) # seperate function that does the same but more readable
loc = cmds.spaceLocator()[0] 
loc.translateX = vecC[0] 
loc.translate = vecC #assign vector directly to double3 attribute 

vecE = vecA ^ vecC
nMat = Matrix( vecA.normal()[:] + [0] + 
               vecE.normal()[:] + [0] + 
               vecC.normal()[:] + [0] + 
               loc1.translate.get()[:] + [1] ) #slice and assign data to matrix
loc.setM(nMat) #set newly created matrix 
```
