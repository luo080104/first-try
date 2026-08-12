Set ws = CreateObject("Wscript.Shell")
ws.CurrentDirectory = "C:\Users\luoji\shopping-agent"
ws.Run "python src\fill_shop_founded.py 500 > data\fill_shop.log 2>&1", 0, False
