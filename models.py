from __future__ import annotations

from datetime import datetime, date
from sqlalchemy import Date, Integer, String, Float, Boolean, DateTime, Text, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from .db import Base

class DebtType(enum.Enum):
    BUILDING_FUND = "Building Fund"
    AUCTION = "Auction"
    WELFARE_LEVY = "Welfare Levy"
    YOUTH_CAMP_FEE = "Youth Camp Fee"
    HARVEST = "Harvest"
    MISSION = "Mission"
    OTHER = "Other"

class PaymentStatus(enum.Enum):
    PENDING = "Pending"
    PARTIAL = "Partial"
    PAID = "Paid"
    OVERDUE = "Overdue"
    CANCELLED = "Cancelled"

class Member(Base):
    __tablename__ = "members"
    
    member_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Optional fields
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    joined_date: Mapped[date] = mapped_column(Date, default=date.today)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Metadata
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    debts: Mapped[list["Debt"]] = relationship(back_populates="member", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="member", cascade="all, delete-orphan")
    reminders: Mapped[list["ReminderLog"]] = relationship(back_populates="member", cascade="all, delete-orphan")

class Debt(Base):
    __tablename__ = "debts"
    
    debt_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(Integer, ForeignKey("members.member_id", ondelete="CASCADE"))
    
    # Debt details
    debt_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    debt_type: Mapped[DebtType] = mapped_column(Enum(DebtType), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Financial details
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    amount_paid: Mapped[float] = mapped_column(Float, default=0.0)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Dates
    commitment_date: Mapped[date] = mapped_column(Date, default=date.today)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # Status
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    
    # Reminder settings
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reminder_sent: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Metadata
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    member: Mapped["Member"] = relationship(back_populates="debts")
    payments: Mapped[list["Payment"]] = relationship(back_populates="debt", cascade="all, delete-orphan")
    reminders: Mapped[list["ReminderLog"]] = relationship(back_populates="debt", cascade="all, delete-orphan")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-generate debt number
        if not self.debt_number:
            date_str = datetime.now().strftime("%Y%m")
            self.receipt_number = f"RCP{date_str}{int(datetime.now().timestamp())}"
    
    def update_status(self):
        """Update status based on balance and due date"""
        if self.balance <= 0:
            self.status = PaymentStatus.PAID
            self.completed_date = date.today()
        elif self.due_date < date.today() and self.balance > 0:
            self.status = PaymentStatus.OVERDUE
        elif self.amount_paid > 0:
            self.status = PaymentStatus.PARTIAL
        else:
            self.status = PaymentStatus.PENDING

class Payment(Base):
    __tablename__ = "payments"
    
    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    debt_id: Mapped[int] = mapped_column(Integer, ForeignKey("debts.debt_id", ondelete="CASCADE"))
    member_id: Mapped[int] = mapped_column(Integer, ForeignKey("members.member_id", ondelete="CASCADE"))
    
    # Payment details
    receipt_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, default=date.today)
    
    # Payment method
    payment_method: Mapped[str] = mapped_column(String(50), default="Cash")
    transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Metadata
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    
    # Relationships
    debt: Mapped["Debt"] = relationship(back_populates="payments")
    member: Mapped["Member"] = relationship(back_populates="payments")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-generate receipt number
        if not self.receipt_number:
            date_str = datetime.now().strftime("%Y%m%d")
            self.receipt_number = f"RCP{date_str}{int(datetime.now().timestamp())}"

class ReminderLog(Base):
    __tablename__ = "reminder_logs"
    
    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(Integer, ForeignKey("members.member_id", ondelete="CASCADE"))
    debt_id: Mapped[int] = mapped_column(Integer, ForeignKey("debts.debt_id", ondelete="CASCADE"))
    
    reminder_type: Mapped[str] = mapped_column(String(20))  # Email, SMS
    recipient: Mapped[str] = mapped_column(String(100))  # email or phone
    message: Mapped[Text] = mapped_column(Text)
    
    status: Mapped[str] = mapped_column(String(20))  # Sent, Failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    
    # Relationships
    member: Mapped["Member"] = relationship(back_populates="reminders")
    debt: Mapped["Debt"] = relationship(back_populates="reminders")