Set ws = CreateObject("Wscript.Shell")
ws.CurrentDirectory = "C:\Users\luoji\shopping-agent"
ws.Run "python src\login_tb.py > data\login_tb.log 2>&1", 0, False
