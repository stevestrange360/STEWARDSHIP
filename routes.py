from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from sqlalchemy import func, and_

from . import db as db_module
from .models import Member, Debt, Payment, ReminderLog, DebtType, PaymentStatus
from .sms_service import SMSService, MessageTemplates
from .reports import ReportGenerator      # ← NOTE: reports (with 's')
from .pdf_exporter import PDFExporter     # ← NOTE: pdf_exporter
from sqlalchemy.orm import joinedload

bp = Blueprint("main", __name__)
sms_service = SMSService()
def _require_login():
    if not session.get("logged_in"):
        return redirect(url_for("main.login"))
    return None

# -----------------------
# Login Routes
# -----------------------
@bp.get("/login")
def login():
    return render_template("login.html")

@bp.post("/login")
def login_post():
    username = request.form.get("username")
    password = request.form.get("password")
    
    if username == os.getenv("ADMIN_USERNAME", "admin") and password == os.getenv("ADMIN_PASSWORD", "admin123"):
        session["logged_in"] = True
        return redirect(url_for("main.home"))  # Changed to home page
    
    flash("Invalid credentials", "danger")
    return redirect(url_for("main.login"))

@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))

# ========== HOMEPAGE ROUTE ==========
@bp.get("/home")
def home():
    gate = _require_login()
    if gate:
        return gate
    
    import os
    
    with db_module.SessionLocal() as db:
        stats = {
            "total_members": db.query(Member).count(),
            "total_committed": db.query(func.sum(Debt.total_amount)).scalar() or 0,
            "pending_count": db.query(Debt).filter(Debt.status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIAL])).count(),
            "paid_count": db.query(Debt).filter(Debt.status == PaymentStatus.PAID).count(),
        }
        
        recent_debts = db.query(Debt).join(Member).order_by(Debt.created_at.desc()).limit(5).all()
        
        recent_debtors = []
        for debt in recent_debts:
            recent_debtors.append({
                "debt_id": debt.debt_id,
                "name": debt.member.name,
                "email": debt.member.email or "—",
                "debt_type": debt.debt_type,
                "total_amount": debt.total_amount,
                "amount_paid": debt.amount_paid,
                "balance": debt.balance,
                "status": debt.status,
                "due_date": debt.due_date
            })
        
        # Check if images exist
        logo_path = os.path.join('app', 'static', 'images', 'church-logo.png')
        banner_path = os.path.join('app', 'static', 'images', 'church-banner.jpg')
        logo_exists = os.path.exists(logo_path)
        banner_exists = os.path.exists(banner_path)
    
    return render_template("home.html", 
                          stats=stats, 
                          recent_debtors=recent_debtors,
                          logo_exists=logo_exists,
                          banner_exists=banner_exists)
# ========== ROOT ROUTE (Redirects to home) ==========
@bp.get("/")
def index():
    gate = _require_login()
    if gate:
        return gate
    return redirect(url_for("main.home"))

# ========== DASHBOARD ROUTE ==========
@bp.get("/dashboard")
def dashboard():
    gate = _require_login()
    if gate:
        return gate
    
    with db_module.SessionLocal() as db:
        # Get all debts with member info
        debts = db.query(Debt).join(Member).all()
        
        # Calculate stats
        stats = {
            "total_members": db.query(Member).count(),
            "total_committed": db.query(func.sum(Debt.total_amount)).scalar() or 0,
            "pending_count": db.query(Debt).filter(Debt.status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIAL])).count(),
            "paid_count": db.query(Debt).filter(Debt.status == PaymentStatus.PAID).count(),
        }
        
        # Prepare debtors list
        debtors = []
        for debt in debts:
            debtors.append({
                "debt_id": debt.debt_id,
                "name": debt.member.name,
                "email": debt.member.email or "—",
                "debt_type": debt.debt_type,
                "total_amount": debt.total_amount,
                "amount_paid": debt.amount_paid,
                "balance": debt.balance,
                "status": debt.status,
                "due_date": debt.due_date
            })
    
    from datetime import datetime

    return render_template(
        "dashboard.html",
        debtors=debtors,
        stats=stats,
        now=datetime.now
    )

