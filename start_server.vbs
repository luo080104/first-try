Set ws = CreateObject("Wscript.Shell")
ws.CurrentDirectory = "C:\Users\luoji\shopping-agent"
' 2026-08-11 pythonw 完整路径：无控制台窗口（彻底无任务栏图标）
ws.Run """C:\Users\luoji\AppData\Local\Programs\Python\Python314\pythonw.exe"" -u src\app.py > data\server.log 2>&1", 0, False
