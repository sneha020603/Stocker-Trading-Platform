from flask import Flask, render_template, request, redirect, session
import mysql.connector
import uuid
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import yfinance as yf
from flask_mail import Mail, Message
import random
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import time
app = Flask(__name__)
app.secret_key = "stocker_secret"
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'stocker2815@gmail.com'
app.config['MAIL_PASSWORD'] = 'pfxdrdxdvrymiagw'

mail = Mail(app)
# -----------------------------
# MYSQL CONFIG
# -----------------------------

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="stocker_db"
)

cursor = db.cursor(dictionary=True, buffered=True)
def generate_otp():
    return str(random.randint(100000,999999))
# -----------------------------
# STOCK PRICE FUNCTION
# -----------------------------
def send_otp(email, otp):

    msg = Message(
        subject="Stocker OTP Verification",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )

    msg.body = f"""
Hello,

Your OTP for Stocker login/signup is:

{otp}

This OTP will expire in 5 minutes.

Regards,
Stocker Trading Platform
"""

    mail.send(msg)
def stock_monitor():

    while True:

        try:

            db = mysql.connector.connect(
                host="localhost",
                user="root",
                password="ROOT",
                database="stocker_db"
            )

            cursor = db.cursor(dictionary=True)

            stocks = get_all_stocks()

            for stock in stocks:

                symbol = stock["symbol"]

                price = get_live_price(symbol)

                if price == "N/A":
                    continue

                cursor.execute("""
                INSERT INTO stock_price_history(symbol,price,recorded_at)
                VALUES(%s,%s,%s)
                """,(symbol,price,datetime.now()))

            db.commit()

            cursor.close()
            db.close()

        except Exception as e:

            print("Stock monitor error:", e)

        # wait 10 minutes
        time.sleep(600)
def detect_drop():

    try:

        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="ROOT",
            database="stocker_db"
        )

        cursor = db.cursor(dictionary=True)

        stocks = get_all_stocks()

        for stock in stocks:

            symbol = stock["symbol"]

            cursor.execute("""
            SELECT price
            FROM stock_price_history
            WHERE symbol=%s
            AND recorded_at >= NOW() - INTERVAL 3 HOUR
            ORDER BY recorded_at ASC
            """,(symbol,))

            data = cursor.fetchall()

            if len(data) < 5:
                continue

            prices = [row["price"] for row in data]

            dropping = True

            for i in range(1,len(prices)):

                if prices[i] >= prices[i-1]:

                    dropping = False
                    break

            if dropping:

                send_sell_alert(symbol, prices[-1])

        cursor.close()
        db.close()

    except Exception as e:

        print("Drop detection error:", e)
def save_stock_prices():

    stocks = get_all_stocks()

    for stock in stocks:

        symbol = stock["symbol"]

        price = get_live_price(symbol)

        if price == "N/A":
            continue

        cursor.execute("""
        INSERT INTO stock_price_history(symbol,price,recorded_at)
        VALUES(%s,%s,%s)
        """,(symbol,price,datetime.now()))

    db.commit()
def detect_price_drop():

    stocks = get_all_stocks()

    for stock in stocks:

        symbol = stock["symbol"]

        cursor.execute("""
        SELECT price
        FROM stock_price_history
        WHERE symbol=%s
        AND recorded_at >= NOW() - INTERVAL 3 HOUR
        ORDER BY recorded_at ASC
        """,(symbol,))

        data = cursor.fetchall()

        if len(data) < 5:
            continue

        prices = [row["price"] for row in data]

        # check continuous drop
        dropping = True

        for i in range(1,len(prices)):
            if prices[i] >= prices[i-1]:
                dropping = False
                break

        if dropping:

            send_sell_alert(symbol, prices[-1])
def send_sell_alert(symbol, price):

    cursor.execute("SELECT email FROM users WHERE role='trader'")
    users = cursor.fetchall()

    for user in users:

        msg = Message(
            subject="Stocker Risk Alert",
            sender=app.config['MAIL_USERNAME'],
            recipients=[user["email"]]
        )

        msg.body = f"""
⚠ Stock Price Alert

Stock: {symbol}
Current Price: ${price}

Our monitoring system has detected that this stock price
has been continuously declining for more than 3 hours.

To prevent further losses, you may consider reviewing
your portfolio and selling the stock if necessary.

Please log in to your Stocker dashboard to take action.

This is an automated alert from the Stocker Risk Monitoring System.

Regards,
Stocker Market Monitoring Team
Stocker Trading Platform
"""

        mail.send(msg)
