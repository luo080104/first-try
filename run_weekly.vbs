' GuanFu weekly report push (v1.2 - Friday 15:30 after close, with equity chart)
Set ws = CreateObject("Wscript.Shell")
ws.CurrentDirectory = "C:\Users\luoji\shopping-agent"
ws.Environment("Process")("PYTHONIOENCODING") = "utf-8"
ws.Run "cmd /c ""C:\Users\luoji\AppData\Local\Programs\Python\Python314\python.exe -m tools.strategy_engine.weekly_report --push >> data\weekly.log 2>&1""", 0, False
