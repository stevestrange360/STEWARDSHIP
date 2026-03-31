# app/reports.py
from __future__ import annotations
from datetime import datetime, timedelta, date
from sqlalchemy import func, and_
from .models import Member, Debt, Payment, DebtType, PaymentStatus
import pandas as pd
from io import BytesIO
import calendar


class ReportGenerator:
    """Generate all reports for the stewardship system"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def get_date_range(self, period, start_date=None, end_date=None):
        """Get date range based on period selection"""
        today = date.today()
        
        if period == 'this_month':
            start = today.replace(day=1)
            next_month = start.replace(day=28) + timedelta(days=4)
            end = next_month - timedelta(days=next_month.day)
            return start, end
        elif period == 'last_month':
            first_day_this_month = today.replace(day=1)
            last_day_last_month = first_day_this_month - timedelta(days=1)
            first_day_last_month = last_day_last_month.replace(day=1)
            return first_day_last_month, last_day_last_month
        elif period == 'this_quarter':
            quarter = (today.month - 1) // 3
            start = date(today.year, quarter * 3 + 1, 1)
            if quarter == 0:
                end = date(today.year, 4, 1) - timedelta(days=1)
            elif quarter == 1:
                end = date(today.year, 7, 1) - timedelta(days=1)
            elif quarter == 2:
                end = date(today.year, 10, 1) - timedelta(days=1)
            else:
                end = date(today.year + 1, 1, 1) - timedelta(days=1)
            return start, end
        elif period == 'this_year':
            start = date(today.year, 1, 1)
            end = date(today.year, 12, 31)
            return start, end
        elif period == 'last_year':
            start = date(today.year - 1, 1, 1)
            end = date(today.year - 1, 12, 31)
            return start, end
        elif period == 'custom':
            if start_date and end_date:
                return start_date, end_date
            return date(2000, 1, 1), today
        else:  # all_time
            first_debt = self.db.query(Debt).order_by(Debt.commitment_date.asc()).first()
            if first_debt:
                start = first_debt.commitment_date
            else:
                start = date(2000, 1, 1)
            return start, today
    
    def financial_summary(self, start_date, end_date):
        """Generate financial summary report"""
        # Get all debts in period
        debts = self.db.query(Debt).filter(
            Debt.commitment_date.between(start_date, end_date)
        ).all()
        
        total_pledged = sum(d.total_amount for d in debts)
        total_collected = sum(d.amount_paid for d in debts)
        outstanding = total_pledged - total_collected
        
        # Get payments in period
        payments = self.db.query(Payment).filter(
            Payment.payment_date.between(start_date, end_date)
        ).all()
        period_collected = sum(p.amount for p in payments)
        
        active_pledges = self.db.query(Debt).filter(
            Debt.balance > 0,
            Debt.status != PaymentStatus.PAID
        ).count()
        
        completed_pledges = self.db.query(Debt).filter(
            Debt.status == PaymentStatus.PAID
        ).count()
        
        overdue_pledges = self.db.query(Debt).filter(
            Debt.status == PaymentStatus.OVERDUE
        ).count()
        
        completion_rate = (total_collected / total_pledged * 100) if total_pledged > 0 else 0
        
        return {
            'total_pledged': total_pledged,
            'total_collected': total_collected,
            'period_collected': period_collected,
            'outstanding': outstanding,
            'completion_rate': completion_rate,
            'active_pledges': active_pledges,
            'completed_pledges': completed_pledges,
            'overdue_pledges': overdue_pledges
        }
    
    def pledges_by_type(self, start_date, end_date):
        """Generate pledges grouped by type"""
        types = {}
        for debt_type in DebtType:
            pledges = self.db.query(Debt).filter(
                Debt.debt_type == debt_type,
                Debt.commitment_date.between(start_date, end_date)
            ).all()
            
            total = sum(d.total_amount for d in pledges)
            collected = sum(d.amount_paid for d in pledges)
            balance = total - collected
            percentage = (collected / total * 100) if total > 0 else 0
            
            if total > 0:
                types[debt_type.value] = {
                    'name': debt_type.value,
                    'total': total,
                    'collected': collected,
                    'balance': balance,
                    'percentage': percentage
                }
        
        pledge_types = list(types.values())
        total_pledged = sum(t['total'] for t in pledge_types)
        total_collected = sum(t['collected'] for t in pledge_types)
        total_balance = sum(t['balance'] for t in pledge_types)
        overall_percentage = (total_collected / total_pledged * 100) if total_pledged > 0 else 0
        
        return {
            'pledge_types': pledge_types,
            'total_pledged': total_pledged,
            'total_collected': total_collected,
            'total_balance': total_balance,
            'overall_percentage': overall_percentage
        }
    
    def overdue_pending(self):
        """Generate overdue and pending pledges report"""
        today = date.today()
        
        # Overdue pledges (due date passed, balance > 0)
        overdue = self.db.query(Debt).join(Member).filter(
            Debt.due_date < today,
            Debt.balance > 0,
            Debt.status == PaymentStatus.OVERDUE
        ).all()
        
        # Pending pledges (balance > 0, due date not passed)
        pending = self.db.query(Debt).join(Member).filter(
            Debt.due_date >= today,
            Debt.balance > 0,
            Debt.status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIAL])
        ).all()
        
        overdue_list = []
        for d in overdue:
            days_overdue = (today - d.due_date).days
            overdue_list.append({
                'member_name': d.member.name,
                'phone': d.member.phone,
                'email': d.member.email or '—',
                'debt_type': d.debt_type.value,
                'total_amount': d.total_amount,
                'amount_paid': d.amount_paid,
                'balance': d.balance,
                'due_date': d.due_date.strftime('%d %b %Y'),
                'days_overdue': days_overdue
            })
        
        pending_list = []
        for d in pending:
            pending_list.append({
                'member_name': d.member.name,
                'phone': d.member.phone,
                'email': d.member.email or '—',
                'debt_type': d.debt_type.value,
                'total_amount': d.total_amount,
                'amount_paid': d.amount_paid,
                'balance': d.balance,
                'due_date': d.due_date.strftime('%d %b %Y')
            })
        
        return {
            'overdue': overdue_list,
            'pending': pending_list,
            'overdue_count': len(overdue_list),
            'pending_count': len(pending_list)
        }
    
    def monthly_collection(self, year, month):
        """Generate monthly collection report"""
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        payments = self.db.query(Payment).join(Member, Payment.member_id == Member.member_id).filter(
        Payment.payment_date.between(start_date, end_date)
        ).all()
        
        total_collected = sum(p.amount for p in payments)
        total_payments = len(payments)
        avg_payment = total_collected / total_payments if total_payments > 0 else 0
        
        # Weekly breakdown
        weeks = {}
        for p in payments:
            week = ((p.payment_date.day - 1) // 7) + 1
            if week not in weeks:
                weeks[week] = {'amount': 0, 'count': 0}
            weeks[week]['amount'] += p.amount
            weeks[week]['count'] += 1
        
        weekly_breakdown = []
        for week_num in range(1, 6):  # Max 5 weeks in a month
            week_data = weeks.get(week_num, {'amount': 0, 'count': 0})
            weekly_breakdown.append({
                'week': week_num,
                'payment_count': week_data['count'],
                'amount': week_data['amount'],
                'percentage': (week_data['amount'] / total_collected * 100) if total_collected > 0 else 0
            })
        
        # Payment methods breakdown
        methods = {}
        for p in payments:
            methods[p.payment_method] = methods.get(p.payment_method, 0) + p.amount
        
        payment_methods = [{'name': k, 'amount': v, 'percentage': (v / total_collected * 100) if total_collected > 0 else 0} 
                          for k, v in methods.items()]
        
        # Top members
        member_totals = {}
        for p in payments:
            member_totals[p.member.name] = member_totals.get(p.member.name, 0) + p.amount
        
        sorted_members = sorted(member_totals.items(), key=lambda x: x[1], reverse=True)
        top_members = [{'name': name, 'amount': amount} for name, amount in sorted_members[:5]]
        
        return {
            'total_collected': total_collected,
            'total_payments': total_payments,
            'avg_payment': avg_payment,
            'weekly_breakdown': weekly_breakdown,
            'payment_methods': payment_methods,
            'top_members': top_members,
            'month_name': calendar.month_name[month],
            'year': year
        }
    
    def member_statement(self, member_id, start_date, end_date):
        """Generate statement for a specific member"""
        member = self.db.get(Member, member_id)
        if not member:
            return None
        
        debts = self.db.query(Debt).filter(Debt.member_id == member_id).all()
        
        pledges = []
        total_pledged = 0
        total_paid = 0
        
        for debt in debts:
            payments = self.db.query(Payment).filter(
                Payment.debt_id == debt.debt_id,
                Payment.payment_date.between(start_date, end_date)
            ).order_by(Payment.payment_date.asc()).all()
            
            percentage = (debt.amount_paid / debt.total_amount * 100) if debt.total_amount > 0 else 0
            total_pledged += debt.total_amount
            total_paid += debt.amount_paid
            
            pledges.append({
                'debt_id': debt.debt_id,
                'debt_number': debt.debt_number,
                'debt_type': debt.debt_type.value,
                'total_amount': debt.total_amount,
                'amount_paid': debt.amount_paid,
                'balance': debt.balance,
                'percentage': percentage,
                'due_date': debt.due_date.strftime('%d %b %Y'),
                'status': debt.status.value,
                'payments': [{
                    'date': p.payment_date.strftime('%d %b %Y'),
                    'receipt': p.receipt_number,
                    'amount': p.amount,
                    'method': p.payment_method
                } for p in payments]
            })
        
        return {
            'member': {
                'name': member.name,
                'phone': member.phone,
                'email': member.email,
                'occupation': member.occupation,
                'joined_date': member.joined_date.strftime('%d %b %Y')
            },
            'pledges': pledges,
            'total_pledged': total_pledged,
            'total_paid': total_paid,
            'outstanding': total_pledged - total_paid,
            'period': f"{start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')}",
            'generated_date': date.today().strftime('%d %b %Y')
        }
    
    def yearly_summary(self, year):
        """Generate yearly summary report"""
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
        # Quarterly breakdown
        quarterly_payments = {1: 0, 2: 0, 3: 0, 4: 0}
        
        payments = self.db.query(Payment).filter(
            Payment.payment_date.between(start_date, end_date)
        ).all()
        
        total_collected = 0
        for p in payments:
            total_collected += p.amount
            q = (p.payment_date.month - 1) // 3 + 1
            quarterly_payments[q] += p.amount
        
        quarters = {
            'Q1': quarterly_payments[1],
            'Q2': quarterly_payments[2],
            'Q3': quarterly_payments[3],
            'Q4': quarterly_payments[4]
        }
        
        # Previous year for growth calculation
        prev_start = date(year - 1, 1, 1)
        prev_end = date(year - 1, 12, 31)
        prev_payments = self.db.query(Payment).filter(
            Payment.payment_date.between(prev_start, prev_end)
        ).all()
        prev_total = sum(p.amount for p in prev_payments)
        
        growth_rate = ((total_collected - prev_total) / prev_total * 100) if prev_total > 0 else 0
        
        # Total pledged for the year
        debts = self.db.query(Debt).filter(
            Debt.commitment_date.between(start_date, end_date)
        ).all()
        total_pledged = sum(d.total_amount for d in debts)
        
        # Active members
        active_members = self.db.query(Member).count()
        
        # Monthly breakdown for chart
        monthly_data = []
        for month in range(1, 13):
            month_start = date(year, month, 1)
            if month == 12:
                month_end = date(year, 12, 31)
            else:
                month_end = date(year, month + 1, 1) - timedelta(days=1)
            
            month_payments = self.db.query(Payment).filter(
                Payment.payment_date.between(month_start, month_end)
            ).all()
            month_total = sum(p.amount for p in month_payments)
            monthly_data.append({
                'month': calendar.month_name[month][:3],
                'amount': month_total
            })
        
        return {
            'year': year,
            'total_collected': total_collected,
            'total_pledged': total_pledged,
            'growth_rate': growth_rate,
            'active_members': active_members,
            'quarters': quarters,
            'monthly_data': monthly_data
        }
    
    def payment_history(self, start_date, end_date):
        """Generate payment history report"""
        payments = self.db.query(Payment).join(Member, Payment.member_id == Member.member_id).join(
            Debt, Payment.debt_id == Debt.debt_id
        ).filter(
            Payment.payment_date.between(start_date, end_date)
        ).order_by(Payment.payment_date.desc()).all()
        
        payment_list = []
        total_amount = 0
        
        for p in payments:
            total_amount += p.amount
            payment_list.append({
                'date': p.payment_date.strftime('%d %b %Y'),
                'receipt': p.receipt_number,
                'member_name': p.member.name,
                'member_phone': p.member.phone,
                'debt_type': p.debt.debt_type.value,
                'amount': p.amount,
                'method': p.payment_method,
                'transaction_id': p.transaction_id or '-'
            })
        
        return {
            'payments': payment_list,
            'total_amount': total_amount,
            'total_count': len(payment_list),
            'start_date': start_date,
            'end_date': end_date
        }
    
    def completed_pledges(self, start_date, end_date):
        """Generate completed pledges report"""
        pledges = self.db.query(Debt).join(Member).filter(
            Debt.status == PaymentStatus.PAID,
            Debt.completed_date.between(start_date, end_date)
        ).all()
        
        pledge_list = []
        total_amount = 0
        
        for d in pledges:
            total_amount += d.total_amount
            days_diff = (d.completed_date - d.due_date).days if d.due_date else 0
            pledge_list.append({
                'member_name': d.member.name,
                'phone': d.member.phone,
                'email': d.member.email or '—',
                'debt_type': d.debt_type.value,
                'total_amount': d.total_amount,
                'completed_date': d.completed_date.strftime('%d %b %Y'),
                'due_date': d.due_date.strftime('%d %b %Y') if d.due_date else 'N/A',
                'days_diff': days_diff
            })
        
        return {
        'pledges': pledge_list,
        'completed_count': len(pledge_list),
        'total_amount': total_amount,
        'start_date': start_date,
        'end_date': end_date
    }
    
    def export_to_excel(self, report_type, data, title, period):
        """Export report data to Excel file"""
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if report_type == 'financial_summary':
                df = pd.DataFrame([{
                    'Metric': 'Total Pledged',
                    'Amount (Tsh)': data['total_pledged']
                }, {
                    'Metric': 'Total Collected',
                    'Amount (Tsh)': data['total_collected']
                }, {
                    'Metric': 'Outstanding Balance',
                    'Amount (Tsh)': data['outstanding']
                }, {
                    'Metric': 'Completion Rate (%)',
                    'Amount (Tsh)': data['completion_rate']
                }, {
                    'Metric': 'Active Pledges',
                    'Amount (Tsh)': data['active_pledges']
                }, {
                    'Metric': 'Completed Pledges',
                    'Amount (Tsh)': data['completed_pledges']
                }, {
                    'Metric': 'Overdue Pledges',
                    'Amount (Tsh)': data['overdue_pledges']
                }])
                df.to_excel(writer, sheet_name='Financial Summary', index=False)
            
            elif report_type == 'pledges_by_type':
                df = pd.DataFrame(data['pledge_types'])
                df.to_excel(writer, sheet_name='Pledges by Type', index=False)
            
            elif report_type == 'overdue_pending':
                if data['overdue']:
                    df_overdue = pd.DataFrame(data['overdue'])
                    df_overdue.to_excel(writer, sheet_name='Overdue Pledges', index=False)
                if data['pending']:
                    df_pending = pd.DataFrame(data['pending'])
                    df_pending.to_excel(writer, sheet_name='Pending Pledges', index=False)
            
            elif report_type == 'monthly_collection':
                df_weekly = pd.DataFrame(data['weekly_breakdown'])
                df_methods = pd.DataFrame(data['payment_methods'])
                df_top = pd.DataFrame(data['top_members'])
                df_weekly.to_excel(writer, sheet_name='Weekly Breakdown', index=False)
                df_methods.to_excel(writer, sheet_name='Payment Methods', index=False)
                df_top.to_excel(writer, sheet_name='Top Contributors', index=False)
            
            elif report_type == 'member_statement':
                df = pd.DataFrame([{
                    'Name': data['member']['name'],
                    'Phone': data['member']['phone'],
                    'Email': data['member']['email'],
                    'Total Pledged': data['total_pledged'],
                    'Total Paid': data['total_paid'],
                    'Outstanding': data['outstanding']
                }])
                df.to_excel(writer, sheet_name='Member Info', index=False)
                
                if data['pledges']:
                    payments_list = []
                    for pledge in data['pledges']:
                        for payment in pledge['payments']:
                            payments_list.append({
                                'Pledge Type': pledge['debt_type'],
                                'Date': payment['date'],
                                'Receipt': payment['receipt'],
                                'Amount': payment['amount'],
                                'Method': payment['method']
                            })
                    if payments_list:
                        df_payments = pd.DataFrame(payments_list)
                        df_payments.to_excel(writer, sheet_name='Payment History', index=False)
            
            elif report_type == 'yearly_summary':
                df_quarters = pd.DataFrame([data['quarters']])
                df_monthly = pd.DataFrame(data['monthly_data'])
                df_quarters.to_excel(writer, sheet_name='Quarterly Summary', index=False)
                df_monthly.to_excel(writer, sheet_name='Monthly Breakdown', index=False)
            
            elif report_type == 'payment_history':
                df = pd.DataFrame(data['payments'])
                df.to_excel(writer, sheet_name='Payment History', index=False)
            
            elif report_type == 'completed_pledges':
                df = pd.DataFrame(data['pledges'])
                df.to_excel(writer, sheet_name='Completed Pledges', index=False)
        
        output.seek(0)
        return output