def get_live_price(symbol):

    try:

        ticker = yf.Ticker(symbol)

        data = ticker.history(period="2d")

        if data.empty or len(data) < 2:
            return 0.0, 0.0, 0.0

        current_price = float(data["Close"].iloc[-1])
        previous_close = float(data["Close"].iloc[-2])

        change = current_price - previous_close

        if previous_close == 0:
            percent = 0.0
        else:
            percent = (change / previous_close) * 100

        return (
            round(current_price, 2),
            round(change, 2),
            round(percent, 2)
        )

    except Exception as e:

        print("Stock price error:", e)

        return (0.0, 0.0, 0.0)

# -----------------------------
# DATABASE FUNCTIONS
# -----------------------------

def get_all_stocks():
    cursor.execute("SELECT * FROM stocks")
    return cursor.fetchall()

def get_stock_by_id(stock_id):
    cursor.execute("SELECT * FROM stocks WHERE id=%s",(stock_id,))
    return cursor.fetchone()

def get_user_by_email(email):
    cursor.execute("SELECT * FROM users WHERE email=%s",(email,))
    return cursor.fetchone()

def get_traders():
    cursor.execute("SELECT * FROM users WHERE role='trader'")
    return cursor.fetchall()

def delete_user_by_email(email):
    cursor.execute("DELETE FROM users WHERE email=%s",(email,))
    db.commit()

def create_transaction(user_id, stock_id, action, quantity, price):

    transaction_id = str(uuid.uuid4())

    cursor.execute("""
    INSERT INTO transactions
    (id,user_id,stock_id,action,quantity,price,transaction_date)
    VALUES (%s,%s,%s,%s,%s,%s,%s)
    """,(transaction_id,user_id,stock_id,action,quantity,price,datetime.now()))

    db.commit()

def get_transactions():
    cursor.execute("SELECT * FROM transactions")
    return cursor.fetchall()

def get_user_transactions(user_id):
    cursor.execute("SELECT * FROM transactions WHERE user_id=%s",(user_id,))
    return cursor.fetchall()

def update_portfolio(user_id, stock_id, quantity):

    cursor.execute(
        "SELECT * FROM portfolio WHERE user_id=%s AND stock_id=%s",
        (user_id,stock_id)
    )

    result = cursor.fetchone()

    if result:

        new_quantity = result["quantity"] + quantity

        cursor.execute(
        "UPDATE portfolio SET quantity=%s WHERE user_id=%s AND stock_id=%s",
        (new_quantity,user_id,stock_id)
        )

    else:

        cursor.execute(
        "INSERT INTO portfolio(user_id,stock_id,quantity) VALUES(%s,%s,%s)",
        (user_id,stock_id,quantity)
        )

    db.commit()

def get_user_portfolio(user_id):
    cursor.execute("SELECT * FROM portfolio WHERE user_id=%s",(user_id,))
    return cursor.fetchall()

# -----------------------------
# HOME
# -----------------------------

@app.route("/")
def index():
    return render_template("index.html")

# -----------------------------
# SIGNUP
# -----------------------------
@app.route("/signup", methods=["GET","POST"])
def signup():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        photo = request.files["photo"]

        filename = secure_filename(photo.filename)
        photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        # check if email already exists
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user:
            return "Email already registered"

        # generate OTP
        otp = str(random.randint(100000,999999))

        # store signup data in session
        session["signup_data"] = {
            "username": username,
            "email": email,
            "password": password,
            "role": role,
            "photo": filename
        }

        session["signup_otp"] = otp

        # send OTP email
        msg = Message(
            subject="Stocker OTP Verification",
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )

        msg.body = f"""
Welcome to Stocker Trading Platform!

Thank you for creating your account.

Your One-Time Password (OTP) for account verification is:

OTP: {otp}

This OTP is valid for the next 5 minutes.

Please do not share this OTP with anyone for security reasons.

If you did not request this signup, you can safely ignore this email.

Regards,
Stocker Security Team
Stocker Trading Platform
"""

        mail.send(msg)

        return redirect("/verify_signup")

    return render_template("signup.html")
@app.route("/verify_signup", methods=["GET","POST"])
def verify_signup():

    if request.method == "POST":

        user_otp = request.form["otp"]

        if user_otp == session.get("signup_otp"):

            data = session.get("signup_data")

            cursor.execute(
            "INSERT INTO users(id,username,email,password,role,photo,wallet) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                str(uuid.uuid4()),
                data["username"],
                data["email"],
                data["password"],
                data["role"],
                data["photo"],
                10000
            ))

            db.commit()

            session.pop("signup_otp")
            session.pop("signup_data")

            return redirect("/login")

        else:
            return "Invalid OTP"

    return render_template("verify_otp.html")
