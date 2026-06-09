# REVIEW: [line-endings] 这个文件用的是 CRLF (\r\n) 换行。
# 整个项目的换行风格非常混乱：
#   - 大部分 src/ 下的文件用 CRLF (Windows 风格)
#   - tests/ 下的文件用 LF (Unix 风格)
#   - __main__.py, config.py, commands.py 甚至是 CRLF+LF 混用！
#   - 新加的几个文件 (runtime_state.py, state.py, weather_schedule.py) 用 LF
# 这说明: 早期代码在 Windows 上写的 (README 里的 PowerShell 路径也证实了)，
# 后来部分文件被 AI 或其他工具重新生成时用了 LF，没人注意到不一致。
# 修复: 1) 全量转成 LF  2) 加 .gitattributes: `* text=auto eol=lf`
#       3) CI 加 `git diff --check` 防止 CRLF 再混入
"""Telegram agent bot package."""