# -----------------------
# Add Debtor
# -----------------------
@bp.get("/debtor/add")
def add_debtor():
    gate = _require_login()
    if gate:
        return gate
    
    return render_template("add_debtor.html", 
                         debt_types=[t for t in DebtType],
                         today=date.today().isoformat())

@bp.post("/debtor/add")
def add_debtor_post():
    gate = _require_login()
    if gate:
        return gate
    
    with db_module.SessionLocal() as db:
        # Create member
        member = Member(
            name=request.form.get("name"),
            email=request.form.get("email"),
            phone=request.form.get("phone"),
            occupation=request.form.get("occupation")
        )
        db.add(member)
        db.flush()
        
        # Create debt
        total_amount = float(request.form.get("total_amount") or 0)
        initial_payment = float(request.form.get("initial_payment") or 0)
        due_date = datetime.strptime(request.form.get("due_date"), "%Y-%m-%d").date()
        
        # Generate debt number
        date_str = datetime.now().strftime("%Y%m")
        
        count = db.query(Debt).filter(
            Debt.debt_number.like(f"DBT{date_str}%")
        ).count() + 1
        
        debt_number = f"DBT{date_str}{count:04d}"
        
        debt = Debt(
            member_id=member.member_id,
            debt_number=debt_number,
            debt_type=DebtType(request.form.get("debt_type")),
            total_amount=total_amount,
            amount_paid=initial_payment,
            balance=total_amount - initial_payment,
            due_date=due_date,
            description=request.form.get("description"),
            notes=request.form.get("notes")
        )
        
        if initial_payment > 0:
            payment = Payment(
                member_id=member.member_id,
                debt=debt,
                amount=initial_payment,
                payment_method="Cash",
                notes="Initial payment"
            )
            db.add(payment)
        
        db.add(debt)
        debt.update_status()
        db.commit()
        
        # Send welcome message if requested
        if request.form.get("send_welcome") and member.phone:
            message = f"Welcome {member.name}! Your {debt.debt_type.value} commitment of Tsh{total_amount:,.0f} has been recorded. Due date: {due_date.strftime('%d %b %Y')}"
            success, error = sms_service.send_sms(member.phone, message)
            
            log = ReminderLog(
                member_id=member.member_id,
                debt_id=debt.debt_id,
                reminder_type="SMS",
                recipient=member.phone,
                message=message,
                status="Sent" if success else "Failed",
                error_message=error
            )
            db.add(log)
            db.commit()
        
        flash(f"Debtor {member.name} added successfully!", "success")
    
    return redirect(url_for("main.dashboard"))

# -----------------------
# Edit Debtor
# -----------------------
@bp.get("/debtor/<int:debt_id>/edit")
def edit_debtor(debt_id):
    gate = _require_login()
    if gate:
        return gate
    
    with db_module.SessionLocal() as db:
        debt = db.query(Debt).options(
            joinedload(Debt.member),
            joinedload(Debt.payments)   # 🔥 ADD THIS
        ).filter_by(debt_id=debt_id).first()
        if not debt:
            flash("Debt not found", "danger")
            return redirect(url_for("main.dashboard"))
        
        # Get payment history
        payments = db.query(Payment).filter_by(debt_id=debt_id).order_by(Payment.payment_date.desc()).all()
    
    return render_template("edit_debtor.html", 
                         member=debt.member,
                         debt=debt,
                         payments=payments,
                         debt_types=[t for t in DebtType])

