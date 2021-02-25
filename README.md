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

place cmdWrapper folder in the mydocuments/maya/scripts folder
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
import cmdWrapper
node = cmdWrapper.createNode("transform")
#matrix function
mat = node.worldMatrix[0].get()
# vector function
pos = node.translate.get()
pos.normal() # example vector operation
node.translate.set(pos)
```

connection works as follows: 

```python
import cmdWrapper
# maya commands can be accessed from here as well
sphere = cmdWrapper.getNode(cmdWrapper.cmds.polySphere()[0])
loc = cmdWrapper.getNode(cmdWrapper.cmds.spaceLocator()[0])
loc.translate.connect(sphere.translate)
```

