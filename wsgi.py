from cacao_accounting import create_app, DEVELOPMENT
from cacao_accounting.conf import config

app = create_app(config)
if DEVELOPMENT:
    app.config["EXPLAIN_TEMPLATE_LOADING"] = True
    app.config["DEBUG"] = True
    app.config["SECRET_KEY "] = "dev"

if __name__ == "__main__":
    app.run()
