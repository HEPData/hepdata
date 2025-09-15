#
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

"""
HEPData email module test cases.
Used to specifically test email sending call functions.
"""
import re

from unittest.mock import patch, MagicMock

from .conftest import create_record_with_participant
from hepdata.modules.submission.models import SubmissionObserver
from hepdata.modules.email.api import send_cookie_email, notify_submission_created


def test_send_cookie_email(app):
    """
    Basic testing of the send_cookie_email method.
    Tests expected output (argument calls) of the create_send_email_task function.
    """

    test_submission, test_participant, record_information = create_record_with_participant()

    message = "TestMessage"

    # Set up the patch for call access then run
    with patch("hepdata.modules.email.api.create_send_email_task", side_effect=None) as task_patch:
        # Execute the test function
        send_cookie_email(test_participant, record_information, message=message)
        # Check to see if the email function was properly called
        task_patch.assert_called_once()

        # Get the arguments used from the function call
        called_args = task_patch.call_args.args
        called_kwargs = task_patch.call_args.kwargs

        # Check email was used in task call, and as recipient email
        assert called_args[0] == test_participant.email
        assert called_kwargs["reply_to_address"] == test_participant.email

        # TODO - Expand to further check email contents
        # Confirm existence of message sent in email
        assert message in called_args[2]

def test_notify_submission_created(app):
    """
    Tests the notify_submission_created function to ensure that the submission observer
    key is being properly inserted into the creation email.

    Currently only checking for the existence of the observer key.
    """
    test_submission, test_participant, record_information = create_record_with_participant()

     # Test sending the initial submission creation email
    with patch("hepdata.modules.email.api.create_send_email_task", side_effect=None) as task_patch:

        test_recid = test_submission.publication_recid
        # Creating a valid user object for rendering with full_name and email
        user = MagicMock(full_name="HEPData User", email="e@mail.com")

        # Execute the target function
        notify_submission_created(record_information, test_submission.coordinator, user, user)

        task_patch.assert_called_once()
        called_args = task_patch.call_args.args

        # called_args[2] should contain the result of render_template on email/created.html
        # Also discard everything prior to what we require
        base_text = called_args[2].split("special permissions:")[1]

        # Get the contents of anchor tags
        match = re.search(r'<a href="(.*?)">(.*?)</a>', base_text)

        # Check that they are both properly selected
        try:
            anchor_url = match.group(1)
            anchor_text = match.group(2)
        except IndexError:
            raise AssertionError(f"Value for anchor_url: {anchor_url}/anchor_text: {anchor_text} is invalid")

        # Get SubmissionObserver to get key
        test_observer = SubmissionObserver.query.filter_by(publication_recid=test_recid).first()

        # Build expected URL for verification
        site_url = app.config.get('SITE_URL')
        expected_url = f"{site_url}/record/{test_recid}?observer_key={test_observer.observer_key}"

        assert anchor_url == expected_url
        assert anchor_text == expected_url

