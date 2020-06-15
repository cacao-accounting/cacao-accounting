import click
from flask import Flask, redirect, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


@app.cli.command("init-db")
def db_command():
    """Crea la base de datos."""
    db.drop_all()
    db.create_all()
    click.echo("Base de datos creada.")


@app.route("/")
def hello():
    return redirect("/login")


@app.route("/base")
def base():
    return render_template("base.html")


@app.route("/login")
def login():
    return render_template("auth/login.html")


@app.route("/setup")
def septup():
    return render_template("setup/setup.html")


@app.route("/legal")
def legal():
    return render_template("varios/legal.html")


@app.route("/notas")
def notas():
    return render_template("notas.html")


@app.route("/indice")
def indice():
    return render_template("indice.html")


@app.route("/principal")
def principal():
    return render_template("principal.html")


if __name__ == "__main__":
    app.run()
