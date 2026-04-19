from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Invoice, InvoiceItem, SponsorCompany, DriverCompanyLink, DriverPointsHistory, DriverProfile
from datetime import datetime
from functools import wraps
from decimal import Decimal


invoice_bp = Blueprint('invoice', __name__)


# ---- Helpers ----
def admin_required(fn):
    @wraps(fn)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)

    return decorated



@invoice_bp.route("/admin/invoices")
@admin_required
def invoice_list():
    invoices = Invoice.query.order_by(Invoice.created_date.desc()).all()

    for invoice in invoices:
        invoice.fee_amount = round(invoice.total_amount * Decimal('0.01'), 2)
        invoice.total_with_fee = round(invoice.total_amount + invoice.fee_amount, 2)

    return render_template("admin/reports/admin_invoices.html", invoices=invoices)


# ---- Create Invoice (GET = form, POST = submit) ----
@invoice_bp.route("/admin/invoices/create", methods=["GET", "POST"])
@admin_required
def invoice_create():
    companies = SponsorCompany.query.order_by(SponsorCompany.name).all()

    if request.method == "GET":
        return render_template("admin/reports/admin_invoice_create.html", companies=companies)

    # POST — generate the invoice
    company_id = request.form.get("company_id", type=int)
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    notes = request.form.get("notes", "")

    if not company_id or not start_date or not end_date:
        flash("Please fill in all required fields.", "danger")
        return render_template("admin/reports/admin_invoice_create.html", companies=companies)

    start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    if start_date > end_date:
        flash("Start date cannot be after end date.", "danger")
        return render_template("admin/reports/admin_invoice_create.html", companies=companies)

    company = SponsorCompany.query.get(company_id)
    if not company:
        flash("Sponsor company not found.", "danger")
        return render_template("admin/reports/admin_invoice_create.html", companies=companies)

    # Find all point history records for drivers linked to this company in the date range
    history_records = (
        db.session.query(DriverPointsHistory)
        .join(DriverCompanyLink, DriverPointsHistory.link_id == DriverCompanyLink.id)
        .filter(
            DriverCompanyLink.company_id == company_id,
            DriverPointsHistory.update_date >= datetime.combine(start_date, datetime.min.time()),
            DriverPointsHistory.update_date <= datetime.combine(end_date, datetime.max.time())
        )
        .all()
    )

    # Create the invoice
    total_points = sum(abs(r.points_change) for r in history_records)
    total_amount = round(float(total_points) * float(company.points_conversion), 2)

    invoice = Invoice(
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        total_points=total_points,
        total_amount=total_amount,
        created_by=current_user.id,
        notes=notes
    )
    db.session.add(invoice)
    db.session.flush()  # get the invoice.id before adding items

    # Create line items from history
    for record in history_records:
        link = DriverCompanyLink.query.get(record.link_id)
        item = InvoiceItem(
            invoice_id=invoice.id,
            driver_id=link.driver_id,
            points_history_id=record.id,
            description=record.reason,
            points=record.points_change,
            amount=round(float(abs(record.points_change)) * float(company.points_conversion), 2),
            transaction_date=record.update_date
        )
        db.session.add(item)

    db.session.commit()
    flash(f"Invoice #{invoice.id} created for {company.name}.", "success")
    return redirect(url_for("invoice.invoice_view", invoice_id=invoice.id))


@invoice_bp.route("/admin/invoices/<int:invoice_id>")
@admin_required
def invoice_view(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)

    fee_amount = round(invoice.total_amount * Decimal('0.01'), 2)
    total_with_fee = round(invoice.total_amount + fee_amount, 2)

    return render_template(
        "admin/reports/admin_invoice_view.html",
        invoice=invoice,
        fee_amount=fee_amount,
        total_with_fee=total_with_fee
    )


# ---- Delete Invoice ----
@invoice_bp.route("/admin/invoices/<int:invoice_id>/delete", methods=["POST"])
@admin_required
def invoice_delete(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    db.session.delete(invoice)
    db.session.commit()
    flash("Invoice deleted.", "info")
    return redirect(url_for("invoice.invoice_list"))