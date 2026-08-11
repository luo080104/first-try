Set ws = CreateObject("Wscript.Shell")
ws.CurrentDirectory = "C:\Users\luoji\shopping-agent"
ws.Environment("Process")("PYTHONIOENCODING") = "utf-8"
' 2026-08-11 pythonw 完整路径：无控制台窗口 + UTF-8 编码
ws.Run """C:\Users\luoji\AppData\Local\Programs\Python\Python314\pythonw.exe"" -u src\app.py > data\server.log 2>&1", 0, False
