from PyQt5.QtWebEngineWidgets import QWebEngineView


class WebEngineView(QWebEngineView):
    def __init__(self):
        super(WebEngineView, self).__init__()

    def createWindow(self, QWebEnginePage_WebWindowType):
        return self