# -----------------------------
# LOGIN
# -----------------------------

@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = get_user_by_email(email)

        if user and user["password"] == password:

            # generate OTP
            otp = str(random.randint(100000,999999))

            session["login_otp"] = otp
            session["login_user"] = user

            # send email
            msg = Message(
                subject="Stocker Login OTP",
                sender=app.config['MAIL_USERNAME'],
                recipients=[email]
            )

            msg.body = f"""
Stocker Login Verification

A login attempt was detected for your Stocker account.

Your One-Time Password (OTP) is:

OTP: {otp}

Enter this OTP to complete your login.

This OTP will expire in 5 minutes.

If you did not attempt to login, please secure your account immediately.

Regards,
Stocker Security Team
Stocker Trading Platform
"""

            mail.send(msg)

            return redirect("/verify_login")

        return "Invalid credentials"

    return render_template("login.html")
@app.route("/verify_login", methods=["GET","POST"])
def verify_login():

    if request.method == "POST":

        user_otp = request.form["otp"]

        if user_otp == session.get("login_otp"):

            user = session.get("login_user")

            session["email"] = user["email"]
            session["role"] = user["role"]
            session["user_id"] = user["id"]
            session["photo"] = user["photo"]

            # clear OTP session
            session.pop("login_otp")
            session.pop("login_user")

            if user["role"] == "admin":
                return redirect("/dashboard_admin")
            else:
                return redirect("/dashboard_trader")

        return "Invalid OTP"

    return render_template("verify_login.html")
# -----------------------------
# ADMIN DASHBOARD
# -----------------------------

@app.route("/dashboard_admin")
def dashboard_admin():

    if session.get("role") != "admin":
        return redirect("/login")

    return render_template("dashboard_admin.html")

# -----------------------------
# TRADER DASHBOARD
# -----------------------------

@app.route("/dashboard_trader")
def dashboard_trader():

    if session.get("role") != "trader":
        return redirect("/login")

    stocks = get_all_stocks()

    for stock in stocks:

        price, change, percent = get_live_price(stock["symbol"])

        stock["live_price"] = price
        stock["change"] = change
        stock["percent"] = percent

    user_id = session["user_id"]

    cursor.execute("SELECT wallet FROM users WHERE id=%s",(user_id,))
    wallet = cursor.fetchone()["wallet"]

    return render_template("dashboard_trader.html",stocks=stocks,wallet=wallet)

# -----------------------------
# WALLET
# -----------------------------

@app.route("/wallet", methods=["GET","POST"])
def wallet():

    if session.get("role") != "trader":
        return redirect("/login")

    user_id = session["user_id"]

    cursor.execute("SELECT wallet FROM users WHERE id=%s",(user_id,))
    wallet = cursor.fetchone()["wallet"]

    if request.method == "POST":

        amount = float(request.form["amount"])

        new_balance = wallet + amount

        cursor.execute(
        "UPDATE users SET wallet=%s WHERE id=%s",
        (new_balance,user_id)
        )

        db.commit()

        return redirect("/wallet")

    return render_template("wallet.html",wallet=wallet)

# -----------------------------
# HELP / FAQ / SUPPORT / ABOUT
# -----------------------------

@app.route("/help")
def help_page():
    return render_template("help.html")

@app.route("/faq")
def faq_page():
    return render_template("faq.html")

@app.route("/support")
def support_page():
    return render_template("support.html")

@app.route("/about")
def about():
    return render_template("about.html")

# -----------------------------
# UPDATE PROFILE PHOTO
# -----------------------------

@app.route("/update_photo", methods=["GET","POST"])
def update_photo():

    if request.method == "POST":

        photo = request.files["photo"]

        filename = secure_filename(photo.filename)

        photo.save(os.path.join(app.config["UPLOAD_FOLDER"],filename))

        email = session["email"]

        cursor.execute(
        "UPDATE users SET photo=%s WHERE email=%s",
        (filename,email)
        )

        db.commit()

        session["photo"] = filename

        return redirect("/dashboard_trader")

    return render_template("update_photo.html")

# -----------------------------
# DELETE ACCOUNT
# -----------------------------

@app.route("/delete_account")
def delete_account():

    email = session.get("email")

    cursor.execute("DELETE FROM users WHERE email=%s",(email,))
    db.commit()

    session.clear()

    return redirect("/")

# -----------------------------
# STOCK CHART API
# -----------------------------

