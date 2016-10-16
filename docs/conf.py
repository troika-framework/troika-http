#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
sys.path.insert(0, os.path.abspath('..'))

from troika.http import __version__

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
]

templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'

# General information about the project.
project = 'Troika HTTP'
copyright = '2016, Gavin M. Roy'
author = 'Gavin M. Roy'

version = '.'.join(__version__.split('.')[0:1])
release = __version__
language = None
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
pygments_style = 'sphinx'
todo_include_todos = False
htmlhelp_basename = 'TroikaHTTPdoc'

intersphinx_mapping = {'https://docs.python.org/': None}
