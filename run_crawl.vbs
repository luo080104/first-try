Set ws = CreateObject("Wscript.Shell")
ws.CurrentDirectory = "C:\Users\luoji\shopping-agent"
ws.Run "python -u src\crawl.py > data\crawl.log 2>&1", 0, False