@app.route("/stock_chart/<symbol>")
def stock_chart(symbol):

    try:

        stock = yf.Ticker(symbol)

        data = stock.history(period="1d", interval="5m")

        labels = []
        prices = []

        for index, row in data.iterrows():

            labels.append(index.strftime("%H:%M"))
            prices.append(round(float(row["Close"]),2))

        return {
            "labels": labels[-10:],
            "prices": prices[-10:]
        }

    except:

        return {
            "labels":["1","2","3","4","5"],
            "prices":[10,12,9,14,11]
        }
@app.route("/buy/<stock_id>", methods=["GET","POST"])
def buy_stock(stock_id):

    if session.get("role") != "trader":
        return redirect("/login")

    stock = get_stock_by_id(stock_id)
    user_id = session["user_id"]

    if request.method == "POST":

        quantity = int(request.form["quantity"])

        if quantity <= 0:
            return "Invalid quantity"

        price = stock["price"]
        total_cost = price * quantity

        # get wallet balance
        cursor.execute(
        "SELECT wallet FROM users WHERE id=%s",
        (user_id,)
        )

        wallet = cursor.fetchone()["wallet"]

        # check wallet balance
        if wallet < total_cost:
            return "Insufficient wallet balance"

        # deduct wallet money
        new_balance = wallet - total_cost

        cursor.execute(
        "UPDATE users SET wallet=%s WHERE id=%s",
        (new_balance,user_id)
        )

        # create transaction
        create_transaction(
            user_id,
            stock_id,
            "BUY",
            quantity,
            price
        )

        # update portfolio
        update_portfolio(user_id,stock_id,quantity)

        db.commit()

        return redirect("/service05")

    return render_template("buy_stock.html",stock=stock)
@app.route("/sell/<stock_id>", methods=["GET","POST"])
def sell_stock(stock_id):

    if session.get("role") != "trader":
        return redirect("/login")

    stock = get_stock_by_id(stock_id)
    user_id = session["user_id"]

    if request.method == "POST":

        quantity = int(request.form["quantity"])

        if quantity <= 0:
            return "Invalid quantity"

        # check portfolio
        cursor.execute(
        "SELECT * FROM portfolio WHERE user_id=%s AND stock_id=%s",
        (user_id,stock_id)
        )

        portfolio = cursor.fetchone()

        if not portfolio or portfolio["quantity"] < quantity:
            return "Not enough stock to sell"

        new_quantity = portfolio["quantity"] - quantity

        if new_quantity == 0:

            cursor.execute(
            "DELETE FROM portfolio WHERE user_id=%s AND stock_id=%s",
            (user_id,stock_id)
            )

        else:

            cursor.execute(
            "UPDATE portfolio SET quantity=%s WHERE user_id=%s AND stock_id=%s",
            (new_quantity,user_id,stock_id)
            )

        price = stock["price"]
        total_gain = price * quantity

        # add money to wallet
        cursor.execute(
        "SELECT wallet FROM users WHERE id=%s",
        (user_id,)
        )

        wallet = cursor.fetchone()["wallet"]

        new_balance = wallet + total_gain

        cursor.execute(
        "UPDATE users SET wallet=%s WHERE id=%s",
        (new_balance,user_id)
        )

        # create transaction
        create_transaction(
            user_id,
            stock_id,
            "SELL",
            quantity,
            price
        )

        db.commit()

        return redirect("/service05")

    return render_template("sell_stock.html",stock=stock)
@app.route("/service05")
def service05():

    if session.get("role") != "trader":
        return redirect("/login")

    user_id = session["user_id"]

    portfolio = get_user_portfolio(user_id)
    transactions = get_user_transactions(user_id)

    total_pnl = 0

    for item in portfolio:

        stock = get_stock_by_id(item["stock_id"])

        symbol = stock["symbol"]
        buy_price = stock["price"]
        quantity = item["quantity"]

        current_price, change, percent = get_live_price(symbol)

        if current_price == "N/A":

            item["profit_loss"] = "N/A"
            item["current_price"] = "N/A"

        else:

            pnl = (current_price - buy_price) * quantity

            item["profit_loss"] = round(pnl,2)
            item["current_price"] = current_price

            total_pnl += pnl

        item["symbol"] = symbol
        item["buy_price"] = buy_price

    return render_template(
        "service-details-5.html",
        portfolio=portfolio,
        transactions=transactions,
        total_pnl=round(total_pnl,2)
    )
@app.route("/service01")
def service01():

    if session.get("role") != "admin":
        return redirect("/login")

    traders = get_traders()

    return render_template(
        "service-details-1.html",
        traders=traders
    )
@app.route("/delete_trader/<email>", methods=["POST"])
def delete_trader(email):

    if session.get("role") != "admin":
        return redirect("/login")

    delete_user_by_email(email)

    return redirect("/service01")
