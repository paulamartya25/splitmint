import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Fix Jinja 'do' tag error
app.jinja_env.add_extension('jinja2.ext.do')

# -------- DATABASE CONFIG --------
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Use Supabase PostgreSQL on Vercel
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    # Use local SQLite for development
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "splitmint.db")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)  # ← THIS WAS MISSING


# -------- MODELS --------
class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    participants = db.relationship(
        "Participant", backref="group", cascade="all, delete-orphan"
    )
    expenses = db.relationship(
        "Expense", backref="group", cascade="all, delete-orphan"
    )


class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(20), default="#007bff")

    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)

    payer_id = db.Column(db.Integer, db.ForeignKey("participant.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)

    payer = db.relationship("Participant", foreign_keys=[payer_id])


# -------- CREATE DB --------
with app.app_context():
    db.create_all()


# -------- ROUTES --------
@app.route("/")
def index():
    groups = Group.query.all()
    return render_template("index.html", groups=groups)


@app.route("/add_group", methods=["POST"])
def add_group():
    group_name = request.form.get("group_name")

    if group_name:
        db.session.add(Group(name=group_name))
        db.session.commit()

    return redirect(url_for("index"))


@app.route("/group/<int:group_id>")
def group_detail(group_id):
    group = Group.query.get_or_404(group_id)
    search_query = request.args.get("search", "")

    expenses = group.expenses
    if search_query:
        expenses = [e for e in expenses if search_query.lower() in e.description.lower()]

    balances = {p.name: 0.0 for p in group.participants}

    total_spent = sum(e.amount for e in group.expenses)
    share = total_spent / len(group.participants) if group.participants else 0

    for e in group.expenses:
        balances[e.payer.name] += e.amount

    for name in balances:
        balances[name] -= share

    return render_template("group.html", group=group, balances=balances, expenses=expenses)


@app.route("/add_participant/<int:group_id>", methods=["POST"])
def add_participant(group_id):
    group = Group.query.get_or_404(group_id)

    if len(group.participants) < 4:
        new_p = Participant(
            name=request.form.get("name"),
            color=request.form.get("color"),
            group_id=group_id,
        )
        db.session.add(new_p)
        db.session.commit()

    return redirect(url_for("group_detail", group_id=group_id))


@app.route("/add_expense/<int:group_id>", methods=["POST"])
def add_expense(group_id):
    try:
        new_expense = Expense(
            description=request.form.get("description"),
            amount=float(request.form.get("amount")),
            payer_id=int(request.form.get("payer_id")),
            group_id=group_id,
        )

        db.session.add(new_expense)
        db.session.commit()

    except Exception as e:
        print("ERROR adding expense:", e)

    return redirect(url_for("group_detail", group_id=group_id))


# -------- LOCAL RUN --------
if __name__ == "__main__":
    app.run(debug=True)
