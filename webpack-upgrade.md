Installed webpack (via brew)
Ensure node version >=12.13 (check!)

Tips
----
* Use `pip install -e.[all] hepdata` if setup.py changes
* `hepdata webpack buildall` if webpack.py has changed
* If getting keyerror not in manifest.json, check that the webpack build did not give eslint errors higher up.
* {{ webpack[...] }} in templates is provided by Flask-WebpackExt