@app.route("/service02")
def service02():

    if session.get("role") != "admin":
        return redirect("/login")

    transactions = get_transactions()

    return render_template(
        "service-details-2.html",
        transactions=transactions
    )
@app.route("/service03")
def service03():

    # Total trades
    cursor.execute("SELECT COUNT(*) AS total FROM transactions")
    total_transactions = cursor.fetchone()["total"]

    # Buy vs Sell
    cursor.execute("SELECT COUNT(*) AS buy_count FROM transactions WHERE action='BUY'")
    buy_count = cursor.fetchone()["buy_count"]

    cursor.execute("SELECT COUNT(*) AS sell_count FROM transactions WHERE action='SELL'")
    sell_count = cursor.fetchone()["sell_count"]

    # Trades per stock
    cursor.execute("""
        SELECT s.symbol, COUNT(t.id) AS total
        FROM transactions t
        JOIN stocks s ON t.stock_id = s.id
        GROUP BY s.symbol
    """)
    stock_stats = cursor.fetchall()

    stock_labels = [row["symbol"] for row in stock_stats]
    stock_values = [row["total"] for row in stock_stats]

    # Daily trades
    cursor.execute("""
        SELECT DATE(transaction_date) AS day, COUNT(*) AS total
        FROM transactions
        GROUP BY DATE(transaction_date)
    """)
    daily_stats = cursor.fetchall()

    day_labels = [str(row["day"]) for row in daily_stats]
    day_values = [row["total"] for row in daily_stats]

    # Top traders leaderboard
    cursor.execute("""
        SELECT u.username, COUNT(t.id) AS trades
        FROM transactions t
        JOIN users u ON t.user_id = u.id
        GROUP BY u.username
        ORDER BY trades DESC
        LIMIT 5
    """)
    trader_stats = cursor.fetchall()

    trader_labels = [row["username"] for row in trader_stats]
    trader_values = [row["trades"] for row in trader_stats]

    # Most traded stock
    cursor.execute("""
        SELECT s.symbol, COUNT(t.id) AS trades
        FROM transactions t
        JOIN stocks s ON t.stock_id = s.id
        GROUP BY s.symbol
        ORDER BY trades DESC
        LIMIT 5
    """)
    top_stocks = cursor.fetchall()

    top_stock_labels = [row["symbol"] for row in top_stocks]
    top_stock_values = [row["trades"] for row in top_stocks]

    return render_template(
        "service-details-3.html",
        total_transactions=total_transactions,
        buy_count=buy_count,
        sell_count=sell_count,
        stock_labels=stock_labels,
        stock_values=stock_values,
        day_labels=day_labels,
        day_values=day_values,
        trader_labels=trader_labels,
        trader_values=trader_values,
        top_stock_labels=top_stock_labels,
        top_stock_values=top_stock_values
    )


@app.route("/manage_stocks")
def manage_stocks():

    if session.get("role") != "admin":
        return redirect("/login")

    stocks = get_all_stocks()

    return render_template(
        "manage_stocks.html",
        stocks=stocks
    )
@app.route("/add_stock", methods=["GET","POST"])
def add_stock():

    if session.get("role") != "admin":
        return redirect("/login")

    if request.method == "POST":

        symbol = request.form["symbol"]
        price = request.form["price"]

        cursor.execute(
        "INSERT INTO stocks(symbol,price) VALUES(%s,%s)",
        (symbol,price)
        )

        db.commit()

        return redirect("/manage_stocks")

    return render_template("add_stock.html")
@app.route("/delete_stock/<stock_id>", methods=["POST"])
def delete_stock(stock_id):

    if session.get("role") != "admin":
        return redirect("/login")

    cursor.execute(
        "DELETE FROM transactions WHERE stock_id=%s",
        (stock_id,)
    )

    cursor.execute(
        "DELETE FROM stocks WHERE id=%s",
        (stock_id,)
    )

    db.commit()

    return redirect("/manage_stocks")
# -----------------------------
# LOGOUT
# -----------------------------

@app.route("/logout")
def logout():

    session.clear()
    return redirect("/")
# -----------------------------
# BACKGROUND STOCK MONITOR
# -----------------------------

# -----------------------------
# RUN APP
# -----------------------------
# -----------------------------
# START BACKGROUND MONITOR
# -----------------------------

def start_background_monitor():

    monitor_thread = threading.Thread(target=stock_monitor)

    monitor_thread.daemon = True

    monitor_thread.start()
if __name__ == "__main__":
    start_background_monitor()
    app.run(debug=True)