@bp.post("/debtor/<int:debt_id>/edit")
def edit_debtor_post(debt_id):
    gate = _require_login()
    if gate:
        return gate
    
    with db_module.SessionLocal() as db:
        debt = db.query(Debt).filter_by(debt_id=debt_id).first()
        if not debt:
            flash("Debt not found", "danger")
            return redirect(url_for("main.dashboard"))
        
        # Store old total amount for comparison
        old_total = debt.total_amount
        old_due_date = debt.due_date
        
        # Update member information
        member = debt.member
        member.name = request.form.get("name")
        member.phone = request.form.get("phone")
        member.email = request.form.get("email") or None
        member.occupation = request.form.get("occupation") or None
        member.updated_at = datetime.now()
        
        # Update debt information
        new_total = float(request.form.get("total_amount") or 0)
        debt.debt_type = DebtType(request.form.get("debt_type"))
        debt.total_amount = new_total
        debt.due_date = datetime.strptime(request.form.get("due_date"), "%Y-%m-%d").date()
        debt.description = request.form.get("description") or None
        debt.notes = request.form.get("notes") or None
        
        # Recalculate balance if total amount changed
        if new_total != old_total:
            debt.balance = new_total - debt.amount_paid
            if debt.balance < 0:
                debt.balance = 0
                flash("Warning: Total amount was set less than amount paid. Balance set to 0.", "warning")
        
        # Update status based on new balance and due date
        debt.update_status()
        debt.updated_at = datetime.now()
        
        db.commit()
        
        # Send notification SMS if due date changed
        if debt.due_date != old_due_date and member.phone:
            message = f"Dear {member.name}, your {debt.debt_type.value} pledge due date has been updated to {debt.due_date.strftime('%d %b %Y')}. Current balance: Tsh{debt.balance:,.0f}"
            sms_service.send_sms(member.phone, message)
            
            log = ReminderLog(
                member_id=member.member_id,
                debt_id=debt.debt_id,
                reminder_type="SMS",
                recipient=member.phone,
                message=message,
                status="Sent"
            )
            db.add(log)
            db.commit()
        
        flash(f"Debtor {member.name} updated successfully!", "success")
    
    return redirect(url_for("main.dashboard"))


@bp.post("/debtor/<int:debt_id>/delete")
def delete_debtor(debt_id):
    gate = _require_login()
    if gate:
        return gate

    with db_module.SessionLocal() as db:
        debt = db.query(Debt).filter_by(debt_id=debt_id).first()

        if not debt:
            flash("Debtor not found", "danger")
            return redirect(url_for("main.dashboard"))

        # Delete related payments first
        db.query(Payment).filter_by(debt_id=debt_id).delete()

        # Delete reminders
        db.query(ReminderLog).filter_by(debt_id=debt_id).delete()

        # Delete debt
        db.delete(debt)

        db.commit()

        flash("Debtor deleted successfully", "success")

    return redirect(url_for("main.dashboard"))

@bp.post("/payment/<int:debt_id>/quick")
def quick_pay(debt_id):
    gate = _require_login()
    if gate:
        return gate

    with db_module.SessionLocal() as db:
        debt = db.query(Debt).options(joinedload(Debt.member)).filter_by(debt_id=debt_id).first()

        if not debt:
            flash("Debt not found", "danger")
            return redirect(url_for("main.dashboard"))

        if debt.balance <= 0:
            flash("This debt is already fully paid", "info")
            return redirect(url_for("main.dashboard"))

        amount = debt.balance  # Pay all remaining

        # Generate receipt
        receipt = f"RCP{datetime.now().strftime('%Y%m%d%H%M%S')}"

        payment = Payment(
            receipt_number=receipt,
            member_id=debt.member_id,
            debt_id=debt_id,
            amount=amount,
            payment_method="Quick Pay",
            notes="Full payment from dashboard"
        )

        debt.amount_paid += amount
        debt.balance = 0
        debt.update_status()

        db.add(payment)
        db.commit()

        flash(f"✅ {debt.member.name} has fully paid Tsh{amount:,.0f}", "success")

    return redirect(url_for("main.dashboard"))

