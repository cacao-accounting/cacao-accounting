from flask import Flask, redirect, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:test.db'
db = SQLAlchemy(app)


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


if __name__ == "__main__":
    app.run()
