' GuanFu morning brief push (v1.1 - daily 9:00)
Set ws = CreateObject("Wscript.Shell")
ws.CurrentDirectory = "C:\Users\luoji\shopping-agent"
ws.Environment("Process")("PYTHONIOENCODING") = "utf-8"
ws.Run "cmd /c ""C:\Users\luoji\AppData\Local\Programs\Python\Python314\python.exe -m tools.strategy_engine.notify_gf >> data\brief.log 2>&1""", 0, False
