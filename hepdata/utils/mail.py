from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP

from celery import shared_task

from hepdata import config

@shared_task
def send_email(destination, subject, message):
    try:
        connection = connect()
        mmp_msg = MIMEMultipart('alternative')
        mmp_msg['Subject'] = subject
        mmp_msg['From'] = config.MAIL_DEFAULT_SENDER
        mmp_msg['To'] = destination

        part1 = MIMEText(message, 'html')
        mmp_msg.attach(part1)

        connection.sendmail(config.MAIL_DEFAULT_SENDER, destination, mmp_msg.as_string())
        connection.quit()
    except Exception as e:
        print 'Exception occurred.'
        raise e


def connect():
    smtp = SMTP()
    smtp.connect(config.MAIL_SERVER, config.MAIL_PORT)
    if not config.SMTP_NO_PASSWORD:
        smtp.login(config.MAIL_DEFAULT_SENDER, config.MAIL_PASSWORD)

    return smtp
