# This file is part of HEPData.
# Copyright (C) 2016 CERN.
#
# HEPData is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# HEPData is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HEPData; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.


"""Provides high-level common email utilities."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP, SMTPRecipientsRefused

from celery import shared_task
from flask import current_app
from flask_celeryext import create_celery_app


def create_send_email_task(destination, subject, message, reply_to_address=None):
    """
    Schedules a task to send an email.

    :param destination:
    :param subject:
    :param message:
    :param reply_to_address:
    :return: send_email
    """

    # this is required for some unknown reason due to an initialisation problem with celery.
    if not current_app.config.get('TESTING', False):
        create_celery_app(current_app)
        print('Sending email to {0}'.format(destination))
        send_email.delay(destination, subject, message, reply_to_address)
    else:
        print('Not sending email as TESTING=True; would have sent email to {0}:'.format(destination))
        import re
        clean = re.compile('(?s)<.*?>')
        newlines = re.compile(r'(?ms)(\n(\s*)){2,}')
        print(re.sub(newlines, '\n', re.sub(clean, '', message)))


@shared_task
def send_email(destination, subject, message, reply_to_address=None):
    try:
        connection = connect()
        mmp_msg = MIMEMultipart('alternative')
        mmp_msg['Subject'] = subject
        mmp_msg['From'] = reply_to_address if reply_to_address else current_app.config['MAIL_DEFAULT_SENDER']
        mmp_msg['To'] = destination

        part1 = MIMEText(message, 'html', 'utf-8')
        mmp_msg.attach(part1)

        recipients = destination.split(',')
        recipients.append(current_app.config['ADMIN_EMAIL'])

        connection.send_message(mmp_msg, current_app.config['MAIL_DEFAULT_SENDER'], recipients)
        connection.quit()
    except SMTPRecipientsRefused as smtp_error:
        send_error_mail(smtp_error)
    except Exception as e:
        print('Exception occurred.')
        raise e


def send_error_mail(exception):
    """
    Sends an error email to the default system email (which should always be valid!).

    :param exception: SMTPRecipientsRefused exception
    """
    # get default
    destination_email = current_app.config['SECURITY_EMAIL_SENDER']
    create_send_email_task(destination_email, '[HEPData Error] Error sending email', str(exception))


def connect():
    smtp = SMTP()
    smtp.connect(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT'])
    if not current_app.config['SMTP_NO_PASSWORD']:
        if current_app.config['SMTP_ENCRYPTION']:
            smtp.starttls()
        smtp.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])

    return smtp