# -----------------------
# Send Reminder
# -----------------------
@bp.get("/reminder/<int:debt_id>")
def send_reminder(debt_id):
    gate = _require_login()
    if gate:
        return gate
    
    with db_module.SessionLocal() as db:
        # Eager-load member and payments
        debt = db.query(Debt).options(
            joinedload(Debt.member),
            joinedload(Debt.payments),   # <-- add this
            joinedload(Debt.reminders)   # optional if you need reminders too
        ).filter_by(debt_id=debt_id).first()
        
        if not debt:
            flash("Debt not found", "danger")
            return redirect(url_for("main.dashboard"))
        
        # Force loading while session is active
        payments = list(debt.payments)
        reminders = list(debt.reminders)
    
    return render_template(
        "send_reminder.html", 
        member=debt.member, 
        debt=debt,
        payments=payments,
        reminders=reminders
    )

@bp.post("/reminder/<int:debt_id>/email")
def send_email_reminder(debt_id):
    gate = _require_login()
    if gate:
        return gate

    with db_module.SessionLocal() as db:
        debt = db.get(Debt, debt_id)
        
        if not debt.member.email:
            flash("No email address for this member.", "warning")
            return redirect(url_for("main.send_reminder", debt_id=debt_id))

        # Send the real email
        from .email_service import EmailService, EmailTemplates
        email_service = EmailService()

        body = EmailTemplates.pledge_reminder(
            debt.member.name,
            debt.total_amount,
            debt.due_date.strftime('%d %b %Y'),
            debt.balance
        )

        success, error = email_service.send_email(
            recipient=debt.member.email,
            subject="Pledge Reminder",
            body=body
        )

        # Log the reminder in database
        log = ReminderLog(
            member_id=debt.member_id,
            debt_id=debt_id,
            reminder_type="Email",
            recipient=debt.member.email,
            message=body,
            status="Sent" if success else "Failed",
            error_message=error if not success else None
        )
        db.add(log)

        if success:
            debt.reminder_count += 1
            debt.last_reminder_sent = datetime.now()
            flash(f"Email reminder sent to {debt.member.name}", "success")
        else:
            flash(f"Failed to send email: {error}", "danger")

        db.commit()

    return redirect(url_for("main.send_reminder", debt_id=debt_id))

@bp.post("/reminder/<int:debt_id>/sms")
def send_sms_reminder(debt_id):
    gate = _require_login()
    if gate:
        return gate
    
    with db_module.SessionLocal() as db:
        debt = db.get(Debt, debt_id)
        
        message = MessageTemplates.pledge_reminder(
            debt.member.name,
            debt.total_amount,
            debt.due_date.strftime('%d %b %Y'),
            debt.balance
        )
        
        success, error = sms_service.send_sms(debt.member.phone, message)
        
        log = ReminderLog(
            member_id=debt.member_id,
            debt_id=debt_id,
            reminder_type="SMS",
            recipient=debt.member.phone,
            message=message,
            status="Sent" if success else "Failed",
            error_message=error
        )
        db.add(log)
        
        if success:
            debt.reminder_count += 1
            debt.last_reminder_sent = datetime.now()
            flash(f"SMS reminder sent to {debt.member.name}", "success")
        else:
            flash(f"Failed to send SMS: {error}", "danger")
        
        db.commit()
    
    return redirect(url_for("main.send_reminder", debt_id=debt_id))

