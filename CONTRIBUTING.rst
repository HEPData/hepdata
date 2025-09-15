Contributing
============

Contributions are welcome, and they are greatly appreciated!
Every little bit helps, and credit will always be given.

Types of Contributions
----------------------

Report Bugs
~~~~~~~~~~~

Report bugs by opening a GitHub issue or by sending an email to ``info@hepdata.net``.

Fix Bugs
~~~~~~~~

Look through the GitHub issues for bugs. Anything tagged with "type: bug"
is open to whoever wants to implement it.

Implement Features
~~~~~~~~~~~~~~~~~~

Look through the GitHub issues for features. Anything tagged with "type: enhancement"
is open to whoever wants to implement it.

Write Documentation
~~~~~~~~~~~~~~~~~~~

HEPData could always use more documentation, whether as part of the
official HEPData docs, in docstrings, or even on the web in blog posts,
articles, and such.

Submit Feedback
~~~~~~~~~~~~~~~

The best way to send feedback is to send an email to ``info@hepdata.net``.
Alternatively, open an issue at https://github.com/HEPData/hepdata/issues
or post in the `HEPData Forum <https://hepdata-forum.cern.ch>`_.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that contributions are welcome :)

Get Started!
------------

Ready to contribute? Here's how to set up ``hepdata`` for local development.

1. Fork the ``hepdata`` repo on GitHub.
2. Clone your fork locally:

   .. code-block:: console

      $ git clone https://github.com/your_name_here/hepdata.git

3. Install your local copy into a virtualenv as described in :ref:`installation`.

4. Create a branch for local development:

   .. code-block:: console

      $ git checkout -b name-of-your-bugfix-or-feature

   Now you can make your changes locally.

5. When you're done making changes, check that your changes pass tests as described in :ref:`running-the-tests`:

   .. code-block:: console

      $ ./run-tests.sh

6. Commit your changes and push your branch to GitHub:

   .. code-block:: console

      $ git add .
      $ git commit -s -m "Your detailed description of your changes."
      $ git push origin name-of-your-bugfix-or-feature

7. The continuous integration (CI) run via GitHub Actions requires access to secrets only available to the
https://github.com/HEPData/hepdata repository, not to forks. Therefore, pull requests should be made only
from branches of this repository, not from forks. You can request Write access to the repository by
sending an email to ``info@hepdata.net``.

8. Submit a pull request through the GitHub website, perhaps initially as a
`draft pull request <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests#draft-pull-requests>`_
until you make sure that all checks have passed.

Pull Request Guidelines
-----------------------

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests and must not decrease test coverage.
2. If the pull request adds functionality, the docs should be updated. Put
   your new functionality into a function with a docstring.
3. The pull request should work for Python 3.9. Check
   https://github.com/HEPData/hepdata/actions?query=event%3Apull_request
   and make sure that the tests pass.  Sometimes there are temporary failures,
   for example, due to unavailability of an external service or the test infrastructure.
   If you have sufficient permissions for the repository, you can restart failed jobs by
   clicking on "Re-run jobs" then "Re-run failed jobs".
