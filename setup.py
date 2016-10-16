#!/usr/bin/env python
import codecs
import setuptools

from troika.http import __version__


def read_requirements_file(name):
    reqs = []
    try:
        with open(name, 'r') as req_file:
            for line in req_file:
                if line.startswith('-r'):
                    continue
                elif '#' in line:
                    line = line[0:line.index('#')]
                line = line.strip()
                if line:
                    reqs.append(line)
    except IOError:
        pass
    return reqs

with codecs.open('README.rst', 'rb', encoding='utf-8') as file_obj:
    long_description = '\n' + file_obj.read()

setuptools.setup(
    name='troika-http',
    version=__version__,
    description=('A Python 3 AsyncIO HTTP Application Framework inspired by '
                 'Tornado'),
    long_description=long_description,
    author='Gavin M. Roy',
    author_email='gavinmroy@gmail.com',
    url='http://github.com/gmr/troika',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Communications', 'Topic :: Internet',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Application Frameworks'
    ],
    include_package_data=True,
    install_requires=read_requirements_file('requires/installation.txt'),
    license='BSD',
    namespace_packages=['troika'],
    py_modules=['troika.http'],
    package_data={'': ['LICENSE', 'README.rst']},
    tests_require=read_requirements_file('requires/testing.txt'),
    test_suite='nose.collector',
    zip_safe=True)
