# cmd wrapper

A simple & light-wight wrapper for maya cmds and OpenMaya (api2.0) functionality


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

Attributes can be used as python attributes directly and will return wrapped math functions:

```python
from cmdWrapper import createNode
node = createNode("transform")
#matrix function
mat = node.worldMatrix[0]() # alternatively use: node.worldMatrix[0].get()
# vector function
pos = node.translate() # alternatively use: node.translate.get()
node.translate = pos # alternatively use: node.translate.set(pos)
```

connection works as follows: 

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
from maya import cmds

loc = cmds.spaceLocator()[0]
sphere = cmds.polySphere()[0]
cmds.connectAttr("{0}.translate".format(loc), "{0}.translate".format(sphere))
trsValue = cmds.getAttr("{0}.translate".format(loc))
```

This becomes:
```python
from cmdWrapper import cmds

loc = cmds.spaceLocator()[0]
sphere = cmds.polySphere()[0]
loc.translate.connect(sphere.translate)
trsValue = loc.translate()
```
