import os
import re

from setuptools import find_packages, setup

regexp = re.compile(r".*__version__ = [\'\"](.*?)[\'\"]", re.S)


init_file = os.path.join(
    os.path.dirname(__file__), "src", "aisexporter", "__init__.py"
)
with open(init_file, "r") as f:  # pylint: disable=unspecified-encoding
    module_content = f.read()
    match = regexp.match(module_content)
    if match:
        version = match.group(1)
    else:
        raise RuntimeError(f"Cannot find __version__ in {init_file}")

with open("README.md", "r") as f:  # pylint: disable=unspecified-encoding
    readme = f.read()


def parse_requirements(filename):
    """Load requirements from a pip requirements file"""
    with open(filename, "r") as fd:  # pylint: disable=unspecified-encoding
        lines = []
        for line in fd:
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    return lines


if __name__ == "__main__":

    setup(
        name="aisexporter",
        version=version,
        author="Chris Laws",
        author_email="clawsicus@gmail.com",
        description="A Prometheus metrics exporter for the ais Mode S decoder for RTLSDR",
        long_description_content_type="text/markdown",
        long_description=readme,
        license="MIT",
        keywords=["prometheus", "monitoring", "metrics", "ais", "ADSB"],
        url="https://github.com/claws/aisexporter",
        package_dir={"": "src"},
        packages=find_packages("src"),
        install_requires=parse_requirements("requirements.txt"),
        extras_require={
            "develop": parse_requirements("requirements.dev.txt"),
            "uvloop": ["uvloop==0.16.0"],
        },
        classifiers=[
            "Development Status :: 5 - Production/Stable",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Natural Language :: English",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Topic :: System :: Monitoring",
        ],
        entry_points={
            "console_scripts": ["aisexporter = aisexporter.__main__:main"]
        },
    )
