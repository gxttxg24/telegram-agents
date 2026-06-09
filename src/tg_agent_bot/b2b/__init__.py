# REVIEW: `from .x import *` 是反模式。导入了什么完全取决于 protocol.py 里有什么，
# 且 protocol.py 没有定义 __all__，所以所有公开名字都会被导入。
# 这意味着 protocol.py 加一个顶层变量就会污染 b2b 包的命名空间。
# 改成显式导入: from .protocol import B2BEnvelope, parse_envelope, ...
from .protocol import *
