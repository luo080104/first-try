Set ws = CreateObject("Wscript.Shell")
ws.CurrentDirectory = "C:\Users\luoji\shopping-agent"
ws.Environment("Process")("PYTHONIOENCODING") = "utf-8"
' 2026-08-13 headroom token 节省：LLM 走本地 proxy（8787）——2026-08-14 kompress 压缩模型已下完，proxy 压缩模式运行（实测输入省 25%）
ws.Environment("Process")("LLM_API_URL") = "http://127.0.0.1:8787/v1/chat/completions"
' 2026-08-11 pythonw 完整路径：无控制台窗口 + UTF-8 编码
ws.Run """C:\Users\luoji\AppData\Local\Programs\Python\Python314\pythonw.exe"" -u src\app.py > data\server.log 2>&1", 0, False
