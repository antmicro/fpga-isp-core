#!/usr/bin/env python3

from setuptools import setup
from setuptools import find_packages

setup(
    name="fpga_isp",
    description="",
    author="Antmicro",
    author_email="contact@antmicro.com",
    url="https:antmicro.com",
    download_url="https://github.com/antmicro/fpga-isp",
    test_suite="test",
    license="Apache-2.0",
    python_requires="~=3.6",
    packages=find_packages(exclude=("test*", "sim*", "doc*", "examples*")),
    include_package_data=True,
)
