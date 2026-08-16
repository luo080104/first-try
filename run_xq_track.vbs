Set ws = CreateObject("Wscript.Shell")
ws.CurrentDirectory = "C:\Users\luoji\shopping-agent"
ws.Run "cmd /c set PYTHONIOENCODING=utf-8 && python -m tools.strategy_engine.xq_track track >> data\xq_track.log 2>&1", 0, False
