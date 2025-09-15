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


from unittest.mock import patch

from hepdata.modules.email.api import send_cookie_email
from hepdata.modules.permissions.models import SubmissionParticipant
from .conftest import create_record_with_participant


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

