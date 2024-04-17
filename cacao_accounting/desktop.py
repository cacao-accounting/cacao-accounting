from cacao_accounting.server import app
from flaskwebgui import FlaskUI  # import FlaskUI


def serve_desktop():
    # If you are debugging you can do that in the browser:
    # app.run()
    # If you want to view the flaskwebgui window:
    FlaskUI(app=app, server="flask", port=5000).run()


if __name__ == "__main__":
    serve_desktop()
