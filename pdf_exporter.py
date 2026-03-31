# app/pdf_exporter.py
from __future__ import annotations
from datetime import date
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

class PDFExporter:
    """Export reports to PDF format"""
    
    def __init__(self, church_name="KKKT CHANGANYIKENI"):
        self.church_name = church_name
        self.styles = self._create_styles()
    
    def _create_styles(self):
        """Create custom styles for PDF"""
        styles = getSampleStyleSheet()
        
        # Title style
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30,
            alignment=1
        )
        
        # Heading style
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#3498db'),
            spaceAfter=12,
            spaceBefore=20
        )
        
        # Subheading style
        subheading_style = ParagraphStyle(
            'CustomSubheading',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#7f8c8d'),
            spaceAfter=10
        )
        
        # Normal style
        normal_style = styles['Normal']
        
        # Footer style
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#95a5a6'),
            alignment=1
        )
        
        return {
            'title': title_style,
            'heading': heading_style,
            'subheading': subheading_style,
            'normal': normal_style,
            'footer': footer_style
        }
    
    def _format_currency(self, amount):
        """Format currency with Tsh and commas"""
        return f"Tsh {amount:,.0f}"
    
    def _format_percentage(self, percentage):
        """Format percentage"""
        return f"{percentage:.1f}%"
    
    def _add_header_footer(self, canvas, doc):
        """Add header and footer to each page"""
        canvas.saveState()
        
        # Header
        canvas.setFont('Helvetica-Bold', 10)
        canvas.setFillColor(colors.HexColor('#3498db'))
        canvas.drawString(72, doc.height + doc.topMargin - 20, self.church_name)
        
        # Footer
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#95a5a6'))
        footer_text = f"Generated on {date.today().strftime('%d %b %Y')} | Stewardship Reminder System"
        canvas.drawString(72, 30, footer_text)
        canvas.drawRightString(doc.width + 72 - 72, 30, f"Page {doc.page}")
        
        canvas.restoreState()
    
    def export_financial_summary(self, data, title, period):
        """Export financial summary to PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=72)
        doc.build(self._build_financial_summary(data, title, period),
                  onFirstPage=self._add_header_footer,
                  onLaterPages=self._add_header_footer)
        buffer.seek(0)
        return buffer
    
    def _build_financial_summary(self, data, title, period):
        """Build financial summary PDF content"""
        story = []
        
        # Title
        story.append(Paragraph(title, self.styles['title']))
        story.append(Paragraph(f"Period: {period}", self.styles['subheading']))
        story.append(Spacer(1, 20))
        
        # Summary Table
        summary_data = [
            ['Metric', 'Amount'],
            ['Total Pledged', self._format_currency(data['total_pledged'])],
            ['Total Collected', self._format_currency(data['total_collected'])],
            ['Outstanding Balance', self._format_currency(data['outstanding'])],
            ['Completion Rate', self._format_percentage(data['completion_rate'])],
            ['Active Pledges', str(data['active_pledges'])],
            ['Completed Pledges', str(data['completed_pledges'])],
            ['Overdue Pledges', str(data['overdue_pledges'])]
        ]
        
        table = Table(summary_data, colWidths=[200, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        story.append(table)
        
        return story
    
    def export_pledges_by_type(self, data, title, period):
        """Export pledges by type to PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=72)
        doc.build(self._build_pledges_by_type(data, title, period),
                  onFirstPage=self._add_header_footer,
                  onLaterPages=self._add_header_footer)
        buffer.seek(0)
        return buffer
    
    def _build_pledges_by_type(self, data, title, period):
        """Build pledges by type PDF content"""
        story = []
        
        story.append(Paragraph(title, self.styles['title']))
        story.append(Paragraph(f"Period: {period}", self.styles['subheading']))
        story.append(Spacer(1, 20))
        
        table_data = [['Debt Type', 'Total Pledged', 'Collected', 'Balance', 'Progress']]
        for t in data['pledge_types']:
            table_data.append([
                t['name'],
                self._format_currency(t['total']),
                self._format_currency(t['collected']),
                self._format_currency(t['balance']),
                self._format_percentage(t['percentage'])
            ])
        
        table_data.append([
            'TOTAL',
            self._format_currency(data['total_pledged']),
            self._format_currency(data['total_collected']),
            self._format_currency(data['total_balance']),
            self._format_percentage(data['overall_percentage'])
        ])
        
        table = Table(table_data, colWidths=[120, 100, 100, 100, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        story.append(table)
        
        return story
    
    def export_overdue_pending(self, data, title, period):
        """Export overdue and pending to PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=72)
        doc.build(self._build_overdue_pending(data, title, period),
                  onFirstPage=self._add_header_footer,
                  onLaterPages=self._add_header_footer)
        buffer.seek(0)
        return buffer
    
    def _build_overdue_pending(self, data, title, period):
        """Build overdue and pending PDF content"""
        story = []
        
        story.append(Paragraph(title, self.styles['title']))
        story.append(Paragraph(f"Period: {period}", self.styles['subheading']))
        story.append(Spacer(1, 20))
        
        if data['overdue']:
            story.append(Paragraph("Overdue Pledges", self.styles['heading']))
            
            overdue_data = [['Member', 'Phone', 'Debt Type', 'Balance', 'Due Date', 'Days Overdue']]
            for d in data['overdue']:
                overdue_data.append([
                    d['member_name'], d['phone'], d['debt_type'],
                    self._format_currency(d['balance']), d['due_date'], str(d['days_overdue'])
                ])
            
            table = Table(overdue_data, colWidths=[100, 90, 100, 90, 80, 70])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
            ]))
            story.append(table)
            story.append(Spacer(1, 20))
        
        if data['pending']:
            story.append(Paragraph("Pending Pledges", self.styles['heading']))
            
            pending_data = [['Member', 'Phone', 'Debt Type', 'Balance', 'Due Date']]
            for d in data['pending']:
                pending_data.append([
                    d['member_name'], d['phone'], d['debt_type'],
                    self._format_currency(d['balance']), d['due_date']
                ])
            
            table = Table(pending_data, colWidths=[100, 90, 100, 90, 80])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f39c12')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
            ]))
            story.append(table)
        
        return story
    
    def export_monthly_collection(self, data, title, period):
        """Export monthly collection to PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=72)
        doc.build(self._build_monthly_collection(data, title, period),
                  onFirstPage=self._add_header_footer,
                  onLaterPages=self._add_header_footer)
        buffer.seek(0)
        return buffer
    
    def _build_monthly_collection(self, data, title, period):
        """Build monthly collection PDF content"""
        story = []
        
        story.append(Paragraph(title, self.styles['title']))
        story.append(Paragraph(f"Period: {period}", self.styles['subheading']))
        story.append(Spacer(1, 20))
        
        summary_data = [
            ['Total Collected', self._format_currency(data['total_collected'])],
            ['Total Payments', str(data['total_payments'])],
            ['Average Payment', self._format_currency(data['avg_payment'])]
        ]
        
        table = Table(summary_data, colWidths=[150, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
        ]))
        story.append(table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("Weekly Breakdown", self.styles['heading']))
        
        week_data = [['Week', 'Payments', 'Amount', 'Percentage']]
        for w in data['weekly_breakdown']:
            week_data.append([
                str(w['week']), str(w['payment_count']),
                self._format_currency(w['amount']), self._format_percentage(w['percentage'])
            ])
        
        table = Table(week_data, colWidths=[80, 80, 120, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        story.append(table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("Payment Methods", self.styles['heading']))
        
        method_data = [['Method', 'Amount', 'Percentage']]
        for m in data['payment_methods']:
            method_data.append([
                m['name'], self._format_currency(m['amount']), self._format_percentage(m['percentage'])
            ])
        
        table = Table(method_data, colWidths=[120, 120, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        story.append(table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("Top Contributors", self.styles['heading']))
        
        top_data = [['Member', 'Amount']]
        for t in data['top_members']:
            top_data.append([t['name'], self._format_currency(t['amount'])])
        
        table = Table(top_data, colWidths=[200, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f39c12')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        story.append(table)
        
        return story
    
    def export_member_statement(self, data, title, period):
        """Export member statement to PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=72)
        doc.build(self._build_member_statement(data, title, period),
                  onFirstPage=self._add_header_footer,
                  onLaterPages=self._add_header_footer)
        buffer.seek(0)
        return buffer
    
    def _build_member_statement(self, data, title, period):
        """Build member statement PDF content"""
        story = []
        
        story.append(Paragraph(title, self.styles['title']))
        story.append(Paragraph(f"Member: {data['member']['name']}", self.styles['heading']))
        story.append(Paragraph(f"Phone: {data['member']['phone']}", self.styles['normal']))
        story.append(Paragraph(f"Email: {data['member']['email'] or 'N/A'}", self.styles['normal']))
        story.append(Paragraph(f"Member Since: {data['member']['joined_date']}", self.styles['normal']))
        story.append(Spacer(1, 20))
        
        summary_data = [
            ['Total Pledged', 'Total Paid', 'Outstanding'],
            [
                self._format_currency(data['total_pledged']),
                self._format_currency(data['total_paid']),
                self._format_currency(data['outstanding'])
            ]
        ]
        
        table = Table(summary_data, colWidths=[150, 150, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
        ]))
        story.append(table)
        story.append(Spacer(1, 20))
        
        for pledge in data['pledges']:
            story.append(Paragraph(f"{pledge['debt_type']} - {pledge['debt_number']}", self.styles['heading']))
            
            pledge_data = [
                ['Total', 'Paid', 'Balance', 'Due Date', 'Status'],
                [
                    self._format_currency(pledge['total_amount']),
                    self._format_currency(pledge['amount_paid']),
                    self._format_currency(pledge['balance']),
                    pledge['due_date'],
                    pledge['status']
                ]
            ]
            
            table = Table(pledge_data, colWidths=[100, 100, 100, 100, 80])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey)
            ]))
            story.append(table)
            
            if pledge['payments']:
                story.append(Spacer(1, 10))
                story.append(Paragraph("Payment History", self.styles['subheading']))
                
                payment_data = [['Date', 'Receipt', 'Amount', 'Method']]
                for p in pledge['payments']:
                    payment_data.append([
                        p['date'], p['receipt'],
                        self._format_currency(p['amount']), p['method']
                    ])
                
                table = Table(payment_data, colWidths=[100, 120, 100, 100])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey)
                ]))
                story.append(table)
            
            story.append(Spacer(1, 20))
        
        return story
    
    def export_yearly_summary(self, data, title, period):
        """Export yearly summary to PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=72)
        doc.build(self._build_yearly_summary(data, title, period),
                  onFirstPage=self._add_header_footer,
                  onLaterPages=self._add_header_footer)
        buffer.seek(0)
        return buffer
    
    def _build_yearly_summary(self, data, title, period):
        """Build yearly summary PDF content"""
        story = []
        
        story.append(Paragraph(title, self.styles['title']))
        story.append(Paragraph(f"Year: {data['year']}", self.styles['subheading']))
        story.append(Spacer(1, 20))
        
        summary_data = [
            ['Total Collected', self._format_currency(data['total_collected'])],
            ['Total Pledged', self._format_currency(data['total_pledged'])],
            ['Growth Rate', f"{data['growth_rate']:+.1f}%"],
            ['Active Members', str(data['active_members'])]
        ]
        
        table = Table(summary_data, colWidths=[150, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
        ]))
        story.append(table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("Quarterly Breakdown", self.styles['heading']))
        
        quarter_data = [['Quarter', 'Amount']]
        for q, amt in data['quarters'].items():
            quarter_data.append([q, self._format_currency(amt)])
        
        table = Table(quarter_data, colWidths=[100, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f39c12')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        story.append(table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("Monthly Breakdown", self.styles['heading']))
        
        monthly_data = [['Month', 'Amount']]
        for m in data['monthly_data']:
            monthly_data.append([m['month'], self._format_currency(m['amount'])])
        
        table = Table(monthly_data, colWidths=[100, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        story.append(table)
        
        return story
    
    def export_payment_history(self, data, title, period):
        """Export payment history to PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=72)
        doc.build(self._build_payment_history(data, title, period),
                  onFirstPage=self._add_header_footer,
                  onLaterPages=self._add_header_footer)
        buffer.seek(0)
        return buffer
    
    def _build_payment_history(self, data, title, period):
        """Build payment history PDF content"""
        story = []
        
        story.append(Paragraph(title, self.styles['title']))
        story.append(Paragraph(f"Period: {period}", self.styles['subheading']))
        story.append(Spacer(1, 20))
        
        story.append(Paragraph(f"Total: {self._format_currency(data['total_amount'])} from {data['total_count']} payments", 
                              self.styles['heading']))
        story.append(Spacer(1, 20))
        
        payment_data = [['Date', 'Receipt', 'Member', 'Amount', 'Method', 'Transaction ID']]
        for p in data['payments'][:100]:
            payment_data.append([
                p['date'], p['receipt'], p['member_name'],
                self._format_currency(p['amount']), p['method'], p['transaction_id']
            ])
        
        if len(data['payments']) > 100:
            payment_data.append(['...', '...', f"and {len(data['payments']) - 100} more records", '...', '...', '...'])
        
        table = Table(payment_data, colWidths=[80, 100, 100, 80, 80, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        story.append(table)
        
        return story
    
    def export_completed_pledges(self, data, title, period):
        """Export completed pledges to PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=72)
        doc.build(self._build_completed_pledges(data, title, period),
                  onFirstPage=self._add_header_footer,
                  onLaterPages=self._add_header_footer)
        buffer.seek(0)
        return buffer
    
    def _build_completed_pledges(self, data, title, period):
        """Build completed pledges PDF content"""
        story = []
        
        story.append(Paragraph(title, self.styles['title']))
        story.append(Paragraph(f"Period: {period}", self.styles['subheading']))
        story.append(Spacer(1, 20))
        
        story.append(Paragraph(f"Completed Pledges: {data['completed_count']}", self.styles['heading']))
        story.append(Paragraph(f"Total Amount: {self._format_currency(data['total_amount'])}", self.styles['normal']))
        story.append(Spacer(1, 20))
        
        pledges_data = [['Member', 'Phone', 'Debt Type', 'Amount', 'Completed Date', 'Due Date']]
        for p in data['pledges']:
            pledges_data.append([
                p['member_name'], p['phone'], p['debt_type'],
                self._format_currency(p['total_amount']), p['completed_date'], p['due_date']
            ])
        
        table = Table(pledges_data, colWidths=[100, 90, 100, 100, 90, 90])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))
        story.append(table)
        
        return story