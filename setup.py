#!/usr/bin/env python

# ------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# -------------------------------------------------------------------------

import re
import os.path
from io import open
from setuptools import find_packages, setup
from pathlib import Path

PACKAGE_NAME = "azure-sdk-document-track-classifier"
PACKAGE_PPRINT_NAME = "AzureSDK Document Track Classifier"

package_folder_path = "azureSDKTrackCLassifier"
namespace_name = "azureSDKTrackCLassifier"

# Version extraction inspired from 'requests'
with open(os.path.join(package_folder_path, '_version.py'), 'r') as fd:
    version = re.search(r'^VERSION\s*=\s*[\'"]([^\'"]*)[\'"]',
                        fd.read(), re.MULTILINE).group(1)

if not version:
    raise RuntimeError('Cannot find version information')

with open('README.md', encoding='utf-8') as f:
    readme = f.read()
with open('CHANGELOG.md', encoding='utf-8') as f:
    changelog = f.read()

requires = [r for r in Path('requirements.txt').read_text().split('\n') if r.strip()] # Because I like being able to install from requirements.txt in dev and have that be source-of-truth.

setup(
    name=PACKAGE_NAME,
    version=version,
    description='Microsoft {} Client Library for Python'.format(PACKAGE_PPRINT_NAME),
    long_description=readme + '\n\n' + changelog,
    long_description_content_type='text/markdown',
    license='', #'MIT License', # TODO: Populate once decided.
    author='Microsoft Corporation',
    author_email='azpysdkhelp@microsoft.com',
    url='https://github.com/KieranBrantnerMagee/azure-sdk-track1-classifier',
    classifiers=[
        "Development Status :: 4 - Beta",
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        # 'License :: OSI Approved :: MIT License', #TODO: readd this once decided.
    ],
    zip_safe=False,
    packages=find_packages(exclude=[
        'tests',
        'TestCorpus',
        'Experiments'
    ]),
    install_requires=requires
)
