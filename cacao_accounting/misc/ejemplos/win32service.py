"""
Ejemplo para ejecutar Cacao Accounting como servicio en Windows.

Requiere pywin32:

  pip install pywin32

Referencias:
 - https://pythonpedia.com/en/tutorial/9065/creating-a-windows-service-using-python
 - https://stackoverflow.com/questions/55677165/python-flask-as-windows-service
 - https://exceptionshub.com/deploy-flask-app-as-windows-service.html
"""

from win32serviceutil import HandleCommandLine, ServiceFramework
import win32service
from multiprocessing import Process
from cacao_accounting import create_app

conf = None

if conf:
    app = create_app(conf)
else:
    from cacao_accounting.conf import configuracion

    app = create_app(configuracion)


class Service(ServiceFramework):
    import win32serviceutil
    import win32event
    import servicemanager

    _svc_name_ = "CacaoAccounting"
    _svc_display_name_ = "Cacao Accounting Service"
    _svc_description_ = "Cacao Accounting service"

    def __init__(self, *args):
        super().__init__(*args)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.process.terminate()
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self):
        self.process = Process(target=self.main)
        self.process.start()
        self.process.run()

    def main(self):
        app.run()


if __name__ == "__main__":
    HandleCommandLine(Service)
