import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

entry_points = {
    'console_scripts': [
        'haumea = haumea.__main__:main',
        'haumea-quickstart = haumea.quickstart:main',
    ]
}

setuptools.setup(
    name="haumea",
    version="0.71.5",
    author="Guillaume Betrand",
    author_email="gbe.io@pm.me",
    description="Small & fast python library to build static websites",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/guillbertrand/haumea",
    keywords='SSG graphql json python static website generator ',
    packages=setuptools.find_packages(),
    entry_points=entry_points,
    install_requires=[
          'requests',
          'watchdog',
          'python-dateutil'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Environment :: Console",
    ],
    python_requires='>=3.6',
)
