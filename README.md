# cmd wrapper

simple wrapper for maya cmds and OpenMaya (api2.0) functionality


## Authors

* [Trevor van Hoof](http://trevorius.com/scrapbook/)
* [Perry Leijten](https://www.perryleijten.com/)


## Prerequisites

```
 - Maya 2017+
 - Python 2.7 (3.7)
```

## launch

place cmdWrapper folder with the '__init__.py' in the mydocuments/maya/scripts folder
```python
import cmdWrapper
```

the following functions are for creating a new wrapped transform node node:

```python
import cmdWrapper
trs = cmdWrapper.createNode("transform")
```

or to get the node out of a current scene:
(returns the selected items, or name / list of strings can be given to return as wrapped nodes)

```python
import cmdWrapper
nodes = cmdWrapper.getNode()
```
attributes can be used as python attributes directly and will return wrapped math functions

```python
from cmdWrapper import createNode
node = createNode("transform")
#matrix function
mat = node.worldMatrix[0].get()
# vector function
pos = node.translate.get()
pos.normal() # example vector operation
node.translate.set(pos)
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

# instead of maya.cmds
```python
from maya import cmds

loc = cmds.spaceLocator()[0]
sphere = cmds.polySphere()[0]
cmds.connectAttr("{0}.translate".format(loc), "{0}.translate".format(sphere))
trsValue = cmds.getAttr("{0}.translate".format(loc))
```
now becomes:
```python
from cmdWrapper import cmds

loc = cmds.spaceLocator()[0]
sphere = cmds.polySphere()[0]
loc.translate.connect(sphere.translate)
trsValue = loc.translate.get()
```
