import requests
import os
import logging
from typing import Optional
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SMSService:
    """SMS service for sending reminders to debtors"""
    
    def __init__(self):
        # Load configuration from environment
        self.provider = os.getenv("SMS_PROVIDER", "mock")  # mock, africastalking, twilio
        print("PROVIDER:", self.provider)
        self.api_key = os.getenv("SMS_API_KEY", "")
        self.username = os.getenv("SMS_USERNAME", "sandbox")
        self.sender_id = os.getenv("SMS_SENDER_ID", "Stewardship")
        
        logger.info(f"SMS Service initialized with provider: {self.provider}")
    
    def send_sms(self, phone: str, message: str) -> tuple[bool, Optional[str]]:
        """
        Send SMS to a phone number
        Returns: (success, error_message)
        """
        try:
            # Format phone number
            phone = self._format_phone(phone)
            
            if not phone:
                return False, "Invalid phone number"
            
            # Send based on provider
            if self.provider == "beem":
                return self._send_beem(phone, message)
            elif self.provider == "africastalking":
                return self._send_africastalking(phone, message)
            elif self.provider == "twilio":
                return self._send_twilio(phone, message)
            else:
                return self._send_mock(phone, message)
                
        except Exception as e:
            logger.error(f"SMS sending failed: {str(e)}")
            return False, str(e)
    
    def _format_phone(self, phone: str) -> Optional[str]:
        """Format phone number to international format"""
        if not phone:
            return None
        
        # Remove any non-numeric characters
        phone = re.sub(r'\D', '', str(phone))
        
        # Handle Tanzanian/Nigerian numbers
        if phone.startswith('0'):
            # Assume Tanzania (255) or Nigeria (234) - default to Tanzania
            phone = '255' + phone[1:]
        elif phone.startswith('+'):
            phone = phone[1:]
        elif not phone.startswith('255') and not phone.startswith('234'):
            # If no country code, assume Tanzania
            phone = '255' + phone
        
        # Ensure minimum length
        if len(phone) < 10:
            return None
        
        return phone
    
    def _send_mock(self, phone: str, message: str) -> tuple[bool, Optional[str]]:
        """Mock SMS sending for testing"""
        logger.info(f"[MOCK SMS] To: {phone}")
        logger.info(f"[MOCK SMS] Message: {message[:50]}...")
        
        # Simulate successful send
        print(f"\n📱 SIMULATED SMS")
        print(f"   To: {phone}")
        print(f"   From: {self.sender_id}")
        print(f"   Message: {message}")
        print(f"   { '-' * 40 }\n")
        
        return True, None
    def _send_beem(self, phone: str, message: str) -> tuple[bool, Optional[str]]:
        """Send SMS via Beem Africa"""
        
        url = "https://apisms.beem.africa/v1/send"
        
        api_key = os.getenv("BEEM_API_KEY")
        secret_key = os.getenv("BEEM_SECRET_KEY")
        
        if not api_key or not secret_key:
            return False, "Beem credentials not configured"
        
        import base64
        
        # Create Basic Auth header correctly
        auth_string = f"{api_key}:{secret_key}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_auth}"
        }
        
        # Remove spaces from sender ID - Beem may reject spaces
        sender_id = self.sender_id.replace(" ", "").upper()
        
        payload = {
            "source_addr": sender_id,
            "encoding": 0,
            "schedule_time": "",
            "message": message,
            "recipients": [
                {
                    "recipient_id": 1,
                    "dest_addr": phone
                }
            ]
        }
        
        # DEBUG: Print what we're sending
        print(f"\n📤 BEEM DEBUG - Sending:")
        print(f"   Phone: {phone}")
        print(f"   Sender ID: {sender_id}")
        print(f"   Message: {message[:50]}...")
        print(f"   API Key: {api_key[:10]}...")
        print(f"   Auth Header: Basic {encoded_auth[:20]}...")
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            # DEBUG: Print full response
            print(f"\n📥 BEEM DEBUG - Response:")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response Body: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Beem returns code 100 (integer) for success
                if data.get("code") == 100:
                    request_id = data.get("data", {}).get("request_id") if data.get("data") else "N/A"
                    print(f"   ✅ SUCCESS! Request ID: {request_id}")
                    logger.info(f"Beem SMS sent to {phone}, Request ID: {request_id}")
                    return True, None
                else:
                    error_msg = data.get("message", "Unknown Beem error")
                    print(f"   ❌ BEEM REJECTED: {error_msg}")
                    logger.error(f"Beem failed: {error_msg}")
                    return False, error_msg
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                print(f"   ❌ HTTP ERROR: {error_msg}")
                return False, error_msg
                
        except requests.exceptions.Timeout:
            return False, "Beem API timeout - please try again"
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to Beem API - check internet"
        except requests.exceptions.RequestException as e:
            return False, f"Network error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    
    def _send_twilio(self, phone: str, message: str) -> tuple[bool, Optional[str]]:
        """Send via Twilio"""
        try:
            from twilio.rest import Client
            
            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            
            if not account_sid or not auth_token:
                return False, "Twilio credentials not configured"
            
            client = Client(account_sid, auth_token)
            
            twilio_phone = os.getenv("TWILIO_PHONE_NUMBER", self.sender_id)
            
            response = client.messages.create(
                body=message,
                from_=twilio_phone,
                to=phone
            )
            
            if response.sid:
                logger.info(f"Twilio SMS sent successfully: {response.sid}")
                return True, None
            else:
                return False, "Twilio send failed"
                
        except ImportError:
            return False, "Twilio library not installed"
        except Exception as e:
            error = f"Twilio error: {str(e)}"
            logger.error(error)
            return False, error
    
    def send_bulk_sms(self, recipients: list[tuple[str, str]], message_template: str) -> dict:
        """
        Send bulk SMS to multiple recipients
        recipients: list of (phone, name)
        message_template: template string with {name} placeholder
        """
        results = {
            "total": len(recipients),
            "success": 0,
            "failed": 0,
            "errors": []
        }
        
        for phone, name in recipients:
            # Personalize message
            personalized_msg = message_template.replace("{name}", name)
            
            success, error = self.send_sms(phone, personalized_msg)
            
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({
                    "phone": phone,
                    "name": name,
                    "error": error
                })
        
        return results


