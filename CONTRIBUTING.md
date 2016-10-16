Contributing to troika-http
===========================
To contribute to troika-http, please make sure that any new features or changes
to existing functionality **include test coverage**.

*Pull requests that add or change code without coverage will most likely be rejected.*

Additionally, please format your code using [yapf](http://pypi.python.org/pypi/yapf) with
`pep8` style prior to issuing your pull request.

Set up a development environment
--------------------------------
The first thing that you need to do is set up a development environment
so that you can run the test suite.  The easiest way to do that is to
create a virtual environment for your endeavours:

```bash
$ python3 -m venv env
```

*requires/development.txt* is a pip-formatted requirements file that will
install everything that you need:

```bash
$ env/bin/pip install -qr requires/development.txt
$ env/bin/pip freeze
alabaster==0.7.9
astroid==1.4.8
Babel==2.3.4
coverage==4.2
Cython==0.24.1
docutils==0.12
flake8==3.0.4
httptools==0.0.9
ietfparse==1.4.0
imagesize==0.7.1
isort==4.2.5
Jinja2==2.8
lazy-object-proxy==1.2.2
MarkupSafe==0.23
mccabe==0.5.2
nose==1.3.7
pycodestyle==2.0.0
pyflakes==1.2.3
Pygments==2.1.3
pylint==1.6.4
pytz==2016.7
six==1.10.0
snowballstemmer==1.2.1
Sphinx==1.4.8
wrapt==1.10.8
```

The following commands are the ones that you will be using most
often:

- `nosetests`:
   Run the test suite using [nose](http://nose.readthedocs.org) and
   generate a coverage report.

- `docs/make html`:
   Generate the documentation suite into *build/sphinx/html*

- `yapf -i -r --style pep8 troika`:
   Run [yapf](http://pypi.python.org/pypi/yapf) over the code to ensure
   consistent code formatting.

- `flake8`:
   Run [flake8](http://flake8.readthedocs.org) over the code and report
   any style violations.

- `pylint troika`:
   Run [pylint](https://www.pylint.org) over the code and provide a code
   quality report.

- `./setup.py clean`:
   Remove generated files.  By default, this will remove any top-level
   egg-related files and the *build* directory.
