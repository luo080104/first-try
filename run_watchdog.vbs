' GuanFu watchdog (independent - every 30min)
Set ws = CreateObject("Wscript.Shell")
ws.CurrentDirectory = "C:\Users\luoji\shopping-agent"
ws.Environment("Process")("PYTHONIOENCODING") = "utf-8"
ws.Run "cmd /c ""C:\Users\luoji\AppData\Local\Programs\Python\Python314\python.exe -m tools.strategy_engine.watchdog >> data\watchdog.log 2>&1""", 0, False
