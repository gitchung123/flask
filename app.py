import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    cashrow = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    cashrow[0]["cash"] = usd(cashrow[0]["cash"])
    current = db.execute("SELECT * FROM current WHERE id = ?", session["user_id"])
    for row in current:
        row["total"] = usd(float(row["price"]) * float(row["shares"]))
        row["price"] = usd(float(row["price"]))
    return render_template("index.html", cashrow=cashrow, current=current)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        data = lookup(symbol)
        if data != None:
            shares = request.form.get("shares")
            if shares.isnumeric():
                if float(shares) > 0 and float(shares) == round(float(shares), 0):
                    name = data["name"]
                    price = data["price"]
                    total = float(price) * float(shares)
                    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
                    if cash[0]["cash"] - total >= 0:
                        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash[0]["cash"] - total, session["user_id"])
                        db.execute("INSERT INTO history (id, symbol, shares, name, price, total) VALUES(?, ?, ?, ?, ?, ?)",
                                   session["user_id"], symbol, shares, name, price, total)
                        existing = db.execute("SELECT shares FROM current WHERE symbol = ?", symbol)
                        if len(existing) == 1:
                            db.execute("UPDATE current SET shares = ? WHERE symbol = ?",
                                       int(shares) + existing[0]["shares"], symbol)
                        else:
                            db.execute("INSERT INTO current (id, symbol, shares, name, price, total) VALUES(?, ?, ?, ?, ?, ?)",
                                       session["user_id"], symbol, shares, name, price, total)
                        return redirect("/")
                    else:
                        return apology("Not enough cash", 400)
                else:
                    return apology("Invalid shares", 400)
            else:
                return apology("Invalid shares", 400)
        else:
            return apology("No symbol found", 400)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    data = db.execute("SELECT * FROM history WHERE ID = ?", session["user_id"])
    return render_template("history.html", data=data)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        result = lookup(request.form.get("symbol"))
        if result != None:
            result["price"] = usd(result["price"])
            return render_template("result.html", result=result)
        else:
            return apology("No symbol found", 400)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username").strip()
        names = db.execute("SELECT username FROM users")
        for name in names:
            if username == name["username"]:
                return apology("Invalid username", 400)
        if username != "":
            password = request.form.get("password")
            confirmation = request.form.get("confirmation")
            if password == confirmation and password != "":
                passhash = generate_password_hash(password)
                db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, passhash)
                return render_template("login.html")
            else:
                return apology("Password does not match", 400)
        else:
            return apology("Invalid username", 400)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        data = lookup(symbol)
        name = data["name"]
        shares = request.form.get("shares")
        price = data["price"]
        total = float(price) * float(shares)
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash[0]["cash"] + total, session["user_id"])
        db.execute("INSERT INTO history (id, symbol, shares, name, price, total) VALUES(?, ?, ?, ?, ?, ?)",
                   session["user_id"], symbol, '-' + shares, name, price, total)
        existing = db.execute("SELECT shares FROM current WHERE symbol = ?", symbol)
        if int(shares) < existing[0]["shares"]:
            db.execute("UPDATE current SET shares = ? WHERE symbol = ?", existing[0]["shares"] - int(shares), symbol)
        elif int(shares) == existing[0]["shares"]:
            db.execute("DELETE FROM current WHERE symbol = ?", symbol)
        else:
            return apology("Not enough shares", 400)
        return redirect("/")
    else:
        data = db.execute("SELECT symbol FROM current WHERE id = ?", session["user_id"])
        return render_template("sell.html", data=data)


@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    if request.method == "POST":
        oldhash = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])
        if check_password_hash(oldhash[0]["hash"], request.form.get("old")):
            password = request.form.get("password")
            confirmation = request.form.get("confirmation")
            if password == confirmation and password != "":
                passhash = generate_password_hash(password)
                db.execute("UPDATE users SET hash = ? WHERE id = ?", passhash, session["user_id"])
                return redirect("/")
            else:
                return apology("New password does not match", 400)
        else:
            return apology("Old password does not match", 400)
    else:
        return render_template("password.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
