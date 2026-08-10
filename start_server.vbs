' 开机静默启动 Go购 服务（隐藏窗口）
Set ws = CreateObject("Wscript.Shell")
ws.CurrentDirectory = "C:\Users\luoji\shopping-agent"
ws.Run "python src\app.py > data\server.log 2>&1", 0, False
