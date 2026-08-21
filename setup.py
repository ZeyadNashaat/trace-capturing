from setuptools import setup, find_packages
from pathlib import Path

def read_requirements(file):
    return [
        line.strip()
        for line in Path(file).read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="capture_pkg",
    version="0.1.0",
    packages=find_packages(),
    install_requires=read_requirements("requirements.txt"),
)