class MessageTemplates:
    """SMS message templates"""
    
    @staticmethod
    def pledge_reminder(name: str, amount: float, due_date: str, balance: float) -> str:
        return f"""Dear {name},

REMINDER: Your pledge of Tsh{amount:,.0f} is due on {due_date}.
Paid: Tsh{amount - balance:,.0f} | Balance: Tsh{balance:,.0f}

Thank you for your faithfulness!
- KKKT CHANGANYIKENI"""

    @staticmethod
    def payment_thankyou(name: str, amount: float, receipt: str, balance: float) -> str:
        if balance <= 0:
            return f"""Dear {name},

🎉 THANK YOU for completing your pledge of Tsh{amount:,.0f}!
Receipt: {receipt}

God bless you abundantly!
- KKKT CHANGANYIKENI"""
        else:
            return f"""Dear {name},

Thank you for your payment of Tsh{amount:,.0f}!
Receipt: {receipt}
Remaining balance: Tsh{balance:,.0f}

- KKKT CHANGANYIKENI"""

    @staticmethod
    def overdue_reminder(name: str, amount: float, days_overdue: int, balance: float) -> str:
        return f"""Dear {name},

URGENT: Your pledge of Tsh{amount:,.0f} is {days_overdue} days overdue.
Outstanding balance: Tsh{balance:,.0f}

Please contact us to arrange payment.
- KKKT CHANGANYIKENI"""

    @staticmethod
    def welcome_message(name: str, debt_type: str, amount: float, due_date: str) -> str:
        return f"""Dear {name},

Welcome! Your {debt_type} pledge of Tsh{amount:,.0f} has been recorded.
Due date: {due_date}

Thank you for your generosity!
- KKKT CHANGANYIKENI"""

    @staticmethod
    def edit_confirmation(name: str, debt_type: str, total_amount: float, balance: float, due_date: str) -> str:
        return f"""Dear {name},

Your {debt_type} pledge has been updated.
New total: Tsh{total_amount:,.0f}
Remaining balance: Tsh{balance:,.0f}
Due date: {due_date}

Thank you for your faithfulness!
- KKKT CHANGANYIKENI"""
