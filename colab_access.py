import os
import time
import datetime
import webbrowser

# 30時間毎に任意のノートブックを開く
for i in range(24):
    browse = webbrowser.get(
        '"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" %s')
    browse.open(os.environ["COLAB_URL"])
    print(i, datetime.datetime.today())
    time.sleep(30*60)
