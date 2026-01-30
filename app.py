# ==== app.py (FINAL with separate real & demo admins + demo lock) =============

from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "change_this_secret_key_later"

# ---------- DATABASE CONFIG ----------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "mini_erp.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

print("DB path:", DB_PATH)

db = SQLAlchemy(app)

# ---------- MODELS ----------

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emp_code = db.Column(db.String(32), unique=True, nullable=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(80), nullable=False)           # 'admin' / 'employee'
    status = db.Column(db.String(20), default="Active")       # Active / On Leave / Inactive

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    login_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    logout_time = db.Column(db.DateTime, nullable=True)

    employee = db.relationship("Employee", backref="attendances")


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default="Pending")
    due_date = db.Column(db.Date, nullable=True)

    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    employee = db.relationship("Employee", backref="tasks")


# ---------- HELPERS ----------

DEMO_USERNAMES = ["demo_admin", "rahul", "priya", "amit"]

def login_required(role=None):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("Access denied", "danger")
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper


def reset_demo_data_for_user(emp: Employee):
    """Demo users ke liye dashboard data har login par reset kare."""
    if emp.username not in DEMO_USERNAMES:
        return

    if emp.role == "employee":
        # demo employee ka pura data clean karke ek simple task de do
        Task.query.filter_by(employee_id=emp.id).delete()
        Attendance.query.filter_by(employee_id=emp.id).delete()

        demo_task = Task(
            title="Demo Task",
            status="Pending",
            due_date=None,
            employee_id=emp.id,
        )
        db.session.add(demo_task)

    db.session.commit()


def init_db():
    """
    - Tables create karega (drop_all nahi).
    - Agar admins / seed employees nahi hain tab hi create karega.
    - REAL admin password env var se aata hai (ADMIN_PASSWORD).
    """
    db.create_all()

    # -------- REAL ADMIN (production) --------
    real_admin = Employee.query.filter_by(username="admin").first()
    if not real_admin:
        real_password = os.environ.get("ADMIN_PASSWORD", "Admin@2026_REAL")

        real_admin = Employee(
            emp_code="ADM-REAL",
            username="admin",
            name="Real Admin",
            role="admin",
            status="Active",
            password_hash=""
        )
        real_admin.set_password(real_password)
        db.session.add(real_admin)

    # -------- DEMO ADMIN (testing) --------
    demo_admin = Employee.query.filter_by(username="demo_admin").first()
    if not demo_admin:
        demo_admin = Employee(
            emp_code="ADM-DEMO",
            username="demo_admin",
            name="Demo Admin",
            role="admin",
            status="Active",
            password_hash=""
        )
        demo_admin.set_password("admin_demo_123")
        db.session.add(demo_admin)

    # -------- DEMO EMPLOYEES (sirf jab koi employee nahi) --------
    employee_count = Employee.query.filter_by(role="employee").count()
    if employee_count == 0:
        e1 = Employee(
            emp_code="E001",
            username="rahul",
            name="Rahul Sharma",
            role="employee",
            status="Active",
            password_hash=""
        )
        e1.set_password("rahul@123")

        e2 = Employee(
            emp_code="E002",
            username="priya",
            name="Priya Verma",
            role="employee",
            status="On Leave",
            password_hash=""
        )
        e2.set_password("priya@123")

        e3 = Employee(
            emp_code="E003",
            username="amit",
            name="Amit Singh",
            role="employee",
            status="Active",
            password_hash=""
        )
        e3.set_password("amit@123")

        db.session.add_all([e1, e2, e3])

    db.session.commit()


# ---------- ROUTES ----------

