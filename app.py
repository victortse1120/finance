import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, check_valid_input

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    portfolio = db.execute("SELECT symbol, SUM(shares) AS total_shares FROM history WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0", session["user_id"])
    total = 0
    for row in portfolio:
        result = lookup(row["symbol"])
        row["price"] = usd(result["price"])
        row["total"] = usd(row["total_shares"] * result["price"])
        total += row["total_shares"] * result["price"]

    cashRows = db.execute("SELECT cash FROM users WHERE id = ? ", session["user_id"])
    cash = cashRows[0]["cash"]
    total += cash
    return render_template("index.html", portfolio=portfolio, cash=usd(cash), total=usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)
        elif not request.form.get("shares"):
            return apology("must provide shares", 400)
        elif not check_valid_input(request.form.get("shares")):
            return apology("value of shares is invalid", 400)
        result = lookup(request.form.get("symbol"))
        if not result:
            return apology("fail to lookup", 400)

        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        buyAmount = result["price"]*float(request.form.get("shares"))

        if buyAmount > rows[0]["cash"]:
            return apology("no enough cash", 403)
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", buyAmount, session["user_id"])
        db.execute("INSERT INTO history (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)", session["user_id"], result["symbol"], request.form.get("shares"), result["price"])
        return redirect("/")
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    portfolio = db.execute("SELECT symbol, shares, price, created_at FROM history WHERE user_id = ? ", session["user_id"])

    for row in portfolio:
        row["price"] = usd(row["price"])

    return render_template("history.html", portfolio=portfolio)


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
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)
        result = lookup(request.form.get("symbol"))
        if not result:
            return apology("fail to lookup", 400)
        return render_template("quoted.html", name=result["name"], symbol=result["symbol"], price=usd(result["price"]))
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 400)
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("must reconfirm password", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password do not match", 400)

        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE username = ? ", username)
        if len(rows) > 0:
            return apology("duplicate username", 400)

        hash = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
        return redirect("/login")
    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)
        elif not request.form.get("shares"):
            return apology("must provide shares", 400)
        result = lookup(request.form.get("symbol"))
        if not result:
            return apology("fail to lookup", 400)

        portfolio = db.execute("SELECT SUM(shares) AS total_shares FROM history WHERE user_id = ? AND symbol = ? GROUP BY symbol HAVING total_shares > 0", session["user_id"], request.form.get("symbol"))
        if portfolio[0]["total_shares"] < int(request.form.get("shares")):
            return apology("too many shares", 400)

        sellAmount = result["price"]*float(request.form.get("shares"))

        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", sellAmount, session["user_id"])
        db.execute("INSERT INTO history (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)", session["user_id"], request.form.get("symbol"), -int(request.form.get("shares")), result["price"])
        return redirect("/")
    else:
        portfolio = db.execute("SELECT symbol, SUM(shares) AS total_shares FROM history WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0", session["user_id"])

        return render_template("sell.html", portfolio=portfolio)


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """add additional cash to account"""
    if request.method == "POST":
        if not request.form.get("deposit"):
            return apology("must provide deposit amount", 403)
        elif float(request.form.get("deposit")) <= 0:
            return apology("amount must be greater than 0", 403)
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", float(request.form.get("deposit")), session["user_id"])
        return redirect("/")
    else:
        return render_template("deposit.html")