# -----------------------
# Payment Recording
# -----------------------
@bp.post("/payment/<int:debt_id>")
def record_payment(debt_id):
    gate = _require_login()
    if gate:
        return gate
    
    amount = float(request.form.get("amount") or 0)
    send_sms = request.form.get("send_sms") == 'on'
    
    with db_module.SessionLocal() as db:
        debt = db.get(Debt, debt_id)
        
        # Validate amount
        if amount <= 0:
            flash("Payment amount must be greater than zero", "danger")
            return redirect(url_for("main.send_reminder", debt_id=debt_id))
        
        if amount > debt.balance:
            flash(f"Payment amount (Tsh{amount:,.0f}) exceeds remaining balance (Tsh{debt.balance:,.0f})", "danger")
            return redirect(url_for("main.send_reminder", debt_id=debt_id))
        
        # Generate receipt number
        date_str = datetime.now().strftime("%Y%m%d")
        count = db.query(Payment).filter(
            Payment.receipt_number.like(f"RCP{date_str}%")
        ).count() + 1
        receipt_number = f"RCP{date_str}{count:04d}"
        
        # Create payment record
        payment = Payment(
            receipt_number=receipt_number,
            member_id=debt.member_id,
            debt_id=debt_id,
            amount=amount,
            payment_method=request.form.get("payment_method", "Cash"),
            transaction_id=request.form.get("transaction_id") or None,
            notes=request.form.get("notes") or None
        )
        
        # Update debt
        was_completed = debt.balance <= 0
        debt.amount_paid += amount
        debt.balance -= amount
        debt.update_status()
        
        db.add(payment)
        db.commit()
        
        # Send SMS if requested
        if send_sms and debt.member.phone:
            message = MessageTemplates.payment_thankyou(
                debt.member.name,
                amount,
                payment.receipt_number,
                debt.balance
            )
            success, error = sms_service.send_sms(debt.member.phone, message)
            
            # Log SMS
            log = ReminderLog(
                member_id=debt.member_id,
                debt_id=debt_id,
                reminder_type="SMS",
                recipient=debt.member.phone,
                message=message,
                status="Sent" if success else "Failed",
                error_message=error if not success else None
            )
            db.add(log)
            db.commit()
        
        # Flash message
        if debt.balance <= 0:
            flash(f"✅ Payment of Tsh{amount:,.0f} recorded! Pledge is now COMPLETED. Receipt: {receipt_number}", "success")
        else:
            flash(f"✅ Payment of Tsh{amount:,.0f} recorded! Remaining balance: Tsh{debt.balance:,.0f}. Receipt: {receipt_number}", "success")
    
    return redirect(url_for("main.send_reminder", debt_id=debt_id))
# -----------------------
# Auto-Reminder Cron Job
# -----------------------
@bp.get("/cron/send-reminders")
def send_auto_reminders():
    """Endpoint for cron job to send automatic reminders"""
    
    with db_module.SessionLocal() as db:
        today = date.today()
        upcoming = db.query(Debt).filter(
            and_(
                Debt.due_date <= today + timedelta(days=7),
                Debt.due_date > today,
                Debt.balance > 0,
                Debt.reminder_enabled == True
            )
        ).all()
        
        overdue = db.query(Debt).filter(
            and_(
                Debt.due_date < today,
                Debt.balance > 0,
                Debt.reminder_enabled == True
            )
        ).all()
        
        reminders_sent = 0
        
        for debt in upcoming + overdue:
            if debt.last_reminder_sent and (datetime.now() - debt.last_reminder_sent).days < 7:
                continue
            
            message = MessageTemplates.pledge_reminder(
                debt.member.name,
                debt.total_amount,
                debt.due_date.strftime('%d %b %Y'),
                debt.balance
            )
            
            success, error = sms_service.send_sms(debt.member.phone, message)
            
            log = ReminderLog(
                member_id=debt.member_id,
                debt_id=debt.debt_id,
                reminder_type="SMS",
                recipient=debt.member.phone,
                message=message,
                status="Sent" if success else "Failed",
                error_message=error
            )
            db.add(log)
            
            if success:
                debt.reminder_count += 1
                debt.last_reminder_sent = datetime.now()
                reminders_sent += 1
        
        db.commit()
    
    return f"Sent {reminders_sent} reminders"