@app.route("/")
def index():
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        else:
            return redirect(url_for("employee_dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        emp = Employee.query.filter_by(username=username).first()

        if emp and emp.check_password(password):
            session["user_id"] = emp.id
            session["username"] = emp.username
            session["role"] = emp.role

            # demo users ka data reset
            reset_demo_data_for_user(emp)

            if emp.role == "employee":
                today = date.today()
                record = Attendance.query.filter_by(
                    employee_id=emp.id, date=today
                ).first()
                if not record:
                    record = Attendance(employee_id=emp.id, date=today)
                    db.session.add(record)
                    db.session.commit()

            flash("Logged in successfully", "success")
            if emp.role == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("employee_dashboard"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    user_id = session.get("user_id")
    role = session.get("role")

    if user_id and role == "employee":
        emp = Employee.query.get(user_id)
        if emp:
            today = date.today()
            record = (
                Attendance.query.filter_by(employee_id=emp.id, date=today)
                .order_by(Attendance.login_time.desc())
                .first()
            )
            if record and record.logout_time is None:
                record.logout_time = datetime.utcnow()
                db.session.commit()

    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("login"))


@app.route("/admin/dashboard")
@login_required(role="admin")
def admin_dashboard():
    total_employees = Employee.query.filter_by(role="employee").count()
    active_status = Employee.query.filter_by(role="employee", status="Active").count()
    on_leave = Employee.query.filter_by(role="employee", status="On Leave").count()

    stats = {
        "total_employees": total_employees,
        "active_today": active_status,
        "on_leave": on_leave,
        "pending_tasks": Task.query.filter(Task.status != "Done").count(),
    }

    today = date.today()
    labels = []
    values = []
    for i in range(4, -1, -1):
        d = today.fromordinal(today.toordinal() - i)
        labels.append(d.strftime("%a"))
        c = (
            db.session.query(Attendance.employee_id)
            .filter_by(date=d)
            .distinct()
            .count()
        )
        values.append(c)

    return render_template(
        "admin_dashboard.html",
        stats=stats,
        attendance_labels=labels,
        attendance_values=values,
    )


@app.route("/employee/dashboard")
@login_required(role="employee")
def employee_dashboard():
    user_id = session.get("user_id")
    emp = Employee.query.get(user_id)
    tasks = Task.query.filter_by(employee_id=emp.id).order_by(Task.id.desc()).all()
    return render_template("employee_dashboard.html", user=emp.username, tasks=tasks)


@app.route("/admin/employees")
@login_required(role="admin")
def admin_employees():
    employees = Employee.query.filter_by(role="employee").order_by(Employee.id).all()
    return render_template("employee_list.html", employees=employees)


@app.route("/admin/employees/create", methods=["GET", "POST"])
@login_required(role="admin")
def create_employee():
    if request.method == "POST":
        emp_code = request.form.get("emp_code", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        name = request.form.get("name", "").strip()
        role_ = request.form.get("role", "").strip() or "employee"
        status = request.form.get("status", "").strip() or "Active"

        if not (username and password and name and role_):
            flash("Username, password, name and role are required.", "danger")
            return render_template("employee_create.html")

        if emp_code:
            if Employee.query.filter_by(emp_code=emp_code).first():
                flash("Employee code already exists, choose another one.", "danger")
                return render_template("employee_create.html")

        if Employee.query.filter_by(username=username).first():
            flash("Username already exists, choose another one.", "danger")
            return render_template("employee_create.html")

        new_emp = Employee(
            emp_code=emp_code or None,
            username=username,
            name=name,
            role=role_,
            status=status,
            password_hash=""
        )
        new_emp.set_password(password)
        db.session.add(new_emp)
        db.session.commit()
        flash(f"Employee '{name}' added.", "success")
        return redirect(url_for("admin_employees"))

    return render_template("employee_create.html")


@app.route("/admin/employees/<int:emp_id>/edit", methods=["GET", "POST"])
@login_required(role="admin")
def edit_employee(emp_id):
    emp = Employee.query.get(emp_id)
    if not emp:
        flash("Employee not found.", "danger")
        return redirect(url_for("admin_employees"))

    if request.method == "POST":
        emp_code = request.form.get("emp_code", "").strip()
        username = request.form.get("username", "").strip()
        name = request.form.get("name", "").strip()
        role_ = request.form.get("role", "").strip()
        status = request.form.get("status", "").strip() or "Active"
        new_password = request.form.get("password", "").strip()

        if not (username and name and role_):
            flash("Username, name and role are required.", "danger")
            return render_template("employee_edit.html", emp=emp)

        if emp_code:
            existing_code = Employee.query.filter_by(emp_code=emp_code).first()
            if existing_code and existing_code.id != emp.id:
                flash("This employee code is used by another employee.", "danger")
                return render_template("employee_edit.html", emp=emp)

        existing = Employee.query.filter_by(username=username).first()
        if existing and existing.id != emp.id:
            flash("This username is used by another employee.", "danger")
            return render_template("employee_edit.html", emp=emp)

        emp.emp_code = emp_code or None
        emp.username = username
        emp.name = name
        emp.role = role_
        emp.status = status

        if new_password:
            emp.set_password(new_password)

        db.session.commit()
        flash("Employee updated.", "success")
        return redirect(url_for("admin_employees"))

    return render_template("employee_edit.html", emp=emp)


@app.route("/admin/employees/<int:emp_id>/delete", methods=["POST"])
@login_required(role="admin")
def delete_employee(emp_id):
    emp = Employee.query.get(emp_id)
    if not emp:
        flash("Employee not found.", "danger")
    else:
        Attendance.query.filter_by(employee_id=emp.id).delete()
        Task.query.filter_by(employee_id=emp.id).delete()
        db.session.delete(emp)
        db.session.commit()
        flash("Employee deleted.", "success")
    return redirect(url_for("admin_employees"))


@app.route("/admin/tasks", methods=["GET", "POST"])
@login_required(role="admin")
def admin_tasks():
    employees = Employee.query.filter_by(role="employee").all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        status = request.form.get("status", "").strip() or "Pending"
        due_date_str = request.form.get("due_date", "").strip()
        employee_id = request.form.get("employee_id", type=int)

        if not (title and employee_id):
            flash("Title and employee are required.", "danger")
        else:
            due_date = None
            if due_date_str:
                try:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                except ValueError:
                    flash("Invalid date format.", "danger")

            task = Task.query.filter_by(
                employee_id=employee_id,
                title=title
            ).first()

            if task:
                task.status = status
                task.due_date = due_date
                db.session.commit()
                flash("Task status updated for this employee.", "success")
            else:
                task = Task(
                    title=title,
                    status=status,
                    due_date=due_date,
                    employee_id=employee_id,
                )
                db.session.add(task)
                db.session.commit()
                flash("Task assigned.", "success")

            return redirect(url_for("admin_tasks"))

    all_tasks = Task.query.order_by(Task.id.desc()).all()
    return render_template("admin_tasks.html", employees=employees, tasks=all_tasks)


@app.route("/admin/tasks/<int:task_id>/reset", methods=["POST"])
@login_required(role="admin")
def admin_task_reset(task_id):
    task = Task.query.get(task_id)
    if not task:
        flash("Task not found.", "danger")
    else:
        task.status = "Pending"
        db.session.commit()
        flash("Task reset to Pending.", "success")
    return redirect(url_for("admin_tasks"))


@app.route("/admin/tasks/<int:task_id>/delete", methods=["POST"])
@login_required(role="admin")
def admin_task_delete(task_id):
    task = Task.query.get(task_id)
    if not task:
        flash("Task not found.", "danger")
    else:
        db.session.delete(task)
        db.session.commit()
        flash("Task deleted.", "success")
    return redirect(url_for("admin_tasks"))


@app.route("/admin/attendance")
@login_required(role="admin")
def admin_attendance_list():
    employees = Employee.query.filter_by(role="employee").all()
    selected_emp_id = request.args.get("employee_id", type=int)
    selected_date_str = request.args.get("date", "")

    query = Attendance.query

    if selected_emp_id:
        query = query.filter_by(employee_id=selected_emp_id)

    if selected_date_str:
        try:
            d = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            query = query.filter_by(date=d)
        except ValueError:
            pass

    records = query.order_by(Attendance.date.desc(), Attendance.login_time.desc()).all()

    return render_template(
        "admin_attendance.html",
        employees=employees,
        records=records,
        selected_emp_id=selected_emp_id,
        selected_date=selected_date_str,
    )


@app.route("/admin/attendance/<int:att_id>/reset", methods=["POST"])
@login_required(role="admin")
def admin_attendance_reset(att_id):
    rec = Attendance.query.get(att_id)
    if not rec:
        flash("Attendance record not found.", "danger")
    else:
        rec.login_time = datetime.utcnow()
        rec.logout_time = None
        db.session.commit()
        flash("Attendance reset.", "success")
    return redirect(request.referrer or url_for("admin_attendance_list"))


# ===== UPDATED ACCOUNT SETTINGS ROUTE =====

@app.route("/account/settings", methods=["GET", "POST"])
@login_required()
def account_settings():
    user_id = session.get("user_id")
    role = session.get("role")

    user = Employee.query.get(user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("login"))

    is_demo_user = user.username in DEMO_USERNAMES

    if request.method == "POST":
        if is_demo_user:
            flash("Demo accounts cannot change password or email.", "warning")
            return redirect(url_for("account_settings"))

        new_email = request.form.get("email", "").strip()
        new_password = request.form.get("password", "").strip()

        if new_email:
            user.email = new_email

        if new_password:
            user.set_password(new_password)

        db.session.commit()
        flash("Account settings updated successfully.", "success")
        return redirect(url_for("account_settings"))

    return render_template(
        "account_settings.html",
        user=user.username,
        role=role,
        is_demo_user=is_demo_user,
    )


# ---------- MAIN ----------

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