# -----------------------
# Report Generation
# -----------------------
@bp.post("/reports/generate")
def generate_report():
    gate = _require_login()
    if gate:
        return gate
    
    # Get form data
    report_type = request.form.get("report_type")
    period = request.form.get("period")
    format_type = request.form.get("format", "html")
    member_id = request.form.get("member_id")
    
    # Get date range
    start_date = None
    end_date = None
    
    if period == "custom":
        start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date()
        end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d").date()
    
    # Create database session
    with db_module.SessionLocal() as db:
        # Create report generator instance
        report_gen = ReportGenerator(db)
        
        # Get date range
        if period != "custom":
            start_date, end_date = report_gen.get_date_range(period)
        
        # Generate data based on report type
        data = None
        title = ""
        
        if report_type == "financial_summary":
            data = report_gen.financial_summary(start_date, end_date)
            title = "Financial Summary Report"
        
        elif report_type == "pledges_by_type":
            data = report_gen.pledges_by_type(start_date, end_date)
            title = "Pledges by Type Report"
        
        elif report_type == "overdue_pending":
            data = report_gen.overdue_pending()
            title = "Overdue & Pending Pledges Report"
        
        elif report_type == "monthly_collection":
            # For monthly collection, we need year and month from period
            if period == "this_month":
                year = date.today().year
                month = date.today().month
            elif period == "last_month":
                last_month = date.today().replace(day=1) - timedelta(days=1)
                year = last_month.year
                month = last_month.month
            else:
                year = date.today().year
                month = date.today().month
            data = report_gen.monthly_collection(year, month)
            title = f"Monthly Collection Report - {data['month_name']} {year}"
        
        elif report_type == "member_statement":
            if member_id:
                data = report_gen.member_statement(int(member_id), start_date, end_date)
                title = f"Member Statement - {data['member']['name']}"
            else:
                flash("Please select a member", "warning")
                return redirect(url_for("main.reports_page"))
        
        elif report_type == "yearly_summary":
            year = date.today().year
            if period == "last_year":
                year = date.today().year - 1
            data = report_gen.yearly_summary(year)
            title = f"Yearly Summary Report - {year}"
        
        elif report_type == "payment_history":
            data = report_gen.payment_history(start_date, end_date)
            title = "Payment History Report"
        
        elif report_type == "completed_pledges":
            data = report_gen.completed_pledges(start_date, end_date)
            title = "Completed Pledges Report"
        
        if not data:
            flash("No data available for the selected period", "warning")
            return redirect(url_for("main.reports_page"))
        
        # Format period string for display
        period_str = f"{start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')}" if start_date and end_date else "All Time"
        
        # Export based on format
        if format_type == "excel":
            excel_buffer = report_gen.export_to_excel(report_type, data, title, period_str)
            return send_file(
                excel_buffer,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=f"{report_type}_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )
        
        elif format_type == "pdf":
            pdf_exporter = PDFExporter(church_name="KKKT CHANGANYIKENI")
            
            if report_type == "financial_summary":
                pdf_buffer = pdf_exporter.export_financial_summary(data, title, period_str)
            elif report_type == "pledges_by_type":
                pdf_buffer = pdf_exporter.export_pledges_by_type(data, title, period_str)
            elif report_type == "overdue_pending":
                pdf_buffer = pdf_exporter.export_overdue_pending(data, title, period_str)
            elif report_type == "monthly_collection":
                pdf_buffer = pdf_exporter.export_monthly_collection(data, title, period_str)
            elif report_type == "member_statement":
                pdf_buffer = pdf_exporter.export_member_statement(data, title, period_str)
            elif report_type == "yearly_summary":
                pdf_buffer = pdf_exporter.export_yearly_summary(data, title, period_str)
            elif report_type == "payment_history":
                pdf_buffer = pdf_exporter.export_payment_history(data, title, period_str)
            elif report_type == "completed_pledges":
                pdf_buffer = pdf_exporter.export_completed_pledges(data, title, period_str)
            else:
                pdf_buffer = pdf_exporter.export_financial_summary(data, title, period_str)
            
            return send_file(
                pdf_buffer,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=f"{report_type}_{datetime.now().strftime('%Y%m%d')}.pdf"
            )
        
        else:  # HTML view
            return render_template(
                "report_results.html",
                report_type=report_type,
                report_title=title,
                report_period=period_str,
                generation_date=datetime.now().strftime('%d %b %Y, %H:%M'),
                data=data,
                chart_data=None
            )
@bp.get("/reports")
def reports_page():
    gate = _require_login()
    if gate:
        return gate
    
    with db_module.SessionLocal() as db:
        members = db.query(Member).order_by(Member.name).all()
    
    return render_template("reports.html", members=members)            
